package data

import (
	"fmt"
	"strings"
	"time"

	"github.com/tidwall/gjson"
)

func init() {
	registerToolHandler("GetWallstreetcnLives", handleGetWallstreetcnLives)
	registerToolHandler("GetWallstreetcnMarketReal", handleGetWallstreetcnMarketReal)
	registerToolHandler("GetWallstreetcnKline", handleGetWallstreetcnKline)
	registerToolHandler("GetWallstreetcnCalendar", handleGetWallstreetcnCalendar)
}

func handleGetWallstreetcnLives(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": fmt.Sprintf("\r\n```\r\n🔧 开始调用工具：GetWallstreetcnLives，\n参数：%s\r\n```\r\n", funcArguments),
		"time":              time.Now().Format(time.DateTime),
	}

	channel := gjson.Get(funcArguments, "channel").String()
	limit := int(gjson.Get(funcArguments, "limit").Int())
	if channel == "" {
		channel = "global-channel"
	}
	if limit <= 0 {
		limit = 20
	}

	res := NewWallstreetcnApi().GetLivesReadable(channel, limit)

	appendToolMessages(
		ctx.Messages,
		ctx.CurrentAIContent.String(),
		ctx.ReasoningContentText.String(),
		ctx.CurrentCallID,
		ctx.FuncName,
		funcArguments,
		res,
	)
	return nil
}

func handleGetWallstreetcnMarketReal(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": fmt.Sprintf("\r\n```\r\n🔧 开始调用工具：GetWallstreetcnMarketReal，\n参数：%s\r\n```\r\n", funcArguments),
		"time":              time.Now().Format(time.DateTime),
	}

	prodCodesStr := gjson.Get(funcArguments, "prodCodes").String()
	var prodCodes []string
	if prodCodesStr != "" {
		prodCodes = strings.Split(prodCodesStr, ",")
	}

	res := NewWallstreetcnApi().GetMarketRealReadable(prodCodes)

	appendToolMessages(
		ctx.Messages,
		ctx.CurrentAIContent.String(),
		ctx.ReasoningContentText.String(),
		ctx.CurrentCallID,
		ctx.FuncName,
		funcArguments,
		res,
	)
	return nil
}

func handleGetWallstreetcnKline(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": fmt.Sprintf("\r\n```\r\n🔧 开始调用工具：GetWallstreetcnKline，\n参数：%s\r\n```\r\n", funcArguments),
		"time":              time.Now().Format(time.DateTime),
	}

	prodCode := gjson.Get(funcArguments, "prodCode").String()
	periodType := int(gjson.Get(funcArguments, "periodType").Int())
	limit := int(gjson.Get(funcArguments, "limit").Int())
	if prodCode == "" {
		prodCode = "XAUUSD.OTC"
	}
	if periodType <= 0 {
		periodType = 300
	}
	if limit <= 0 {
		limit = 50
	}

	res := NewWallstreetcnApi().GetKlineReadable(prodCode, periodType, limit)

	appendToolMessages(
		ctx.Messages,
		ctx.CurrentAIContent.String(),
		ctx.ReasoningContentText.String(),
		ctx.CurrentCallID,
		ctx.FuncName,
		funcArguments,
		res,
	)
	return nil
}

func handleGetWallstreetcnCalendar(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": fmt.Sprintf("\r\n```\r\n🔧 开始调用工具：GetWallstreetcnCalendar，\n参数：%s\r\n```\r\n", funcArguments),
		"time":              time.Now().Format(time.DateTime),
	}

	days := int(gjson.Get(funcArguments, "days").Int())
	if days <= 0 {
		days = 3
	}

	res := NewWallstreetcnApi().GetCalendarReadable(days)

	appendToolMessages(
		ctx.Messages,
		ctx.CurrentAIContent.String(),
		ctx.ReasoningContentText.String(),
		ctx.CurrentCallID,
		ctx.FuncName,
		funcArguments,
		res,
	)
	return nil
}
