package data

import "time"

func init() {
	registerToolHandler("GetCurrentTime", handleGetCurrentTime)
}

func handleGetCurrentTime(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	now := time.Now()
	weekday := weekdayCN(now.Weekday())
	content := "当前本地时间是：" + now.Format("2006-01-02 15:04:05") + " " + weekday

	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：GetCurrentTime\r\n```\r\n",
		"time":              now.Format(time.DateTime),
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

func WeekdayCN(wd time.Weekday) string {
	names := []string{"星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"}
	return names[wd]
}

func weekdayCN(wd time.Weekday) string {
	return WeekdayCN(wd)
}
