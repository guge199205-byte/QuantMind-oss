"""
JoinQuant策略示例 - 用于测试策略转换功能
这个文件应该被检测为JoinQuant平台，并触发转换提示
"""


def initialize(context):
    """初始化函数"""
    # 设置股票池
    set_universe(["000001.XSHE", "000002.XSHE", "600000.XSHG"])

    # 设置全局变量
    g.stock_num = 10
    g.buy_threshold = 0.05

    # 设置手续费
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5,
        )
    )


def handle_data(context, data):
    """每日交易逻辑"""
    # 获取当前持仓
    positions = context.portfolio.positions

    # 获取当前股票池
    stock_list = context.universe

    # 计算每只股票的收益率
    for stock in stock_list:
        # 获取历史价格
        hist = attribute_history(stock, 5, "1d", ["close"])

        # 计算5日收益率
        if len(hist) >= 5:
            returns = hist["close"][-1] / hist["close"][0] - 1

            # 买入信号：收益率大于阈值
            if returns > g.buy_threshold and stock not in positions:
                # 等权重买入
                order_target_percent(stock, 1.0 / g.stock_num)
                log.info(f"买入 {stock}, 收益率: {returns:.2%}")

            # 卖出信号：收益率小于0
            elif returns < 0 and stock in positions:
                order_target_percent(stock, 0)
                log.info(f"卖出 {stock}, 收益率: {returns:.2%}")


def before_trading_start(context):
    """每日开盘前执行"""
    log.info(f"当前日期: {context.current_dt}")
    log.info(f"持仓数量: {len(context.portfolio.positions)}")
