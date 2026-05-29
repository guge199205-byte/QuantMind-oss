package data

import (
	"time"

	"github.com/duke-git/lancet/v2/random"
	"github.com/tidwall/gjson"
)

func init() {
	registerToolHandler("SearchBk", handleSearchBk)
}

// handleSearchBk 处理 SearchBk 工具调用
func handleSearchBk(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	words := gjson.Get(funcArguments, "words").String()

	// 通知前端开始调用工具
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：SearchBk，\n参数：" + words + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	res := NewSearchStockApi(words).SearchBk(random.RandInt(50, 120))
	content := thsResultToMarkdown(res, "工具筛选出的相关板块/概念数据")
	//logger.SugaredLogger.Infof("SearchBk:words:%s  --> \n%s", words, content)

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
