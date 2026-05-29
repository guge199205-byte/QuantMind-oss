/**
 * 标注服务测试
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { AnnotationService } from '../AnnotationService';

describe('AnnotationService', () => {
  let service: AnnotationService;
  const chartId = 'test-chart';

  beforeEach(() => {
    service = new AnnotationService();
    service.clearAll();
  });

  afterEach(() => {
    service.clearAll();
  });

  describe('addAnnotation', () => {
    it('应该添加新标注', () => {
      const annotation = service.addAnnotation(chartId, {
        type: 'trendline',
        data: { startPoint: { x: 0, y: 0 }, endPoint: { x: 100, y: 100 } },
        chartId,
        symbol: 'BTCUSDT'
      });

      expect(annotation.id).toBeDefined();
      expect(annotation.createdAt).toBeDefined();
      expect(annotation.updatedAt).toBeDefined();
      expect(annotation.type).toBe('trendline');
    });

    it('应该能添加多个标注', () => {
      service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      service.addAnnotation(chartId, {
        type: 'horizontal',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      const annotations = service.getAnnotations(chartId);
      expect(annotations).toHaveLength(2);
    });
  });

  describe('getAnnotations', () => {
    it('空图表应该返回空数组', () => {
      const annotations = service.getAnnotations(chartId);
      expect(annotations).toEqual([]);
    });

    it('应该返回正确的标注', () => {
      service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      const annotations = service.getAnnotations(chartId);
      expect(annotations).toHaveLength(1);
      expect(annotations[0].type).toBe('trendline');
    });
  });

  describe('updateAnnotation', () => {
    it('应该更新标注', () => {
      const annotation = service.addAnnotation(chartId, {
        type: 'trendline',
        data: { value: 100 },
        chartId,
        symbol: 'BTCUSDT'
      });

      const updated = service.updateAnnotation(chartId, annotation.id, {
        data: { value: 200 }
      });

      expect(updated).toBe(true);

      const annotations = service.getAnnotations(chartId);
      expect(annotations[0].data.value).toBe(200);
    });

    it('不存在的标注应该返回false', () => {
      const updated = service.updateAnnotation(chartId, 'nonexistent', {
        data: {}
      });

      expect(updated).toBe(false);
    });
  });

  describe('deleteAnnotation', () => {
    it('应该删除标注', () => {
      const annotation = service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      const deleted = service.deleteAnnotation(chartId, annotation.id);
      expect(deleted).toBe(true);

      const annotations = service.getAnnotations(chartId);
      expect(annotations).toHaveLength(0);
    });

    it('删除不存在的标注应该返回false', () => {
      const deleted = service.deleteAnnotation(chartId, 'nonexistent');
      expect(deleted).toBe(false);
    });
  });

  describe('clearAnnotations', () => {
    it('应该清除所有标注', () => {
      service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      service.addAnnotation(chartId, {
        type: 'horizontal',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      service.clearAnnotations(chartId);

      const annotations = service.getAnnotations(chartId);
      expect(annotations).toHaveLength(0);
    });
  });

  describe('undo/redo', () => {
    it('应该支持撤销操作', () => {
      service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      expect(service.getAnnotations(chartId)).toHaveLength(1);

      service.undo(chartId);

      expect(service.getAnnotations(chartId)).toHaveLength(0);
    });

    it('应该支持重做操作', () => {
      service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      service.undo(chartId);
      service.redo(chartId);

      expect(service.getAnnotations(chartId)).toHaveLength(1);
    });

    it('应该正确报告是否可以撤销/重做', () => {
      expect(service.canUndo(chartId)).toBe(false);
      expect(service.canRedo(chartId)).toBe(false);

      service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      expect(service.canUndo(chartId)).toBe(true);
      expect(service.canRedo(chartId)).toBe(false);

      service.undo(chartId);

      expect(service.canUndo(chartId)).toBe(false);
      expect(service.canRedo(chartId)).toBe(true);
    });
  });

  describe('export/import', () => {
    it('应该导出标注数据', () => {
      service.addAnnotation(chartId, {
        type: 'trendline',
        data: { value: 100 },
        chartId,
        symbol: 'BTCUSDT'
      });

      const exported = service.exportAnnotations(chartId);
      expect(exported).toBeTruthy();
      expect(JSON.parse(exported)).toHaveLength(1);
    });

    it('应该导入标注数据', () => {
      const data = JSON.stringify([
        {
          id: 'test-1',
          type: 'trendline',
          data: { value: 100 },
          chartId,
          symbol: 'BTCUSDT',
          createdAt: Date.now(),
          updatedAt: Date.now()
        }
      ]);

      const imported = service.importAnnotations(chartId, data);
      expect(imported).toBe(true);

      const annotations = service.getAnnotations(chartId);
      expect(annotations).toHaveLength(1);
    });

    it('无效的JSON应该导入失败', () => {
      const imported = service.importAnnotations(chartId, 'invalid json');
      expect(imported).toBe(false);
    });
  });

  describe('templates', () => {
    it('应该保存为模板', () => {
      service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      const template = service.saveAsTemplate(chartId, '测试模板', '这是一个测试模板');

      expect(template.id).toBeDefined();
      expect(template.name).toBe('测试模板');
      expect(template.annotations).toHaveLength(1);
    });

    it('应该应用模板', () => {
      service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      const template = service.saveAsTemplate(chartId, '测试模板', '描述');

      const newChartId = 'new-chart';
      service.applyTemplate(newChartId, template.id);

      const annotations = service.getAnnotations(newChartId);
      expect(annotations).toHaveLength(1);
    });

    it('应该获取所有模板', () => {
      service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      service.saveAsTemplate(chartId, '模板1', '描述1');
      service.saveAsTemplate(chartId, '模板2', '描述2');

      const templates = service.getTemplates();
      expect(templates.length).toBeGreaterThanOrEqual(1);
    });

    it('应该删除模板', () => {
      service.addAnnotation(chartId, {
        type: 'trendline',
        data: {},
        chartId,
        symbol: 'BTCUSDT'
      });

      const template = service.saveAsTemplate(chartId, '测试模板', '描述');
      const deleted = service.deleteTemplate(template.id);

      expect(deleted).toBe(true);
      expect(service.getTemplates()).toHaveLength(0);
    });
  });

  describe('detectSupportResistance', () => {
    it('应该识别支撑阻力位', () => {
      const prices = [
        100, 105, 103, 108, 106, 110, 108, 112, 109, 107,
        105, 103, 106, 104, 102, 105, 107, 109, 111, 110
      ];

      const levels = service.detectSupportResistance(prices, 0.5);

      expect(levels.length).toBeGreaterThan(0);
      expect(levels.every(l => l.type === 'support' || l.type === 'resistance')).toBe(true);
    });

    it('数据不足应该返回空数组', () => {
      const prices = [100, 105, 103];
      const levels = service.detectSupportResistance(prices);

      expect(levels).toEqual([]);
    });

    it('应该按强度排序', () => {
      const prices = [
        100, 105, 103, 108, 106, 110, 108, 112, 109, 107,
        105, 103, 106, 104, 102, 105, 107, 109, 111, 110
      ];

      const levels = service.detectSupportResistance(prices);

      for (let i = 0; i < levels.length - 1; i++) {
        expect(levels[i].strength).toBeGreaterThanOrEqual(levels[i + 1].strength);
      }
    });
  });
});
