"""News enrichment subpackage.

提供把 Huntly 抓回的资讯文章自动打上股票/行业/事件/情感标签的能力。

公开接口：
- enrich_article(huntly_page_id, title, content) -> EnrichmentResult
- get_matcher() -> NewsMatcher  (单例 Aho-Corasick + finance_lexicon)
- run_enrichment_batch(limit=200) -> int  扫描 Huntly 新增文章并写 enrichment 表
"""
from .matcher import NewsMatcher, get_matcher, MODEL_VERSION
from .enricher import (
    enrich_article,
    run_enrichment_batch,
    EnrichmentResult,
    start_full_rebuild_async,
    get_rebuild_progress,
)

__all__ = [
    "NewsMatcher",
    "get_matcher",
    "MODEL_VERSION",
    "enrich_article",
    "run_enrichment_batch",
    "EnrichmentResult",
    "start_full_rebuild_async",
    "get_rebuild_progress",
]
