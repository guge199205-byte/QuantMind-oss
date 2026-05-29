//go:build linux
// +build linux

package data

import (
	"go-stock/backend/logger"
	"os"
	"os/exec"
	"strings"
)

// findBrowser 在 Linux 上查找浏览器可执行文件
func findBrowser(paths []string) (string, bool) {
	for _, path := range paths {
		// 检查是否是绝对路径
		if strings.HasPrefix(path, "/") {
			_, err := os.Stat(path)
			if err == nil {
				return path, true
			}
		} else {
			// 在 PATH 中查找
			execPath, err := exec.LookPath(path)
			if err == nil {
				return execPath, true
			}
		}
	}
	return "", false
}

// CheckChrome 检查 Linux 是否安装了 Chrome 浏览器
func CheckChrome() (string, bool) {
	locations := []string{
		// Google Chrome
		"/usr/bin/google-chrome",
		"/usr/bin/google-chrome-stable",
		"/usr/bin/google-chrome-beta",
		"/usr/bin/google-chrome-unstable",
		"/usr/local/bin/google-chrome",
		// Chromium
		"/usr/bin/chromium",
		"/usr/bin/chromium-browser",
		"/snap/bin/chromium",
		"/usr/local/bin/chromium",
		"/usr/local/bin/chromium-browser",
		// Gentoo
		"/usr/bin/chromium-browser",
		// Arch Linux
		"/usr/bin/chromium",
	}
	return findBrowser(locations)
}

// CheckEdge 检查 Linux 是否安装了 Edge 浏览器
func CheckEdge() (string, bool) {
	locations := []string{
		"/usr/bin/microsoft-edge",
		"/usr/bin/microsoft-edge-stable",
		"/usr/bin/microsoft-edge-beta",
		"/usr/bin/microsoft-edge-dev",
		"/snap/bin/microsoft-edge",
		"/usr/local/bin/microsoft-edge",
	}
	return findBrowser(locations)
}

// CheckFirefox 检查 Linux 是否安装了 Firefox 浏览器
func CheckFirefox() (string, bool) {
	locations := []string{
		"/usr/bin/firefox",
		"/usr/bin/firefox-esr",
		"/snap/bin/firefox",
		"/usr/local/bin/firefox",
		"/usr/bin/firefox-developer-edition",
		"/usr/bin/firefox-nightly",
		// Flatpak
		"firefox",
	}
	return findBrowser(locations)
}

// CheckSafari 检查 Linux 是否安装了 Safari 浏览器（Linux 上通常没有 Safari）
func CheckSafari() (string, bool) {
	// Safari 是 macOS 专属，Linux 上基本不存在
	// 但为了完整性保留检测
	locations := []string{
		"/usr/bin/safari",
		"/usr/local/bin/safari",
	}
	return findBrowser(locations)
}

// CheckBrave 检查 Linux 是否安装了 Brave 浏览器
func CheckBrave() (string, bool) {
	locations := []string{
		"/usr/bin/brave",
		"/usr/bin/brave-browser",
		"/usr/bin/brave-browser-stable",
		"/snap/bin/brave",
		"/usr/local/bin/brave",
		"/usr/local/bin/brave-browser",
	}
	return findBrowser(locations)
}

// CheckOpera 检查 Linux 是否安装了 Opera 浏览器
func CheckOpera() (string, bool) {
	locations := []string{
		"/usr/bin/opera",
		"/usr/bin/opera-stable",
		"/usr/bin/opera-beta",
		"/usr/bin/opera-developer",
		"/snap/bin/opera",
		"/usr/local/bin/opera",
	}
	return findBrowser(locations)
}

// CheckVivaldi 检查 Linux 是否安装了 Vivaldi 浏览器
func CheckVivaldi() (string, bool) {
	locations := []string{
		"/usr/bin/vivaldi",
		"/usr/bin/vivaldi-stable",
		"/usr/bin/vivaldi-snapshot",
		"/snap/bin/vivaldi",
		"/usr/local/bin/vivaldi",
	}
	return findBrowser(locations)
}

// CheckBrowser 在 Linux 上按优先级检查浏览器
// 优先级：Edge > Chrome/Chromium > Brave > Vivaldi > Opera > Safari > Firefox
// 基于 Chromium 的浏览器优先，因为 chromedp 对 Chromium 内核支持最好
func CheckBrowser() (string, bool) {
	// 1. 优先检测 Edge（基于 Chromium，兼容性好）
	if path, ok := CheckEdge(); ok {
		logger.SugaredLogger.Infof("检测到 Edge 浏览器：%s", path)
		return path, true
	}
	// 2. 检测 Chrome/Chromium
	if path, ok := CheckChrome(); ok {
		logger.SugaredLogger.Infof("检测到 Chrome/Chromium 浏览器：%s", path)
		return path, true
	}
	// 3. 检测 Brave（基于 Chromium）
	if path, ok := CheckBrave(); ok {
		logger.SugaredLogger.Infof("检测到 Brave 浏览器：%s", path)
		return path, true
	}
	// 4. 检测 Vivaldi（基于 Chromium）
	if path, ok := CheckVivaldi(); ok {
		logger.SugaredLogger.Infof("检测到 Vivaldi 浏览器：%s", path)
		return path, true
	}
	// 5. 检测 Opera（基于 Chromium）
	if path, ok := CheckOpera(); ok {
		logger.SugaredLogger.Infof("检测到 Opera 浏览器：%s", path)
		return path, true
	}
	// 6. 检测 Safari（Linux 上很少见）
	if path, ok := CheckSafari(); ok {
		logger.SugaredLogger.Infof("检测到 Safari 浏览器：%s", path)
		return path, true
	}
	// 7. 最后检测 Firefox
	if path, ok := CheckFirefox(); ok {
		logger.SugaredLogger.Infof("检测到 Firefox 浏览器：%s", path)
		return path, true
	}
	return "", false
}
