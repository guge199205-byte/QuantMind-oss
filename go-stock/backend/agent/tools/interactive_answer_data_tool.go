package tools

import (
	"context"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/schema"
	"github.com/duke-git/lancet/v2/convertor"
	"github.com/tidwall/gjson"
	"go-stock/backend/data"
	"go-stock/backend/util"
)

// @Author spark
// @Date 2025/8/5 12:46
// @Desc
//-----------------------------------------------------------------------------------

func GetInteractiveAnswerDataTool() tool.InvokableTool {
	return &InteractiveAnswerDataTool{}
}

type InteractiveAnswerDataTool struct {
}

func (i InteractiveAnswerDataTool) Info(ctx context.Context) (*schema.ToolInfo, error) {
	return &schema.ToolInfo{
		Name: "QueryInteractiveAnswerData",
		Desc: "获取投资者与上市公司互动问答的数据,反映当前投资者关注的热点问题。",
		ParamsOneOf: schema.NewParamsOneOfByParams(map[string]*schema.ParameterInfo{
			"page": {
				Type:     "string",
				Desc:     "分页号",
				Required: true,
			},
			"pageSize": {
				Type:     "string",
				Desc:     "分页大小",
				Required: true,
			},
			"keyWord": {
				Type:     "string",
				Desc:     "搜索关键词,多个关键词空格隔开（可输入股票名称或者当前热门板块/行业/概念/标的/事件等）",
				Required: false,
			},
		}),
	}, nil
}

func (i InteractiveAnswerDataTool) InvokableRun(ctx context.Context, funcArguments string, opts ...tool.Option) (string, error) {
	page := gjson.Get(funcArguments, "page").String()
	pageSize := gjson.Get(funcArguments, "pageSize").String()
	keyWord := gjson.Get(funcArguments, "keyWord").String()
	pageNo, err := convertor.ToInt(page)
	if err != nil {
		pageNo = 1
	}
	pageSizeNum, err := convertor.ToInt(pageSize)
	if err != nil {
		pageSizeNum = 50
	}
	datas := data.NewMarketNewsApi().InteractiveAnswer(int(pageNo), int(pageSizeNum), keyWord)
	content := util.MarkdownTableWithTitle("投资互动数据", datas.Results)
	return content, nil
}
