package data

import (
	"encoding/json"
	"fmt"
	"github.com/duke-git/lancet/v2/convertor"
	"go-stock/backend/logger"
	"regexp"
	"strings"
	"time"
)

type FundKLineApi struct {
	fundApi *FundApi
}

func NewFundKLineApi() *FundKLineApi {
	return &FundKLineApi{
		fundApi: NewFundApi(),
	}
}

type FundKLinePeriod struct {
	Code        string `json:"code"`
	Name        string `json:"name"`
	Description string `json:"description"`
	SupportDay  bool   `json:"supportDay"`
}

var FundKLinePeriods = []FundKLinePeriod{
	{Code: "101", Name: "日K", Description: "日K线", SupportDay: true},
	{Code: "102", Name: "周K", Description: "周K线", SupportDay: true},
	{Code: "103", Name: "月K", Description: "月K线", SupportDay: true},
	{Code: "1", Name: "1分钟", Description: "1分钟K线", SupportDay: false},
	{Code: "5", Name: "5分钟", Description: "5分钟K线", SupportDay: false},
	{Code: "15", Name: "15分钟", Description: "15分钟K线", SupportDay: false},
	{Code: "30", Name: "30分钟", Description: "30分钟K线", SupportDay: false},
	{Code: "60", Name: "60分钟", Description: "60分钟K线", SupportDay: false},
}

var (
	reNetWorthTrend = regexp.MustCompile(`var\s+Data_netWorthTrend\s*=\s*(\[.+?\]);`)
	reACWorthTrend  = regexp.MustCompile(`var\s+Data_ACWorthTrend\s*=\s*(\[.+?\]);`)
)

func (f *FundKLineApi) GetFundKLine(fundCode, klt string, limit int) *KLineSourceResult {
	if IsOnExchangeFund(fundCode) {
		return f.getOnExchangeFundKLine(fundCode, klt, limit)
	}
	return f.getOffExchangeFundKLine(fundCode, klt, limit)
}

func (f *FundKLineApi) GetFundKLineWithFallback(fundCode, klt string, limit int) *KLineSourceResult {
	result := f.GetFundKLine(fundCode, klt, limit)
	if result != nil && result.Data != nil && len(*result.Data) > 0 {
		return result
	}

	if IsOnExchangeFund(fundCode) {
		logger.SugaredLogger.Warnf("场内基金K线所有数据源失败: code=%s klt=%s, 尝试净值K线", fundCode, klt)
		fallback := f.getOffExchangeFundKLine(fundCode, klt, limit)
		if fallback != nil && fallback.Data != nil && len(*fallback.Data) > 0 {
			fallback.Source = fallback.Source + "(净值合成)"
			return fallback
		}
	}

	if result == nil {
		return &KLineSourceResult{Data: &[]KLineData{}, Source: ""}
	}
	return result
}

func (f *FundKLineApi) getOnExchangeFundKLine(fundCode, klt string, limit int) *KLineSourceResult {
	secid := fundKLineSecid(fundCode)
	sinaCode := ""
	if secid != "" {
		parts := strings.Split(secid, ".")
		if len(parts) == 2 {
			if parts[0] == "1" {
				sinaCode = "sh" + parts[1]
			} else {
				sinaCode = "sz" + parts[1]
			}
		}
	}

	if sinaCode != "" {
		sinaResult := fetchFromSina(sinaCode, klt, limit)
		if sinaResult != nil && sinaResult.Data != nil && len(*sinaResult.Data) > 0 {
			sinaResult.Source = "sina(场内)"
			return sinaResult
		}
	}
	logger.SugaredLogger.Warnf("新浪场内基金K线为空，尝试东财: code=%s klt=%s", fundCode, klt)

	emResult := f.fetchOnExchangeFromEastMoney(fundCode, klt, limit)
	if emResult != nil && emResult.Data != nil && len(*emResult.Data) > 0 {
		emResult.Source = "eastmoney(场内)"
		return emResult
	}
	logger.SugaredLogger.Warnf("东财场内基金K线也为空，尝试腾讯: code=%s klt=%s", fundCode, klt)

	if sinaCode != "" {
		tencentResult := fetchFromTencent(sinaCode, klt, limit)
		if tencentResult != nil && tencentResult.Data != nil && len(*tencentResult.Data) > 0 {
			tencentResult.Source = "tencent(场内)"
			return tencentResult
		}
	}
	logger.SugaredLogger.Warnf("腾讯场内基金K线也为空，尝试净值合成: code=%s klt=%s", fundCode, klt)

	return f.getOffExchangeFundKLine(fundCode, klt, limit)
}

func (f *FundKLineApi) fetchOnExchangeFromEastMoney(fundCode, klt string, limit int) *KLineSourceResult {
	secid := fundKLineSecid(fundCode)
	if secid == "" {
		return &KLineSourceResult{Data: &[]KLineData{}}
	}
	api := NewEastMoneyKLineApi(GetSettingConfig())
	data := api.GetKLineDataBefore(secid, klt, "1", limit, "20500101")
	return &KLineSourceResult{Data: data}
}

func (f *FundKLineApi) getOffExchangeFundKLine(fundCode, klt string, limit int) *KLineSourceResult {
	emResult := f.fetchOffExchangeFromEastMoney(fundCode, klt, limit)
	if emResult != nil && emResult.Data != nil && len(*emResult.Data) > 0 {
		emResult.Source = "eastmoney(净值)"
		return emResult
	}
	logger.SugaredLogger.Warnf("东财净值K线为空，尝试pingzhongdata: code=%s klt=%s", fundCode, klt)

	pzResult := f.fetchOffExchangeFromPingZhongData(fundCode, klt, limit)
	if pzResult != nil && pzResult.Data != nil && len(*pzResult.Data) > 0 {
		pzResult.Source = "pingzhongdata(净值)"
		return pzResult
	}

	return &KLineSourceResult{Data: &[]KLineData{}, Source: ""}
}

func (f *FundKLineApi) fetchOffExchangeFromEastMoney(fundCode, klt string, limit int) *KLineSourceResult {
	effectiveKlt := klt
	switch klt {
	case "101", "102", "103":
	default:
		effectiveKlt = "101"
	}

	days := limit
	switch effectiveKlt {
	case "102":
		days = limit * 5
	case "103":
		days = limit * 22
	}

	endDate := time.Now().Format("2006-01-02")
	startDate := time.Now().AddDate(0, 0, -days).Format("2006-01-02")

	history, err := f.fundApi.GetFundHistoryNetValue(fundCode, 1, days, startDate, endDate)
	if err != nil {
		logger.SugaredLogger.Warnf("获取基金历史净值失败: %v", err)
		return &KLineSourceResult{Data: &[]KLineData{}}
	}

	var klines []KLineData
	for _, item := range history {
		klines = append(klines, KLineData{
			Day:           item.Date,
			Open:          fmt.Sprintf("%.4f", item.NetValue),
			Close:         fmt.Sprintf("%.4f", item.NetValue),
			High:          fmt.Sprintf("%.4f", item.NetValue),
			Low:           fmt.Sprintf("%.4f", item.NetValue),
			Volume:        "0",
			Amount:        "0",
			ChangePercent: fmt.Sprintf("%.2f", item.DailyGrowth),
			ChangeValue:   "0",
			Amplitude:     "0",
			TurnoverRate:  "0",
		})
	}

	if effectiveKlt != "101" && len(klines) > 0 {
		klines = f.aggregateKLineByPeriod(klines, effectiveKlt)
	}

	if limit > 0 && len(klines) > limit {
		klines = klines[len(klines)-limit:]
	}

	return &KLineSourceResult{Data: &klines}
}

func (f *FundKLineApi) fetchOffExchangeFromPingZhongData(fundCode, klt string, limit int) *KLineSourceResult {
	effectiveKlt := klt
	switch klt {
	case "101", "102", "103":
	default:
		effectiveKlt = "101"
	}

	url := fmt.Sprintf("http://fund.eastmoney.com/pingzhongdata/%s.js", fundCode)
	resp, err := f.fundApi.client.R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", fmt.Sprintf("http://fund.eastmoney.com/%s.html", fundCode)).
		Get(url)
	if err != nil || resp.StatusCode() != 200 {
		return &KLineSourceResult{Data: &[]KLineData{}}
	}

	body := string(resp.Body())
	var klines []KLineData

	if reNetWorthTrend.MatchString(body) {
		m := reNetWorthTrend.FindStringSubmatch(body)
		if len(m) > 1 {
			var dataItems [][]interface{}
			if err := json.Unmarshal([]byte(m[1]), &dataItems); err == nil {
				for _, item := range dataItems {
					if len(item) < 2 {
						continue
					}
					timestamp, ok := item[0].(float64)
					if !ok {
						continue
					}
					value, ok := item[1].(float64)
					if !ok {
						continue
					}
					date := time.Unix(int64(timestamp)/1000, 0).Format("2006-01-02")

					var growth float64
					if len(item) >= 3 {
						if g, ok := item[2].(float64); ok {
							growth = g
						}
					}

					klines = append(klines, KLineData{
						Day:           date,
						Open:          fmt.Sprintf("%.4f", value),
						Close:         fmt.Sprintf("%.4f", value),
						High:          fmt.Sprintf("%.4f", value),
						Low:           fmt.Sprintf("%.4f", value),
						Volume:        "0",
						Amount:        "0",
						ChangePercent: fmt.Sprintf("%.2f", growth),
						ChangeValue:   "0",
						Amplitude:     "0",
						TurnoverRate:  "0",
					})
				}
			}
		}
	}

	if len(klines) == 0 && reACWorthTrend.MatchString(body) {
		m := reACWorthTrend.FindStringSubmatch(body)
		if len(m) > 1 {
			var dataItems [][]interface{}
			if err := json.Unmarshal([]byte(m[1]), &dataItems); err == nil {
				for _, item := range dataItems {
					if len(item) < 2 {
						continue
					}
					timestamp, ok := item[0].(float64)
					if !ok {
						continue
					}
					value, ok := item[1].(float64)
					if !ok {
						continue
					}
					date := time.Unix(int64(timestamp)/1000, 0).Format("2006-01-02")
					klines = append(klines, KLineData{
						Day:    date,
						Open:   fmt.Sprintf("%.4f", value),
						Close:  fmt.Sprintf("%.4f", value),
						High:   fmt.Sprintf("%.4f", value),
						Low:    fmt.Sprintf("%.4f", value),
						Volume: "0",
						Amount: "0",
					})
				}
			}
		}
	}

	if effectiveKlt != "101" && len(klines) > 0 {
		klines = f.aggregateKLineByPeriod(klines, effectiveKlt)
	}

	if limit > 0 && len(klines) > limit {
		klines = klines[len(klines)-limit:]
	}

	return &KLineSourceResult{Data: &klines}
}

func (f *FundKLineApi) aggregateKLineByPeriod(dailyKlines []KLineData, klt string) []KLineData {
	if len(dailyKlines) == 0 {
		return dailyKlines
	}

	switch klt {
	case "102":
		return f.aggregateToWeek(dailyKlines)
	case "103":
		return f.aggregateToMonth(dailyKlines)
	default:
		return dailyKlines
	}
}

func (f *FundKLineApi) aggregateToWeek(dailyKlines []KLineData) []KLineData {
	var result []KLineData
	var weekData *KLineData
	var currentWeek string

	for _, kd := range dailyKlines {
		t, err := time.Parse("2006-01-02", kd.Day)
		if err != nil {
			continue
		}
		_, week := t.ISOWeek()
		weekKey := fmt.Sprintf("%d-W%02d", t.Year(), week)

		if weekKey != currentWeek {
			if weekData != nil {
				result = append(result, *weekData)
			}
			weekData = &KLineData{
				Day:    kd.Day,
				Open:   kd.Open,
				Close:  kd.Close,
				High:   kd.High,
				Low:    kd.Low,
				Volume: kd.Volume,
				Amount: kd.Amount,
			}
			currentWeek = weekKey
		} else {
			if weekData == nil {
				continue
			}
			weekData.Close = kd.Close
			if compareFloatStr(kd.High, weekData.High) > 0 {
				weekData.High = kd.High
			}
			if compareFloatStr(kd.Low, weekData.Low) < 0 && kd.Low != "0" {
				weekData.Low = kd.Low
			}
		}
	}
	if weekData != nil {
		result = append(result, *weekData)
	}
	return result
}

func (f *FundKLineApi) aggregateToMonth(dailyKlines []KLineData) []KLineData {
	var result []KLineData
	var monthData *KLineData
	var currentMonth string

	for _, kd := range dailyKlines {
		t, err := time.Parse("2006-01-02", kd.Day)
		if err != nil {
			continue
		}
		monthKey := fmt.Sprintf("%d-%02d", t.Year(), t.Month())

		if monthKey != currentMonth {
			if monthData != nil {
				result = append(result, *monthData)
			}
			monthData = &KLineData{
				Day:    kd.Day,
				Open:   kd.Open,
				Close:  kd.Close,
				High:   kd.High,
				Low:    kd.Low,
				Volume: kd.Volume,
				Amount: kd.Amount,
			}
			currentMonth = monthKey
		} else {
			if monthData == nil {
				continue
			}
			monthData.Close = kd.Close
			if compareFloatStr(kd.High, monthData.High) > 0 {
				monthData.High = kd.High
			}
			if compareFloatStr(kd.Low, monthData.Low) < 0 && kd.Low != "0" {
				monthData.Low = kd.Low
			}
		}
	}
	if monthData != nil {
		result = append(result, *monthData)
	}
	return result
}

func compareFloatStr(a, b string) int {
	fa, errA := convertor.ToFloat(a)
	fb, errB := convertor.ToFloat(b)
	if errA != nil || errB != nil {
		return 0
	}
	if fa > fb {
		return 1
	} else if fa < fb {
		return -1
	}
	return 0
}
