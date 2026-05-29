/**
 * 交易所API使用示例
 */

import { ExchangeFactory } from './ExchangeFactory';
import { BinanceAPI } from './binance/BinanceAPI';

async function main() {
  console.log('=== Binance API示例 ===\n');

  // 1. 创建API实例
  const api = ExchangeFactory.create('binance', {
    apiKey: process.env.BINANCE_API_KEY || '',
    apiSecret: process.env.BINANCE_API_SECRET || '',
    sandbox: true // 使用测试网（sandbox 字段兼容 ExchangeConfig）
  }) as BinanceAPI;

  try {
    // 2. 获取K线数据
    console.log('📊 获取BTCUSDT 1小时K线...');
    const klines = await api.getKlines('BTCUSDT', '1h', 5);

    if (klines.success && klines.data) {
      console.log(`✅ 获取${klines.data.length}条K线数据`);
      console.log('最新K线:', klines.data[klines.data.length - 1]);
    }

    // 3. 获取24h行情
    console.log('\n📈 获取BTCUSDT 24h行情...');
    const ticker = await api.getTicker24h('BTCUSDT');

    if (ticker.success && ticker.data) {
      const raw = ticker.data as unknown;
      const t = Array.isArray(raw) ? (raw[0] as Record<string, unknown>) : (raw as Record<string, unknown>);
      console.log('✅ 24h行情:');
      console.log(`   价格: $${t.lastPrice}`);
      console.log(`   涨跌: ${t.priceChangePercent}%`);
      console.log(`   成交量: ${t.volume}`);
    }

    // 4. 获取订单簿
    console.log('\n📖 获取BTCUSDT订单簿...');
    const orderBook = await api.getOrderBook('BTCUSDT', 5);

    if (orderBook.success && orderBook.data) {
      console.log('✅ 订单簿:');
      console.log('   买盘 (前5档):');
      orderBook.data.bids.slice(0, 5).forEach(([price, qty]) => {
        console.log(`     ${price} - ${qty}`);
      });
      console.log('   卖盘 (前5档):');
      orderBook.data.asks.slice(0, 5).forEach(([price, qty]) => {
        console.log(`     ${price} - ${qty}`);
      });
    }

    // 5. 获取最近成交
    console.log('\n💱 获取最近成交...');
    const trades = await api.getTrades('BTCUSDT', 5);

    if (trades.success && trades.data) {
      console.log(`✅ 获取${trades.data.length}条成交记录`);
      trades.data.forEach(trade => {
        console.log(`   ${trade.side} ${trade.quantity} @ ${trade.price}`);
      });
    }

    // 6. 账户信息（需要有效的API密钥）
    if (process.env.BINANCE_API_KEY) {
      console.log('\n💰 获取账户余额...');
      const balances = await api.getBalances();

      if (balances.success && balances.data) {
        console.log('✅ 账户余额:');
        balances.data.slice(0, 5).forEach(balance => {
          console.log(`   ${balance.asset}: ${balance.total} (可用: ${balance.free})`);
        });
      }
    }

    console.log('\n✅ 所有API调用成功完成！');
  } catch (error) {
    console.error('❌ 错误:', error);
  }
}

// 运行示例
if (require.main === module) {
  main().catch(console.error);
}

export { main };
