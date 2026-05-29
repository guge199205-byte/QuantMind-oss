package data

import (
	"time"

	"go-stock/backend/util"

	"github.com/duke-git/lancet/v2/convertor"
	"github.com/tidwall/gjson"
)

func init() {
	registerToolHandler("HotStrategyTable", handleHotStrategyTable)
	registerToolHandler("HotStockTable", handleHotStockTable)
	registerToolHandler("GetStockMoneyData", handleGetStockMoneyData)
}

// handleHotStrategyTable 处理 HotStrategyTable 工具调用
func handleHotStrategyTable(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：HotStrategyTable，\n参数：" + funcArguments + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	table := NewSearchStockApi("").HotStrategyTable()
	//logger.SugaredLogger.Infof("%s", table)

	appendToolMessages(
		ctx.Messages,
		ctx.CurrentAIContent.String(),
		ctx.ReasoningContentText.String(),
		ctx.CurrentCallID,
		ctx.FuncName,
		funcArguments,
		table,
	)

	return nil
}

// handleHotStockTable 处理 HotStockTable 工具调用
func handleHotStockTable(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	pageSize := gjson.Get(funcArguments, "pageSize").String()

	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：HotStockTable，\n参数：" + funcArguments + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	pageSizeNum, convErr := convertor.ToInt(pageSize)
	if convErr != nil {
		pageSizeNum = 50
	}

	res := NewMarketNewsApi().XUEQIUHotStock(int(pageSizeNum), "10")
	md := util.MarkdownTableWithTitle("当前热门股票排名", res)
	//logger.SugaredLogger.Infof("pageSize:%s HotStockTable:\n %s", pageSize, md)

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

// handleGetStockMoneyData 处理 GetStockMoneyData 工具调用
func handleGetStockMoneyData(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：GetStockMoneyData，\n参数：" + funcArguments + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	res := NewStockDataApi().GetStockMoneyData()
	md := util.MarkdownTableWithTitle("今日个股资金流向Top50", res.Data.Diff)
	//logger.SugaredLogger.Infof("%s", md)

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
