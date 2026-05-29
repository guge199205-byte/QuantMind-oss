package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"go-stock/backend/data"

	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/schema"
	"github.com/duke-git/lancet/v2/convertor"
	"github.com/duke-git/lancet/v2/random"
)

// @Author spark
// @Date 2025/8/5 11:17
// @Desc
//-----------------------------------------------------------------------------------

func GetChoiceStockByIndicatorsTool() tool.InvokableTool {
	return &ChoiceStockByIndicators{}
}

type ChoiceStockByIndicators struct {
}

func (c ChoiceStockByIndicators) Info(ctx context.Context) (*schema.ToolInfo, error) {
	return &schema.ToolInfo{
		Name: "ChoiceStockByIndicators",
		Desc: "根据自然语言筛选股票，返回自然语言选股条件要求的股票所有相关数据。输入股票名称可以获取当前股票最新的股价交易数据和基础财务指标信息，多个股票名称使用,分隔。",
		ParamsOneOf: schema.NewParamsOneOfByParams(map[string]*schema.ParameterInfo{
			"words": {
				Type: "string",
				Desc: "选股自然语言。" +
					"例：上海贝岭,macd,rsi,kdj,boll,5日均线,14日均线,30日均线,60日均线,成交量,OBV,EMA" +
					"例1：创新药,半导体;PE<30;净利润增长率>50%。 " +
					"例2：上证指数,科创50。 " +
					"例3：长电科技,上海贝岭。" +
					"例4：长电科技,上海贝岭;KDJ,MACD,RSI,BOLL,主力净流入/流出" +
					"例5：换手率大于3%小于25%.量比1以上. 10日内有过涨停.股价处于峰值的二分之一以下.流通股本<100亿.当日和连续四日净流入;股价在20日均线以上.分时图股价在均线之上.热门板块下涨幅领先的A股. 当日量能20000手以上.沪深个股.近一年市盈率波动小于150%.MACD金叉;不要ST股及不要退市股，非北交所，每股收益>0。" +
					"例6：沪深主板.流通市值小于100亿.市值大于10亿.60分钟dif大于dea.60分钟skdj指标k值大于d值.skdj指标k值小于90.换手率大于3%.成交额大于1亿元.量比大于2.涨幅大于2%小于7%.股价大于5小于50.创业板.10日均线大于20日均线;不要ST股及不要退市股;不要北交所;不要科创板;不要创业板。" +
					"例7：股价在20日线上，一月之内涨停次数>=1，量比大于1，换手率大于3%，流通市值大于 50亿小于200亿。" +
					"例8：基本条件：前期有爆量，回调到 10 日线，当日是缩量阴线，均线趋势向上。;优选条件：一月之内涨停次数>=1" +
					"例9：今日涨幅大于等于2%小于等于9%;量比大于等于1.1小于等于5;换手率大于等于5%小于等于20%;市值大于等于30小于等于300亿;5日、10日、30日、60日均线、5周、10周、30周、60周均线多头排列",
				Required: true,
			},
		}),
	}, nil
}

func (c ChoiceStockByIndicators) InvokableRun(ctx context.Context, argumentsInJSON string, opts ...tool.Option) (string, error) {
	parms := map[string]any{}
	err := json.Unmarshal([]byte(argumentsInJSON), &parms)
	if err != nil {
		return "", err
	}
	content := "无符合条件的数据"
	words := parms["words"].(string)
	res := data.NewSearchStockApi(words).SearchStock(random.RandInt(5, 20))
	if convertor.ToString(res["code"]) == "100" {
		resData := res["data"].(map[string]any)
		result := resData["result"].(map[string]any)
		dataList := result["dataList"].([]any)
		columns := result["columns"].([]any)
		headers := map[string]string{}
		for _, v := range columns {
			//logger.SugaredLogger.Infof("v:%+v", v)
			d := v.(map[string]any)
			//logger.SugaredLogger.Infof("key:%s title:%s dateMsg:%s unit:%s", d["key"], d["title"], d["dateMsg"], d["unit"])
			title := convertor.ToString(d["title"])
			if convertor.ToString(d["dateMsg"]) != "" {
				title = title + "[" + convertor.ToString(d["dateMsg"]) + "]"
			}
			if convertor.ToString(d["unit"]) != "" {
				title = title + "(" + convertor.ToString(d["unit"]) + ")"
			}
			headers[d["key"].(string)] = title
		}
		table := &[]map[string]any{}
		for _, v := range dataList {
			d := v.(map[string]any)
			tmp := map[string]any{}
			for key, title := range headers {
				tmp[title] = convertor.ToString(d[key])
			}
			*table = append(*table, tmp)
		}
		jsonData, _ := json.Marshal(*table)
		markdownTable, _ := JSONToMarkdownTable(jsonData)
		//logger.SugaredLogger.Infof("markdownTable=\n%s", markdownTable)
		content = "\r\n### 工具筛选出的股票数据：\r\n" + markdownTable + "\r\n"
	}
	return content, nil
}

// JSONToMarkdownTable 将JSON数据转换为Markdown表格
func JSONToMarkdownTable(jsonData []byte) (string, error) {
	var data []map[string]interface{}
	err := json.Unmarshal(jsonData, &data)
	if err != nil {
		return "", err
	}

	if len(data) == 0 {
		return "", nil
	}

	// 获取表头
	headers := []string{}
	for key := range data[0] {
		headers = append(headers, key)
	}

	// 构建表头行
	headerRow := "|"
	for _, header := range headers {
		headerRow += fmt.Sprintf(" %s |", header)
	}
	headerRow += "\n"

	// 构建分隔行
	separatorRow := "|"
	for range headers {
		separatorRow += " --- |"
	}
	separatorRow += "\n"

	// 构建数据行
	bodyRows := ""
	for _, rowData := range data {
		bodyRow := "|"
		for _, header := range headers {
			value := rowData[header]
			bodyRow += fmt.Sprintf(" %v |", value)
		}
		bodyRows += bodyRow + "\n"
	}

	return headerRow + separatorRow + bodyRows, nil
}
