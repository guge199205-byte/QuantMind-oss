package tools

import (
	"context"
	"encoding/json"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/schema"
	"go-stock/backend/data"
	"strings"
)

// @Author spark
// @Date 2025/8/4 17:58
// @Desc
//-----------------------------------------------------------------------------------

func GetQueryStockPriceInfoTool() tool.InvokableTool {
	return &ToolQueryStockPriceInfo{}
}

type ToolQueryStockPriceInfo struct{}

func (t ToolQueryStockPriceInfo) Info(ctx context.Context) (*schema.ToolInfo, error) {
	return &schema.ToolInfo{
		Name: "QueryStockPriceInfo",
		Desc: "批量获取实时股价数据",
		ParamsOneOf: schema.NewParamsOneOfByParams(map[string]*schema.ParameterInfo{
			"stockCodes": {
				Type:     "string",
				Desc:     "股票代码,多个,隔开,股票代码必须转化为sh或者sz或者hk开头的形式，例如：sz399001,sh600859",
				Required: true,
			},
		}),
	}, nil
}

func (t ToolQueryStockPriceInfo) InvokableRun(ctx context.Context, argumentsInJSON string, opts ...tool.Option) (string, error) {
	parms := map[string]any{}
	err := json.Unmarshal([]byte(argumentsInJSON), &parms)
	if err != nil {
		return "", err
	}
	stockCodes := strings.Split(parms["stockCodes"].(string), ",")
	var codes []string
	for _, code := range stockCodes {
		codes = append(codes, GetStockCode(code))
	}
	realTimeData, err := data.NewStockDataApi().GetStockCodeRealTimeData(codes...)
	if err != nil {
		return "", err
	}
	marshal, err := json.Marshal(realTimeData)
	if err != nil {
		return "", err
	}
	return string(marshal), nil
}
