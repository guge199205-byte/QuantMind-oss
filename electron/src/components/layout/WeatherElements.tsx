import React from 'react';
import { motion } from 'framer-motion';

/**
 * 晴天场景 (Sunny)
 * 大部分指数上涨，光芒四射
 */
export const SunScene: React.FC = () => {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-40">
      <motion.div
        className="absolute -top-32 -right-32 w-[600px] h-[600px]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        {/* 太阳主体 */}
        <motion.div
          className="absolute inset-0 bg-gradient-to-br from-amber-300 to-orange-400 rounded-full blur-3xl shadow-[0_0_100px_rgba(251,191,36,0.4)]"
          animate={{ scale: [1, 1.1, 1] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        />
        
        {/* 旋转射线 */}
        <motion.svg
          viewBox="0 0 100 100"
          className="w-full h-full"
          animate={{ rotate: 360 }}
          transition={{ duration: 60, repeat: Infinity, ease: "linear" }}
        >
          {[...Array(12)].map((_, i) => (
            <motion.line
              key={i}
              x1="50" y1="50"
              x2="50" y2="100"
              stroke="white"
              strokeWidth="0.5"
              strokeLinecap="round"
              transform={`rotate(${i * 30} 50 50)`}
              animate={{ opacity: [0.1, 0.4, 0.1], strokeWidth: [0.2, 0.8, 0.2] }}
              transition={{ duration: 3, repeat: Infinity, delay: i * 0.2 }}
            />
          ))}
        </motion.svg>
      </motion.div>
    </div>
  );
};

/**
 * 多云场景 (Cloudy)
 * 涨跌互现，云朵漂浮
 */
export const CloudyScene: React.FC = () => {
  const clouds = [
    { top: '15%', left: '-10%', scale: 1.5, duration: 45, opacity: 0.6 },
    { top: '45%', left: '-20%', scale: 1.0, duration: 60, opacity: 0.4 },
    { top: '10%', left: '50%', scale: 1.2, duration: 55, opacity: 0.5 },
    { top: '70%', left: '-15%', scale: 1.4, duration: 70, opacity: 0.3 },
  ];

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none opacity-40">
      {clouds.map((cloud, i) => (
        <motion.div
          key={i}
          className="absolute"
          style={{ top: cloud.top, left: cloud.left }}
          initial={{ x: '-100%' }}
          animate={{ x: '120vw' }}
          transition={{ 
            duration: cloud.duration, 
            repeat: Infinity, 
            ease: "linear",
            delay: i * -15 // 错开起始位置
          }}
        >
          <svg width="200" height="120" viewBox="0 0 200 120" style={{ transform: `scale(${cloud.scale})` }}>
            <path
              d="M45,80 C45,60 65,45 85,45 C95,25 125,25 145,45 C175,45 195,65 195,95 C195,115 175,135 145,135 L45,135 C25,135 5,115 5,95 C5,75 25,60 45,80 Z"
              fill="white"
              fillOpacity={cloud.opacity}
            />
          </svg>
        </motion.div>
      ))}
    </div>
  );
};

/**
 * 阴雨场景 (Rainy/Gloomy)
 * 全线下跌，冷色调下雨
 */
export const RainyScene: React.FC = () => {
  // 底部灰色调混合
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* 整体环境色降噪 */}
      <motion.div 
        className="absolute inset-0 bg-slate-400 opacity-[0.03]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.03 }}
        exit={{ opacity: 0 }}
      />
      
      {/* 雨迹动画 */}
      {[...Array(40)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-[1px] h-[20px] bg-slate-300 opacity-20"
          style={{
            top: `${Math.random() * 100}%`,
            left: `${Math.random() * 100}%`,
          }}
          animate={{ 
            y: ['0', '100vh'],
            opacity: [0, 0.3, 0]
          }}
          transition={{
            duration: 0.8 + Math.random() * 0.5,
            repeat: Infinity,
            ease: "linear",
            delay: Math.random() * 2
          }}
        />
      ))}

      {/* 低沉的暗云层 */}
      <div className="absolute top-0 left-0 w-full h-[300px] bg-gradient-to-b from-slate-200/20 to-transparent" />
    </div>
  );
};
