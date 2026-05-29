/**
 * 图表标注数据管理服务
 * 负责标注数据的存储、导入导出和模板管理
 */

export interface Annotation {
  id: string;
  type: 'trendline' | 'horizontal' | 'vertical' | 'rectangle' | 'text' | 'marker' | 'fibonacci';
  data: any;
  chartId: string;
  symbol: string;
  createdAt: number;
  updatedAt: number;
  metadata?: Record<string, any>;
}

export interface AnnotationTemplate {
  id: string;
  name: string;
  description: string;
  annotations: Annotation[];
  createdAt: number;
  thumbnail?: string;
}

export interface SupportResistanceLevel {
  id: string;
  price: number;
  type: 'support' | 'resistance';
  strength: number; // 0-1, 强度
  touches: number; // 接触次数
  confirmed: boolean;
  color: string;
  label?: string;
}

/**
 * 标注数据管理服务
 */
export class AnnotationService {
  private storageKey = 'chart_annotations';
  private templateKey = 'annotation_templates';
  private annotations: Map<string, Annotation[]>;
  private templates: Map<string, AnnotationTemplate>;
  private undoStack: Map<string, Annotation[][]>;
  private redoStack: Map<string, Annotation[][]>;

  constructor() {
    this.annotations = new Map();
    this.templates = new Map();
    this.undoStack = new Map();
    this.redoStack = new Map();
    this.loadFromStorage();
  }

  /**
   * 获取图表的所有标注
   * @param chartId 图表ID
   * @returns 标注数组
   */
  getAnnotations(chartId: string): Annotation[] {
    return this.annotations.get(chartId) || [];
  }

  /**
   * 添加标注
   * @param chartId 图表ID
   * @param annotation 标注对象
   */
  addAnnotation(chartId: string, annotation: Omit<Annotation, 'id' | 'createdAt' | 'updatedAt'>): Annotation {
    const newAnnotation: Annotation = {
      ...annotation,
      id: `annotation-${Date.now()}-${Math.random()}`,
      createdAt: Date.now(),
      updatedAt: Date.now()
    };

    this.saveToUndoStack(chartId);

    const existing = this.annotations.get(chartId) || [];
    this.annotations.set(chartId, [...existing, newAnnotation]);

    this.saveToStorage();
    return newAnnotation;
  }

  /**
   * 更新标注
   * @param chartId 图表ID
   * @param annotationId 标注ID
   * @param updates 更新内容
   */
  updateAnnotation(chartId: string, annotationId: string, updates: Partial<Annotation>): boolean {
    const annotations = this.annotations.get(chartId);
    if (!annotations) return false;

    this.saveToUndoStack(chartId);

    const index = annotations.findIndex(a => a.id === annotationId);
    if (index === -1) return false;

    annotations[index] = {
      ...annotations[index],
      ...updates,
      updatedAt: Date.now()
    };

    this.saveToStorage();
    return true;
  }

  /**
   * 删除标注
   * @param chartId 图表ID
   * @param annotationId 标注ID
   */
  deleteAnnotation(chartId: string, annotationId: string): boolean {
    const annotations = this.annotations.get(chartId);
    if (!annotations) return false;

    this.saveToUndoStack(chartId);

    const filtered = annotations.filter(a => a.id !== annotationId);
    if (filtered.length === annotations.length) return false;

    this.annotations.set(chartId, filtered);
    this.saveToStorage();
    return true;
  }

  /**
   * 清除图表的所有标注
   * @param chartId 图表ID
   */
  clearAnnotations(chartId: string): void {
    this.saveToUndoStack(chartId);
    this.annotations.delete(chartId);
    this.saveToStorage();
  }

  /**
   * 撤销操作
   * @param chartId 图表ID
   */
  undo(chartId: string): boolean {
    const undoStack = this.undoStack.get(chartId);
    if (!undoStack || undoStack.length === 0) return false;

    const currentState = this.annotations.get(chartId) || [];
    const previousState = undoStack.pop()!;

    // 保存到重做栈
    const redoStack = this.redoStack.get(chartId) || [];
    redoStack.push(currentState);
    this.redoStack.set(chartId, redoStack);

    // 恢复到之前的状态
    this.annotations.set(chartId, previousState);
    this.saveToStorage();
    return true;
  }

  /**
   * 重做操作
   * @param chartId 图表ID
   */
  redo(chartId: string): boolean {
    const redoStack = this.redoStack.get(chartId);
    if (!redoStack || redoStack.length === 0) return false;

    const currentState = this.annotations.get(chartId) || [];
    const nextState = redoStack.pop()!;

    // 保存到撤销栈
    const undoStack = this.undoStack.get(chartId) || [];
    undoStack.push(currentState);
    this.undoStack.set(chartId, undoStack);

    // 恢复到下一个状态
    this.annotations.set(chartId, nextState);
    this.saveToStorage();
    return true;
  }

  /**
   * 检查是否可以撤销
   * @param chartId 图表ID
   */
  canUndo(chartId: string): boolean {
    const undoStack = this.undoStack.get(chartId);
    return !!(undoStack && undoStack.length > 0);
  }

  /**
   * 检查是否可以重做
   * @param chartId 图表ID
   */
  canRedo(chartId: string): boolean {
    const redoStack = this.redoStack.get(chartId);
    return !!(redoStack && redoStack.length > 0);
  }

  /**
   * 保存当前状态到撤销栈
   * @param chartId 图表ID
   */
  private saveToUndoStack(chartId: string): void {
    const currentState = this.annotations.get(chartId) || [];
    const undoStack = this.undoStack.get(chartId) || [];

    // 限制撤销栈大小
    if (undoStack.length >= 50) {
      undoStack.shift();
    }

    undoStack.push([...currentState]);
    this.undoStack.set(chartId, undoStack);

    // 清空重做栈
    this.redoStack.set(chartId, []);
  }

  /**
   * 导出标注数据
   * @param chartId 图表ID
   * @returns JSON字符串
   */
  exportAnnotations(chartId: string): string {
    const annotations = this.annotations.get(chartId) || [];
    return JSON.stringify(annotations, null, 2);
  }

  /**
   * 导入标注数据
   * @param chartId 图表ID
   * @param jsonData JSON字符串
   */
  importAnnotations(chartId: string, jsonData: string): boolean {
    try {
      const imported = JSON.parse(jsonData) as Annotation[];
      if (!Array.isArray(imported)) return false;

      this.saveToUndoStack(chartId);
      this.annotations.set(chartId, imported);
      this.saveToStorage();
      return true;
    } catch (error) {
      console.error('导入标注数据失败:', error);
      return false;
    }
  }

  /**
   * 保存为模板
   * @param chartId 图表ID
   * @param name 模板名称
   * @param description 模板描述
   */
  saveAsTemplate(chartId: string, name: string, description: string): AnnotationTemplate {
    const annotations = this.annotations.get(chartId) || [];
    const template: AnnotationTemplate = {
      id: `template-${Date.now()}`,
      name,
      description,
      annotations: JSON.parse(JSON.stringify(annotations)), // 深拷贝
      createdAt: Date.now()
    };

    this.templates.set(template.id, template);
    this.saveToStorage();
    return template;
  }

  /**
   * 应用模板
   * @param chartId 图表ID
   * @param templateId 模板ID
   */
  applyTemplate(chartId: string, templateId: string): boolean {
    const template = this.templates.get(templateId);
    if (!template) return false;

    this.saveToUndoStack(chartId);

    // 复制模板的标注并更新ID和时间戳
    const newAnnotations = template.annotations.map(a => ({
      ...a,
      id: `annotation-${Date.now()}-${Math.random()}`,
      chartId,
      createdAt: Date.now(),
      updatedAt: Date.now()
    }));

    this.annotations.set(chartId, newAnnotations);
    this.saveToStorage();
    return true;
  }

  /**
   * 获取所有模板
   */
  getTemplates(): AnnotationTemplate[] {
    return Array.from(this.templates.values());
  }

  /**
   * 删除模板
   * @param templateId 模板ID
   */
  deleteTemplate(templateId: string): boolean {
    const deleted = this.templates.delete(templateId);
    if (deleted) {
      this.saveToStorage();
    }
    return deleted;
  }

  /**
   * 自动识别支撑阻力位
   * @param prices 价格数组
   * @param sensitivity 敏感度 (0-1)
   * @returns 支撑阻力位数组
   */
  detectSupportResistance(prices: number[], sensitivity: number = 0.5): SupportResistanceLevel[] {
    if (prices.length < 10) return [];

    const levels: SupportResistanceLevel[] = [];
    const threshold = this.calculatePriceThreshold(prices, sensitivity);

    // 找到局部极值点
    const peaks: number[] = [];
    const valleys: number[] = [];

    for (let i = 1; i < prices.length - 1; i++) {
      if (prices[i] > prices[i - 1] && prices[i] > prices[i + 1]) {
        peaks.push(prices[i]);
      } else if (prices[i] < prices[i - 1] && prices[i] < prices[i + 1]) {
        valleys.push(prices[i]);
      }
    }

    // 聚类相近的价格点
    const resistanceClusters = this.clusterPrices(peaks, threshold);
    const supportClusters = this.clusterPrices(valleys, threshold);

    // 创建阻力位
    resistanceClusters.forEach((cluster, index) => {
      const avgPrice = cluster.reduce((a, b) => a + b, 0) / cluster.length;
      levels.push({
        id: `resistance-${index}`,
        price: avgPrice,
        type: 'resistance',
        strength: cluster.length / peaks.length,
        touches: cluster.length,
        confirmed: cluster.length >= 2,
        color: '#ef4444',
        label: `阻力 ${avgPrice.toFixed(2)}`
      });
    });

    // 创建支撑位
    supportClusters.forEach((cluster, index) => {
      const avgPrice = cluster.reduce((a, b) => a + b, 0) / cluster.length;
      levels.push({
        id: `support-${index}`,
        price: avgPrice,
        type: 'support',
        strength: cluster.length / valleys.length,
        touches: cluster.length,
        confirmed: cluster.length >= 2,
        color: '#10b981',
        label: `支撑 ${avgPrice.toFixed(2)}`
      });
    });

    return levels.sort((a, b) => b.strength - a.strength);
  }

  /**
   * 计算价格阈值
   */
  private calculatePriceThreshold(prices: number[], sensitivity: number): number {
    const max = Math.max(...prices);
    const min = Math.min(...prices);
    const range = max - min;
    return range * (0.02 + (1 - sensitivity) * 0.03);
  }

  /**
   * 聚类相近的价格
   */
  private clusterPrices(prices: number[], threshold: number): number[][] {
    if (prices.length === 0) return [];

    const sorted = [...prices].sort((a, b) => a - b);
    const clusters: number[][] = [];
    let currentCluster: number[] = [sorted[0]];

    for (let i = 1; i < sorted.length; i++) {
      if (sorted[i] - sorted[i - 1] <= threshold) {
        currentCluster.push(sorted[i]);
      } else {
        if (currentCluster.length >= 2) {
          clusters.push(currentCluster);
        }
        currentCluster = [sorted[i]];
      }
    }

    if (currentCluster.length >= 2) {
      clusters.push(currentCluster);
    }

    return clusters;
  }

  /**
   * 保存到本地存储
   */
  private saveToStorage(): void {
    try {
      const annotationsData = Array.from(this.annotations.entries());
      const templatesData = Array.from(this.templates.entries());

      localStorage.setItem(this.storageKey, JSON.stringify(annotationsData));
      localStorage.setItem(this.templateKey, JSON.stringify(templatesData));
    } catch (error) {
      console.error('保存标注数据失败:', error);
    }
  }

  /**
   * 从本地存储加载
   */
  private loadFromStorage(): void {
    try {
      const annotationsData = localStorage.getItem(this.storageKey);
      if (annotationsData) {
        const entries = JSON.parse(annotationsData);
        this.annotations = new Map(entries);
      }

      const templatesData = localStorage.getItem(this.templateKey);
      if (templatesData) {
        const entries = JSON.parse(templatesData);
        this.templates = new Map(entries);
      }
    } catch (error) {
      console.error('加载标注数据失败:', error);
    }
  }

  /**
   * 清除所有数据
   */
  clearAll(): void {
    this.annotations.clear();
    this.templates.clear();
    this.undoStack.clear();
    this.redoStack.clear();
    localStorage.removeItem(this.storageKey);
    localStorage.removeItem(this.templateKey);
  }
}

export default new AnnotationService();
