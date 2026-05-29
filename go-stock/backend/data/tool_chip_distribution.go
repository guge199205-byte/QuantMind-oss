package data

import (
	"fmt"
	"strings"
	"time"

	"github.com/tidwall/gjson"
)

func init() {
	registerToolHandler("GetChipDistribution", handleGetChipDistribution)
}

func handleGetChipDistribution(o *OpenAi, funcArguments string, ctx *ToolContext) error {
	days := int(gjson.Get(funcArguments, "days").Int())
	if days <= 0 {
		days = 120
	}
	bins := int(gjson.Get(funcArguments, "bins").Int())
	if bins <= 0 {
		bins = 80
	}
	adjustFlag := strings.TrimSpace(strings.ToLower(gjson.Get(funcArguments, "adjustFlag").String()))
	if adjustFlag != "" && adjustFlag != "qfq" && adjustFlag != "hfq" {
		adjustFlag = "qfq"
	}

	codes := parseStockCodesFromToolArgs(funcArguments, "stockCode")
	if len(codes) == 0 {
		appendToolMessages(ctx.Messages, ctx.CurrentAIContent.String(), ctx.ReasoningContentText.String(),
			ctx.CurrentCallID, ctx.FuncName, funcArguments, "参数 stockCode 或 stockCodes 不能为空，请传入股票代码（多只可用英文逗号分隔）。")
		return nil
	}

	ctx.Ch <- map[string]any{
		"code":              1,
		"question":          ctx.Question,
		"chatId":            ctx.StreamResponseID,
		"model":             ctx.Model,
		"reasoning_content": "\r\n```\r\n🔧 开始调用工具：GetChipDistribution，\n参数：" + funcArguments + "\r\n```\r\n",
		"time":              time.Now().Format(time.DateTime),
	}

	calculator := NewChipDistributionCalculator()

	res := parallelStockToolSections(codes, func(stockCode string) string {
		api := NewEastMoneyKLineApi(GetSettingConfig())
		if !api.ValidateStockCode(stockCode) {
			return stockCode + "：股票代码无效，请使用正确格式（如 000001.SZ、600000.SH、00700.HK）。"
		}

		var kLines *[]KLineData
		if adjustFlag != "" {
			kLines = api.GetKLineData(stockCode, "101", adjustFlag, days)
		} else {
			result := FetchKLineWithFallback(stockCode, "", "101", days, "")
			if result != nil && result.Data != nil {
				kLines = result.Data
			}
		}
		if kLines == nil || len(*kLines) == 0 {
			return stockCode + "：未获取到K线数据，无法计算筹码分布。"
		}

		r, err := calculator.Calculate(stockCode, *kLines, bins)
		if err != nil {
			return stockCode + "：筹码分布计算失败：" + err.Error()
		}

		top := r.TopN(10)
		var sb strings.Builder
		sb.WriteString("### " + stockCode + " 筹码分布（近 " + fmt.Sprintf("%d", r.Days) + " 日）\n\n")
		sb.WriteString(fmt.Sprintf("- 最新收盘：**%.4f**  平均成本：**%.4f**  获利筹码占比：**%.2f%%**\n",
			r.Current, r.AvgCost, r.ProfitRatio*100))
		sb.WriteString(fmt.Sprintf("- 价格区间：%.4f ~ %.4f  分箱：%d\n\n", r.MinPrice, r.MaxPrice, r.Bins))

		if len(top) > 0 {
			sb.WriteString("**筹码峰 Top10（按占比）：**\n\n")
			sb.WriteString("| 序号 | 价位 | 占比(%) |\n|---:|---:|---:|\n")
			for i, b := range top {
				sb.WriteString(fmt.Sprintf("| %d | %.4f | %.3f |\n", i+1, b.Price, b.Ratio*100))
			}
			sb.WriteString("\n")
		}

		// 输出完整分布 JSON，便于前端直接绘制筹码图
		sb.WriteString("```json\n")
		sb.WriteString(r.ToJSON(false))
		sb.WriteString("\n```\n")
		return sb.String()
	})

	appendToolMessages(ctx.Messages, ctx.CurrentAIContent.String(), ctx.ReasoningContentText.String(),
		ctx.CurrentCallID, ctx.FuncName, funcArguments, res)
	return nil
}
