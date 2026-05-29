package tools

import (
	"github.com/duke-git/lancet/v2/strutil"
	"strings"
)

// @Author spark
// @Date 2025/8/5 17:20
// @Desc
//-----------------------------------------------------------------------------------

func GetStockCode(dcCode string) string {
	if strutil.ContainsAny(dcCode, []string{"."}) {
		sp := strings.Split(dcCode, ".")
		return strings.ToLower(sp[1] + sp[0])
	}

	//北京证券交易所	8（83、87、88 等）	创新型中小企业（专精特新为主）
	//上海证券交易所	6（60、688 等）	大盘蓝筹、科创板（高新技术）
	//深圳证券交易所	0、3（000、002、30 等）	中小盘、创业板（成长型创新企业）
	switch dcCode[0:1] {
	case "8":
		return "bj" + dcCode
	case "9":
		return "bj" + dcCode
	case "6":
		return "sh" + dcCode
	case "0":
		return "sz" + dcCode
	case "3":
		return "sz" + dcCode
	}
	return dcCode
}
