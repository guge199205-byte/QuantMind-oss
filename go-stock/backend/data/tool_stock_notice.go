package data

import (
	"strings"
	"time"

	"go-stock/backend/util"

	"github.com/duke-git/lancet/v2/convertor"
	"github.com/tidwall/gjson"
)

func init() {
	registerToolHandler("StockNotice", handleStockNotice)
}

// handleStockNotice 处理 StockNotice 工具调用：获取上市公司公告列表
func handleStockNotice(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	stockList := strings.TrimSpace(gjson.Get(funcArguments, "stock_list").String())
	if stockList == "" {
		appendToolMessages(
			ctx.Messages,
			ctx.CurrentAIContent.String(),
			ctx.ReasoningContentText.String(),
			ctx.CurrentCallID,
			ctx.FuncName,
			funcArguments,
			"参数 stock_list 不能为空，请传入股票代码，多只用英文逗号分隔。",
		)
		return nil
	}

	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：StockNotice，参数：" + stockList + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	res := NewMarketNewsApi().StockNotice(stockList)
	if len(res) == 0 {
		appendToolMessages(
			ctx.Messages,
			ctx.CurrentAIContent.String(),
			ctx.ReasoningContentText.String(),
			ctx.CurrentCallID,
			ctx.FuncName,
			funcArguments,
			"未查询到相关上市公司公告。",
		)
		return nil
	}

	// 转为可表格化的结构：东方财富接口返回的 list 中每项为 map，字段名多为驼峰
	type row struct {
		Title      string `md:"公告标题"`
		NoticeDate string `md:"公告日期"`
		ColumnName string `md:"公告类型"`
	}
	var rows []row
	for _, a := range res {
		m, ok := a.(map[string]any)
		if !ok {
			continue
		}
		if m["columns"].([]any) != nil && len(m["columns"].([]any)) > 0 {
			columns := m["columns"].([]any)[0].(map[string]any)
			rows = append(rows, row{
				Title:      convertor.ToString(m["title"]),
				NoticeDate: convertor.ToString(m["notice_date"]),
				ColumnName: convertor.ToString(columns["column_name"]),
			})
		} else {
			rows = append(rows, row{
				Title:      convertor.ToString(m["title"]),
				NoticeDate: convertor.ToString(m["notice_date"]),
			})
		}
	}
	md := util.MarkdownTableWithTitle("上市公司公告", rows)
	//logger.SugaredLogger.Infof("StockNotice stock_list:%s count:%d", stockList, len(rows))

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
