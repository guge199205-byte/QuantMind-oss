/**
 * API签名工具
 */

import * as crypto from 'crypto';

export class Signature {
  /**
   * HMAC-SHA256签名
   */
  static hmacSha256(message: string, secret: string): string {
    return crypto
      .createHmac('sha256', secret)
      .update(message)
      .digest('hex');
  }

  /**
   * HMAC-SHA256签名（Base64）
   */
  static hmacSha256Base64(message: string, secret: string): string {
    return crypto
      .createHmac('sha256', secret)
      .update(message)
      .digest('base64');
  }

  /**
   * 生成时间戳（毫秒）
   */
  static timestamp(): number {
    return Date.now();
  }

  /**
   * 生成时间戳（秒）
   */
  static timestampSeconds(): number {
    return Math.floor(Date.now() / 1000);
  }

  /**
   * 生成ISO时间戳
   */
  static timestampISO(): string {
    return new Date().toISOString();
  }

  /**
   * 构建查询字符串（按字母序）
   */
  static buildQueryString(params: Record<string, any>): string {
    return Object.keys(params)
      .filter(key => params[key] !== undefined && params[key] !== null)
      .sort()
      .map(key => `${key}=${encodeURIComponent(params[key])}`)
      .join('&');
  }

  /**
   * 生成随机字符串
   */
  static randomString(length: number = 16): string {
    return crypto.randomBytes(length).toString('hex').slice(0, length);
  }
}
