package data

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"go-stock/backend/logger"
	"strings"

	"github.com/go-resty/resty/v2"
)

const iwencaiAPIURL = "https://openapi.iwencai.com/v1/query2data"
const iwencaiSearchURL = "https://openapi.iwencai.com/v1/comprehensive/search"

func generateTraceID() string {
	b := make([]byte, 32)
	rand.Read(b)
	return hex.EncodeToString(b)
}

func iwencaiCommonHeaders(apiKey, skillID, skillVersion string) map[string]string {
	return map[string]string{
		"Authorization":         "Bearer " + apiKey,
		"Content-Type":          "application/json",
		"X-Claw-Call-Type":      "normal",
		"X-Claw-Skill-Id":       skillID,
		"X-Claw-Skill-Version":  skillVersion,
		"X-Claw-Plugin-Id":      "none",
		"X-Claw-Plugin-Version": "none",
		"X-Claw-Trace-Id":       generateTraceID(),
	}
}

type IwencaiAPI struct {
	client *resty.Client
	config *SettingConfig
}

func NewIwencaiAPI() *IwencaiAPI {
	return &IwencaiAPI{
		client: SharedHTTPClient,
		config: GetSettingConfig(),
	}
}

type IwencaiRequest struct {
	Query       string `json:"query"`
	Page        string `json:"page"`
	Limit       string `json:"limit"`
	IsCache     string `json:"is_cache"`
	ExpandIndex string `json:"expand_index"`
}

type IwencaiResponse struct {
	StatusCode int              `json:"status_code"`
	StatusMsg  string           `json:"status_msg"`
	Datas      []map[string]any `json:"datas"`
	CodeCount  int              `json:"code_count"`
	ChunksInfo any              `json:"chunks_info"`
}

func (api *IwencaiAPI) Query(query string, page, limit int) (*IwencaiResponse, error) {
	apiKey := api.config.Settings.IwencaiApiKey
	if apiKey == "" {
		return nil, fmt.Errorf("同花顺问财API密钥未配置，请在设置中填写IwencaiApiKey")
	}

	if page <= 0 {
		page = 1
	}
	if limit <= 0 {
		limit = 10
	}

	reqBody := IwencaiRequest{
		Query:       query,
		Page:        fmt.Sprintf("%d", page),
		Limit:       fmt.Sprintf("%d", limit),
		IsCache:     "1",
		ExpandIndex: "true",
	}

	var result IwencaiResponse
	resp, err := api.client.R().
		SetHeaders(iwencaiCommonHeaders(apiKey, "query2data", "1.0.0")).
		SetBody(reqBody).
		SetResult(&result).
		Post(iwencaiAPIURL)

	if err != nil {
		return nil, fmt.Errorf("调用同花顺问财API失败: %v", err)
	}

	if resp.StatusCode() != 200 {
		return nil, fmt.Errorf("同花顺问财API返回HTTP错误: %d", resp.StatusCode())
	}

	if result.StatusCode != 0 {
		return nil, fmt.Errorf("同花顺问财API返回错误: %s", result.StatusMsg)
	}

	return &result, nil
}

func (api *IwencaiAPI) QueryToMarkdown(query string, page, limit int) string {
	result, err := api.Query(query, page, limit)
	if err != nil {
		logger.SugaredLogger.Errorf("问财查询失败: %v", err)
		return fmt.Sprintf("查询失败: %v", err)
	}

	if len(result.Datas) == 0 {
		return fmt.Sprintf("未查询到「%s」的相关数据。可到同花顺问财查询：https://www.iwencai.com/unifiedwap/chat", query)
	}

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("### 同花顺问财查询结果（%s）\n\n", query))
	sb.WriteString(fmt.Sprintf("共查到 %d 只标的，当前显示第 %d 页（每页 %d 条）\n\n", result.CodeCount, page, limit))

	if len(result.Datas) > 0 {
		first := result.Datas[0]
		headers := make([]string, 0, len(first))
		for k := range first {
			headers = append(headers, k)
		}

		sb.WriteString("| ")
		for _, h := range headers {
			sb.WriteString(h + " | ")
		}
		sb.WriteString("\n| ")
		for range headers {
			sb.WriteString("--- | ")
		}
		sb.WriteString("\n")

		for _, item := range result.Datas {
			sb.WriteString("| ")
			for _, h := range headers {
				val := ""
				if v, ok := item[h]; ok && v != nil {
					val = fmt.Sprintf("%v", v)
				}
				sb.WriteString(val + " | ")
			}
			sb.WriteString("\n")
		}
	}

	sb.WriteString("\n> 数据来源于同花顺问财")
	return sb.String()
}

type IwencaiSearchRequest struct {
	Channels []string `json:"channels"`
	AppID    string   `json:"app_id"`
	Query    string   `json:"query"`
}

type IwencaiSearchResponse struct {
	Data []IwencaiSearchItem `json:"data"`
}

type IwencaiSearchItem struct {
	Title       string `json:"title"`
	Summary     string `json:"summary"`
	URL         string `json:"url"`
	PublishDate string `json:"publish_date"`
}

func (api *IwencaiAPI) searchComprehensive(channel string, query string) (*IwencaiSearchResponse, error) {
	apiKey := api.config.Settings.IwencaiApiKey
	if apiKey == "" {
		return nil, fmt.Errorf("同花顺问财API密钥未配置，请在设置中填写IwencaiApiKey")
	}

	if query == "" {
		return nil, fmt.Errorf("搜索关键词不能为空")
	}

	reqBody := IwencaiSearchRequest{
		Channels: []string{channel},
		AppID:    "AIME_SKILL",
		Query:    query,
	}

	var result IwencaiSearchResponse
	resp, err := api.client.R().
		SetHeaders(iwencaiCommonHeaders(apiKey, "news-search", "1.0.0")).
		SetBody(reqBody).
		SetResult(&result).
		Post(iwencaiSearchURL)

	if err != nil {
		return nil, fmt.Errorf("调用同花顺问财搜索API失败: %v", err)
	}

	if resp.StatusCode() != 200 {
		return nil, fmt.Errorf("同花顺问财搜索API返回HTTP错误: %d", resp.StatusCode())
	}

	return &result, nil
}

func (api *IwencaiAPI) SearchReport(query string) (*IwencaiSearchResponse, error) {
	return api.searchComprehensive("report", query)
}

func (api *IwencaiAPI) SearchNews(query string) (*IwencaiSearchResponse, error) {
	return api.searchComprehensive("news", query)
}

func (api *IwencaiAPI) SearchInvestor(query string) (*IwencaiSearchResponse, error) {
	return api.searchComprehensive("investor", query)
}

func (api *IwencaiAPI) SearchAnnouncement(query string) (*IwencaiSearchResponse, error) {
	return api.searchComprehensive("announcement", query)
}

func searchResultToMarkdown(query string, result *IwencaiSearchResponse, label string) string {
	if len(result.Data) == 0 {
		return fmt.Sprintf("未搜索到「%s」的相关%s。", query, label)
	}

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("### %s搜索结果（%s）\n\n", label, query))
	sb.WriteString(fmt.Sprintf("共找到 %d 条结果\n\n", len(result.Data)))

	for i, item := range result.Data {
		sb.WriteString(fmt.Sprintf("%d. **%s**\n", i+1, item.Title))
		if item.PublishDate != "" {
			sb.WriteString(fmt.Sprintf("   - 发布时间: %s\n", item.PublishDate))
		}
		if item.Summary != "" {
			sb.WriteString(fmt.Sprintf("   - 摘要: %s\n", item.Summary))
		}
		if item.URL != "" {
			sb.WriteString(fmt.Sprintf("   - 链接: %s\n", item.URL))
		}
		sb.WriteString("\n")
	}

	sb.WriteString("> 数据来源于同花顺问财")
	return sb.String()
}

func (api *IwencaiAPI) SearchReportToMarkdown(query string) string {
	result, err := api.SearchReport(query)
	if err != nil {
		logger.SugaredLogger.Errorf("研报搜索失败: %v", err)
		return fmt.Sprintf("搜索失败: %v", err)
	}
	return searchResultToMarkdown(query, result, "研报")
}

func (api *IwencaiAPI) SearchNewsToMarkdown(query string) string {
	result, err := api.SearchNews(query)
	if err != nil {
		logger.SugaredLogger.Errorf("新闻搜索失败: %v", err)
		return fmt.Sprintf("搜索失败: %v", err)
	}
	return searchResultToMarkdown(query, result, "新闻")
}

func (api *IwencaiAPI) SearchInvestorToMarkdown(query string) string {
	result, err := api.SearchInvestor(query)
	if err != nil {
		logger.SugaredLogger.Errorf("投资者关系活动搜索失败: %v", err)
		return fmt.Sprintf("搜索失败: %v", err)
	}
	return searchResultToMarkdown(query, result, "投资者关系活动")
}

func (api *IwencaiAPI) SearchAnnouncementToMarkdown(query string) string {
	result, err := api.SearchAnnouncement(query)
	if err != nil {
		logger.SugaredLogger.Errorf("公告搜索失败: %v", err)
		return fmt.Sprintf("搜索失败: %v", err)
	}
	return searchResultToMarkdown(query, result, "公告")
}
