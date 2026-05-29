package data

import (
	"strings"
	"time"

	"go-stock/backend/util"
)

func init() {
	registerToolHandler("GetStockRZRQInfo", handleGetStockRZRQInfo)
}

// handleGetStockRZRQInfo 处理 GetStockRZRQInfo 工具调用：获取融资融券信息
func handleGetStockRZRQInfo(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	codes := parseStockCodesFromToolArgs(funcArguments, "stockCode")
	if len(codes) == 0 {
		appendToolMessages(
			ctx.Messages,
			ctx.CurrentAIContent.String(),
			ctx.ReasoningContentText.String(),
			ctx.CurrentCallID,
			ctx.FuncName,
			funcArguments,
			"参数 stockCode 或 stockCodes 不能为空，请传入股票代码（多只可用英文逗号分隔）。",
		)
		return nil
	}

	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：GetStockRZRQInfo，参数：" + strings.Join(codes, ",") + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	api := NewStockDataApi()
	md := parallelStockToolSections(codes, func(stockCode string) string {
		res := api.GetStockRZRQInfo(stockCode)
		if len(res.Result.Data) == 0 {
			return stockCode + "：未查询到该股票的融资融券数据（可能非两融标的或代码有误）。"
		}
		return util.MarkdownTableWithTitle(stockCode+" 融资融券信息", res.Result.Data)
	})

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
