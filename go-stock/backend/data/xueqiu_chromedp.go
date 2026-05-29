package data

import (
	"context"
	"fmt"
	"go-stock/backend/logger"
	"strings"
	"time"

	"github.com/chromedp/cdproto/network"
	"github.com/chromedp/chromedp"
)

const xueqiuCookieChromedpMinTimeout = 2 * time.Minute

const XueqiuCookieCacheTTL = 12 * time.Minute

const xueqiuHomePage = "https://xueqiu.com/"

var xueqiuCookieCache = &cookieCache{
	items: make(map[string]*cookieCacheItem),
}

func InvalidateXueqiuCookieCache() {
	xueqiuCookieCache.mu.Lock()
	defer xueqiuCookieCache.mu.Unlock()
	xueqiuCookieCache.items = make(map[string]*cookieCacheItem)
}

func GetXueqiuCookieCacheInfo() map[string]interface{} {
	xueqiuCookieCache.mu.Lock()
	defer xueqiuCookieCache.mu.Unlock()

	now := time.Now()
	info := make(map[string]interface{})
	items := make([]map[string]string, 0, len(xueqiuCookieCache.items))

	for key, item := range xueqiuCookieCache.items {
		isExpired := now.After(item.expiry)
		items = append(items, map[string]string{
			"cacheKey": key,
			"expiry":   item.expiry.Format(time.RFC3339),
			"expired":  fmt.Sprintf("%v", isExpired),
		})
	}

	info["count"] = len(items)
	info["items"] = items
	info["ttl_minutes"] = fmt.Sprintf("%.0f", XueqiuCookieCacheTTL.Minutes())

	return info
}

func FetchXueqiuCookiesViaChromedp(browserPath string, timeout time.Duration, pageURL string) (cookieHeader string, err error) {
	return fetchXueqiuCookiesViaChromedp(browserPath, timeout, pageURL)
}

func fetchXueqiuCookiesViaChromedp(browserPath string, timeout time.Duration, pageURL string) (cookieHeader string, err error) {
	browserPath = strings.TrimSpace(browserPath)
	if browserPath == "" {
		browserPath, _ = CheckBrowser()
		if browserPath == "" {
			return "", fmt.Errorf("chromedp: 未配置浏览器路径且未检测到系统浏览器 (Edge/Chrome/Firefox)")
		}
		logger.SugaredLogger.Infof("chromedp: 自动检测到浏览器路径：%s", browserPath)
	}

	now := time.Now()
	urlCacheKey := getURLCacheKey(pageURL)
	cacheKey := browserPath + "||" + urlCacheKey

	xueqiuCookieCache.mu.Lock()
	if item, ok := xueqiuCookieCache.items[cacheKey]; ok && now.Before(item.expiry) {
		xueqiuCookieCache.mu.Unlock()
		return item.header, nil
	}
	xueqiuCookieCache.mu.Unlock()

	h, err := xueqiuCookiesViaChromedpOnce(browserPath, timeout, pageURL)
	if err != nil {
		return "", err
	}

	xueqiuCookieCache.mu.Lock()
	xueqiuCookieCache.items[cacheKey] = &cookieCacheItem{
		header: h,
		expiry: now.Add(XueqiuCookieCacheTTL),
	}
	xueqiuCookieCache.mu.Unlock()

	return h, nil
}

func xueqiuCookiesViaChromedpOnce(browserPath string, timeout time.Duration, pageURL string) (cookieHeader string, err error) {
	if timeout < xueqiuCookieChromedpMinTimeout {
		timeout = xueqiuCookieChromedpMinTimeout
	}

	parent, cancelParent := context.WithTimeout(context.Background(), timeout)
	defer cancelParent()

	opts := append(
		chromedp.DefaultExecAllocatorOptions[:],
		chromedp.Flag("disable-extensions", true),
		chromedp.Flag("disable-extensions-except", ""),
		chromedp.Flag("disable-extensions-file-access-check", true),
		chromedp.Flag("disable-infobars", true),
		chromedp.Flag("disable-dev-shm-usage", true),
		chromedp.Flag("disable-popup-blocking", true),
		chromedp.Flag("blink-settings", "imagesEnabled=false"),
		chromedp.UserAgent(getRandomUA()),
		chromedp.Flag("disable-blink-features", "AutomationControlled"),
		chromedp.Flag("enable-features", "NetworkService,NetworkServiceInProcess"),
		chromedp.Flag("disable-gpu", true),
		chromedp.Flag("no-sandbox", true),
		chromedp.Flag("disable-webgl", true),
		chromedp.Flag("headless", "new"),
		chromedp.WindowSize(1920, 1080),
	)

	allocCtx, cancelAlloc := chromedp.NewExecAllocator(parent, opts...)
	defer cancelAlloc()

	ctx, cancelCtx := chromedp.NewContext(allocCtx,
		chromedp.WithLogf(logger.SugaredLogger.Infof),
		chromedp.WithErrorf(logger.SugaredLogger.Errorf),
	)
	defer cancelCtx()

	var cookies []*network.Cookie
	err = chromedp.Run(ctx,
		chromedp.ActionFunc(func(actx context.Context) error {
			return network.Enable().Do(actx)
		}),
		chromedp.Navigate(xueqiuHomePage),
		chromedp.WaitReady("body", chromedp.ByQuery),
		chromedp.Sleep(3*time.Second),
		chromedp.Navigate(pageURL),
		chromedp.WaitReady("body", chromedp.ByQuery),
		chromedp.Sleep(3*time.Second),
		chromedp.ActionFunc(func(actx context.Context) error {
			var inner error
			cookies, inner = network.GetCookies().WithURLs([]string{
				pageURL,
			}).Do(actx)
			return inner
		}),
	)
	if err != nil {
		return "", err
	}
	if len(cookies) == 0 {
		return "", nil
	}
	var b strings.Builder
	first := true
	for _, c := range cookies {
		if c == nil || c.Name == "" {
			continue
		}
		if !first {
			b.WriteString("; ")
		}
		first = false
		b.WriteString(c.Name)
		b.WriteByte('=')
		b.WriteString(c.Value)
	}
	return b.String(), nil
}
