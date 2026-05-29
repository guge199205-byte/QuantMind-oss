import React, { useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useMarketData } from '../../hooks/useMarketData';

type WeatherType = 'sunny' | 'cloudy' | 'gloomy';

export const MarketWeatherBackground: React.FC = () => {
  const { data } = useMarketData({ refreshInterval: 15000 });

  const weatherType = useMemo<WeatherType>(() => {
    if (!data || !data.indices || data.indices.length === 0) return 'cloudy';

    const mainIndices = data.indices.slice(0, 6);
    const upCount = mainIndices.filter(idx => idx.changePercent > 0).length;
    const downCount = mainIndices.filter(idx => idx.changePercent < 0).length;

    if (upCount >= 4) return 'sunny';
    if (downCount >= 4) return 'gloomy';
    return 'cloudy';
  }, [data]);

  const colors = {
    sunny: {
      base: 'rgba(139, 92, 246, 0.15)',
      bright: 'rgba(139, 92, 246, 0.25)',
      to: 'transparent'
    },
    cloudy: {
      base: 'rgba(14, 165, 233, 0.15)',
      bright: 'rgba(14, 165, 233, 0.25)',
      to: 'transparent'
    },
    gloomy: {
      base: 'rgba(16, 185, 129, 0.15)',
      bright: 'rgba(16, 185, 129, 0.25)',
      to: 'transparent'
    }
  };

  const breatheTransition = {
    duration: 6,
    ease: "easeInOut" as const,
    repeat: Infinity,
    repeatType: "reverse" as const,
  };

  return (
    <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden select-none">
      <AnimatePresence mode="wait">
        <motion.div
          key={weatherType}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 1.2, ease: "easeInOut" }}
          className="absolute inset-0"
        >
          {/* Top Edge */}
          <motion.div
            className="absolute top-0 left-0 right-0 h-[30px]"
            animate={{
              background: [
                `linear-gradient(to bottom, ${colors[weatherType].base}, ${colors[weatherType].to})`,
                `linear-gradient(to bottom, ${colors[weatherType].bright}, ${colors[weatherType].to})`,
                `linear-gradient(to bottom, ${colors[weatherType].base}, ${colors[weatherType].to})`,
              ],
            }}
            transition={breatheTransition}
          />
          {/* Bottom Edge */}
          <motion.div
            className="absolute bottom-0 left-0 right-0 h-[30px]"
            animate={{
              background: [
                `linear-gradient(to top, ${colors[weatherType].base}, ${colors[weatherType].to})`,
                `linear-gradient(to top, ${colors[weatherType].bright}, ${colors[weatherType].to})`,
                `linear-gradient(to top, ${colors[weatherType].base}, ${colors[weatherType].to})`,
              ],
            }}
            transition={breatheTransition}
          />
          {/* Left Edge */}
          <motion.div
            className="absolute top-0 left-0 bottom-0 w-[30px]"
            animate={{
              background: [
                `linear-gradient(to right, ${colors[weatherType].base}, ${colors[weatherType].to})`,
                `linear-gradient(to right, ${colors[weatherType].bright}, ${colors[weatherType].to})`,
                `linear-gradient(to right, ${colors[weatherType].base}, ${colors[weatherType].to})`,
              ],
            }}
            transition={breatheTransition}
          />
          {/* Right Edge */}
          <motion.div
            className="absolute top-0 right-0 bottom-0 w-[30px]"
            animate={{
              background: [
                `linear-gradient(to left, ${colors[weatherType].base}, ${colors[weatherType].to})`,
                `linear-gradient(to left, ${colors[weatherType].bright}, ${colors[weatherType].to})`,
                `linear-gradient(to left, ${colors[weatherType].base}, ${colors[weatherType].to})`,
              ],
            }}
            transition={breatheTransition}
          />
        </motion.div>
      </AnimatePresence>

      {/* 极轻微的微弱纹理 */}
      <div className="absolute inset-0 opacity-[0.012] pointer-events-none bg-[url('https://www.transparenttextures.com/patterns/cubes.png')]" />
    </div>
  );
};

