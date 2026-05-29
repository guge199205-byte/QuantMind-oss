package data

import (
	"fmt"
	"go-stock/backend/logger"
	"strings"
	"time"

	fakeUserAgent "github.com/lib4u/fake-useragent"
)

func init() {
	registerToolHandler("GetMarketData", handleGetMarketData)
}

// APIResponse API响应结构
type APIResponse struct {
	Code int     `json:"code"`
	Msg  string  `json:"msg"`
	Data APIData `json:"data"`
}

// APIData API数据结构
type APIData struct {
	IndexQuote    []APIIndexQuote `json:"index_quote"`
	UpDownDis     APIUpDownDis    `json:"up_down_dis"`
	PurchaseToday []APIPurchase   `json:"purchase_today"`
}

// APIIndexQuote API指数行情结构
type APIIndexQuote struct {
	SecuCode string  `json:"secu_code" md:"指数代码"`
	SecuName string  `json:"secu_name" md:"指数名称"`
	LastPx   float64 `json:"last_px" md:"最新价格"`
	Change   float64 `json:"change" md:"涨跌"`
	ChangePx float64 `json:"change_px" md:"涨跌点数"`
	UpNum    int     `json:"up_num" md:"上涨家数"`
	DownNum  int     `json:"down_num" md:"下跌家数"`
	FlatNum  int     `json:"flat_num" md:"平盘家数"`
}

// APIUpDownDis API涨跌分布结构
type APIUpDownDis struct {
	UpNum       int     `json:"up_num" md:"涨停家数"`
	DownNum     int     `json:"down_num" md:"跌停家数"`
	AverageRise float64 `json:"average_rise" md:"平均涨幅"`
	RiseNum     int     `json:"rise_num" md:"上涨家数总计"`
	FallNum     int     `json:"fall_num" md:"下跌家数总计"`
	Down10      int     `json:"down_10" md:"跌幅8%~10%家数"`
	Down8       int     `json:"down_8" md:"跌幅6%~8%家数"`
	Down6       int     `json:"down_6" md:"跌幅4%~6%家数"`
	Down4       int     `json:"down_4" md:"跌幅2%~4%家数"`
	Down2       int     `json:"down_2" md:"跌幅0%~2%家数"`
	FlatNum     int     `json:"flat_num" md:"平盘家数"`
	Up2         int     `json:"up_2" md:"涨幅0%~2%家数"`
	Up4         int     `json:"up_4" md:"涨幅2%~4%家数"`
	Up6         int     `json:"up_6" md:"涨幅4%~6%家数"`
	Up8         int     `json:"up_8" md:"涨幅6%~8%家数"`
	Up10        int     `json:"up_10" md:"涨幅8%~10%家数"`
	SuspendNum  int     `json:"suspend_num" md:"停牌家数"`
	Status      bool    `json:"status" md:"状态"`
}

// APIPurchase API今日申购结构
type APIPurchase struct {
	SecuCode     string   `json:"secu_code"`
	SecuName     string   `json:"secu_name"`
	SecuCodeFull string   `json:"SecuCode"`
	IPOPrice     float64  `json:"ipo_price"`
	IPOPE        float64  `json:"ipo_pe"`
	AllotMax     int      `json:"allot_max"`
	LotRate      *float64 `json:"lot_rate"`
}

// handleGetMarketData 处理 GetMarketData 工具调用
func handleGetMarketData(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	// 调用实际的API获取市场数据
	client := SharedHTTPClient
	apiURL := "https://x-quote.cls.cn/quote/index/home?app=CailianpressWeb&os=web&sv=8.4.6"

	// 获取随机User-Agent
	uaGen, err := fakeUserAgent.New()
	if err != nil {
		// 如果获取失败，使用默认User-Agent
		uaGen, _ = fakeUserAgent.New()
	}
	ua := uaGen.GetRandom()

	var apiResp APIResponse
	resp, err := client.R().
		SetHeader("User-Agent", ua).
		SetResult(&apiResp).
		Get(apiURL)

	if err != nil {
		return fmt.Errorf("调用API失败: %v", err)
	}

	if resp.StatusCode() != 200 || apiResp.Code != 200 {
		return fmt.Errorf("API返回错误: 状态码=%d, 错误信息=%s", resp.StatusCode(), apiResp.Msg)
	}

	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：GetMarketData\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	// 构建markdown格式的输出
	content := strings.Builder{}
	content.WriteString("# 市场行情数据\r\n\r\n")

	// 1. 指数行情部分
	content.WriteString("## 指数行情\r\n\r\n")
	content.WriteString("| 指数代码 | 指数名称 | 最新价格 | 涨跌(%) | 涨跌点数 | 上涨家数 | 下跌家数 | 平盘家数 |\r\n")
	content.WriteString("|----------|----------|----------|---------|----------|----------|----------|----------|\r\n")
	for _, index := range apiResp.Data.IndexQuote {
		content.WriteString(fmt.Sprintf("| %s | %s | %.2f | %.2f | %.2f | %d | %d | %d |\r\n",
			index.SecuCode, index.SecuName, index.LastPx, index.Change*100, index.ChangePx,
			index.UpNum, index.DownNum, index.FlatNum))
	}

	// 2. 涨跌分布部分
	content.WriteString("\r\n## 涨跌分布\r\n\r\n")
	content.WriteString("| 涨停家数 | 跌停家数 | 平均涨幅(%) | 上涨家数总计 | 下跌家数总计 |\r\n")
	content.WriteString("|----------|----------|-------------|--------------|--------------|\r\n")
	content.WriteString(fmt.Sprintf("| %d | %d | %.2f | %d | %d |\r\n",
		apiResp.Data.UpDownDis.UpNum, apiResp.Data.UpDownDis.DownNum, apiResp.Data.UpDownDis.AverageRise*100,
		apiResp.Data.UpDownDis.RiseNum, apiResp.Data.UpDownDis.FallNum))

	content.WriteString("\r\n### 跌幅分布\r\n\r\n")
	content.WriteString("| 跌幅8%~10% | 跌幅6%~8% | 跌幅4%~6% | 跌幅2%~4% | 跌幅0%~2% |\r\n")
	content.WriteString("|-----------|-----------|-----------|-----------|-----------|\r\n")
	content.WriteString(fmt.Sprintf("| %d | %d | %d | %d | %d |\r\n",
		apiResp.Data.UpDownDis.Down10, apiResp.Data.UpDownDis.Down8, apiResp.Data.UpDownDis.Down6,
		apiResp.Data.UpDownDis.Down4, apiResp.Data.UpDownDis.Down2))

	content.WriteString("\r\n### 涨幅分布\r\n\r\n")
	content.WriteString("| 涨幅0%~2% | 涨幅2%~4% | 涨幅4%~6% | 涨幅6%~8% | 涨幅8%~10% |\r\n")
	content.WriteString("|-----------|-----------|-----------|-----------|------------|\r\n")
	content.WriteString(fmt.Sprintf("| %d | %d | %d | %d | %d |\r\n",
		apiResp.Data.UpDownDis.Up2, apiResp.Data.UpDownDis.Up4, apiResp.Data.UpDownDis.Up6,
		apiResp.Data.UpDownDis.Up8, apiResp.Data.UpDownDis.Up10))

	content.WriteString("\r\n### 其他统计\r\n\r\n")
	content.WriteString(fmt.Sprintf("- 平盘家数: %d\r\n", apiResp.Data.UpDownDis.FlatNum))
	content.WriteString(fmt.Sprintf("- 停牌家数: %d\r\n", apiResp.Data.UpDownDis.SuspendNum))

	// 3. 今日申购部分
	content.WriteString("\r\n## 今日申购\r\n\r\n")
	if len(apiResp.Data.PurchaseToday) > 0 {
		content.WriteString("| 股票代码 | 股票名称 | 申购价格 | 申购PE | 最大申购数量 | 中签率(%) |\r\n")
		content.WriteString("|----------|----------|----------|--------|--------------|-----------|\r\n")
		for _, purchase := range apiResp.Data.PurchaseToday {
			lotRate := "-"
			if purchase.LotRate != nil {
				lotRate = fmt.Sprintf("%.2f", *purchase.LotRate)
			}
			content.WriteString(fmt.Sprintf("| %s | %s | %.2f | %.2f | %d | %s |\r\n",
				purchase.SecuCode, purchase.SecuName, purchase.IPOPrice, purchase.IPOPE,
				purchase.AllotMax, lotRate))
		}
	} else {
		content.WriteString("今日无新股申购\r\n")
	}

	logger.SugaredLogger.Debug("%s", content.String())

	appendToolMessages(
		ctx.Messages,
		ctx.CurrentAIContent.String(),
		ctx.ReasoningContentText.String(),
		ctx.CurrentCallID,
		ctx.FuncName,
		funcArguments,
		content.String(),
	)

	return nil
}
