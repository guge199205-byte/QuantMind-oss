package data

import (
	"strings"
	"time"
)

func init() {
	registerToolHandler("GetStockResearchReport", handleGetStockResearchReport)
}

func buildStockResearchReportMarkdown(stockCode string) string {
	news := NewMarketNewsApi()
	res := news.StockResearchReport(stockCode, 30)
	var md strings.Builder
	for _, a := range res {
		d, ok := a.(map[string]any)
		if !ok {
			continue
		}
		infoCode, _ := d["infoCode"].(string)
		md.WriteString(news.GetIndustryReportInfo(infoCode))
	}
	out := strings.TrimSpace(md.String())
	if out == "" {
		return stockCode + "：未查询到相关研究报告。"
	}
	return "### " + stockCode + " 研究报告\r\n" + out
}

// handleGetStockResearchReport 处理 GetStockResearchReport 工具调用
func handleGetStockResearchReport(o *OpenAi, funcArguments string, ctx *ToolContext) error {
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
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：GetStockResearchReport，\n参数：" + strings.Join(codes, ",") + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	content := parallelStockToolSections(codes, buildStockResearchReportMarkdown)

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
