"""股票别名 + 金融词典匹配器（Aho-Corasick 单例）。

加载 PostgreSQL 的 stock_aliases / finance_lexicon 一次性构建自动机，
后续 enrich 每篇文章只走纯 C 扫描，性能远高于多次 LIKE。

重载策略：
- 进程启动时构建一次
- 上层每 10 分钟可以调 force_reload() 拉取新增词条
"""
from __future__ import annotations

import logging
import math
import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Iterable

import ahocorasick
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("news.matcher")

MODEL_VERSION = "ac-v4+lex-v3+ent+cn"

# 别名长度 ≤ 此值时要求左右两侧不能再粘中文/字母，
# 防止 "中"、"国"、"茅台" 之类的二字别名乱命中；
# 3 字及以上的中文公司名（如 "比亚迪"、"宁德时代"）天然区分度足够，不做严格边界。
_STRICT_BOUNDARY_MAX_LEN = 2
_CJK_OR_ALNUM = re.compile(r"[一-鿿A-Za-z0-9]")

# 日期实体抽取正则 (按优先级排, ISO 优先于中文日期)
_RE_DATE_ISO = re.compile(r"(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])")
_RE_DATE_CN = re.compile(r"(20\d{2})\s*年\s*(0?[1-9]|1[0-2])\s*月(?:\s*(0?[1-9]|[12]\d|3[01])\s*日)?")
_RE_DATE_SHORT = re.compile(r"(?<![\d/])(0?[1-9]|1[0-2])\s*月\s*(0?[1-9]|[12]\d|3[01])\s*日")
_RE_QUARTER = re.compile(r"(20\d{2})\s*年?\s*(?:第)?\s*([一二三四1-4])\s*季度")
_RE_HALF_YEAR = re.compile(r"(20\d{2})\s*年?\s*(上半年|下半年|H1|H2)")
_RE_YEAR_ONLY = re.compile(r"(?<![\d.])(20\d{2})\s*年(?![\d月])")


def _db_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "quantmind-db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "quantmind"),
        password=os.getenv("POSTGRES_PASSWORD", "quantmind2026"),
        dbname=os.getenv("POSTGRES_DB", "quantmind"),
    )


@dataclass
class _AliasEntry:
    ticker: str
    alias: str
    alias_type: str
    priority: int
    industry: str | None
    sector: str | None


@dataclass
class _LexEntry:
    term: str
    kind: str  # sentiment_pos / sentiment_neg / event
    event_tag: str | None
    weight: float


@dataclass
class MatchHit:
    """单次匹配结果。pos 是命中起点（字符索引）。"""
    pos: int
    end: int  # 包含尾字符的下一个位置
    alias_entries: list[_AliasEntry] = field(default_factory=list)
    lex_entries: list[_LexEntry] = field(default_factory=list)


class NewsMatcher:
    _lock = threading.RLock()

    def __init__(self):
        self.alias_automaton = ahocorasick.Automaton()
        self.lex_automaton = ahocorasick.Automaton()
        self._alias_index: dict[str, list[_AliasEntry]] = {}
        self._lex_index: dict[str, list[_LexEntry]] = {}
        self.loaded_at: float = 0.0
        self.alias_count = 0
        self.lex_count = 0

    # ---------- build ----------

    def reload(self):
        """从 DB 拉取并重建自动机。线程安全。"""
        t0 = time.time()
        new_alias_idx: dict[str, list[_AliasEntry]] = {}
        new_lex_idx: dict[str, list[_LexEntry]] = {}
        with _db_conn() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT ticker, alias, alias_type, priority, industry, sector
                FROM stock_aliases
            """)
            for r in cur.fetchall():
                alias = r["alias"]
                if not alias or len(alias) < 2:
                    continue
                entry = _AliasEntry(
                    ticker=r["ticker"],
                    alias=alias,
                    alias_type=r["alias_type"],
                    priority=int(r["priority"] or 50),
                    industry=r.get("industry"),
                    sector=r.get("sector"),
                )
                new_alias_idx.setdefault(alias, []).append(entry)

            cur.execute("""
                SELECT term, kind, event_tag, weight
                FROM finance_lexicon
                WHERE enabled = TRUE
            """)
            for r in cur.fetchall():
                term = r["term"]
                if not term or len(term) < 2:
                    continue
                new_lex_idx.setdefault(term, []).append(_LexEntry(
                    term=term,
                    kind=r["kind"],
                    event_tag=r.get("event_tag"),
                    weight=float(r["weight"] or 1.0),
                ))

        alias_aut = ahocorasick.Automaton()
        for term in new_alias_idx:
            alias_aut.add_word(term, term)
        alias_aut.make_automaton()

        lex_aut = ahocorasick.Automaton()
        for term in new_lex_idx:
            lex_aut.add_word(term, term)
        lex_aut.make_automaton()

        with self._lock:
            self._alias_index = new_alias_idx
            self._lex_index = new_lex_idx
            self.alias_automaton = alias_aut
            self.lex_automaton = lex_aut
            self.alias_count = len(new_alias_idx)
            self.lex_count = len(new_lex_idx)
            self.loaded_at = time.time()

        logger.info(
            "NewsMatcher 已加载: alias=%d, lex=%d (%.2fs)",
            self.alias_count, self.lex_count, time.time() - t0,
        )

    # ---------- match ----------

    @staticmethod
    def _boundary_ok(text: str, start: int, end: int, term: str) -> bool:
        """边界校验：
        - 纯数字/英文（股票代码、ticker）：左右不能再粘字母数字
        - 长度 ≤ 2 的中文/混合别名：左右不能再粘 CJK/字母数字
        - 其他（3+ 字中文公司名）：免检
        """
        is_ascii = term.isascii()
        if not is_ascii and len(term) > _STRICT_BOUNDARY_MAX_LEN:
            return True
        left = text[start - 1] if start > 0 else ""
        right = text[end] if end < len(text) else ""
        if is_ascii:
            ascii_re = re.compile(r"[A-Za-z0-9]")
            if (left and ascii_re.match(left)) or (right and ascii_re.match(right)):
                return False
            return True
        if left and _CJK_OR_ALNUM.match(left):
            return False
        if right and _CJK_OR_ALNUM.match(right):
            return False
        return True

    def match(self, text: str) -> tuple[
        dict[str, int],          # ticker -> hit count
        dict[str, int],          # industry -> hit count
        dict[str, int],          # event_tag -> hit count
        float,                   # sentiment_score in [-1, 1]
        dict,                    # raw stats (extras: countries, regions, key_terms)
    ]:
        if not text:
            return {}, {}, {}, 0.0, {
                "length": 0,
                "countries": {}, "regions": {}, "key_terms": {},
                "provinces": {}, "cities": {}, "politicians": {}, "visits": {},
                "departments": {},
            }

        text_len = len(text)
        # cap 防止超长文章拖垮 (FinBERT 最多 512 token，这里到 8000 字符足够)
        if text_len > 8000:
            text = text[:8000]

        ticker_hits: dict[str, int] = {}
        industry_hits: dict[str, int] = {}
        event_hits: dict[str, int] = {}
        # 细粒度词级命中（用于前端高亮 / 过滤）
        countries: dict[str, int] = {}
        regions: dict[str, int] = {}
        key_terms: dict[str, int] = {}  # 产业/政策/地缘/外汇/加密/财报 等的具体词
        provinces: dict[str, int] = {}
        cities: dict[str, int] = {}
        politicians: dict[str, int] = {}
        visits: dict[str, int] = {}
        departments: dict[str, int] = {}  # 国家部门/监管机构
        pos_weight = 0.0
        neg_weight = 0.0
        n_sent = 0

        with self._lock:
            alias_aut = self.alias_automaton
            lex_aut = self.lex_automaton
            alias_idx = self._alias_index
            lex_idx = self._lex_index

        # 股票别名匹配 (同时记录每次命中的位置, 用于"调研词同句"加权)
        ticker_positions: list[tuple[str, int]] = []  # (ticker, start_pos)
        for end_idx, term in alias_aut.iter(text):
            start = end_idx - len(term) + 1
            end = end_idx + 1
            if not self._boundary_ok(text, start, end, term):
                continue
            for entry in alias_idx.get(term, []):
                ticker_hits[entry.ticker] = ticker_hits.get(entry.ticker, 0) + 1
                if entry.industry:
                    industry_hits[entry.industry] = industry_hits.get(entry.industry, 0) + 1
                ticker_positions.append((entry.ticker, start))

        # 词典匹配（情感 + 事件 + 行业板块名 + 国家/地区/产业/省份/城市/领导人/调研）
        _KEY_TERM_TAGS = ("产业", "政策", "地缘", "外汇", "加密", "财报", "市场", "宏观", "期货", "监管")
        visit_positions: list[int] = []  # 调研词位置, 后面用于同句加权 ticker
        for end_idx, term in lex_aut.iter(text):
            start = end_idx - len(term) + 1
            end = end_idx + 1
            if not self._boundary_ok(text, start, end, term):
                continue
            for entry in lex_idx.get(term, []):
                if entry.kind == "sentiment_pos":
                    pos_weight += entry.weight
                    n_sent += 1
                elif entry.kind == "sentiment_neg":
                    neg_weight += entry.weight
                    n_sent += 1
                elif entry.kind == "event":
                    tag = entry.event_tag or term
                    event_hits[tag] = event_hits.get(tag, 0) + 1
                    if entry.event_tag in ("行业板块", "概念板块", "股票行业"):
                        industry_hits[term] = industry_hits.get(term, 0) + 1
                    elif entry.event_tag == "国家":
                        countries[term] = countries.get(term, 0) + 1
                    elif entry.event_tag == "地区":
                        regions[term] = regions.get(term, 0) + 1
                    elif entry.event_tag == "省份":
                        provinces[term] = provinces.get(term, 0) + 1
                    elif entry.event_tag == "城市":
                        cities[term] = cities.get(term, 0) + 1
                    elif entry.event_tag == "领导人":
                        politicians[term] = politicians.get(term, 0) + 1
                    elif entry.event_tag == "调研":
                        visits[term] = visits.get(term, 0) + 1
                        visit_positions.append(start)
                    elif entry.event_tag == "部门":
                        departments[term] = departments.get(term, 0) + 1
                    elif entry.event_tag in _KEY_TERM_TAGS:
                        key_terms[term] = key_terms.get(term, 0) + 1
                elif entry.kind == "department":
                    departments[term] = departments.get(term, 0) + 1

        # 调研词 × 上市公司同句加权: 若调研动词与 ticker 在 80 字符窗口内同句出现,
        # 该 ticker 命中数额外 +1 (即原 1 -> 2, 等效 1.5x~2x 提权), 且作为 industry_hits 也再 +1
        if visit_positions and ticker_positions:
            window = self._SENT_WINDOW
            for tkr, tpos in ticker_positions:
                for vpos in visit_positions:
                    if abs(tpos - vpos) <= window:
                        ticker_hits[tkr] = ticker_hits.get(tkr, 0) + 1
                        break  # 一次加权足够

        # 字典法情感分：tanh((pos - neg) / 3) 压缩到 [-1, 1]
        import math
        raw = pos_weight - neg_weight
        sentiment_score = math.tanh(raw / 3.0) if raw != 0 else 0.0

        stats = {
            "length": text_len,
            "pos_weight": round(pos_weight, 3),
            "neg_weight": round(neg_weight, 3),
            "n_sent": n_sent,
            "countries": countries,
            "regions": regions,
            "key_terms": key_terms,
            "provinces": provinces,
            "cities": cities,
            "politicians": politicians,
            "visits": visits,
            "departments": departments,
        }
        return ticker_hits, industry_hits, event_hits, sentiment_score, stats

    # ---------- 实体级情感 ----------

    _SENT_WINDOW = 80   # 实体前后 80 字符内的 sentiment 词视为修饰该实体
    _SENT_SPLIT_RE = re.compile(r"[。！？\n!?]+")

    def match_entity_sentiments(self, text: str) -> dict[str, float]:
        """返回 {entity_key: score_in_[-1,1]}.

        entity_key 形如:
          - "ticker:600519.SH"
          - "country:美国"
          - "region:欧盟"
          - "key_term:AI"
        逻辑:
          - 把 text 切成"句子"(以中英标点+换行分)
          - 每个句子里出现的 实体 (alias/country/region/key_term)
            被该句子里出现的 sentiment_pos/neg 词共同修饰
          - 实体得分 = tanh((Σ pos_w - Σ neg_w) / 3) 累计跨句子的加权平均
        长文章只处理前 8000 字符 (和 match 一致)。
        """
        if not text:
            return {}
        if len(text) > 8000:
            text = text[:8000]

        with self._lock:
            alias_aut = self.alias_automaton
            lex_aut = self.lex_automaton
            alias_idx = self._alias_index
            lex_idx = self._lex_index

        # 先把全文实体/情感词的 (start, end, kind, payload) 收集起来
        # entity = ("ticker:xxx" | "country:xxx" | "region:xxx" | "key_term:xxx", pos, end)
        entities: list[tuple[str, int, int]] = []
        sentiments: list[tuple[int, int, float, str]] = []  # pos, end, weight (+/-), tag(pos|neg)

        for end_idx, term in alias_aut.iter(text):
            start = end_idx - len(term) + 1
            end = end_idx + 1
            if not self._boundary_ok(text, start, end, term):
                continue
            for entry in alias_idx.get(term, []):
                entities.append((f"ticker:{entry.ticker}", start, end))

        for end_idx, term in lex_aut.iter(text):
            start = end_idx - len(term) + 1
            end = end_idx + 1
            if not self._boundary_ok(text, start, end, term):
                continue
            for entry in lex_idx.get(term, []):
                if entry.kind == "sentiment_pos":
                    sentiments.append((start, end, float(entry.weight), "pos"))
                elif entry.kind == "sentiment_neg":
                    sentiments.append((start, end, float(entry.weight), "neg"))
                elif entry.kind == "event":
                    if entry.event_tag == "国家":
                        entities.append((f"country:{term}", start, end))
                    elif entry.event_tag == "地区":
                        entities.append((f"region:{term}", start, end))
                    elif entry.event_tag == "省份":
                        entities.append((f"province:{term}", start, end))
                    elif entry.event_tag == "城市":
                        entities.append((f"city:{term}", start, end))
                    elif entry.event_tag == "领导人":
                        entities.append((f"politician:{term}", start, end))
                    elif entry.event_tag == "部门":
                        entities.append((f"department:{term}", start, end))
                    elif entry.event_tag in ("产业", "政策", "地缘", "外汇", "加密",
                                              "财报", "市场", "宏观", "期货", "监管"):
                        entities.append((f"key_term:{term}", start, end))
                elif entry.kind == "department":
                    entities.append((f"department:{term}", start, end))

        if not entities or not sentiments:
            return {}

        # 句子边界 (字符 offset 列表): [0, e1, e2, ..., len]
        sent_bounds = [0]
        for m in self._SENT_SPLIT_RE.finditer(text):
            sent_bounds.append(m.end())
        if sent_bounds[-1] != len(text):
            sent_bounds.append(len(text))

        def _sent_idx_of(pos: int) -> int:
            # 二分: 返回 pos 所在句子的 index
            lo, hi = 0, len(sent_bounds) - 1
            while lo < hi - 1:
                mid = (lo + hi) // 2
                if sent_bounds[mid] <= pos:
                    lo = mid
                else:
                    hi = mid
            return lo

        # 把 sentiments 按句子聚合: sent_id -> (pos_sum, neg_sum)
        sent_pos_neg: dict[int, list[float]] = {}
        for spos, send, w, tag in sentiments:
            sid = _sent_idx_of(spos)
            cell = sent_pos_neg.setdefault(sid, [0.0, 0.0])
            if tag == "pos":
                cell[0] += w
            else:
                cell[1] += w

        # 每个 entity 按其句子取分, 也算上 ±1 邻句的衰减 (0.5)
        ent_scores: dict[str, list[float]] = {}
        ent_weights: dict[str, list[float]] = {}
        for key, epos, eend in entities:
            sid = _sent_idx_of(epos)
            for offset, decay in ((0, 1.0), (-1, 0.4), (1, 0.4)):
                cell = sent_pos_neg.get(sid + offset)
                if not cell:
                    continue
                raw = cell[0] - cell[1]
                if raw == 0:
                    continue
                score = math.tanh(raw / 3.0)
                ent_scores.setdefault(key, []).append(score * decay)
                ent_weights.setdefault(key, []).append(decay)

        result: dict[str, float] = {}
        for key, scores in ent_scores.items():
            weights = ent_weights[key]
            wsum = sum(weights) or 1.0
            avg = sum(s for s in scores) / wsum
            # 限定在 [-1, 1]
            avg = max(-1.0, min(1.0, avg))
            if abs(avg) >= 0.05:  # 极弱信号丢弃
                result[key] = round(avg, 3)
        return result

    # ---------- 日期实体抽取 ----------

    @staticmethod
    def extract_dates(text: str, limit: int = 8) -> list[str]:
        """从文章里抽取最多 N 个日期实体, 归一化成 'YYYY-MM-DD' / 'YYYY-MM' / 'YYYY-Qx' / 'YYYY-H1' / 'YYYY' 字符串。

        识别格式:
          - 2026-05-25 / 2026/5/25      → 2026-05-25
          - 2026年5月25日 / 2026年5月    → 2026-05-25 / 2026-05
          - 5月25日 (上下文无年份, 默认当年) → 2026-05-25
          - 2026年第三季度 / 2026年三季度 → 2026-Q3
          - 2026年上半年                  → 2026-H1
          - 仅 2026年                     → 2026
        """
        if not text:
            return []
        from datetime import datetime
        current_year = datetime.utcnow().year

        seen: list[str] = []
        seen_set: set[str] = set()

        def _push(s: str):
            if s and s not in seen_set:
                seen.append(s)
                seen_set.add(s)

        # ISO
        for m in _RE_DATE_ISO.finditer(text):
            y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
            _push(f"{y}-{mo:02d}-{d:02d}")
            if len(seen) >= limit:
                return seen

        # 中文 YYYY年M月[D日]
        for m in _RE_DATE_CN.finditer(text):
            y, mo, d = m.group(1), int(m.group(2)), m.group(3)
            if d:
                _push(f"{y}-{mo:02d}-{int(d):02d}")
            else:
                _push(f"{y}-{mo:02d}")
            if len(seen) >= limit:
                return seen

        # 短日期 M月D日 (默认当年, 但要求附近没有 ISO 年份避免冲突)
        for m in _RE_DATE_SHORT.finditer(text):
            mo, d = int(m.group(1)), int(m.group(2))
            _push(f"{current_year}-{mo:02d}-{int(d):02d}")
            if len(seen) >= limit:
                return seen

        # 季度
        cn_q = {"一": 1, "二": 2, "三": 3, "四": 4}
        for m in _RE_QUARTER.finditer(text):
            y = m.group(1)
            q_raw = m.group(2)
            q = cn_q.get(q_raw, int(q_raw) if q_raw.isdigit() else 0)
            if q:
                _push(f"{y}-Q{q}")
            if len(seen) >= limit:
                return seen

        # 半年
        for m in _RE_HALF_YEAR.finditer(text):
            y = m.group(1)
            tag = m.group(2)
            h = "H1" if tag in ("上半年", "H1") else "H2"
            _push(f"{y}-{h}")
            if len(seen) >= limit:
                return seen

        # 仅年份
        for m in _RE_YEAR_ONLY.finditer(text):
            _push(m.group(1))
            if len(seen) >= limit:
                return seen

        return seen


# ---------- 单例 ----------

_singleton: NewsMatcher | None = None
_singleton_lock = threading.Lock()


def get_matcher(force_reload: bool = False) -> NewsMatcher:
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = NewsMatcher()
            _singleton.reload()
        elif force_reload:
            _singleton.reload()
        return _singleton
