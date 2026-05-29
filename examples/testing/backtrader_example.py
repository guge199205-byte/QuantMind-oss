"""
Backtrader策略示例 - 用于测试策略转换功能
这个文件应该被检测为Backtrader平台，并触发转换提示
"""

import backtrader as bt


class MyStrategy(bt.Strategy):
    """简单的均线策略"""

    params = (
        ("fast_period", 10),
        ("slow_period", 30),
    )

    def __init__(self):
        """初始化指标"""
        # 计算快速均线
        self.fast_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.fast_period
        )

        # 计算慢速均线
        self.slow_ma = bt.indicators.SimpleMovingAverage(
            self.data.close, period=self.params.slow_period
        )

        # 交叉信号
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)

    def next(self):
        """每个bar执行"""
        # 如果没有持仓
        if not self.position:
            # 金叉买入
            if self.crossover > 0:
                self.buy(size=100)
                print(f"{self.data.datetime.date()}: 买入信号")

        # 如果有持仓
        else:
            # 死叉卖出
            if self.crossover < 0:
                self.sell(size=100)
                print(f"{self.data.datetime.date()}: 卖出信号")

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Completed]:
            if order.isbuy():
                print(f"买入成交: 价格={order.executed.price:.2f}")
            elif order.issell():
                print(f"卖出成交: 价格={order.executed.price:.2f}")

    def notify_trade(self, trade):
        """交易状态通知"""
        if trade.isclosed:
            print(f"交易盈亏: {trade.pnl:.2f}")


if __name__ == "__main__":
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()

    # 添加策略
    cerebro.addstrategy(MyStrategy)

    # 添加数据源
    # data = bt.feeds.YahooFinanceData(dataname='AAPL', ...)
    # cerebro.adddata(data)

    # 运行回测
    # cerebro.run()
