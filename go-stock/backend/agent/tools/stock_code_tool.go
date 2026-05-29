package tools

import (
	"context"
	"encoding/json"

	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/schema"
	"go-stock/backend/data"
	"go-stock/backend/logger"
)

// @Author spark
// @Date 2025/8/4 18:25
// @Desc
//-----------------------------------------------------------------------------------

func GetQueryStockCodeInfoTool() tool.InvokableTool {
	return &QueryStockCodeInfo{}
}

type QueryStockCodeInfo struct {
}

func (q QueryStockCodeInfo) Info(ctx context.Context) (*schema.ToolInfo, error) {
	return &schema.ToolInfo{
		Name: "QueryStockCodeInfo",
		Desc: "查询股票/指数信息(股票/指数名称,股票/指数代码,股票/指数拼音,股票/指数拼音首字母,股票/指数交易所等",
		ParamsOneOf: schema.NewParamsOneOfByParams(map[string]*schema.ParameterInfo{
			"searchWord": {
				Type:     "string",
				Desc:     "股票搜索关键词",
				Required: true,
			},
		}),
	}, nil
}

func (q QueryStockCodeInfo) InvokableRun(ctx context.Context, argumentsInJSON string, opts ...tool.Option) (string, error) {
	logger.SugaredLogger.Infof("QueryStockCodeInfo called with args: %s", argumentsInJSON)
	parms := map[string]any{}
	err := json.Unmarshal([]byte(argumentsInJSON), &parms)
	if err != nil {
		logger.SugaredLogger.Errorf("QueryStockCodeInfo unmarshal error: %v", err)
		return "", err
	}
	searchWord, ok := parms["searchWord"].(string)
	if !ok {
		logger.SugaredLogger.Errorf("QueryStockCodeInfo searchWord not found in args")
		return "未找到股票信息", nil
	}
	logger.SugaredLogger.Infof("QueryStockCodeInfo searching for: %s", searchWord)
	stockList := data.NewStockDataApi().GetStockList(searchWord)
	marshal, err := json.Marshal(stockList)
	if err != nil {
		logger.SugaredLogger.Errorf("QueryStockCodeInfo marshal error: %v", err)
		return "", err
	}
	logger.SugaredLogger.Infof("QueryStockCodeInfo result length: %d", len(marshal))
	return string(marshal), nil
}
