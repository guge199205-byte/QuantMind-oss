export const fetchChartData = async (chartType: string) => {
  // 在这里，你应该调用你的API来获取数据
  // 为了演示，我们返回一个模拟的响应
  console.log(`Fetching chart data for ${chartType}...`);
  await new Promise(resolve => setTimeout(resolve, 1000)); // 模拟网络延迟

  const generateData = () => {
    return Array.from({ length: 30 }, (_, i) => {
      // 生成包含正负收益的混合数据
      let value;
      if (chartType === 'dailyReturn') {
        // 日收益数据：50%概率为正收益，50%概率为负收益
        const isPositive = Math.random() > 0.5;
        if (isPositive) {
          value = Math.random() * 6000 + 400; // 400-6400的正收益金额
        } else {
          value = -(Math.random() * 4500 + 250); // -250到-4750的负收益金额
        }
      } else {
        // 其他图表类型保持原有逻辑
        value = Math.random() * 100 + 50;
      }

      return {
        timestamp: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000).toISOString(),
        value: Math.round(value * 100) / 100, // 保留两位小数
        label: `第${i + 1}天数据`
      };
    });
  };

  return generateData();
};
