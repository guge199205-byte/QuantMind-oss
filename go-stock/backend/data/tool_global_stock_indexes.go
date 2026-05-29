package data

import "time"

func init() {
	registerToolHandler("GlobalStockIndexesReadable", handleGlobalStockIndexesReadable)
}

// handleGlobalStockIndexesReadable 处理 GlobalStockIndexesReadable 工具调用
func handleGlobalStockIndexesReadable(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：GlobalStockIndexesReadable\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	content := NewMarketNewsApi().GlobalStockIndexesReadable(30)
	if content == "" {
		content = "暂无全球指数数据。"
	}

	appendToolMessages(
		ctx.Messages,
		ctx.CurrentAIContent.String(),
		ctx.ReasoningContentText.String(),
		ctx.CurrentCallID,
		ctx.FuncName,
		funcArguments,
		content,
	)

	return nil
}
