"""
RiceQuant策略示例 - 用于测试策略转换功能
这个文件应该被检测为RiceQuant平台，并触发转换提示
"""


def init(context):
    """初始化函数"""
    context.stocks = ["000001.XSHE", "000002.XSHE", "600000.XSHG"]
    context.stock_num = 10

    # 设置手续费
<<<<<<< HEAD
    context.set_commission(PerOrder(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
=======
    context.set_commission(
        PerOrder(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
>>>>>>> refactor/service-cleanup

    # 每天运行
    scheduler.run_daily(rebalance, time_rule=market_open(hour=9, minute=30))


def rebalance(context, bar_dict):
    """调仓函数"""
    # 获取当前持仓
    positions = context.portfolio.positions

    # 获取股票池
    stock_list = context.stocks

    # 计算买入信号
    buy_list = []

    for stock in stock_list:
        # 获取历史数据
        hist = history_bars(stock, 5, "1d", "close")

        if len(hist) >= 5:
            # 计算收益率
            returns = hist[-1] / hist[0] - 1

            # 买入条件：5日收益率大于5%
            if returns > 0.05:
                buy_list.append(stock)

                # 执行交易
    if len(buy_list) > 0:
        weight = 1.0 / len(buy_list)

        # 先卖出不在买入列表的股票
        for stock in positions:
            if stock not in buy_list:
                order_target_percent(stock, 0)

                # 买入目标股票
        for stock in buy_list:
            order_target_percent(stock, weight)


def handle_bar(context, bar_dict):
    """每个bar执行"""
