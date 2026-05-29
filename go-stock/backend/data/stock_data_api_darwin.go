//go:build darwin
// +build darwin

package data

import (
	"go-stock/backend/logger"
	"os"
)

// CheckChrome 检查 macOS 是否安装了 Chrome 浏览器
func CheckChrome() (string, bool) {
	// 检查 /Applications 目录下是否存在 Chrome
	locations := []string{
		"/Applications/Chromium.app/Contents/MacOS/Chromium",
		"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
	}
	for _, location := range locations {
		_, err := os.Stat(location)
		if err == nil {
			return location, true
		}
	}
	return "", false
}

// CheckEdge 检查 macOS 是否安装了 Edge 浏览器
func CheckEdge() (string, bool) {
	location := "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
	_, err := os.Stat(location)
	if err == nil {
		return location, true
	}
	return "", false
}

// CheckFirefox 检查 macOS 是否安装了 Firefox 浏览器
func CheckFirefox() (string, bool) {
	location := "/Applications/Firefox.app/Contents/MacOS/firefox"
	_, err := os.Stat(location)
	if err == nil {
		return location, true
	}
	return "", false
}

// CheckSafari 检查 macOS 是否安装了 Safari 浏览器（苹果自带浏览器）
func CheckSafari() (string, bool) {
	location := "/Applications/Safari.app/Contents/MacOS/Safari"
	_, err := os.Stat(location)
	if err == nil {
		return location, true
	}
	return "", false
}

// CheckBrowser 在 macOS 上按优先级检查浏览器：Edge > Chrome > Safari > Firefox
func CheckBrowser() (string, bool) {
	// 优先检测 Edge（chromedp 基于 Chromium，Edge 兼容性更好）
	if path, ok := CheckEdge(); ok {
		logger.SugaredLogger.Infof("检测到 Edge 浏览器：%s", path)
		return path, true
	}
	// 其次检测 Chrome
	if path, ok := CheckChrome(); ok {
		logger.SugaredLogger.Infof("检测到 Chrome 浏览器：%s", path)
		return path, true
	}
	// 然后检测 Safari（苹果自带浏览器）
	if path, ok := CheckSafari(); ok {
		logger.SugaredLogger.Infof("检测到 Safari 浏览器：%s", path)
		return path, true
	}
	// 最后检测 Firefox
	if path, ok := CheckFirefox(); ok {
		logger.SugaredLogger.Infof("检测到 Firefox 浏览器：%s", path)
		return path, true
	}
	return "", false
}
