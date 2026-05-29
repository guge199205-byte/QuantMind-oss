package tools

import (
	"context"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/schema"
	"github.com/tidwall/gjson"
	"go-stock/backend/data"
	"go-stock/backend/util"
)

// @Author spark
// @Date 2025/8/5 16:27
// @Desc
//-----------------------------------------------------------------------------------

func GetQueryStockNewsTool() tool.InvokableTool {
	return &QueryStockNewsTool{}
}

type QueryStockNewsTool struct {
}

func (q QueryStockNewsTool) Info(ctx context.Context) (*schema.ToolInfo, error) {
	return &schema.ToolInfo{
		Name: "QueryStockNewsTool",
		Desc: "按关键词搜索相关市场资讯/新闻",
		ParamsOneOf: schema.NewParamsOneOfByParams(map[string]*schema.ParameterInfo{
			"searchWords": {
				Type:     "string",
				Desc:     "搜索关键词(多个关键词使用空格分隔)",
				Required: true,
			},
		}),
	}, nil
}

func (q QueryStockNewsTool) InvokableRun(ctx context.Context, argumentsInJSON string, opts ...tool.Option) (string, error) {
	searchWords := gjson.Get(argumentsInJSON, "searchWords").String()
	res := data.NewMarketNewsApi().CailianpressWeb(searchWords)
	return util.MarkdownTableWithTitle(searchWords+"市场资讯/新闻", res.List), nil
}
