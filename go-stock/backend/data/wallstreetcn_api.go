package data

import (
	"encoding/json"
	"fmt"
	"go-stock/backend/db"
	"go-stock/backend/logger"
	"go-stock/backend/models"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/go-resty/resty/v2"
	"github.com/tidwall/gjson"
)

type WallstreetcnApi struct {
}

func NewWallstreetcnApi() *WallstreetcnApi {
	return &WallstreetcnApi{}
}

type WSCNLivesRequest struct {
	Channel   string `json:"channel"`
	Limit     int    `json:"limit"`
	Cursor    string `json:"cursor,omitempty"`
	FirstPage bool   `json:"first_page,omitempty"`
	Accept    string `json:"accept,omitempty"`
}

type WSCNLiveItem struct {
	ID          int64  `json:"id"`
	Type        string `json:"type"`
	Title       string `json:"title"`
	Content     string `json:"content"`
	ContentText string `json:"content_text"`
	DisplayTime int64  `json:"display_time"`
	Uri         string `json:"uri"`
	IsCalendar  bool   `json:"is_calendar"`
	Score       int    `json:"score"`
	CalendarKey string `json:"calendar_key,omitempty"`
	WscnTicker  string `json:"wscn_ticker,omitempty"`

	Author struct {
		DisplayName string `json:"display_name"`
		Avatar      string `json:"avatar"`
		ID          int64  `json:"id"`
	} `json:"author"`

	Channels []string `json:"channels"`
	Images   []struct {
		URI    string `json:"uri"`
		Width  int    `json:"width"`
		Height int    `json:"height"`
	} `json:"images"`

	Article *struct {
		ID    int64  `json:"id"`
		Title string `json:"title"`
		Image struct {
			URI    string `json:"uri"`
			Width  int    `json:"width"`
			Height int    `json:"height"`
		} `json:"image"`
		Platforms []string `json:"platforms"`
		Uri       string   `json:"uri"`
	} `json:"article"`

	Symbols []any `json:"symbols"`
	Tags    []any `json:"tags"`
}

type WSCNLivesResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    struct {
		Items         []WSCNLiveItem `json:"items"`
		NextCursor    string         `json:"next_cursor"`
		OpCursor      string         `json:"op_cursor"`
		PollingCursor string         `json:"polling_cursor"`
	} `json:"data"`
}

type WSCNMarketRealResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    struct {
		Fields   []string         `json:"fields"`
		Snapshot map[string][]any `json:"snapshot"`
	} `json:"data"`
}

type WSCNKlineResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    struct {
		Candle map[string]struct {
			Lines [][]float64 `json:"lines"`
		} `json:"candle"`
	} `json:"data"`
}

type WSCNCalendarResponse struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    struct {
		Items      []WSCNCalendarItem `json:"items"`
		NextCursor int64              `json:"next_cursor"`
		TotalCount int                `json:"total_count"`
	} `json:"data"`
}

type WSCNCalendarItem struct {
	ID              int64  `json:"id"`
	PublicDate      int64  `json:"public_date"`
	Country         string `json:"country"`
	CountryID       string `json:"country_id"`
	Title           string `json:"title"`
	Event           string `json:"event"`
	Importance      int    `json:"importance"`
	Actual          string `json:"actual"`
	Forecast        string `json:"forecast"`
	Previous        string `json:"previous"`
	Revised         string `json:"revised"`
	Period          string `json:"period"`
	WscnTicker      string `json:"wscn_ticker"`
	FlagURI         string `json:"flag_uri"`
	CalendarType    string `json:"calendar_type"`
	Assets          string `json:"assets"`
	ObservationDate string `json:"observation_date"`
}

var WSCNChannels = map[string]string{
	"global-channel":    "全球7x24",
	"a-stock-channel":   "A股",
	"us-stock-channel":  "美股",
	"hk-stock-channel":  "港股",
	"forex-channel":     "外汇",
	"commodity-channel": "商品",
	"goldc-channel":     "黄金",
	"oil-channel":       "原油",
	"bond-channel":      "债券",
	"crypto-channel":    "加密货币",
	"xgb-channel":       "新股",
}

var WSCNProdCodes = map[string]string{
	"DXY.OTC":    "美元指数",
	"EURUSD.OTC": "欧元/美元",
	"USDJPY.OTC": "美元/日元",
	"USDCNH.OTC": "离岸人民币",
	"XAUUSD.OTC": "现货黄金",
	"USCL.OTC":   "WTI原油",
	"515250.SS":  "智能汽车ETF富国",
	"510300.SS":  "沪深300ETF",
	"510050.SS":  "上证50ETF",
	"159915.SZ":  "创业板ETF",
	"588000.SS":  "科创50ETF",
}

const (
	WSCNBaseURL        = "https://api-one-wscn.awtmt.com/apiv1"
	WSCNMarketDataURL  = "https://api-ddc-wscn.awtmt.com"
	WSCNDefaultUA      = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
	WSCNDefaultReferer = "https://wallstreetcn.com/"
)

func (w WallstreetcnApi) newClient(timeout time.Duration) *resty.Request {
	return resty.New().SetTimeout(timeout).R().
		SetHeader("User-Agent", WSCNDefaultUA).
		SetHeader("Referer", WSCNDefaultReferer).
		SetHeader("Accept", "application/json").
		SetHeader("x-client-type", "pc").
		SetHeader("x-ivanka-app", "wscn|web|0.40.40|0.0|0")
}

func (w WallstreetcnApi) GetLives(channel string, limit int, cursor string) *WSCNLivesResponse {
	if limit <= 0 {
		limit = 20
	}
	if limit > 50 {
		limit = 50
	}
	if _, ok := WSCNChannels[channel]; !ok {
		channel = "global-channel"
	}

	url := fmt.Sprintf("%s/content/lives?channel=%s&client=pc&limit=%d", WSCNBaseURL, channel, limit)
	if cursor != "" {
		url += "&cursor=" + cursor
	} else {
		url += "&first_page=true"
	}
	url += "&accept=live,vip-live"

	result := &WSCNLivesResponse{}
	resp, err := w.newClient(15 * time.Second).SetResult(result).Get(url)
	if err != nil {
		logger.SugaredLogger.Errorf("WallstreetcnApi GetLives error: %v", err)
		return nil
	}
	if resp.StatusCode() != 200 || result.Code != 20000 {
		logger.SugaredLogger.Errorf("WallstreetcnApi GetLives status=%d code=%d msg=%s", resp.StatusCode(), result.Code, result.Message)
		return nil
	}
	return result
}

func (w WallstreetcnApi) GetLivesAsTelegraph(channel string, limit int) *[]models.Telegraph {
	resp := w.GetLives(channel, limit, "")
	if resp == nil {
		return &[]models.Telegraph{}
	}

	var telegraphs []models.Telegraph
	channelName := WSCNChannels[channel]
	if channelName == "" {
		channelName = "华尔街见闻"
	}
	source := "华尔街见闻-" + channelName

	for _, item := range resp.Data.Items {
		dataTime := time.Unix(item.DisplayTime, 0).Local()
		content := item.ContentText
		if content == "" {
			content = strings.ReplaceAll(item.Content, "<p>", "")
			content = strings.ReplaceAll(content, "</p>", "\n")
			content = strings.ReplaceAll(content, "<strong>", "")
			content = strings.ReplaceAll(content, "</strong>", "")
			content = strings.TrimSpace(content)
		}
		if content == "" {
			continue
		}

		telegraph := models.Telegraph{
			Title:           item.Title,
			Content:         content,
			Time:            dataTime.Format("15:04:05"),
			DataTime:        &dataTime,
			Url:             item.Uri,
			Source:          source,
			IsRed:           item.Score > 1 || item.IsCalendar,
			SentimentResult: AnalyzeSentiment(content).Description,
		}

		cnt := int64(0)
		if telegraph.Title == "" {
			db.Dao.Model(telegraph).Where("content=?", telegraph.Content).Count(&cnt)
		} else {
			db.Dao.Model(telegraph).Where("title=?", telegraph.Title).Count(&cnt)
		}
		if cnt > 0 {
			continue
		}
		telegraphs = append(telegraphs, telegraph)
		db.Dao.Model(&models.Telegraph{}).Create(&telegraph)
	}
	return &telegraphs
}

func (w WallstreetcnApi) GetLivesReadable(channel string, limit int) string {
	resp := w.GetLives(channel, limit, "")
	if resp == nil || len(resp.Data.Items) == 0 {
		return "暂无快讯数据"
	}

	channelName := WSCNChannels[channel]
	if channelName == "" {
		channelName = "全球7x24"
	}

	var md strings.Builder
	md.WriteString(fmt.Sprintf("### 华尔街见闻 · %s快讯（%d条）\r\n\r\n", channelName, len(resp.Data.Items)))

	for i, item := range resp.Data.Items {
		dataTime := time.Unix(item.DisplayTime, 0).Local()
		content := item.ContentText
		if content == "" {
			content = strings.ReplaceAll(item.Content, "<p>", "")
			content = strings.ReplaceAll(content, "</p>", "\n")
			content = strings.ReplaceAll(content, "<strong>", "**")
			content = strings.ReplaceAll(content, "</strong>", "**")
			content = strings.TrimSpace(content)
		}

		prefix := ""
		if item.Score > 1 || item.IsCalendar {
			prefix = "🔴 "
		}

		md.WriteString(fmt.Sprintf("%d. %s**%s** %s\r\n", i+1, prefix, dataTime.Format("15:04:05"), content))

		if item.Title != "" {
			md.WriteString(fmt.Sprintf("   > %s\r\n", item.Title))
		}

		if item.Article != nil && item.Article.Title != "" {
			md.WriteString(fmt.Sprintf("   📎 [%s](%s)\r\n", item.Article.Title, item.Article.Uri))
		}

		var channelTags []string
		for _, ch := range item.Channels {
			if name, ok := WSCNChannels[ch]; ok && ch != channel {
				channelTags = append(channelTags, name)
			}
		}
		if len(channelTags) > 0 {
			md.WriteString(fmt.Sprintf("   📂 %s\r\n", strings.Join(channelTags, "、")))
		}
		md.WriteString("\r\n")
	}

	return md.String()
}

func (w WallstreetcnApi) GetMarketReal(prodCodes []string, fields []string) *WSCNMarketRealResponse {
	if len(prodCodes) == 0 {
		prodCodes = []string{"DXY.OTC", "EURUSD.OTC", "USDJPY.OTC", "XAUUSD.OTC", "USCL.OTC", "USDCNH.OTC"}
	}
	if len(fields) == 0 {
		fields = []string{"prod_name", "last_px", "px_change", "px_change_rate", "price_precision", "securities_type"}
	}

	url := fmt.Sprintf("%s/market/real?prod_code=%s&fields=%s",
		WSCNMarketDataURL,
		strings.Join(prodCodes, ","),
		strings.Join(fields, ","),
	)

	result := &WSCNMarketRealResponse{}
	resp, err := w.newClient(10 * time.Second).SetResult(result).Get(url)
	if err != nil {
		logger.SugaredLogger.Errorf("WallstreetcnApi GetMarketReal error: %v", err)
		return nil
	}
	if resp.StatusCode() != 200 || result.Code != 20000 {
		logger.SugaredLogger.Errorf("WallstreetcnApi GetMarketReal status=%d code=%d msg=%s", resp.StatusCode(), result.Code, result.Message)
		return nil
	}
	return result
}

func (w WallstreetcnApi) GetMarketRealReadable(prodCodes []string) string {
	result := w.GetMarketReal(prodCodes, nil)
	if result == nil || len(result.Data.Snapshot) == 0 {
		return "暂无行情数据"
	}

	var md strings.Builder
	md.WriteString("### 华尔街见闻 · 全球行情\r\n\r\n")
	md.WriteString("| 品种 | 最新价 | 涨跌额 | 涨跌幅 |\r\n")
	md.WriteString("|------|--------|--------|--------|\r\n")

	type row struct {
		name      string
		lastPx    string
		pxChange  string
		pxChgRate string
	}
	var rows []row

	for code, values := range result.Data.Snapshot {
		if len(values) < 4 {
			continue
		}
		name := fmt.Sprintf("%v", values[0])
		lastPxVal, _ := strconv.ParseFloat(fmt.Sprintf("%v", values[1]), 64)
		pxChangeVal, _ := strconv.ParseFloat(fmt.Sprintf("%v", values[2]), 64)
		pxChgRateVal, _ := strconv.ParseFloat(fmt.Sprintf("%v", values[3]), 64)

		precision := 2
		if len(values) > 4 {
			if p, err := strconv.Atoi(fmt.Sprintf("%v", values[4])); err == nil && p > 0 {
				precision = p
			}
		}

		lastPx := fmt.Sprintf("%.*f", precision, lastPxVal)
		pxChange := fmt.Sprintf("%+.*f", precision, pxChangeVal)
		pxChgRate := fmt.Sprintf("%+.2f%%", pxChgRateVal)

		displayName := name
		if cnName, ok := WSCNProdCodes[code]; ok {
			displayName = cnName
		}

		rows = append(rows, row{displayName, lastPx, pxChange, pxChgRate})
	}

	sort.Slice(rows, func(i, j int) bool {
		return rows[i].name < rows[j].name
	})

	for _, r := range rows {
		md.WriteString(fmt.Sprintf("| %s | %s | %s | %s |\r\n", r.name, r.lastPx, r.pxChange, r.pxChgRate))
	}

	return md.String()
}

// GetKline 获取K线数据
// prodCode: 产品代码，如 XAUUSD.OTC、DXY.OTC 等，详见 WSCNProdCodes
// periodType: K线周期（秒），支持: 60(1分钟)、300(5分钟)、900(15分钟)、1800(30分钟)、3600(1小时)、7200(2小时)、14400(4小时)、86400(日线)
// tickCount: 返回数据条数
// fields: 返回字段，默认 tick_at,open_px,close_px,high_px,low_px
func (w WallstreetcnApi) GetKline(prodCode string, periodType int, tickCount int, fields []string) *WSCNKlineResponse {
	if prodCode == "" {
		prodCode = "XAUUSD.OTC"
	}
	if periodType <= 0 {
		periodType = 300
	}
	if tickCount <= 0 {
		tickCount = 256
	}
	if len(fields) == 0 {
		fields = []string{"tick_at", "open_px", "close_px", "high_px", "low_px"}
	}

	url := fmt.Sprintf("%s/market/kline?prod_code=%s&period_type=%d&tick_count=%d&fields=%s",
		WSCNMarketDataURL,
		prodCode,
		periodType,
		tickCount,
		strings.Join(fields, ","),
	)

	result := &WSCNKlineResponse{}
	resp, err := w.newClient(10 * time.Second).SetResult(result).Get(url)
	if err != nil {
		logger.SugaredLogger.Errorf("WallstreetcnApi GetKline error: %v", err)
		return nil
	}
	if resp.StatusCode() != 200 || result.Code != 20000 {
		logger.SugaredLogger.Errorf("WallstreetcnApi GetKline status=%d code=%d msg=%s", resp.StatusCode(), result.Code, result.Message)
		return nil
	}
	return result
}

func (w WallstreetcnApi) GetKlineReadable(prodCode string, periodType int, limit int) string {
	result := w.GetKline(prodCode, periodType, limit, nil)
	if result == nil {
		return "暂无K线数据"
	}

	cnName := prodCode
	if name, ok := WSCNProdCodes[prodCode]; ok {
		cnName = name
	}

	periodDesc := map[int]string{
		60:    "1分钟",
		300:   "5分钟",
		900:   "15分钟",
		1800:  "30分钟",
		3600:  "1小时",
		7200:  "2小时",
		14400: "4小时",
		86400: "日线",
	}
	periodName := strconv.Itoa(periodType)
	if desc, ok := periodDesc[periodType]; ok {
		periodName = desc
	}

	var md strings.Builder
	md.WriteString(fmt.Sprintf("### %s %sK线数据\r\n\r\n", cnName, periodName))
	md.WriteString("| 时间 | 开盘 | 收盘 | 最高 | 最低 |\r\n")
	md.WriteString("|------|------|------|------|------|\r\n")

	candleData, ok := result.Data.Candle[prodCode]
	if !ok {
		for _, v := range result.Data.Candle {
			candleData = v
			break
		}
	}

	for _, line := range candleData.Lines {
		if len(line) < 5 {
			continue
		}
		t := time.Unix(int64(line[4]), 0).Local().Format("01-02 15:04")
		md.WriteString(fmt.Sprintf("| %s | %.2f | %.2f | %.2f | %.2f |\r\n", t, line[0], line[1], line[2], line[3]))
	}

	return md.String()
}

func (w WallstreetcnApi) GetCalendar(startTime, endTime int64, limit int) *WSCNCalendarResponse {
	if limit <= 0 {
		limit = 20
	}
	if limit > 50 {
		limit = 50
	}
	if startTime == 0 {
		startTime = time.Now().Unix()
	}
	if endTime == 0 {
		endTime = time.Now().Add(7 * 24 * time.Hour).Unix()
	}

	url := fmt.Sprintf("%s/finance/indicator/search?start_time=%d&end_time=%d&limit=%d",
		WSCNBaseURL, startTime, endTime, limit)

	result := &WSCNCalendarResponse{}
	resp, err := w.newClient(10 * time.Second).SetResult(result).Get(url)
	if err != nil {
		logger.SugaredLogger.Errorf("WallstreetcnApi GetCalendar error: %v", err)
		return nil
	}
	if resp.StatusCode() != 200 || result.Code != 20000 {
		logger.SugaredLogger.Errorf("WallstreetcnApi GetCalendar status=%d code=%d msg=%s", resp.StatusCode(), result.Code, result.Message)
		return nil
	}
	return result
}

func (w WallstreetcnApi) GetCalendarReadable(days int) string {
	if days <= 0 {
		days = 3
	}
	startTime := time.Now().Unix()
	endTime := time.Now().Add(time.Duration(days) * 24 * time.Hour).Unix()

	result := w.GetCalendar(startTime, endTime, 30)
	if result == nil || len(result.Data.Items) == 0 {
		return "暂无财经日历数据"
	}

	var md strings.Builder
	md.WriteString(fmt.Sprintf("### 华尔街见闻 · 财经日历（未来%d天）\r\n\r\n", days))
	md.WriteString("| 时间 | 国家 | 事件 | 重要性 | 前值 | 预期 | 实际 |\r\n")
	md.WriteString("|------|------|------|--------|------|------|------|\r\n")

	for _, item := range result.Data.Items {
		t := time.Unix(item.PublicDate, 0).Local().Format("01-02 15:04")
		importance := ""
		for i := 0; i < item.Importance; i++ {
			importance += "⭐"
		}
		actual := item.Actual
		if actual == "" {
			actual = "待公布"
		}

		md.WriteString(fmt.Sprintf("| %s | %s | %s | %s | %s | %s | %s |\r\n",
			t, item.Country, item.Event, importance, item.Previous, item.Forecast, actual))
	}

	return md.String()
}

func (w WallstreetcnApi) SearchNews(query string, page, pageSize int) string {
	if page <= 0 {
		page = 1
	}
	if pageSize <= 0 {
		pageSize = 20
	}

	url := fmt.Sprintf("%s/search/search?keyword=%s&page=%d&pageSize=%d",
		strings.Replace(WSCNBaseURL, "api-one", "search-open-api", 1),
		query, page, pageSize)

	client := resty.New().SetTimeout(15*time.Second).R().
		SetHeader("User-Agent", WSCNDefaultUA).
		SetHeader("Accept", "application/json")

	resp, err := client.Get(url)
	if err != nil {
		logger.SugaredLogger.Errorf("WallstreetcnApi SearchNews error: %v", err)
		return "搜索失败"
	}

	var result map[string]any
	if err := json.Unmarshal(resp.Body(), &result); err != nil {
		return string(resp.Body())
	}

	return gjson.GetBytes(resp.Body(), "data").String()
}
