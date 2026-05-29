package tools

import (
	"context"
	"fmt"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/schema"
	"github.com/tidwall/gjson"
	"go-stock/backend/data"
	"strings"
)

// @Author spark
// @Date 2025/8/5 15:49
// @Desc
//-----------------------------------------------------------------------------------

func GetFinancialReportTool() tool.InvokableTool {
	return &FinancialReportTool{}
}

type FinancialReportTool struct {
}

func (f FinancialReportTool) Info(ctx context.Context) (*schema.ToolInfo, error) {
	return &schema.ToolInfo{
		Name: "GetFinancialReport",
		Desc: "查询股票财务报表数据",
		ParamsOneOf: schema.NewParamsOneOfByParams(map[string]*schema.ParameterInfo{
			"stockCode": {
				Type:     "string",
				Desc:     "股票代码（A股：sh,sz开头;港股hk开头,美股：us开头）不能批量查询",
				Required: true,
			},
		}),
	}, nil
}

func (f FinancialReportTool) InvokableRun(ctx context.Context, argumentsInJSON string, opts ...tool.Option) (string, error) {
	stockCode := gjson.Get(argumentsInJSON, "stockCode").String()
	messages := data.GetFinancialReportsByXUEQIU(GetStockCode(stockCode), 30)
	if messages == nil || len(*messages) == 0 {
		return "", fmt.Errorf("没有找到%s的财务报告", stockCode)
	}
	md := strings.Builder{}
	for _, s := range *messages {
		md.WriteString(s)
	}
	return md.String(), nil
}
