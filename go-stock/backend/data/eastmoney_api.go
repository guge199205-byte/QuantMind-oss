package data

import (
	"crypto/rand"
	"encoding/json"
	"fmt"
	"go-stock/backend/logger"
	"math/big"
	"net/http"
	"strings"
	"time"

	"github.com/go-resty/resty/v2"
)

const (
	emEntityAPI             = "https://ai-saas.eastmoney.com/proxy/entity/dialogTagsV2"
	emReportListAPI         = "https://ai-saas.eastmoney.com/proxy/app-robo-advisor-api/assistant/write/choice/reportList"
	emPerformanceCommentAPI = "https://ai-saas.eastmoney.com/proxy/app-robo-advisor-api/assistant/write/performance/comment"
	emFinancialQAAPI        = "https://ai-saas.eastmoney.com/proxy/app-robo-advisor-api/assistant/ask"
	emIndustryResearchAPI   = "https://ai-saas.eastmoney.com/proxy/app-robo-advisor-api/assistant/write/industry/research"
	emTrackingReportAPI     = "https://ai-saas.eastmoney.com/proxy/app-robo-advisor-api/assistant/write/tracking/report"
	emSearchDataAPI         = "https://ai-saas.eastmoney.com/proxy/b/mcp/tool/searchData"
	emSearchNewsAPI         = "https://ai-saas.eastmoney.com/proxy/b/mcp/tool/searchNews"
	emComparableCompanyAPI  = "https://ai-saas.eastmoney.com/proxy/app-robo-advisor-api/assistant/comparable-company-analysis"
	emHotspotDiscoveryAPI   = "https://ai-saas.eastmoney.com/proxy/app-robo-advisor-api/assistant/hotspot-discovery"
)

type EmAPI struct {
	client *resty.Client
	config *SettingConfig
}

func NewEmAPI() *EmAPI {
	config := GetSettingConfig()
	// 共用连接池但允许更长的超时时间（AI 调用）
	emHTTPClient := &http.Client{
		Transport: SharedHTTPClient.GetClient().Transport,
		Timeout:   120 * time.Second,
	}
	client := resty.NewWithClient(emHTTPClient).
		SetRetryCount(2).
		SetRetryWaitTime(2 * time.Second)
	return &EmAPI{client: client, config: config}
}

func (api *EmAPI) getApiKey() string {
	if api.config != nil && api.config.Settings != nil {
		return strings.TrimSpace(api.config.Settings.EmApiKey)
	}
	return ""
}

func (api *EmAPI) baseHeaders() map[string]string {
	emBaseInfo, _ := json.Marshal(map[string]string{"productType": "mx"})
	return map[string]string{
		"Content-Type": "application/json",
		"em_base_info": string(emBaseInfo),
		"em_api_key":   api.getApiKey(),
	}
}

type EmEntityInfo struct {
	ClassCode  string `json:"classCode"`
	SecuCode   string `json:"secuCode"`
	MarketChar string `json:"marketChar"`
	SecuName   string `json:"secuName"`
	EmCode     string `json:"emCode"`
}

func (e *EmEntityInfo) buildEmCode() string {
	if strings.Contains(e.SecuCode, ".") {
		return e.SecuCode
	}
	suffix := strings.TrimSpace(e.MarketChar)
	if suffix == "" {
		return e.SecuCode
	}
	if !strings.HasPrefix(suffix, ".") {
		suffix = "." + suffix
	}
	return e.SecuCode + suffix
}

func (api *EmAPI) ValidateEntity(query string) (*EmEntityInfo, error) {
	if api.getApiKey() == "" {
		return nil, fmt.Errorf("东方财富API Key未配置，请在设置中填写em_api_key")
	}

	payload := map[string]string{"content": query}

	resp, err := api.client.R().
		SetHeaders(api.baseHeaders()).
		SetBody(payload).
		Post(emEntityAPI)
	if err != nil {
		return nil, fmt.Errorf("实体识别请求失败: %v", err)
	}

	var data map[string]any
	if err := json.Unmarshal(resp.Body(), &data); err != nil {
		return nil, fmt.Errorf("实体识别响应解析失败: %v", err)
	}

	code, _ := data["code"].(float64)
	status, _ := data["status"].(float64)
	if (code != 0 && code != 200) || (status != 0 && status != 200) {
		msg, _ := data["message"].(string)
		return nil, fmt.Errorf("实体识别接口返回异常: code=%.0f, status=%.0f, message=%s", code, status, msg)
	}

	var first map[string]any
	if d, ok := data["data"].(map[string]any); ok {
		if entityList, ok := d["entityMetricList"].([]any); ok && len(entityList) > 0 {
			if inner, ok := entityList[0].([]any); ok && len(inner) > 0 {
				if m, ok := inner[0].(map[string]any); ok {
					first = m
				}
			}
		}
		if first == nil {
			if entityList, ok := d["entityList"].([]any); ok && len(entityList) > 0 {
				if m, ok := entityList[0].(map[string]any); ok {
					first = m
				}
			}
		}
	}
	if first == nil {
		if arr, ok := data["data"].([]any); ok && len(arr) > 0 {
			if m, ok := arr[0].(map[string]any); ok {
				first = m
			}
		}
	}
	if first == nil {
		return nil, fmt.Errorf("实体识别未找到有效实体")
	}

	classCode := fmt.Sprintf("%v", first["classCode"])
	if classCode != "002001" && classCode != "002003" && classCode != "002004" {
		return nil, fmt.Errorf("目前仅支持沪深京港美实体进行业绩点评，识别到classCode=%s", classCode)
	}

	secuCode := fmt.Sprintf("%v", first["secuCode"])
	if secuCode == "" {
		return nil, fmt.Errorf("实体识别缺少secuCode")
	}

	secuName := ""
	if v, ok := first["shortName"].(string); ok && v != "" {
		secuName = v
	} else if v, ok := first["fullName"].(string); ok && v != "" {
		secuName = v
	} else if v, ok := first["secuName"].(string); ok && v != "" {
		secuName = v
	}

	info := &EmEntityInfo{
		ClassCode:  classCode,
		SecuCode:   secuCode,
		MarketChar: fmt.Sprintf("%v", first["marketChar"]),
		SecuName:   secuName,
	}
	info.EmCode = info.buildEmCode()
	return info, nil
}

type EmReportOption struct {
	ReportDate  string `json:"reportDate"`
	PeriodLabel string `json:"periodLabel"`
}

func (api *EmAPI) FetchReportOptions(emCode string) ([]EmReportOption, error) {
	if api.getApiKey() == "" {
		return nil, fmt.Errorf("东方财富API Key未配置")
	}

	payload := map[string]string{"emCode": emCode}

	resp, err := api.client.R().
		SetHeaders(api.baseHeaders()).
		SetBody(payload).
		Post(emReportListAPI)
	if err != nil {
		return nil, fmt.Errorf("报告期列表请求失败: %v", err)
	}

	var raw map[string]any
	if err := json.Unmarshal(resp.Body(), &raw); err != nil {
		return nil, fmt.Errorf("报告期列表响应解析失败: %v", err)
	}

	code, _ := raw["code"].(float64)
	status, _ := raw["status"].(float64)
	if code != 0 && code != 200 && status != 0 && status != 200 {
		msg, _ := raw["message"].(string)
		return nil, fmt.Errorf("报告期接口返回异常: code=%.0f, status=%.0f, message=%s", code, status, msg)
	}

	data, _ := raw["data"].(map[string]any)
	src, _ := data["reportDateList"].([]any)
	if len(src) == 0 {
		return nil, fmt.Errorf("报告期列表获取失败或为空")
	}

	var options []EmReportOption
	for _, item := range src {
		switch v := item.(type) {
		case string:
			options = append(options, EmReportOption{ReportDate: v})
		case map[string]any:
			rd := ""
			if s, ok := v["reportDate"].(string); ok && s != "" {
				rd = s
			} else if s, ok := v["report_date"].(string); ok && s != "" {
				rd = s
			} else if s, ok := v["date"].(string); ok && s != "" {
				rd = s
			}
			if rd != "" {
				pl, _ := v["period"].(string)
				options = append(options, EmReportOption{ReportDate: rd, PeriodLabel: pl})
			}
		}
	}
	if len(options) == 0 {
		return nil, fmt.Errorf("报告期列表解析失败")
	}
	return options, nil
}

type EmEarningsReviewResult struct {
	Title    string `json:"title"`
	Content  string `json:"content"`
	ShareUrl string `json:"shareUrl"`
}

func (api *EmAPI) EarningsReview(emCode, reportDate string) (*EmEarningsReviewResult, error) {
	if api.getApiKey() == "" {
		return nil, fmt.Errorf("东方财富API Key未配置")
	}

	payload := map[string]string{
		"query":      emCode,
		"reportDate": reportDate,
	}

	resp, err := api.client.R().
		SetHeaders(api.baseHeaders()).
		SetBody(payload).
		Post(emPerformanceCommentAPI)
	if err != nil {
		return nil, fmt.Errorf("业绩点评请求失败: %v", err)
	}

	var raw map[string]any
	if err := json.Unmarshal(resp.Body(), &raw); err != nil {
		return nil, fmt.Errorf("业绩点评响应解析失败: %v", err)
	}

	code, _ := raw["code"].(float64)
	status, _ := raw["status"].(float64)
	if code != 0 && code != 200 && status != 0 && status != 200 {
		msg, _ := raw["message"].(string)
		return nil, fmt.Errorf("业绩点评接口返回异常: code=%.0f, status=%.0f, message=%s", code, status, msg)
	}

	data, _ := raw["data"].(map[string]any)
	title, _ := data["title"].(string)
	content, _ := data["content"].(string)
	shareUrl, _ := data["shareUrl"].(string)

	return &EmEarningsReviewResult{
		Title:    title,
		Content:  content,
		ShareUrl: shareUrl,
	}, nil
}

func (api *EmAPI) EarningsReviewToMarkdown(query string, reportDate string) string {
	entity, err := api.ValidateEntity(query)
	if err != nil {
		logger.SugaredLogger.Errorf("实体识别失败: %v", err)
		return fmt.Sprintf("实体识别失败: %v", err)
	}

	var selectedDate string
	if reportDate != "" {
		selectedDate = reportDate
	} else {
		options, err := api.FetchReportOptions(entity.EmCode)
		if err != nil {
			logger.SugaredLogger.Errorf("获取报告期列表失败: %v", err)
			return fmt.Sprintf("获取报告期列表失败: %v", err)
		}
		selectedDate = options[0].ReportDate
		if len(options) > 1 {
			var sb strings.Builder
			sb.WriteString(fmt.Sprintf("### %s 可用报告期\n\n", entity.SecuName))
			for i, opt := range options {
				sb.WriteString(fmt.Sprintf("%d. %s", i+1, opt.ReportDate))
				if opt.PeriodLabel != "" {
					sb.WriteString(fmt.Sprintf(" (%s)", opt.PeriodLabel))
				}
				sb.WriteString("\n")
			}
			sb.WriteString(fmt.Sprintf("\n默认使用最新报告期: **%s**\n\n", selectedDate))
			logger.SugaredLogger.Infof("使用最新报告期: %s", selectedDate)
		}
	}

	result, err := api.EarningsReview(entity.EmCode, selectedDate)
	if err != nil {
		logger.SugaredLogger.Errorf("业绩点评失败: %v", err)
		return fmt.Sprintf("业绩点评失败: %v", err)
	}

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("### %s\n\n", result.Title))
	if result.ShareUrl != "" {
		sb.WriteString(fmt.Sprintf("[查看原文](%s)\n\n", result.ShareUrl))
	}
	if result.Content != "" {
		sb.WriteString(result.Content)
	} else {
		sb.WriteString("暂无业绩点评内容")
	}
	return sb.String()
}

type EmQAReference struct {
	RefId         int    `json:"refId"`
	Type          string `json:"type"`
	ReferenceType string `json:"referenceType"`
	Markdown      string `json:"markdown,omitempty"`
	Title         string `json:"title,omitempty"`
	JumpUrl       string `json:"jumpUrl,omitempty"`
	Source        string `json:"source,omitempty"`
}

type EmQAResult struct {
	Ok         bool            `json:"ok"`
	Answer     string          `json:"answer"`
	References []EmQAReference `json:"references"`
}

func (api *EmAPI) FinancialQA(question string, deepThink bool) (*EmQAResult, error) {
	if api.getApiKey() == "" {
		return nil, fmt.Errorf("东方财富API Key未配置，请在设置中填写em_api_key")
	}

	payload := map[string]any{
		"question": question,
	}
	if deepThink {
		payload["deepThink"] = true
	}

	headers := api.baseHeaders()
	headers["Accept"] = "application/json"

	resp, err := api.client.R().
		SetHeaders(headers).
		SetBody(payload).
		Post(emFinancialQAAPI)
	if err != nil {
		return nil, fmt.Errorf("金融问答请求失败: %v", err)
	}

	var raw map[string]any
	if err := json.Unmarshal(resp.Body(), &raw); err != nil {
		return nil, fmt.Errorf("金融问答响应解析失败: %v", err)
	}

	code, _ := raw["code"].(float64)
	if intCode := int(code); intCode != 0 && intCode != 200 {
		msg, _ := raw["message"].(string)
		return nil, fmt.Errorf("金融问答接口返回异常: code=%d, message=%s", intCode, msg)
	}

	data, _ := raw["data"].(map[string]any)
	answer, _ := data["displayData"].(string)
	if answer == "" {
		return nil, fmt.Errorf("未获取到有效回答")
	}

	var references []EmQAReference
	if refList, ok := data["refIndexList"].([]any); ok {
		for _, item := range refList {
			if m, ok := item.(map[string]any); ok {
				ref := EmQAReference{}
				if v, ok := m["refId"].(float64); ok {
					ref.RefId = int(v)
				}
				if v, ok := m["type"].(string); ok {
					ref.Type = v
				}
				if v, ok := m["referenceType"].(string); ok {
					ref.ReferenceType = v
				}
				if v, ok := m["markdown"].(string); ok {
					ref.Markdown = v
				}
				if v, ok := m["title"].(string); ok {
					ref.Title = v
				}
				if v, ok := m["jumpUrl"].(string); ok {
					ref.JumpUrl = v
				}
				if v, ok := m["source"].(string); ok {
					ref.Source = v
				} else if nested, ok := m["data"].(map[string]any); ok {
					if v, ok := nested["source"].(string); ok {
						ref.Source = v
					}
				}
				references = append(references, ref)
			}
		}
	}

	return &EmQAResult{
		Ok:         true,
		Answer:     answer,
		References: references,
	}, nil
}

func (api *EmAPI) FinancialQAToMarkdown(question string, deepThink bool) string {
	result, err := api.FinancialQA(question, deepThink)
	if err != nil {
		logger.SugaredLogger.Errorf("金融问答失败: %v", err)
		return fmt.Sprintf("金融问答失败: %v", err)
	}

	var sb strings.Builder
	sb.WriteString(result.Answer)

	var citedRefs, otherRefs []EmQAReference
	for _, ref := range result.References {
		if ref.ReferenceType == "CITED_REFERENCE" {
			citedRefs = append(citedRefs, ref)
		} else {
			otherRefs = append(otherRefs, ref)
		}
	}

	if len(citedRefs) > 0 {
		sb.WriteString("\n\n### 溯源参考\n")
		var dataRefs, newsRefs, announcementRefs, reportRefs []EmQAReference
		for _, ref := range citedRefs {
			switch ref.Type {
			case "查数", "选股/基":
				dataRefs = append(dataRefs, ref)
			case "资讯":
				newsRefs = append(newsRefs, ref)
			case "公告":
				announcementRefs = append(announcementRefs, ref)
			case "研报":
				reportRefs = append(reportRefs, ref)
			default:
				dataRefs = append(dataRefs, ref)
			}
		}

		if len(dataRefs) > 0 {
			sb.WriteString("\n\n**数据参考：**\n\n")
			for _, ref := range dataRefs {
				if ref.Markdown != "" {
					sb.WriteString(ref.Markdown)
					sb.WriteString("\n\n")
				}
			}
		}
		if len(newsRefs) > 0 {
			sb.WriteString("\n**资讯引用：**\n\n")
			for _, ref := range newsRefs {
				sb.WriteString(formatRefLink(ref))
				sb.WriteString("\n")
			}
		}
		if len(announcementRefs) > 0 {
			sb.WriteString("\n**公告引用：**\n\n")
			for _, ref := range announcementRefs {
				sb.WriteString(formatRefLink(ref))
				sb.WriteString("\n")
			}
		}
		if len(reportRefs) > 0 {
			sb.WriteString("\n**研报引用：**\n\n")
			for _, ref := range reportRefs {
				sb.WriteString(formatRefLink(ref))
				sb.WriteString("\n")
			}
		}
	}

	if len(otherRefs) > 0 {
		sb.WriteString("\n\n### 扩展阅读\n\n")
		for _, ref := range otherRefs {
			sb.WriteString(formatRefLink(ref))
			sb.WriteString("\n")
		}
	}

	return sb.String()
}

func formatRefLink(ref EmQAReference) string {
	title := ref.Title
	if title == "" {
		title = ref.Type
	}
	if ref.JumpUrl != "" && ref.Source != "" {
		return fmt.Sprintf("- [%s](%s)（来源：%s）", title, ref.JumpUrl, ref.Source)
	}
	if ref.JumpUrl != "" {
		return fmt.Sprintf("- [%s](%s)", title, ref.JumpUrl)
	}
	if ref.Source != "" {
		return fmt.Sprintf("- %s（来源：%s）", title, ref.Source)
	}
	return fmt.Sprintf("- %s", title)
}

type EmIndustryResearchResult struct {
	Title    string `json:"title"`
	Content  string `json:"content"`
	ShareUrl string `json:"shareUrl"`
}

func (api *EmAPI) IndustryResearch(query string) (*EmIndustryResearchResult, error) {
	if api.getApiKey() == "" {
		return nil, fmt.Errorf("东方财富API Key未配置，请在设置中填写em_api_key")
	}

	if len(query) > 500 {
		return nil, fmt.Errorf("字数超出限制，请尝试其它主体")
	}

	payload := map[string]string{"query": query}

	resp, err := api.client.R().
		SetHeaders(api.baseHeaders()).
		SetBody(payload).
		Post(emIndustryResearchAPI)
	if err != nil {
		return nil, fmt.Errorf("行业研究报告请求失败: %v", err)
	}

	var raw map[string]any
	if err := json.Unmarshal(resp.Body(), &raw); err != nil {
		return nil, fmt.Errorf("行业研究报告响应解析失败: %v", err)
	}

	code, _ := raw["code"].(float64)
	if intCode := int(code); intCode != 0 && intCode != 200 {
		msg, _ := raw["message"].(string)
		return nil, fmt.Errorf("行业研究报告接口返回异常: code=%d, message=%s", intCode, msg)
	}

	data, _ := raw["data"].(map[string]any)
	title, _ := data["title"].(string)
	content, _ := data["content"].(string)
	shareUrl, _ := data["shareUrl"].(string)

	return &EmIndustryResearchResult{
		Title:    title,
		Content:  content,
		ShareUrl: shareUrl,
	}, nil
}

func (api *EmAPI) IndustryResearchToMarkdown(query string) string {
	result, err := api.IndustryResearch(query)
	if err != nil {
		logger.SugaredLogger.Errorf("行业研究报告生成失败: %v", err)
		return fmt.Sprintf("行业研究报告生成失败: %v", err)
	}

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("### %s\n\n", result.Title))
	if result.ShareUrl != "" {
		sb.WriteString(fmt.Sprintf("[查看完整报告](%s)\n\n", result.ShareUrl))
	}
	if result.Content != "" {
		sb.WriteString(result.Content)
	} else {
		sb.WriteString("报告内容生成中，请通过分享链接查看完整报告。")
	}
	return sb.String()
}

type EmTrackingReportResult struct {
	Title      string `json:"title"`
	Content    string `json:"content"`
	EntityType string `json:"entityType"`
	ShareUrl   string `json:"shareUrl"`
}

func (api *EmAPI) TrackingReport(query string) (*EmTrackingReportResult, error) {
	if api.getApiKey() == "" {
		return nil, fmt.Errorf("东方财富API Key未配置，请在设置中填写em_api_key")
	}

	payload := map[string]string{"query": query}

	resp, err := api.client.R().
		SetHeaders(api.baseHeaders()).
		SetBody(payload).
		Post(emTrackingReportAPI)
	if err != nil {
		return nil, fmt.Errorf("跟踪报告请求失败: %v", err)
	}

	var raw map[string]any
	if err := json.Unmarshal(resp.Body(), &raw); err != nil {
		return nil, fmt.Errorf("跟踪报告响应解析失败: %v", err)
	}

	code, _ := raw["code"].(string)
	if code == "ERROR_ENTITY" {
		return nil, fmt.Errorf("目前暂不支持此类实体进行分析")
	}

	codeFloat, _ := raw["code"].(float64)
	if intCode := int(codeFloat); intCode != 0 && intCode != 200 && code == "" {
		msg, _ := raw["message"].(string)
		return nil, fmt.Errorf("跟踪报告接口返回异常: code=%d, message=%s", intCode, msg)
	}

	data, _ := raw["data"].(map[string]any)
	if data == nil {
		msg, _ := raw["message"].(string)
		if msg != "" {
			return nil, fmt.Errorf("%s", msg)
		}
		return nil, fmt.Errorf("跟踪报告数据为空")
	}

	dataCode, _ := data["code"].(string)
	if dataCode == "ERROR_ENTITY" {
		return nil, fmt.Errorf("目前暂不支持此类实体进行分析")
	}

	title, _ := data["title"].(string)
	content, _ := data["content"].(string)
	shareUrl, _ := data["shareUrl"].(string)
	entityType, _ := data["entityType"].(string)
	if entityType == "" {
		entityType, _ = data["entity_type"].(string)
	}

	return &EmTrackingReportResult{
		Title:      title,
		Content:    content,
		EntityType: entityType,
		ShareUrl:   shareUrl,
	}, nil
}

func (api *EmAPI) TrackingReportToMarkdown(query string) string {
	result, err := api.TrackingReport(query)
	if err != nil {
		logger.SugaredLogger.Errorf("跟踪报告生成失败: %v", err)
		return fmt.Sprintf("跟踪报告生成失败: %v", err)
	}

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("### %s\n\n", result.Title))
	if result.ShareUrl != "" {
		sb.WriteString(fmt.Sprintf("[查看完整报告](%s)\n\n", result.ShareUrl))
	}
	if result.Content != "" {
		sb.WriteString(result.Content)
	} else {
		sb.WriteString("暂无总结内容，请通过分享链接查看完整报告。")
	}
	return sb.String()
}

func generateCallId() string {
	n, _ := rand.Int(rand.Reader, big.NewInt(99999999))
	return fmt.Sprintf("call_%08d", n)
}

func generateUserId() string {
	n, _ := rand.Int(rand.Reader, big.NewInt(99999999))
	return fmt.Sprintf("user_%08d", n)
}

type EmDataTableDTO struct {
	Title          string         `json:"title"`
	EntityName     string         `json:"entityName"`
	NameMap        map[string]any `json:"nameMap"`
	IndicatorOrder []any          `json:"indicatorOrder"`
	Table          map[string]any `json:"table"`
	Condition      string         `json:"condition"`
}

type EmSearchDataResult struct {
	Tables    []EmDataTableDTO
	Condition string
	Message   string
}

func (api *EmAPI) FinanceDataQuery(query string) (*EmSearchDataResult, error) {
	if api.getApiKey() == "" {
		return nil, fmt.Errorf("东方财富API Key未配置，请在设置中填写em_api_key")
	}

	payload := map[string]any{
		"query": query,
		"toolContext": map[string]any{
			"callId":   generateCallId(),
			"userInfo": map[string]string{"userId": generateUserId()},
		},
	}

	resp, err := api.client.R().
		SetHeaders(api.baseHeaders()).
		SetBody(payload).
		Post(emSearchDataAPI)
	if err != nil {
		return nil, fmt.Errorf("金融数据查询请求失败: %v", err)
	}

	var raw map[string]any
	if err := json.Unmarshal(resp.Body(), &raw); err != nil {
		return nil, fmt.Errorf("金融数据查询响应解析失败: %v", err)
	}

	code, _ := raw["code"].(float64)
	status, _ := raw["status"].(float64)
	if (code != 0 && code != 200) || (status != 0 && status != 200) {
		msg, _ := raw["message"].(string)
		if msg == "" {
			if data, ok := raw["data"].(map[string]any); ok {
				if m, ok2 := data["message"].(string); ok2 {
					msg = m
				}
			}
		}
		return nil, fmt.Errorf("金融数据查询接口返回异常: code=%.0f, status=%.0f, message=%s", code, status, msg)
	}

	var dtoList []any
	if data, ok := raw["data"].(map[string]any); ok {
		if sdto, ok := data["searchDataResultDTO"].(map[string]any); ok {
			dtoList, _ = sdto["dataTableDTOList"].([]any)
		}
		if len(dtoList) == 0 {
			dtoList, _ = data["dataTableDTOList"].([]any)
		}
	}
	if len(dtoList) == 0 {
		dtoList, _ = raw["dataTableDTOList"].([]any)
	}

	var tables []EmDataTableDTO
	var conditionParts []string
	for _, item := range dtoList {
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		dto := EmDataTableDTO{}
		dto.Title, _ = m["title"].(string)
		dto.EntityName, _ = m["entityName"].(string)
		if nm, ok := m["nameMap"].(map[string]any); ok {
			dto.NameMap = nm
		}
		if io, ok := m["indicatorOrder"].([]any); ok {
			dto.IndicatorOrder = io
		}
		if t, ok := m["table"].(map[string]any); ok {
			dto.Table = t
		}
		dto.Condition, _ = m["condition"].(string)
		if dto.Condition != "" {
			entity := dto.EntityName
			if entity == "" {
				entity = dto.Title
			}
			conditionParts = append(conditionParts, fmt.Sprintf("[%s]\n%s", entity, dto.Condition))
		}
		tables = append(tables, dto)
	}

	result := &EmSearchDataResult{Tables: tables}
	if len(conditionParts) > 0 {
		result.Condition = strings.Join(conditionParts, "\n\n")
	}
	if data, ok := raw["data"].(map[string]any); ok {
		if msg, ok := data["message"].(string); ok && msg != "" {
			result.Message = msg
		}
	}

	return result, nil
}

func (api *EmAPI) FinanceDataQueryToMarkdown(query string) string {
	result, err := api.FinanceDataQuery(query)
	if err != nil {
		logger.SugaredLogger.Errorf("金融数据查询失败: %v", err)
		return fmt.Sprintf("金融数据查询失败: %v", err)
	}

	if len(result.Tables) == 0 {
		return "未查询到相关金融数据，请尝试更具体的查询条件。"
	}

	var sb strings.Builder

	if result.Message != "" {
		sb.WriteString(fmt.Sprintf("> %s\n\n", result.Message))
	}

	for i, table := range result.Tables {
		if i > 0 {
			sb.WriteString("\n---\n\n")
		}

		title := table.Title
		if title == "" {
			title = table.EntityName
		}
		if title != "" {
			sb.WriteString(fmt.Sprintf("### %s\n\n", title))
		}

		mdTable := dataTableToMarkdown(table)
		if mdTable != "" {
			sb.WriteString(mdTable)
		} else {
			sb.WriteString("暂无数据\n")
		}
	}

	if result.Condition != "" {
		sb.WriteString(fmt.Sprintf("\n\n### 查询条件\n\n%s", result.Condition))
	}

	return sb.String()
}

func dataTableToMarkdown(dto EmDataTableDTO) string {
	table := dto.Table
	if len(table) == 0 {
		return ""
	}

	nameMap := dto.NameMap
	if nameMap == nil {
		nameMap = make(map[string]any)
	}

	headers, _ := table["headName"].([]any)
	order := dto.IndicatorOrder

	var dataKeys []string
	for k := range table {
		if k != "headName" {
			dataKeys = append(dataKeys, k)
		}
	}

	orderedKeys := orderedIndicatorKeys(dataKeys, order)

	entityName := dto.EntityName
	if entityName == "" {
		entityName = "指标"
	}

	if len(headers) > 1 && len(orderedKeys) > 0 {
		colCount := len(headers)
		headerStrs := make([]string, colCount)
		for i, h := range headers {
			headerStrs[i] = flattenValue(h)
		}

		sb := strings.Builder{}
		sb.WriteString("| ")
		sb.WriteString(entityName)
		sb.WriteString(" | ")
		sb.WriteString(strings.Join(headerStrs, " | "))
		sb.WriteString(" |\n")

		sb.WriteString("| ")
		sb.WriteString(strings.Repeat("--- | ", colCount+1))
		sb.WriteString("\n")

		for _, key := range orderedKeys {
			label := formatIndicatorLabel(key, nameMap)
			rawVals, _ := table[key].([]any)
			vals := normalizeValues(rawVals, colCount)

			sb.WriteString("| ")
			sb.WriteString(label)
			sb.WriteString(" | ")
			sb.WriteString(strings.Join(vals, " | "))
			sb.WriteString(" |\n")
		}
		return sb.String()
	}

	if len(headers) == 1 && len(orderedKeys) > 0 {
		headerStr := flattenValue(headers[0])

		sb := strings.Builder{}
		sb.WriteString("| ")
		sb.WriteString(entityName)
		sb.WriteString(" | ")
		sb.WriteString(headerStr)
		sb.WriteString(" |\n")
		sb.WriteString("| --- | --- |\n")

		for _, key := range orderedKeys {
			label := formatIndicatorLabel(key, nameMap)
			rawVals, _ := table[key].([]any)
			var val string
			if len(rawVals) > 0 {
				val = flattenValue(rawVals[0])
			}
			sb.WriteString("| ")
			sb.WriteString(label)
			sb.WriteString(" | ")
			sb.WriteString(val)
			sb.WriteString(" |\n")
		}
		return sb.String()
	}

	return genericTableToMarkdown(table, nameMap)
}

func orderedIndicatorKeys(dataKeys []string, order []any) []string {
	keyMap := make(map[string]bool)
	for _, k := range dataKeys {
		keyMap[k] = true
	}

	seen := make(map[string]bool)
	var result []string

	for _, o := range order {
		s := fmt.Sprintf("%v", o)
		if keyMap[s] && !seen[s] {
			result = append(result, s)
			seen[s] = true
		}
	}

	for _, k := range dataKeys {
		if !seen[k] {
			result = append(result, k)
			seen[k] = true
		}
	}

	return result
}

func formatIndicatorLabel(key string, nameMap map[string]any) string {
	if v, ok := nameMap[key]; ok && v != nil {
		s := flattenValue(v)
		if s != "" {
			return s
		}
	}
	return key
}

func flattenValue(v any) string {
	if v == nil {
		return ""
	}
	switch val := v.(type) {
	case string:
		return val
	case float64:
		if val == float64(int64(val)) {
			return fmt.Sprintf("%d", int64(val))
		}
		return fmt.Sprintf("%v", val)
	case bool:
		return fmt.Sprintf("%v", val)
	case map[string]any, []any:
		b, _ := json.Marshal(val)
		return string(b)
	default:
		return fmt.Sprintf("%v", val)
	}
}

func normalizeValues(raw []any, expected int) []string {
	vals := make([]string, len(raw))
	for i, v := range raw {
		vals[i] = flattenValue(v)
	}
	for len(vals) < expected {
		vals = append(vals, "")
	}
	return vals[:expected]
}

func genericTableToMarkdown(table map[string]any, nameMap map[string]any) string {
	vals := make([][]string, 0)
	var keys []string
	for k, v := range table {
		if arr, ok := v.([]any); ok {
			keys = append(keys, k)
			strs := make([]string, len(arr))
			for i, item := range arr {
				strs[i] = flattenValue(item)
			}
			vals = append(vals, strs)
		}
	}
	if len(vals) == 0 {
		return ""
	}

	rowCount := len(vals[0])
	for _, v := range vals {
		if len(v) != rowCount {
			return ""
		}
	}

	headers := make([]string, len(keys))
	for i, k := range keys {
		if v, ok := nameMap[k]; ok && v != nil {
			headers[i] = flattenValue(v)
		} else {
			headers[i] = k
		}
	}

	sb := strings.Builder{}
	sb.WriteString("| ")
	sb.WriteString(strings.Join(headers, " | "))
	sb.WriteString(" |\n")
	sb.WriteString("| ")
	sb.WriteString(strings.Repeat("--- | ", len(headers)))
	sb.WriteString("\n")

	for r := 0; r < rowCount; r++ {
		cells := make([]string, len(keys))
		for c := range keys {
			cells[c] = vals[c][r]
		}
		sb.WriteString("| ")
		sb.WriteString(strings.Join(cells, " | "))
		sb.WriteString(" |\n")
	}
	return sb.String()
}

type EmSearchNewsResult struct {
	Content string
}

func (api *EmAPI) FinanceSearch(query string) (*EmSearchNewsResult, error) {
	if api.getApiKey() == "" {
		return nil, fmt.Errorf("东方财富API Key未配置，请在设置中填写em_api_key")
	}

	payload := map[string]any{
		"query": query,
		"toolContext": map[string]any{
			"callId": generateCallId(),
		},
	}

	resp, err := api.client.R().
		SetHeaders(api.baseHeaders()).
		SetBody(payload).
		Post(emSearchNewsAPI)
	if err != nil {
		return nil, fmt.Errorf("金融资讯搜索请求失败: %v", err)
	}

	var raw map[string]any
	if err := json.Unmarshal(resp.Body(), &raw); err != nil {
		return nil, fmt.Errorf("金融资讯搜索响应解析失败: %v", err)
	}

	code, _ := raw["code"].(float64)
	status, _ := raw["status"].(float64)
	if (code != 0 && code != 200) || (status != 0 && status != 200) {
		msg, _ := raw["message"].(string)
		return nil, fmt.Errorf("金融资讯搜索接口返回异常: code=%.0f, status=%.0f, message=%s", code, status, msg)
	}

	content := extractSearchContent(raw)
	if content == "" {
		return nil, fmt.Errorf("未搜索到相关金融资讯")
	}

	return &EmSearchNewsResult{Content: content}, nil
}

func extractSearchContent(raw map[string]any) string {
	if data, ok := raw["data"].(map[string]any); ok {
		for _, key := range []string{"llmSearchResponse", "searchResponse", "content", "answer", "summary"} {
			if v, ok := data[key].(string); ok && strings.TrimSpace(v) != "" {
				return strings.TrimSpace(v)
			}
		}
		return extractSearchContent(data)
	}

	for _, key := range []string{"llmSearchResponse", "searchResponse", "content", "answer", "summary"} {
		if v, ok := raw[key].(string); ok && strings.TrimSpace(v) != "" {
			return strings.TrimSpace(v)
		}
	}

	return ""
}

func (api *EmAPI) FinanceSearchToMarkdown(query string) string {
	result, err := api.FinanceSearch(query)
	if err != nil {
		logger.SugaredLogger.Errorf("金融资讯搜索失败: %v", err)
		return fmt.Sprintf("金融资讯搜索失败: %v", err)
	}

	return result.Content
}

type EmComparableCompanyResult struct {
	Header           map[string]any
	SectionFinance   map[string]any
	SectionValuation map[string]any
	Raw              []map[string]any
}

func (api *EmAPI) ComparableCompanyAnalysis(query string) (*EmComparableCompanyResult, error) {
	if api.getApiKey() == "" {
		return nil, fmt.Errorf("东方财富API Key未配置，请在设置中填写em_api_key")
	}

	payload := map[string]string{"question": query}

	resp, err := api.client.R().
		SetHeaders(api.baseHeaders()).
		SetBody(payload).
		Post(emComparableCompanyAPI)
	if err != nil {
		return nil, fmt.Errorf("可比公司分析请求失败: %v", err)
	}

	var raw map[string]any
	if err := json.Unmarshal(resp.Body(), &raw); err != nil {
		return nil, fmt.Errorf("可比公司分析响应解析失败: %v", err)
	}

	code, _ := raw["code"].(float64)
	status, _ := raw["status"].(float64)
	codeOk := code == 0 || code == 200
	statusOk := status == 0 || status == 200
	if !codeOk || !statusOk {
		msg, _ := raw["message"].(string)
		return nil, fmt.Errorf("可比公司分析接口返回异常: code=%.0f, status=%.0f, message=%s", code, status, msg)
	}

	dataList, _ := raw["data"].([]any)
	if len(dataList) == 0 {
		return nil, fmt.Errorf("可比公司分析数据为空")
	}

	result := &EmComparableCompanyResult{}
	for i, item := range dataList {
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		result.Raw = append(result.Raw, m)
		switch i {
		case 0:
			result.Header = m
		case 1:
			result.SectionFinance = m
		case 2:
			result.SectionValuation = m
		}
	}
	return result, nil
}

func (api *EmAPI) ComparableCompanyAnalysisToMarkdown(query string) string {
	result, err := api.ComparableCompanyAnalysis(query)
	if err != nil {
		logger.SugaredLogger.Errorf("可比公司分析失败: %v", err)
		return fmt.Sprintf("可比公司分析失败: %v", err)
	}

	var sb strings.Builder

	for _, m := range result.Raw {
		title, _ := m["title"].(string)
		inputTitle, _ := m["inputTitle"].(string)
		if title != "" {
			sb.WriteString(fmt.Sprintf("### %s\n\n", title))
		} else if inputTitle != "" {
			sb.WriteString(fmt.Sprintf("### %s\n\n", inputTitle))
		}

		nameMap, _ := m["nameMap"].(map[string]any)
		table, _ := m["table"].(map[string]any)
		if len(table) > 0 {
			md := genericTableToMarkdown(table, nameMap)
			if md != "" {
				sb.WriteString(md)
				sb.WriteString("\n\n")
			}
		}
	}

	if sb.Len() == 0 {
		return "可比公司分析暂无数据"
	}
	return sb.String()
}

func (api *EmAPI) HotspotDiscovery(question string) (string, error) {
	if api.getApiKey() == "" {
		return "", fmt.Errorf("东方财富API Key未配置，请在设置中填写em_api_key")
	}

	payload := map[string]string{"question": question}

	resp, err := api.client.R().
		SetHeaders(api.baseHeaders()).
		SetBody(payload).
		Post(emHotspotDiscoveryAPI)
	if err != nil {
		return "", fmt.Errorf("热点发现请求失败: %v", err)
	}

	var raw map[string]any
	if err := json.Unmarshal(resp.Body(), &raw); err != nil {
		return "", fmt.Errorf("热点发现响应解析失败: %v", err)
	}

	code, _ := raw["code"].(float64)
	status, _ := raw["status"].(float64)
	codeOk := code == 0 || code == 200
	statusOk := status == 0 || status == 200
	if !codeOk || !statusOk {
		msg, _ := raw["message"].(string)
		return "", fmt.Errorf("热点发现接口返回异常: code=%.0f, status=%.0f, message=%s", code, status, msg)
	}

	data, _ := raw["data"].(map[string]any)
	displayData, _ := data["displayData"].(string)
	if displayData == "" {
		return "", fmt.Errorf("热点发现未返回有效内容")
	}
	return displayData, nil
}

func (api *EmAPI) HotspotDiscoveryToMarkdown(question string) string {
	content, err := api.HotspotDiscovery(question)
	if err != nil {
		logger.SugaredLogger.Errorf("热点发现失败: %v", err)
		return fmt.Sprintf("热点发现失败: %v", err)
	}
	return content
}
