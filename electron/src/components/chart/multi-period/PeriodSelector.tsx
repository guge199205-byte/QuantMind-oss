/**
 * 周期选择器组件
 * 支持多周期选择和快速切换
 */

import React, { useState } from 'react';
import { Period } from '../../../services/chart/MultiPeriodDataService';

export interface PeriodSelectorProps {
  periods: Period[];
  selectedPeriod: string;
  onPeriodChange: (periodId: string) => void;
  onTogglePeriod?: (periodId: string, enabled: boolean) => void;
  multiSelect?: boolean;
  className?: string;
}

/**
 * 周期选择器组件
 */
export const PeriodSelector: React.FC<PeriodSelectorProps> = ({
  periods,
  selectedPeriod,
  onPeriodChange,
  onTogglePeriod,
  multiSelect = false,
  className = ''
}) => {
  const [hoveredPeriod, setHoveredPeriod] = useState<string | null>(null);

  const handlePeriodClick = (periodId: string) => {
    if (multiSelect && onTogglePeriod) {
      const period = periods.find(p => p.id === periodId);
      if (period) {
        onTogglePeriod(periodId, !period.enabled);
      }
    } else {
      onPeriodChange(periodId);
    }
  };

  const handlePeriodToggle = (periodId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    const period = periods.find(p => p.id === periodId);
    if (period && onTogglePeriod) {
      onTogglePeriod(periodId, !period.enabled);
    }
  };

  return (
    <div className={`period-selector ${className}`}>
      <div className="period-selector__header">
        <h3 className="period-selector__title">时间周期</h3>
        {multiSelect && (
          <span className="period-selector__subtitle">
            {periods.filter(p => p.enabled).length} 个已选择
          </span>
        )}
      </div>

      <div className="period-selector__list">
        {periods.map(period => {
          const isSelected = period.id === selectedPeriod;
          const isEnabled = period.enabled;
          const isHovered = hoveredPeriod === period.id;

          return (
            <div
              key={period.id}
              className={`period-item ${isSelected ? 'period-item--selected' : ''} ${
                isEnabled ? 'period-item--enabled' : ''
              } ${isHovered ? 'period-item--hovered' : ''}`}
              onClick={() => handlePeriodClick(period.id)}
              onMouseEnter={() => setHoveredPeriod(period.id)}
              onMouseLeave={() => setHoveredPeriod(null)}
              style={{
                borderLeft: `3px solid ${isEnabled || isSelected ? period.color : 'transparent'}`
              }}
            >
              <div className="period-item__content">
                <div className="period-item__main">
                  <span className="period-item__name">{period.name}</span>
                  <span className="period-item__interval">{period.interval}</span>
                </div>

                {multiSelect && onTogglePeriod && (
                  <div className="period-item__actions">
                    <label
                      className="period-item__checkbox"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={isEnabled}
                        onChange={(e) => handlePeriodToggle(period.id, e as any)}
                      />
                      <span className="period-item__checkmark"></span>
                    </label>
                  </div>
                )}
              </div>

              {isEnabled && (
                <div
                  className="period-item__indicator"
                  style={{ backgroundColor: period.color }}
                ></div>
              )}
            </div>
          );
        })}
      </div>

      <style>{`
        .period-selector {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 16px;
          background: #ffffff;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .period-selector__header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-bottom: 12px;
          border-bottom: 1px solid #e5e7eb;
        }

        .period-selector__title {
          font-size: 14px;
          font-weight: 600;
          color: #111827;
          margin: 0;
        }

        .period-selector__subtitle {
          font-size: 12px;
          color: #6b7280;
        }

        .period-selector__list {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .period-item {
          position: relative;
          display: flex;
          align-items: center;
          padding: 10px 12px;
          border-radius: 6px;
          cursor: pointer;
          transition: all 0.2s ease;
          background: #ffffff;
        }

        .period-item:hover {
          background: #f9fafb;
        }

        .period-item--selected {
          background: #eff6ff;
        }

        .period-item--enabled {
          background: #f0f9ff;
        }

        .period-item--hovered {
          transform: translateX(2px);
        }

        .period-item__content {
          display: flex;
          justify-content: space-between;
          align-items: center;
          flex: 1;
        }

        .period-item__main {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .period-item__name {
          font-size: 13px;
          font-weight: 500;
          color: #111827;
        }

        .period-item__interval {
          font-size: 11px;
          color: #6b7280;
          background: #f3f4f6;
          padding: 2px 6px;
          border-radius: 4px;
        }

        .period-item__actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .period-item__checkbox {
          position: relative;
          display: flex;
          align-items: center;
          cursor: pointer;
        }

        .period-item__checkbox input {
          position: absolute;
          opacity: 0;
          cursor: pointer;
        }

        .period-item__checkmark {
          display: block;
          width: 16px;
          height: 16px;
          border: 2px solid #d1d5db;
          border-radius: 3px;
          background: #ffffff;
          transition: all 0.2s ease;
        }

        .period-item__checkbox input:checked ~ .period-item__checkmark {
          background: #3b82f6;
          border-color: #3b82f6;
        }

        .period-item__checkbox input:checked ~ .period-item__checkmark::after {
          content: '';
          position: absolute;
          left: 5px;
          top: 2px;
          width: 4px;
          height: 8px;
          border: solid white;
          border-width: 0 2px 2px 0;
          transform: rotate(45deg);
        }

        .period-item__indicator {
          position: absolute;
          right: 12px;
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }

      `}</style>
    </div>
  );
};

/**
 * 周期切换按钮组
 */
export interface PeriodButtonGroupProps {
  periods: Period[];
  selectedPeriod: string;
  onPeriodChange: (periodId: string) => void;
  size?: 'small' | 'medium' | 'large';
  className?: string;
}

export const PeriodButtonGroup: React.FC<PeriodButtonGroupProps> = ({
  periods,
  selectedPeriod,
  onPeriodChange,
  size = 'medium',
  className = ''
}) => {
  return (
    <div className={`period-button-group period-button-group--${size} ${className}`}>
      {periods.map(period => {
        const isSelected = period.id === selectedPeriod;
        return (
          <button
            key={period.id}
            className={`period-button ${isSelected ? 'period-button--selected' : ''}`}
            onClick={() => onPeriodChange(period.id)}
            style={{
              borderColor: isSelected ? period.color : undefined,
              color: isSelected ? period.color : undefined
            }}
          >
            {period.name}
          </button>
        );
      })}

      <style>{`
        .period-button-group {
          display: flex;
          gap: 4px;
          padding: 4px;
          background: #f3f4f6;
          border-radius: 6px;
        }

        .period-button-group--small {
          gap: 2px;
          padding: 2px;
        }

        .period-button-group--large {
          gap: 6px;
          padding: 6px;
        }

        .period-button {
          padding: 6px 12px;
          font-size: 13px;
          font-weight: 500;
          color: #6b7280;
          background: transparent;
          border: 1px solid transparent;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .period-button-group--small .period-button {
          padding: 4px 8px;
          font-size: 12px;
        }

        .period-button-group--large .period-button {
          padding: 8px 16px;
          font-size: 14px;
        }

        .period-button:hover {
          background: #ffffff;
        }

        .period-button--selected {
          background: #ffffff;
          font-weight: 600;
          box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
        }

      `}</style>
    </div>
  );
};

export default PeriodSelector;
