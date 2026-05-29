package data

import (
	"strconv"
	"strings"
	"time"

	"github.com/tidwall/gjson"

	"go-stock/backend/util"
)

func init() {
	//registerToolHandler("CailianpressWeb", handleCailianpressWeb)
	registerToolHandler("GetSecuritiesCompanyOpinion", handleGetSecuritiesCompanyOpinion)
	registerToolHandler("GetNewsListData", handleGetNewsListData)
}

// handleCailianpressWeb 处理 CailianpressWeb 工具调用
func handleCailianpressWeb(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：CailianpressWeb，\n参数：" + funcArguments + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	searchWords := gjson.Get(funcArguments, "searchWords").String()
	res := NewMarketNewsApi().CailianpressWeb(searchWords)
	md := util.MarkdownTableWithTitle("["+searchWords+"]-新闻资讯", res)
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

// handleGetSecuritiesCompanyOpinion 处理 GetSecuritiesCompanyOpinion 工具调用
func handleGetSecuritiesCompanyOpinion(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：GetSecuritiesCompanyOpinion，\n参数：" + funcArguments + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	startDate := gjson.Get(funcArguments, "startDate").String()
	endDate := gjson.Get(funcArguments, "endDate").String()
	res := NewMarketNewsApi().GetSecuritiesCompanyOpinion(startDate, endDate)
	md := strings.Builder{}
	for _, d := range res.Data {
		md.WriteString(d.OpinionData + "\r\n")
	}
	//logger.SugaredLogger.Infof("%s", md.String())

	appendToolMessages(
		ctx.Messages,
		ctx.CurrentAIContent.String(),
		ctx.ReasoningContentText.String(),
		ctx.CurrentCallID,
		ctx.FuncName,
		funcArguments,
		md.String(),
	)

	return nil
}

// handleGetNewsListData 获取新闻列表数据
func handleGetNewsListData(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：GetNewsListData，\n参数：" + funcArguments + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}
	keyWord := gjson.Get(funcArguments, "keyWord").String()
	startTime := gjson.Get(funcArguments, "startTime").String()
	limit := gjson.Get(funcArguments, "limit").Int()
	page := gjson.Get(funcArguments, "page").Int()
	pageSize := gjson.Get(funcArguments, "pageSize").Int()
	if pageSize <= 0 {
		pageSize = limit
	}
	if pageSize <= 0 {
		pageSize = 20
	}
	if page < 1 {
		page = 1
	}

	parseTime, err := time.Parse(time.DateTime, startTime)
	if err != nil {
		parseTime = time.Now().Add(-time.Hour * 24)
	}
	list, total := NewMarketNewsApi().GetNewsListData(keyWord, parseTime, int(page), int(pageSize))
	md := strings.Builder{}
	md.WriteString("### " + "最近新闻资讯" + "（共 " + strconv.FormatInt(total, 10) + " 条，本页 " + strconv.Itoa(len(*list)) + " 条）\r\n")
	for _, d := range *list {
		md.WriteString(d.DataTime.Format(time.DateTime) + " " + d.Content + "\r\n")
	}
	//logger.SugaredLogger.Infof("%s", md.String())

	appendToolMessages(
		ctx.Messages,
		ctx.CurrentAIContent.String(),
		ctx.ReasoningContentText.String(),
		ctx.CurrentCallID,
		ctx.FuncName,
		funcArguments,
		md.String(),
	)
	return nil
}
