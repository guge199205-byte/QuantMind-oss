/**
 * 技术指标计算服务
 * 导出所有指标计算器
 */

export * from './ATRCalculator';
export * from './OBVCalculator';
export * from './SARCalculator';
export * from './CCICalculator';
export * from './WRCalculator';

// 默认导出所有计算器
import ATR from './ATRCalculator';
import OBV from './OBVCalculator';
import SAR from './SARCalculator';
import CCI from './CCICalculator';
import WR from './WRCalculator';

export const Indicators = {
  ATR,
  OBV,
  SAR,
  CCI,
  WR
};

export default Indicators;
