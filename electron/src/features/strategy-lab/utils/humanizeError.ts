/**
 * Translate raw runner errors into a friendly Chinese title + hint.
 *
 * Used by StrategyLabResultPanel when a run fails — the raw exception
 * message is preserved (copyable) but a clearer headline is shown above it.
 */

export interface HumanError {
  title: string;
  hint?: string;
}

const RULES: Array<{
  match: RegExp;
  title: string;
  hint?: string;
}> = [
  {
    match: /ASTCheckError|disallowed|forbidden node|sandbox/i,
    title: '脚本含禁止用法（沙盒拦截）',
    hint: '只允许使用 SDK 暴露的 API：ctx / position / bar 等。禁止 import os/sys、open、eval、exec 等系统调用。',
  },
  {
    match: /SyntaxError|invalid syntax|EOL while scanning/i,
    title: '代码语法错误',
    hint: '请检查括号、冒号、缩进。Monaco 左侧红波浪线即定位，鼠标悬停可看具体错误。',
  },
  {
    match: /IndentationError/i,
    title: '缩进错误',
    hint: 'Python 严格依赖缩进。请保持 4 空格缩进，不要混用 Tab 与空格。',
  },
  {
    match: /NameError.*not defined/i,
    title: '变量未定义',
    hint: '在 setup() 里声明的变量需要写到 self 上才能在 on_bar 里用，例如 `self.window = 20`。',
  },
  {
    match: /AttributeError.*has no attribute/i,
    title: '调用了不存在的属性',
    hint: '请对照 SDK 文档（ctx / position / bar）；常见错写：bar.Close → bar.close、ctx.SMA → ctx.indicator("sma", ...)。',
  },
  {
    match: /TypeError.*missing.*required/i,
    title: '函数参数缺失',
    hint: '请检查函数签名。例如 ctx.order(symbol, qty, reason) 必须三个参数齐全。',
  },
  {
    match: /KeyError/i,
    title: '取了字典中不存在的键',
    hint: '常见于读 bar 数据：检查 symbol 是否在 universe，日期是否在回测窗口内。',
  },
  {
    match: /ZeroDivisionError|division by zero/i,
    title: '除零错误',
    hint: '请加非零判断：例如 if peak > 0 时再算回撤。',
  },
  {
    match: /ValueError.*could not convert|invalid literal/i,
    title: '数据转换失败',
    hint: '通常是把字符串当数字用。检查 ctx.params 里的参数类型，或是从 csv 读入的字段。',
  },
  {
    match: /TimeoutError|exceeded time|killed.*timeout/i,
    title: '运行超时',
    hint: '回测时长超过 60s。请缩小 universe / 调短回测区间，或检查是否在 on_bar 里写了死循环。',
  },
  {
    match: /MemoryError|out of memory|killed.*memory/i,
    title: '内存超限',
    hint: '请减少在内存中累积的状态（例如不要把每一根 bar 都 append 到 list）。',
  },
  {
    match: /FileNotFoundError|No such file|qlib data path/i,
    title: '行情数据缺失',
    hint: '请确认管理后台 → 数据平台 → 已同步本回测窗口的市场数据。',
  },
  {
    match: /ConnectionError|Redis|redis/i,
    title: '后端连接错误（Redis 不可达）',
    hint: '请联系管理员；通常是 quantmind-redis 容器需要重启。',
  },
];

export function humanizeError(message: string, traceback = ''): HumanError {
  const blob = `${message}\n${traceback}`;
  for (const r of RULES) {
    if (r.match.test(blob)) return { title: r.title, hint: r.hint };
  }
  if (!message) return { title: '运行失败（未知错误）' };
  return { title: '运行失败', hint: '请展开下方错误栈定位问题，或复制后联系管理员。' };
}
