package data

import (
	"go-stock/backend/util"
	"time"

	"github.com/duke-git/lancet/v2/convertor"
	"github.com/tidwall/gjson"
)

func init() {
	registerToolHandler("InteractiveAnswer", handleInteractiveAnswer)
}

// handleInteractiveAnswer 处理 InteractiveAnswer 工具调用
func handleInteractiveAnswer(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	page := gjson.Get(funcArguments, "page").String()
	pageSize := gjson.Get(funcArguments, "pageSize").String()
	keyWord := gjson.Get(funcArguments, "keyWord").String()

	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：InteractiveAnswer，\n参数：" + page + "," + pageSize + "," + keyWord + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	pageNo, convErr := convertor.ToInt(page)
	if convErr != nil {
		pageNo = 1
	}
	pageSizeNum, convErr := convertor.ToInt(pageSize)
	if convErr != nil {
		pageSizeNum = 50
	}

	datas := NewMarketNewsApi().InteractiveAnswer(int(pageNo), int(pageSizeNum), keyWord)
	content := util.MarkdownTableWithTitle("投资互动数据", datas.Results)
	//logger.SugaredLogger.Infof("InteractiveAnswer=\n%s", content)

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
