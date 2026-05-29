//go:build windows
// +build windows

package data

import (
	"go-stock/backend/logger"

	"golang.org/x/sys/windows/registry"
)

// CheckChrome 在 Windows 系统上检查谷歌浏览器是否安装
func CheckChrome() (string, bool) {
	key, err := registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe`, registry.QUERY_VALUE)
	if err != nil {
		// 尝试在 WOW6432Node 中查找（适用于 64 位系统上的 32 位程序）
		key, err = registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe`, registry.QUERY_VALUE)
		if err != nil {
			return "", false
		}
		defer key.Close()
	}
	defer key.Close()
	path, _, err := key.GetStringValue("Path")
	//logger.SugaredLogger.Infof("Chrome 安装路径：%s", path)
	if err != nil {
		return "", false
	}
	return path + "\\chrome.exe", true
}

// CheckEdge 在 Windows 系统上检查 Edge 浏览器是否安装
func CheckEdge() (string, bool) {
	key, err := registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe`, registry.QUERY_VALUE)
	if err != nil {
		// 尝试在 WOW6432Node 中查找（适用于 64 位系统上的 32 位程序）
		key, err = registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\msedge.exe`, registry.QUERY_VALUE)
		if err != nil {
			return "", false
		}
		defer key.Close()
	}
	defer key.Close()
	path, _, err := key.GetStringValue("Path")
	//logger.SugaredLogger.Infof("Edge 安装路径：%s", path)
	if err != nil {
		return "", false
	}
	return path + "\\msedge.exe", true
}

// CheckFirefox 在 Windows 系统上检查 Firefox 浏览器是否安装
func CheckFirefox() (string, bool) {
	key, err := registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe`, registry.QUERY_VALUE)
	if err != nil {
		// 尝试在 WOW6432Node 中查找（适用于 64 位系统上的 32 位程序）
		key, err = registry.OpenKey(registry.LOCAL_MACHINE, `SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\firefox.exe`, registry.QUERY_VALUE)
		if err != nil {
			return "", false
		}
		defer key.Close()
	}
	defer key.Close()
	path, _, err := key.GetStringValue("Path")
	//logger.SugaredLogger.Infof("Firefox 安装路径：%s", path)
	if err != nil {
		return "", false
	}
	return path + "\\firefox.exe", true
}

// CheckBrowser 在 Windows 系统上按优先级检查浏览器：Edge > Chrome > Firefox
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
	// 最后检测 Firefox
	if path, ok := CheckFirefox(); ok {
		logger.SugaredLogger.Infof("检测到 Firefox 浏览器：%s", path)
		return path, true
	}
	return "", false
}
