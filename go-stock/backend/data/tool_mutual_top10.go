package data

import (
	"go-stock/backend/util"
	"time"

	"github.com/tidwall/gjson"
)

func init() {
	registerToolHandler("GetMutualTop10Deal", handleGetMutualTop10Deal)
}

// mutualTypeName 将 MUTUAL_TYPE 代码翻译为中文名称
// 001=沪股通十大成交股, 002=港股通(沪)十大成交股, 003=深股通十大成交股, 004=港股通(深)十大成交股
func mutualTypeName(code string) string {
	switch code {
	case "001":
		return "沪股通十大成交股"
	case "002":
		return "港股通(沪)十大成交股"
	case "003":
		return "深股通十大成交股"
	case "004":
		return "港股通(深)十大成交股"
	default:
		return code
	}
}

// handleGetMutualTop10Deal 处理 GetMutualTop10Deal 工具调用
// 根据互联互通类型（沪股通/深股通/港股通）和交易日期获取十大成交股列表
func handleGetMutualTop10Deal(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	mutualType := gjson.Get(funcArguments, "mutualType").String()
	tradeDate := gjson.Get(funcArguments, "tradeDate").String()
	page := gjson.Get(funcArguments, "page").Int()
	pageSize := gjson.Get(funcArguments, "pageSize").Int()

	if page <= 0 {
		page = 1
	}
	if pageSize <= 0 {
		pageSize = 10
	}

	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：GetMutualTop10Deal，\n参数：" + funcArguments + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	res := NewStockDataApi().GetMutualTop10Deal(mutualType, tradeDate, int(page), int(pageSize))
	if res == nil || !res.Success || res.Code != 0 {
		//logger.SugaredLogger.Errorf("GetMutualTop10Deal api error, code:%d, msg:%s", res.Code, res.Message)
		appendToolMessages(
			ctx.Messages,
			ctx.CurrentAIContent.String(),
			ctx.ReasoningContentText.String(),
			ctx.CurrentCallID,
			ctx.FuncName,
			funcArguments,
			"获取互联互通十大成交股数据失败，请稍后重试。",
		)
		return nil
	}

	title := mutualTypeName(mutualType) + " " + tradeDate
	md := util.MarkdownTableWithTitle(title, res.Result.Data)
	//logger.SugaredLogger.Infof("GetMutualTop10Deal page:%s pageSize:%s\n%s",
	//	convertor.ToString(page),
	//	convertor.ToString(pageSize),
	//	md,
	//)

	appendToolMessages(
		ctx.Messages,
		ctx.CurrentAIContent.String(),
		ctx.ReasoningContentText.String(),
		ctx.CurrentCallID,
		ctx.FuncName,
		funcArguments,
		md,
	)

	return nil
}
