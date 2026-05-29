/**
 * 统一标签选择器组件
 * Unified Tag Selector Component
 *
 * 支持单选、多选、分类显示、搜索等功能
 *
 * @author QuantMind Team
 * @date 2025-12-02
 */

import React, { useState, useMemo } from 'react';
import { Tag, Input, Select, Space, Tooltip } from 'antd';
import { PlusOutlined, CloseCircleOutlined, SearchOutlined } from '@ant-design/icons';
import {
  STRATEGY_TAGS,
  STRATEGY_TAG_CATEGORIES,
  getAllTags,
  getTagsByCategory,
  getTagColor,
  searchTags,
  type StrategyTagCategory,
  type TagConfig,
} from '../../shared/types/strategyTags';

const { Option } = Select;

export interface TagSelectorProps {
  /** 已选标签值列表 */
  value?: string[];
  /** 标签变更回调 */
  onChange?: (tags: string[]) => void;
  /** 最大选择数量 */
  maxCount?: number;
  /** 是否显示分类 */
  showCategories?: boolean;
  /** 是否可搜索 */
  searchable?: boolean;
  /** 模式：select 下拉选择 | tags 标签展示 */
  mode?: 'select' | 'tags';
  /** 尺寸 */
  size?: 'small' | 'middle' | 'large';
  /** 占位符 */
  placeholder?: string;
  /** 禁用 */
  disabled?: boolean;
  /** 样式类名 */
  className?: string;
}

/**
 * 标签选择器组件
 */
export const TagSelector: React.FC<TagSelectorProps> = ({
  value = [],
  onChange,
  maxCount,
  showCategories = true,
  searchable = true,
  mode = 'select',
  size = 'middle',
  placeholder = '选择标签',
  disabled = false,
  className = '',
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState<StrategyTagCategory | 'all'>('all');

  // 过滤标签
  const filteredTags = useMemo(() => {
    let tags = getAllTags();

    // 按分类过滤
    if (activeCategory !== 'all') {
      tags = getTagsByCategory(activeCategory);
    }

    // 按搜索词过滤
    if (searchQuery) {
      tags = searchTags(searchQuery);
    }

    return tags;
  }, [activeCategory, searchQuery]);

  // 处理标签添加
  const handleAddTag = (tagValue: string) => {
    if (value.includes(tagValue)) return;
    if (maxCount && value.length >= maxCount) {
      return;
    }
    onChange?.([...value, tagValue]);
  };

  // 处理标签删除
  const handleRemoveTag = (tagValue: string) => {
    onChange?.(value.filter(v => v !== tagValue));
  };

  // 处理下拉选择
  const handleSelectChange = (selectedValues: string[]) => {
    if (maxCount && selectedValues.length > maxCount) {
      return;
    }
    onChange?.(selectedValues);
  };

  // 渲染下拉选择模式
  if (mode === 'select') {
    return (
      <Select
        mode="multiple"
        size={size}
        placeholder={placeholder}
        value={value}
        onChange={handleSelectChange}
        disabled={disabled}
        className={className}
        showSearch={searchable}
        filterOption={(input, option) =>
          String(option?.label ?? '').toLowerCase().includes(String(input).toLowerCase())
        }
        maxTagCount="responsive"
        style={{ width: '100%' }}
      >
        {showCategories ? (
          <>
            <Option disabled value="__category_type__" style={{ fontWeight: 'bold' }}>
              策略类型
            </Option>
            {STRATEGY_TAGS.type.map(tag => (
              <Option key={tag.value} value={tag.value} label={tag.label}>
                <Tag color={tag.color}>{tag.label}</Tag>
              </Option>
            ))}

            <Option disabled value="__category_market__" style={{ fontWeight: 'bold' }}>
              市场类型
            </Option>
            {STRATEGY_TAGS.market.map(tag => (
              <Option key={tag.value} value={tag.value} label={tag.label}>
                <Tag color={tag.color}>{tag.label}</Tag>
              </Option>
            ))}

            <Option disabled value="__category_style__" style={{ fontWeight: 'bold' }}>
              交易风格
            </Option>
            {STRATEGY_TAGS.style.map(tag => (
              <Option key={tag.value} value={tag.value} label={tag.label}>
                <Tag color={tag.color}>{tag.label}</Tag>
              </Option>
            ))}

            <Option disabled value="__category_risk__" style={{ fontWeight: 'bold' }}>
              风险等级
            </Option>
            {STRATEGY_TAGS.risk.map(tag => (
              <Option key={tag.value} value={tag.value} label={tag.label}>
                <Tag color={tag.color}>{tag.label}</Tag>
              </Option>
            ))}
          </>
        ) : (
          getAllTags().map(tag => (
            <Option key={tag.value} value={tag.value} label={tag.label}>
              <Tag color={tag.color}>{tag.label}</Tag>
            </Option>
          ))
        )}
      </Select>
    );
  }

  // 渲染标签展示模式
  return (
    <div className={`tag-selector ${className}`}>
      {/* 搜索栏 */}
      {searchable && (
        <Input
          prefix={<SearchOutlined />}
          placeholder="搜索标签..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          size={size}
          style={{ marginBottom: 12 }}
          disabled={disabled}
        />
      )}

      {/* 分类标签 */}
      {showCategories && (
        <Space wrap style={{ marginBottom: 12 }}>
          <Tag
            color={activeCategory === 'all' ? 'blue' : 'default'}
            style={{ cursor: 'pointer' }}
            onClick={() => setActiveCategory('all')}
          >
            全部
          </Tag>
          <Tag
            color={activeCategory === 'type' ? 'blue' : 'default'}
            style={{ cursor: 'pointer' }}
            onClick={() => setActiveCategory('type')}
          >
            策略类型
          </Tag>
          <Tag
            color={activeCategory === 'market' ? 'blue' : 'default'}
            style={{ cursor: 'pointer' }}
            onClick={() => setActiveCategory('market')}
          >
            市场类型
          </Tag>
          <Tag
            color={activeCategory === 'style' ? 'blue' : 'default'}
            style={{ cursor: 'pointer' }}
            onClick={() => setActiveCategory('style')}
          >
            交易风格
          </Tag>
          <Tag
            color={activeCategory === 'risk' ? 'blue' : 'default'}
            style={{ cursor: 'pointer' }}
            onClick={() => setActiveCategory('risk')}
          >
            风险等级
          </Tag>
        </Space>
      )}

      {/* 已选标签 */}
      {value.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ marginBottom: 4, fontSize: 12, color: '#999' }}>
            已选择 ({value.length}{maxCount ? `/${maxCount}` : ''})：
          </div>
          <Space wrap>
            {value.map(tagValue => {
              const tagConfig = filteredTags.find(t => t.value === tagValue) ||
                              getAllTags().find(t => t.value === tagValue);
              return (
                <Tag
                  key={tagValue}
                  color={tagConfig?.color || 'default'}
                  closable={!disabled}
                  onClose={() => handleRemoveTag(tagValue)}
                >
                  {tagConfig?.label || tagValue}
                </Tag>
              );
            })}
          </Space>
        </div>
      )}

      {/* 可选标签 */}
      <div>
        <div style={{ marginBottom: 4, fontSize: 12, color: '#999' }}>
          {activeCategory === 'all' ? '所有标签' :
           activeCategory === 'type' ? '策略类型' :
           activeCategory === 'market' ? '市场类型' :
           activeCategory === 'style' ? '交易风格' : '风险等级'}：
        </div>
        <Space wrap>
          {filteredTags.map(tag => {
            const isSelected = value.includes(tag.value);
            const isDisabled = disabled || (maxCount ? value.length >= maxCount && !isSelected : false);

            return (
              <Tooltip
                key={tag.value}
                title={isDisabled && !isSelected ? `最多选择${maxCount}个标签` : tag.label}
              >
                <Tag
                  color={isSelected ? tag.color : 'default'}
                  style={{
                    cursor: isDisabled && !isSelected ? 'not-allowed' : 'pointer',
                    opacity: isDisabled && !isSelected ? 0.5 : 1,
                  }}
                  onClick={() => {
                    if (!isDisabled) {
                      if (isSelected) {
                        handleRemoveTag(tag.value);
                      } else {
                        handleAddTag(tag.value);
                      }
                    }
                  }}
                >
                  {isSelected && <CloseCircleOutlined style={{ marginRight: 4 }} />}
                  {tag.label}
                </Tag>
              </Tooltip>
            );
          })}
        </Space>
      </div>

      {/* 提示信息 */}
      {maxCount && value.length >= maxCount && (
        <div style={{ marginTop: 8, fontSize: 12, color: '#faad14' }}>
          已达到最大选择数量 ({maxCount})
        </div>
      )}
    </div>
  );
};

export default TagSelector;
