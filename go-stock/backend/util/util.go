package util

import uaFake "github.com/lib4u/fake-useragent"

// @Author spark
// @Date 2026/4/10 9:02
// @Desc
//-----------------------------------------------------------------------------------

func GetUserAgent() string {
	ua, _ := uaFake.New()
	if ua != nil {
		randomUA := ua.Filter().Platform("desktop").Get()
		return randomUA
	}
	// 如果库获取失败，返回备用 UA
	return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

}
