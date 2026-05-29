package data

import (
	"encoding/json"
	"fmt"
	"go-stock/backend/db"
	"go-stock/backend/logger"
	"math"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/duke-git/lancet/v2/convertor"
	"github.com/duke-git/lancet/v2/mathutil"
	"github.com/duke-git/lancet/v2/strutil"
	"github.com/go-resty/resty/v2"

	"github.com/PuerkitoBio/goquery"
	"gorm.io/gorm"
)

type FundApi struct {
	client *resty.Client
	config *SettingConfig
}

func NewFundApi() *FundApi {
	return &FundApi{
		client: SharedHTTPClient,
		config: GetSettingConfig(),
	}
}

type FollowedFund struct {
	gorm.Model
	Code string `json:"code" gorm:"index"`
	Name string `json:"name"`

	NetUnitValue     *float64 `json:"netUnitValue"`
	NetUnitValueDate string   `json:"netUnitValueDate"`
	NetEstimatedUnit *float64 `json:"netEstimatedUnit"`
	NetEstimatedTime string   `json:"netEstimatedUnitTime"`
	NetAccumulated   *float64 `json:"netAccumulated"`

	NetEstimatedRate *float64 `json:"netEstimatedRate"`

	NetUnitValuePrev *float64 `json:"netUnitValuePrev"`
	NetActualRate    *float64 `json:"netActualRate"`

	FundBasic FundBasic `json:"fundBasic" gorm:"foreignKey:Code;references:Code"`
}

func (FollowedFund) TableName() string {
	return "followed_fund"
}

type FundBasic struct {
	gorm.Model
	Code           string `json:"code" gorm:"index"`
	Name           string `json:"name"`
	FullName       string `json:"fullName"`
	Type           string `json:"type"`
	Establishment  string `json:"establishment"`
	Scale          string `json:"scale"`
	Company        string `json:"company"`
	Manager        string `json:"manager"`
	Rating         string `json:"rating"`
	TrackingTarget string `json:"trackingTarget"`

	NetUnitValue     *float64 `json:"netUnitValue"`
	NetUnitValueDate string   `json:"netUnitValueDate"`
	NetEstimatedUnit *float64 `json:"netEstimatedUnit"`
	NetEstimatedTime string   `json:"netEstimatedUnitTime"`
	NetAccumulated   *float64 `json:"netAccumulated"`

	NetGrowth1   *float64 `json:"netGrowth1"`
	NetGrowth3   *float64 `json:"netGrowth3"`
	NetGrowth6   *float64 `json:"netGrowth6"`
	NetGrowth12  *float64 `json:"netGrowth12"`
	NetGrowth36  *float64 `json:"netGrowth36"`
	NetGrowth60  *float64 `json:"netGrowth60"`
	NetGrowthYTD *float64 `json:"netGrowthYTD"`
	NetGrowthAll *float64 `json:"netGrowthAll"`
}

func (FundBasic) TableName() string {
	return "fund_basic"
}

func (f *FundApi) CrawlFundBasic(fundCode string) (*FundBasic, error) {
	defer func() {
		if r := recover(); r != nil {
			logger.SugaredLogger.Errorf("CrawlFundBasic panic: %v", r)
		}
	}()

	fund, err := f.crawlFundBasicViaHTML(fundCode)
	if err != nil {
		logger.SugaredLogger.Warnf("crawlFundBasicViaHTML failed for %s: %v, trying pingzhongdata fallback", fundCode, err)
		fund, err = f.crawlFundBasicViaPingZhongData(fundCode)
		if err != nil {
			return nil, fmt.Errorf("所有数据源获取基金基本信息失败: %w", err)
		}
	}

	if fund.NetUnitValue == nil {
		f.crawlFundNetValueViaAPI(fund, fundCode)
	}

	count := int64(0)
	db.Dao.Model(fund).Where("code=?", fund.Code).Count(&count)
	if count == 0 {
		db.Dao.Create(fund)
	} else {
		db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
	}

	return fund, nil
}

func (f *FundApi) crawlFundBasicViaHTML(fundCode string) (*FundBasic, error) {
	url := fmt.Sprintf("http://fund.eastmoney.com/%s.html", fundCode)
	resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8").
		SetHeader("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8").
		SetHeader("Referer", "http://fund.eastmoney.com/").
		Get(url)
	if err != nil {
		return nil, fmt.Errorf("HTTP请求失败: %w", err)
	}
	if resp.StatusCode() != 200 {
		return nil, fmt.Errorf("HTTP状态码: %d", resp.StatusCode())
	}

	htmlContent := string(resp.Body())
	if strings.Contains(htmlContent, "抱歉，您查找的基金不存在") || len(htmlContent) < 500 {
		return nil, fmt.Errorf("基金不存在或页面内容过短")
	}

	doc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlContent))
	if err != nil {
		return nil, fmt.Errorf("HTML解析失败: %w", err)
	}

	fund := &FundBasic{Code: fundCode}

	name := doc.Find(".merchandiseDetail .fundDetail-tit").First().Text()
	fund.Name = strings.TrimSpace(strutil.ReplaceWithMap(name, map[string]string{
		"查看相关ETF联接>": "",
		"查看相关ETF>":   "",
	}))

	doc.Find(".infoOfFund table td").Each(func(i int, s *goquery.Selection) {
		text := strutil.RemoveWhiteSpace(s.Text(), true)
		defer func() {
			if r := recover(); r != nil {
			}
		}()
		splitEx := strutil.SplitEx(text, "：", true)
		if len(splitEx) < 2 {
			return
		}
		if strutil.ContainsAny(text, []string{"基金类型", "类型"}) {
			fund.Type = splitEx[1]
		}
		if strutil.ContainsAny(text, []string{"成立日期", "成立日"}) {
			fund.Establishment = splitEx[1]
		}
		if strutil.ContainsAny(text, []string{"基金规模", "规模"}) {
			fund.Scale = splitEx[1]
		}
		if strutil.ContainsAny(text, []string{"管理人", "基金公司"}) {
			fund.Company = splitEx[1]
		}
		if strutil.ContainsAny(text, []string{"基金经理", "经理人"}) {
			fund.Manager = splitEx[1]
		}
		if strutil.ContainsAny(text, []string{"基金评级", "评级"}) {
			fund.Rating = splitEx[1]
		}
		if strutil.ContainsAny(text, []string{"跟踪标的", "标的"}) {
			fund.TrackingTarget = splitEx[1]
		}
	})

	doc.Find(".dataOfFund dl > dd").Each(func(i int, s *goquery.Selection) {
		text := strutil.RemoveWhiteSpace(s.Text(), true)
		defer func() {
			if r := recover(); r != nil {
			}
		}()
		splitEx := strutil.SplitAndTrim(text, "：", "%")
		if len(splitEx) < 2 {
			return
		}
		toFloat, err1 := convertor.ToFloat(splitEx[1])
		if err1 != nil {
			return
		}
		if strutil.ContainsAny(text, []string{"近1月"}) {
			fund.NetGrowth1 = &toFloat
		}
		if strutil.ContainsAny(text, []string{"近3月"}) {
			fund.NetGrowth3 = &toFloat
		}
		if strutil.ContainsAny(text, []string{"近6月"}) {
			fund.NetGrowth6 = &toFloat
		}
		if strutil.ContainsAny(text, []string{"近1年"}) {
			fund.NetGrowth12 = &toFloat
		}
		if strutil.ContainsAny(text, []string{"近3年"}) {
			fund.NetGrowth36 = &toFloat
		}
		if strutil.ContainsAny(text, []string{"近5年"}) {
			fund.NetGrowth60 = &toFloat
		}
		if strutil.ContainsAny(text, []string{"今年来"}) {
			fund.NetGrowthYTD = &toFloat
		}
		if strutil.ContainsAny(text, []string{"成立来"}) {
			fund.NetGrowthAll = &toFloat
		}
	})

	f.setGrowthFromTable(doc, "#increaseAmount_stage table", fund)
	f.setGrowthFromTable(doc, ".dataOfFund table", fund)

	return fund, nil
}

func (f *FundApi) setGrowthFromTable(doc *goquery.Document, selector string, fund *FundBasic) {
	table := doc.Find(selector)
	if table.Length() == 0 {
		return
	}
	rows := table.Find("tr")
	if rows.Length() < 2 {
		return
	}

	var headers []string
	rows.Eq(0).Find("th").Each(func(_ int, th *goquery.Selection) {
		headers = append(headers, strutil.RemoveWhiteSpace(th.Text(), true))
	})

	rows.Each(func(rowIndex int, row *goquery.Selection) {
		if rowIndex == 0 {
			return
		}
		tds := row.Find("td")
		if tds.Length() == 0 {
			return
		}
		firstTd := strutil.RemoveWhiteSpace(tds.Eq(0).Text(), true)
		if !strutil.ContainsAny(firstTd, []string{"阶段涨幅", "涨幅"}) {
			return
		}
		for j := 1; j < len(headers) && j < tds.Length(); j++ {
			header := headers[j]
			valText := strutil.RemoveWhiteSpace(tds.Eq(j).Text(), true)
			valText = strings.TrimSuffix(valText, "%")
			toFloat, err := convertor.ToFloat(valText)
			if err != nil {
				continue
			}
			if strings.Contains(header, "近1月") && fund.NetGrowth1 == nil {
				fund.NetGrowth1 = &toFloat
			} else if strings.Contains(header, "近3月") && fund.NetGrowth3 == nil {
				fund.NetGrowth3 = &toFloat
			} else if strings.Contains(header, "近6月") && fund.NetGrowth6 == nil {
				fund.NetGrowth6 = &toFloat
			} else if strings.Contains(header, "近1年") && fund.NetGrowth12 == nil {
				fund.NetGrowth12 = &toFloat
			} else if strings.Contains(header, "近3年") && fund.NetGrowth36 == nil {
				fund.NetGrowth36 = &toFloat
			} else if strings.Contains(header, "近5年") && fund.NetGrowth60 == nil {
				fund.NetGrowth60 = &toFloat
			} else if strings.Contains(header, "今年来") && fund.NetGrowthYTD == nil {
				fund.NetGrowthYTD = &toFloat
			} else if strings.Contains(header, "成立来") && fund.NetGrowthAll == nil {
				fund.NetGrowthAll = &toFloat
			}
		}
		return
	})
}

var (
	reFSName      = regexp.MustCompile(`var\s+fS_name\s*=\s*"([^"]*)"`)
	reFSCode      = regexp.MustCompile(`var\s+fS_code\s*=\s*"([^"]*)"`)
	rePerformance = regexp.MustCompile(`var\s+Data_performance\s*=\s*(\{.+?\});`)
	reFundManager = regexp.MustCompile(`var\s+Data_currentFundManager\s*=\s*(\[.+?\]);`)
	reFluctuation = regexp.MustCompile(`var\s+Data_fluctuationScale\s*=\s*(\{.+?\});`)
)

func (f *FundApi) crawlFundBasicViaPingZhongData(fundCode string) (*FundBasic, error) {
	url := fmt.Sprintf("http://fund.eastmoney.com/pingzhongdata/%s.js", fundCode)
	resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", fmt.Sprintf("http://fund.eastmoney.com/%s.html", fundCode)).
		Get(url)
	if err != nil {
		return nil, fmt.Errorf("pingzhongdata请求失败: %w", err)
	}
	if resp.StatusCode() != 200 {
		return nil, fmt.Errorf("pingzhongdata状态码: %d", resp.StatusCode())
	}

	body := string(resp.Body())
	fund := &FundBasic{Code: fundCode}

	if m := reFSName.FindStringSubmatch(body); len(m) > 1 {
		fund.Name = m[1]
	}

	if m := rePerformance.FindStringSubmatch(body); len(m) > 1 {
		f.parsePerformanceJSON(fund, m[1])
	}

	if m := reFundManager.FindStringSubmatch(body); len(m) > 1 {
		f.parseFundManagerJSON(fund, m[1])
	}

	if m := reFluctuation.FindStringSubmatch(body); len(m) > 1 {
		f.parseFluctuationScaleJSON(fund, m[1])
	}

	if fund.Name == "" {
		return nil, fmt.Errorf("pingzhongdata解析失败: 名称为空")
	}

	return fund, nil
}

type performanceData struct {
	SamePeriod map[string][]interface{} `json:"samePeriod"`
	Hb         map[string][]interface{} `json:"hb"`
}

func (f *FundApi) parsePerformanceJSON(fund *FundBasic, jsonStr string) {
	var perf performanceData
	if err := json.Unmarshal([]byte(jsonStr), &perf); err != nil {
		logger.SugaredLogger.Warnf("parsePerformanceJSON error: %v", err)
		return
	}

	for key, values := range perf.SamePeriod {
		if len(values) < 2 {
			continue
		}
		val, ok := values[1].(float64)
		if !ok {
			continue
		}
		switch key {
		case "1":
			fund.NetGrowth1 = &val
		case "3":
			fund.NetGrowth3 = &val
		case "6":
			fund.NetGrowth6 = &val
		case "12":
			fund.NetGrowth12 = &val
		case "36":
			fund.NetGrowth36 = &val
		case "60":
			fund.NetGrowth60 = &val
		case "ytd":
			fund.NetGrowthYTD = &val
		case "all":
			fund.NetGrowthAll = &val
		}
	}
}

func (f *FundApi) parseFundManagerJSON(fund *FundBasic, jsonStr string) {
	var managers []map[string]interface{}
	if err := json.Unmarshal([]byte(jsonStr), &managers); err != nil {
		return
	}
	if len(managers) > 0 {
		if name, ok := managers[0]["name"].(string); ok {
			fund.Manager = name
		}
	}
}

func (f *FundApi) parseFluctuationScaleJSON(fund *FundBasic, jsonStr string) {
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(jsonStr), &data); err != nil {
		return
	}
	if categories, ok := data["categories"].([]interface{}); ok && len(categories) > 0 {
		lastCat, ok := categories[len(categories)-1].(map[string]interface{})
		if ok {
			if scale, ok := lastCat["y"].(float64); ok {
				fund.Scale = fmt.Sprintf("%.2f亿元", scale)
			}
		}
	}
}

func (f *FundApi) crawlFundNetValueViaAPI(fund *FundBasic, fundCode string) {
	url := fmt.Sprintf("http://api.fund.eastmoney.com/f10/lsjz?fundCode=%s&pageIndex=1&pageSize=1&startDate=&endDate=&_%d",
		fundCode, time.Now().UnixMilli())
	resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", fmt.Sprintf("http://fundf10.eastmoney.com/jjjz_%s.html", fundCode)).
		Get(url)
	if err != nil {
		return
	}

	var result struct {
		Data struct {
			LSJZList []struct {
				FSRQ  string `json:"FSRQ"`
				DWJZ  string `json:"DWJZ"`
				LJJZ  string `json:"LJJZ"`
				JZZZL string `json:"JZZZL"`
			} `json:"LSJZList"`
		} `json:"Data"`
	}
	if err := json.Unmarshal(resp.Body(), &result); err != nil {
		return
	}
	if len(result.Data.LSJZList) == 0 {
		return
	}
	item := result.Data.LSJZList[0]
	if val, err := convertor.ToFloat(item.DWJZ); err == nil {
		fund.NetUnitValue = &val
	}
	if val, err := convertor.ToFloat(item.LJJZ); err == nil {
		fund.NetAccumulated = &val
	}
	fund.NetUnitValueDate = item.FSRQ
}

func (f *FundApi) GetFundList(key string) []FundBasic {
	var funds []FundBasic
	db.Dao.Where("code like ? or name like ? or full_name like ?", "%"+key+"%", "%"+key+"%", "%"+key+"%").Limit(10).Find(&funds)
	if len(funds) == 0 {
		f.searchFundOnline(key)
		db.Dao.Where("code like ? or name like ? or full_name like ?", "%"+key+"%", "%"+key+"%", "%"+key+"%").Limit(10).Find(&funds)
	}
	return funds
}

func (f *FundApi) searchFundOnline(key string) {
	url := fmt.Sprintf("https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx?callback=&m=1&key=%s", key)
	resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", "https://fund.eastmoney.com/").
		Get(url)
	if err != nil || resp.StatusCode() != 200 {
		return
	}
	var result struct {
		Datas []struct {
			Code string `json:"Code"`
			Name string `json:"Name"`
			Type string `json:"FundBaseInfo"`
		} `json:"Datas"`
	}
	if err := json.Unmarshal(resp.Body(), &result); err != nil {
		return
	}
	for _, item := range result.Datas {
		var count int64
		db.Dao.Model(&FundBasic{}).Where("code=?", item.Code).Count(&count)
		if count == 0 {
			fund := &FundBasic{
				Code: item.Code,
				Name: item.Name,
				Type: item.Type,
			}
			db.Dao.Create(fund)
		}
	}
}

func (f *FundApi) GetFollowedFund() []FollowedFund {
	var funds []FollowedFund
	db.Dao.Preload("FundBasic").Find(&funds)
	for i, fund := range funds {
		if fund.FundBasic.Code != "" && (fund.FundBasic.Company == "" || fund.FundBasic.NetGrowthYTD == nil) {
			if crawled, err := f.CrawlFundBasic(fund.Code); err == nil && crawled != nil {
				funds[i].FundBasic = *crawled
			}
		}
		f.CrawlFundNetUnitValue(fund.Code)
		f.CrawlFundNetEstimatedUnit(fund.Code)
		for i2 := range funds {
			if funds[i2].Code == fund.Code {
				var updated FollowedFund
				db.Dao.Where("code=?", fund.Code).First(&updated)
				if updated.NetUnitValue != nil {
					funds[i2].NetUnitValue = updated.NetUnitValue
				}
				if updated.NetUnitValueDate != "" {
					funds[i2].NetUnitValueDate = updated.NetUnitValueDate
				}
				if updated.NetEstimatedUnit != nil {
					funds[i2].NetEstimatedUnit = updated.NetEstimatedUnit
				}
				if updated.NetEstimatedTime != "" {
					funds[i2].NetEstimatedTime = updated.NetEstimatedTime
				}
				if updated.NetUnitValuePrev != nil {
					funds[i2].NetUnitValuePrev = updated.NetUnitValuePrev
				}
				if updated.NetActualRate != nil {
					funds[i2].NetActualRate = updated.NetActualRate
				}
				break
			}
		}
		if fund.NetUnitValue == nil && fund.FundBasic.NetUnitValue != nil {
			funds[i].NetUnitValue = fund.FundBasic.NetUnitValue
		}
		if fund.NetUnitValueDate == "" && fund.FundBasic.NetUnitValueDate != "" {
			funds[i].NetUnitValueDate = fund.FundBasic.NetUnitValueDate
		}
		if fund.NetEstimatedUnit == nil && fund.FundBasic.NetEstimatedUnit != nil {
			funds[i].NetEstimatedUnit = fund.FundBasic.NetEstimatedUnit
		}
		if fund.NetEstimatedTime == "" && fund.FundBasic.NetEstimatedTime != "" {
			funds[i].NetEstimatedTime = fund.FundBasic.NetEstimatedTime
		}
		if fund.NetAccumulated == nil && fund.FundBasic.NetAccumulated != nil {
			funds[i].NetAccumulated = fund.FundBasic.NetAccumulated
		}
		if funds[i].NetEstimatedUnit != nil && funds[i].NetUnitValuePrev != nil && *funds[i].NetUnitValuePrev > 0 {
			netEstimatedRate := (*(funds[i].NetEstimatedUnit) - *(funds[i].NetUnitValuePrev)) / *(funds[i].NetUnitValuePrev) * 100
			netEstimatedRate = mathutil.RoundToFloat(netEstimatedRate, 2)
			funds[i].NetEstimatedRate = &netEstimatedRate
		} else if funds[i].NetUnitValue != nil && funds[i].NetEstimatedUnit != nil && *funds[i].NetUnitValue > 0 {
			netEstimatedRate := (*(funds[i].NetEstimatedUnit) - *(funds[i].NetUnitValue)) / *(funds[i].NetUnitValue) * 100
			netEstimatedRate = mathutil.RoundToFloat(netEstimatedRate, 2)
			funds[i].NetEstimatedRate = &netEstimatedRate
		}
		if funds[i].NetActualRate == nil && funds[i].NetUnitValue != nil && funds[i].NetUnitValuePrev != nil && *funds[i].NetUnitValuePrev > 0 {
			estimatedDate := ""
			if funds[i].NetEstimatedTime != "" {
				parts := strings.SplitN(funds[i].NetEstimatedTime, " ", 2)
				estimatedDate = parts[0]
			}
			isNetValueUpdated := false
			if estimatedDate != "" {
				isNetValueUpdated = funds[i].NetUnitValueDate >= estimatedDate
			} else {
				isNetValueUpdated = funds[i].NetUnitValueDate == time.Now().Format("2006-01-02")
			}
			if isNetValueUpdated {
				netActualRate := (*(funds[i].NetUnitValue) - *(funds[i].NetUnitValuePrev)) / *(funds[i].NetUnitValuePrev) * 100
				netActualRate = mathutil.RoundToFloat(netActualRate, 2)
				funds[i].NetActualRate = &netActualRate
			}
		}
	}
	return funds
}

type FollowedFundPagedResult struct {
	Items      []FollowedFund `json:"items"`
	TotalCount int64          `json:"totalCount"`
	PageIndex  int            `json:"pageIndex"`
	PageSize   int            `json:"pageSize"`
	TotalPages int            `json:"totalPages"`
}

var sinajsVarRe = regexp.MustCompile(`var\s+hq_str_([^\s=]+)\s*=\s*"([^"]*)"`)

type sinajsFData struct {
	Name             string
	NetUnitValue     *float64
	NetUnitValueDate string
}

type sinajsFuData struct {
	NetEstimatedUnit *float64
	NetEstimatedRate *float64
	NetUnitValuePrev *float64
	EstimatedTime    string
}

type sinajsStockData struct {
	NetEstimatedUnit *float64
	NetEstimatedRate *float64
	NetEstimatedTime string
	PrevClose        *float64
}

func (f *FundApi) parseSinajsBatchResponse(body string, parsedF map[string]*sinajsFData, parsedFu map[string]*sinajsFuData, parsedStock map[string]*sinajsStockData) {
	matches := sinajsVarRe.FindAllStringSubmatch(body, -1)
	for _, m := range matches {
		if len(m) < 3 {
			continue
		}
		key := m[1]
		value := m[2]
		if value == "" {
			continue
		}

		if strings.HasPrefix(key, "f_") && !strings.HasPrefix(key, "fu_") {
			code := key[2:]
			parts := strings.Split(value, ",")
			if len(parts) < 5 {
				continue
			}
			data := &sinajsFData{Name: strings.TrimSpace(parts[0])}
			if val, err := convertor.ToFloat(parts[1]); err == nil && val > 0 {
				data.NetUnitValue = &val
			}
			if len(parts) > 4 {
				data.NetUnitValueDate = strings.TrimSpace(parts[4])
			}
			if data.NetUnitValue != nil {
				parsedF[code] = data
			}
		} else if strings.HasPrefix(key, "fu_") {
			code := key[3:]
			parts := strings.Split(value, ",")
			if len(parts) < 8 {
				continue
			}
			data := &sinajsFuData{}
			if val, err := convertor.ToFloat(parts[2]); err == nil && val > 0 {
				data.NetEstimatedUnit = &val
			}
			if val, err := convertor.ToFloat(parts[3]); err == nil && val > 0 {
				data.NetUnitValuePrev = &val
			}
			if val, err := convertor.ToFloat(parts[6]); err == nil {
				data.NetEstimatedRate = &val
			}
			tm := strings.TrimSpace(parts[1])
			date := strings.TrimSpace(parts[7])
			if tm != "" && date != "" {
				data.EstimatedTime = date + " " + tm
			}
			if data.NetEstimatedUnit != nil {
				parsedFu[code] = data
			}
		} else if strings.HasPrefix(key, "sh") || strings.HasPrefix(key, "sz") {
			code := key[2:]
			parts := strings.Split(value, ",")
			if len(parts) < 32 {
				continue
			}
			data := &sinajsStockData{}
			currentPrice, err1 := convertor.ToFloat(parts[3])
			prevClose, err2 := convertor.ToFloat(parts[2])
			if err1 != nil || currentPrice == 0 || err2 != nil || prevClose == 0 {
				continue
			}
			data.NetEstimatedUnit = &currentPrice
			data.PrevClose = &prevClose
			changeRate := (currentPrice - prevClose) / prevClose * 100
			changeRate = mathutil.RoundToFloat(changeRate, 2)
			data.NetEstimatedRate = &changeRate
			if len(parts) > 31 {
				data.NetEstimatedTime = strings.TrimSpace(parts[31])
			}
			parsedStock[code] = data
		}
	}
}

func (f *FundApi) batchCrawlFundData(funds []FollowedFund) {
	var sinajsList []string
	var offExchangeCodes []string
	var onExchangeCodes []string

	for _, fund := range funds {
		if IsOnExchangeFund(fund.Code) {
			onExchangeCodes = append(onExchangeCodes, fund.Code)
			if len(fund.Code) >= 1 {
				switch fund.Code[0:1] {
				case "5", "6":
					sinajsList = append(sinajsList, "sh"+fund.Code)
				case "1", "2":
					sinajsList = append(sinajsList, "sz"+fund.Code)
				}
			}
		} else {
			offExchangeCodes = append(offExchangeCodes, fund.Code)
			sinajsList = append(sinajsList, "f_"+fund.Code, "fu_"+fund.Code)
		}
	}

	parsedF := make(map[string]*sinajsFData)
	parsedFu := make(map[string]*sinajsFuData)
	parsedStock := make(map[string]*sinajsStockData)

	if len(sinajsList) > 0 {
		listStr := strings.Join(sinajsList, ",")
		reqURL := fmt.Sprintf("http://hq.sinajs.cn/rn=%d&list=%s", time.Now().UnixMilli(), listStr)
		resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
			SetHeader("Host", "hq.sinajs.cn").
			SetHeader("User-Agent", getRandomUA()).
			SetHeader("Referer", "https://finance.sina.com.cn").
			Get(reqURL)
		if err == nil && resp.StatusCode() == 200 {
			body := string(GB18030ToUTF8(resp.Body()))
			f.parseSinajsBatchResponse(body, parsedF, parsedFu, parsedStock)
		}
	}

	for _, code := range offExchangeCodes {
		if data, ok := parsedF[code]; ok {
			fund := &FollowedFund{
				Code:             code,
				NetUnitValue:     data.NetUnitValue,
				NetUnitValueDate: data.NetUnitValueDate,
			}
			if data.Name != "" {
				fund.Name = data.Name
			}
			db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
		}
		if data, ok := parsedFu[code]; ok {
			fund := &FollowedFund{
				Code:             code,
				NetEstimatedUnit: data.NetEstimatedUnit,
				NetEstimatedRate: data.NetEstimatedRate,
				NetEstimatedTime: data.EstimatedTime,
			}
			if data.NetUnitValuePrev != nil {
				fund.NetUnitValuePrev = data.NetUnitValuePrev
			}
			db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
		}
	}

	for _, code := range onExchangeCodes {
		if data, ok := parsedStock[code]; ok {
			fund := &FollowedFund{
				Code:             code,
				NetEstimatedUnit: data.NetEstimatedUnit,
				NetEstimatedRate: data.NetEstimatedRate,
				NetEstimatedTime: data.NetEstimatedTime,
			}
			if data.PrevClose != nil {
				fund.NetUnitValuePrev = data.PrevClose
			}
			db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
		}
	}

	var wg sync.WaitGroup
	for _, fund := range funds {
		code := fund.Code
		if fund.FundBasic.Code != "" && (fund.FundBasic.Company == "" || fund.FundBasic.NetGrowthYTD == nil) {
			wg.Add(1)
			go func(c string) {
				defer wg.Done()
				f.CrawlFundBasic(c)
			}(code)
		}
	}

	for _, code := range offExchangeCodes {
		if _, ok := parsedF[code]; !ok {
			wg.Add(1)
			go func(c string) {
				defer wg.Done()
				f.crawlFundNetUnitValueViaEastMoney(c)
			}(code)
		}
		if _, ok := parsedFu[code]; !ok {
			wg.Add(1)
			go func(c string) {
				defer wg.Done()
				f.CrawlFundNetEstimatedUnit(c)
			}(code)
		}
	}

	for _, code := range onExchangeCodes {
		wg.Add(1)
		go func(c string) {
			defer wg.Done()
			f.crawlOnExchangeFundNetUnitValue(c)
		}(code)
		if _, ok := parsedStock[code]; !ok {
			wg.Add(1)
			go func(c string) {
				defer wg.Done()
				f.crawlOnExchangeFundQuote(c)
			}(code)
		}
	}

	wg.Wait()
}

func computeFundRates(fund *FollowedFund) {
	if fund.NetEstimatedUnit != nil && fund.NetUnitValuePrev != nil && *fund.NetUnitValuePrev > 0 {
		rate := (*(fund.NetEstimatedUnit) - *(fund.NetUnitValuePrev)) / *(fund.NetUnitValuePrev) * 100
		rate = mathutil.RoundToFloat(rate, 2)
		fund.NetEstimatedRate = &rate
	} else if fund.NetUnitValue != nil && fund.NetEstimatedUnit != nil && *fund.NetUnitValue > 0 {
		rate := (*(fund.NetEstimatedUnit) - *(fund.NetUnitValue)) / *(fund.NetUnitValue) * 100
		rate = mathutil.RoundToFloat(rate, 2)
		fund.NetEstimatedRate = &rate
	}
	if fund.NetActualRate == nil && fund.NetUnitValue != nil && fund.NetUnitValuePrev != nil && *fund.NetUnitValuePrev > 0 {
		estimatedDate := ""
		if fund.NetEstimatedTime != "" {
			parts := strings.SplitN(fund.NetEstimatedTime, " ", 2)
			estimatedDate = parts[0]
		}
		isNetValueUpdated := false
		if estimatedDate != "" {
			isNetValueUpdated = fund.NetUnitValueDate >= estimatedDate
		} else {
			isNetValueUpdated = fund.NetUnitValueDate == time.Now().Format("2006-01-02")
		}
		if isNetValueUpdated {
			rate := (*(fund.NetUnitValue) - *(fund.NetUnitValuePrev)) / *(fund.NetUnitValuePrev) * 100
			rate = mathutil.RoundToFloat(rate, 2)
			fund.NetActualRate = &rate
		}
	}
}

func mergeFundBasicDefaults(fund *FollowedFund) {
	if fund.NetUnitValue == nil && fund.FundBasic.NetUnitValue != nil {
		fund.NetUnitValue = fund.FundBasic.NetUnitValue
	}
	if fund.NetUnitValueDate == "" && fund.FundBasic.NetUnitValueDate != "" {
		fund.NetUnitValueDate = fund.FundBasic.NetUnitValueDate
	}
	if fund.NetEstimatedUnit == nil && fund.FundBasic.NetEstimatedUnit != nil {
		fund.NetEstimatedUnit = fund.FundBasic.NetEstimatedUnit
	}
	if fund.NetEstimatedTime == "" && fund.FundBasic.NetEstimatedTime != "" {
		fund.NetEstimatedTime = fund.FundBasic.NetEstimatedTime
	}
	if fund.NetAccumulated == nil && fund.FundBasic.NetAccumulated != nil {
		fund.NetAccumulated = fund.FundBasic.NetAccumulated
	}
}

func (f *FundApi) GetFollowedFundPaged(pageIndex, pageSize int, keyword string) *FollowedFundPagedResult {
	if pageIndex <= 0 {
		pageIndex = 1
	}
	if pageSize <= 0 {
		pageSize = 4
	}

	query := db.Dao.Model(&FollowedFund{})
	if keyword != "" {
		kw := "%" + keyword + "%"
		query = query.Joins("LEFT JOIN fund_basic ON fund_basic.code = followed_fund.code").
			Where("followed_fund.code LIKE ? OR followed_fund.name LIKE ? OR fund_basic.full_name LIKE ?", kw, kw, kw)
	}

	var totalCount int64
	query.Count(&totalCount)

	totalPages := int(math.Ceil(float64(totalCount) / float64(pageSize)))
	if totalPages == 0 {
		totalPages = 1
	}

	var funds []FollowedFund
	offset := (pageIndex - 1) * pageSize
	if keyword != "" {
		kw := "%" + keyword + "%"
		db.Dao.Preload("FundBasic").
			Joins("LEFT JOIN fund_basic ON fund_basic.code = followed_fund.code").
			Where("followed_fund.code LIKE ? OR followed_fund.name LIKE ? OR fund_basic.full_name LIKE ?", kw, kw, kw).
			Offset(offset).Limit(pageSize).Find(&funds)
	} else {
		db.Dao.Preload("FundBasic").Offset(offset).Limit(pageSize).Find(&funds)
	}

	if len(funds) > 0 {
		f.batchCrawlFundData(funds)

		var codes []string
		for _, fund := range funds {
			codes = append(codes, fund.Code)
		}
		var updatedFunds []FollowedFund
		db.Dao.Preload("FundBasic").Where("code IN ?", codes).Find(&updatedFunds)

		for i := range updatedFunds {
			mergeFundBasicDefaults(&updatedFunds[i])
			computeFundRates(&updatedFunds[i])
		}
		funds = updatedFunds
	}

	if funds == nil {
		funds = []FollowedFund{}
	}

	return &FollowedFundPagedResult{
		Items:      funds,
		TotalCount: totalCount,
		PageIndex:  pageIndex,
		PageSize:   pageSize,
		TotalPages: totalPages,
	}
}

func (f *FundApi) FollowFund(fundCode string) string {
	var fund FundBasic
	db.Dao.Where("code=?", fundCode).First(&fund)
	if fund.Code == "" || fund.Company == "" {
		crawled, err := f.CrawlFundBasic(fundCode)
		if err != nil || crawled == nil {
			if fund.Code == "" {
				return "基金信息不存在或获取失败"
			}
		} else {
			fund = *crawled
		}
	}
	follow := &FollowedFund{
		Code: fundCode,
		Name: fund.Name,
	}
	err := db.Dao.Model(follow).Where("code = ?", fundCode).FirstOrCreate(follow, "code", fund.Code).Error
	if err != nil {
		return "关注失败"
	}
	return "关注成功"
}

func (f *FundApi) UnFollowFund(fundCode string) string {
	var fund FollowedFund
	db.Dao.Where("code=?", fundCode).First(&fund)
	if fund.Code != "" {
		err := db.Dao.Model(&fund).Delete(&fund).Error
		if err != nil {
			return "取消关注失败"
		}
		return "取消关注成功"
	} else {
		return "基金信息不存在"
	}
}

func (f *FundApi) AllFund() {
	defer func() {
		if r := recover(); r != nil {
			logger.SugaredLogger.Errorf("AllFund panic: %v", r)
		}
	}()

	response, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", "https://fund.eastmoney.com/").
		Get("https://fund.eastmoney.com/allfund.html")
	if err != nil {
		return
	}
	htmlContent := GB18030ToUTF8(response.Body())

	doc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlContent))
	if err != nil {
		logger.SugaredLogger.Errorf("AllFund parse HTML error: %v", err)
		return
	}
	cnt := 0
	doc.Find("ul.num_right li").Each(func(i int, s *goquery.Selection) {
		text := strutil.SplitEx(s.Text(), "|", true)
		if len(text) > 0 {
			cnt++
			name := text[0]
			str := strutil.SplitAndTrim(name, "）", "（", "）")
			fund := &FundBasic{
				Code: str[0],
				Name: str[1],
			}
			count := int64(0)
			db.Dao.Model(fund).Where("code=?", fund.Code).Count(&count)
			if count == 0 {
				db.Dao.Create(fund)
			}
		}
	})
}

type FundNetUnitValue struct {
	Fundcode string `json:"fundcode"`
	Name     string `json:"name"`
	Jzrq     string `json:"jzrq"`
	Dwjz     string `json:"dwjz"`
	Gsz      string `json:"gsz"`
	Gszzl    string `json:"gszzl"`
	Gztime   string `json:"gztime"`
}

func (f *FundApi) CrawlFundNetEstimatedUnit(code string) {
	if IsOnExchangeFund(code) {
		f.crawlOnExchangeFundQuote(code)
		return
	}
	var fundNetUnitValue FundNetUnitValue
	response, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", "https://fund.eastmoney.com/").
		SetQueryParams(map[string]string{"rt": strconv.FormatInt(time.Now().UnixMilli(), 10)}).
		Get(fmt.Sprintf("https://fundgz.1234567.com.cn/js/%s.js", code))
	if err != nil {
		logger.SugaredLogger.Errorf("err:%s", err.Error())
	} else if response.StatusCode() == 200 {
		htmlContent := string(response.Body())
		if strings.Contains(htmlContent, "jsonpgz") {
			htmlContent = strutil.Trim(htmlContent, "jsonpgz(", ");")
			htmlContent = strutil.Trim(htmlContent, ");")
			err := json.Unmarshal([]byte(htmlContent), &fundNetUnitValue)
			if err == nil && fundNetUnitValue.Gsz != "" {
				fund := &FollowedFund{
					Code:             fundNetUnitValue.Fundcode,
					Name:             fundNetUnitValue.Name,
					NetEstimatedTime: fundNetUnitValue.Gztime,
				}
				netEstimatedUnit, err := convertor.ToFloat(fundNetUnitValue.Gsz)
				if err == nil {
					fund.NetEstimatedUnit = &netEstimatedUnit
				}
				netEstimatedRate, err := convertor.ToFloat(fundNetUnitValue.Gszzl)
				if err == nil {
					fund.NetEstimatedRate = &netEstimatedRate
				}
				netUnitValuePrev, err := convertor.ToFloat(fundNetUnitValue.Dwjz)
				if err == nil {
					fund.NetUnitValuePrev = &netUnitValuePrev
				}
				db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
				return
			}
		}
	}
	f.crawlFundEstimatedViaSina(code)
}

func (f *FundApi) crawlFundEstimatedViaSina(code string) {
	response, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", "https://finance.sina.com.cn/").
		Get(fmt.Sprintf("http://hq.sinajs.cn/list=fu_%s", code))
	if err == nil && response.StatusCode() == 200 {
		data := string(GB18030ToUTF8(response.Body()))
		datas := strutil.SplitAndTrim(data, "=", "\"")
		if len(datas) >= 2 {
			parts := strings.Split(datas[1], ",")
			if len(parts) >= 8 {
				gsz := strings.TrimSpace(parts[2])
				if gsz != "" && gsz != "0" {
					gszzl := strings.TrimSpace(parts[6])
					dwjz := strings.TrimSpace(parts[3])
					date := strings.TrimSpace(parts[7])
					tm := strings.TrimSpace(parts[1])
					fund := &FollowedFund{
						Code:             code,
						NetEstimatedTime: date + " " + tm,
					}
					netEstimatedUnit, err := convertor.ToFloat(gsz)
					if err == nil {
						fund.NetEstimatedUnit = &netEstimatedUnit
					}
					netEstimatedRate, err := convertor.ToFloat(gszzl)
					if err == nil {
						fund.NetEstimatedRate = &netEstimatedRate
					}
					netUnitValuePrev, err := convertor.ToFloat(dwjz)
					if err == nil {
						fund.NetUnitValuePrev = &netUnitValuePrev
					}
					db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
					return
				}
			}
		}
	}
	f.crawlFundEstimatedViaMobileAPI(code)
}

func (f *FundApi) crawlFundEstimatedViaMobileAPI(code string) {
	type MobileFundInfo struct {
		FCODE     string  `json:"FCODE"`
		SHORTNAME string  `json:"SHORTNAME"`
		PDATE     string  `json:"PDATE"`
		NAV       string  `json:"NAV"`
		ACCNAV    string  `json:"ACCNAV"`
		NAVCHGRT  string  `json:"NAVCHGRT"`
		GSZ       *string `json:"GSZ"`
		GSZZL     *string `json:"GSZZL"`
		GZTIME    *string `json:"GZTIME"`
	}
	type MobileAPIResponse struct {
		Datas   []MobileFundInfo `json:"Datas"`
		ErrCode int              `json:"ErrCode"`
		Success bool             `json:"Success"`
	}

	url := fmt.Sprintf("https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFInfo?pageIndex=1&pageSize=1&plat=Android&appType=ttjj&product=EFund&Version=1&deviceid=1&Ession=1&Fcodes=%s", code)
	resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		Get(url)
	if err != nil || resp.StatusCode() != 200 {
		return
	}

	var result MobileAPIResponse
	if err := json.Unmarshal(resp.Body(), &result); err != nil || !result.Success || len(result.Datas) == 0 {
		return
	}

	data := result.Datas[0]
	fund := &FollowedFund{
		Code: data.FCODE,
		Name: data.SHORTNAME,
	}

	if data.GSZ != nil && *data.GSZ != "" && data.GZTIME != nil && *data.GZTIME != "" {
		gsz, err := convertor.ToFloat(*data.GSZ)
		if err == nil {
			fund.NetEstimatedUnit = &gsz
		}
		if data.GSZZL != nil {
			gszzl, err := convertor.ToFloat(*data.GSZZL)
			if err == nil {
				fund.NetEstimatedRate = &gszzl
			}
		}
		fund.NetEstimatedTime = *data.GZTIME
	}

	if data.PDATE != "" && data.NAV != "" {
		nav, err := convertor.ToFloat(data.NAV)
		if err == nil {
			fund.NetUnitValue = &nav
		}
		fund.NetUnitValueDate = data.PDATE
	}

	if data.NAVCHGRT != "" && data.PDATE == time.Now().Format("2006-01-02") {
		navChgRt, err := convertor.ToFloat(data.NAVCHGRT)
		if err == nil {
			fund.NetActualRate = &navChgRt
		}
	}

	db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
}

func (f *FundApi) crawlOnExchangeFundQuote(code string) {
	var sinaCode string
	if len(code) < 1 {
		return
	}
	switch code[0:1] {
	case "5", "6":
		sinaCode = "sh" + code
	case "1", "2":
		sinaCode = "sz" + code
	default:
		return
	}
	url := fmt.Sprintf("http://hq.sinajs.cn/rn=%d&list=%s", time.Now().UnixMilli(), sinaCode)
	resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("Host", "hq.sinajs.cn").
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", "https://finance.sina.com.cn").
		Get(url)
	if err != nil || resp.StatusCode() != 200 {
		return
	}
	data := string(GB18030ToUTF8(resp.Body()))
	parts := strings.SplitN(data, "=", 2)
	if len(parts) < 2 {
		return
	}
	content := strings.Trim(parts[1], " \"\n\r;")
	if content == "" {
		return
	}
	fields := strings.Split(content, ",")
	if len(fields) < 4 {
		return
	}
	currentPrice, err := convertor.ToFloat(fields[3])
	if err != nil || currentPrice == 0 {
		return
	}
	yesterdayPrice, err := convertor.ToFloat(fields[2])
	if err != nil || yesterdayPrice == 0 {
		return
	}
	changeRate := (currentPrice - yesterdayPrice) / yesterdayPrice * 100
	changeRate = mathutil.RoundToFloat(changeRate, 2)

	fund := &FollowedFund{
		Code:             code,
		NetEstimatedUnit: &currentPrice,
		NetEstimatedRate: &changeRate,
		NetEstimatedTime: strings.TrimSpace(fields[31]),
	}
	db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
}

func (f *FundApi) CrawlFundNetUnitValue(code string) {
	if IsOnExchangeFund(code) {
		f.crawlOnExchangeFundNetUnitValue(code)
		return
	}
	url := fmt.Sprintf("http://hq.sinajs.cn/rn=%d&list=f_%s", time.Now().UnixMilli(), code)
	response, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("Host", "hq.sinajs.cn").
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", "https://finance.sina.com.cn").
		Get(url)
	if err != nil {
		logger.SugaredLogger.Errorf("err:%s", err.Error())
	}
	if err == nil && response.StatusCode() == 200 {
		data := string(GB18030ToUTF8(response.Body()))
		datas := strutil.SplitAndTrim(data, "=", "\"")
		if len(datas) >= 2 {
			parts := strutil.SplitAndTrim(datas[1], ",", "\"")
			val, err := convertor.ToFloat(parts[1])
			if err == nil {
				fund := &FollowedFund{
					Name:             parts[0],
					Code:             code,
					NetUnitValue:     &val,
					NetUnitValueDate: parts[4],
				}
				db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
				return
			}
		}
	}
	f.crawlFundNetUnitValueViaEastMoney(code)
}

func (f *FundApi) crawlOnExchangeFundNetUnitValue(code string) {
	klineApi := NewFundKLineApi()
	result := klineApi.GetFundKLine(code, "101", 3)
	if result == nil || result.Data == nil || len(*result.Data) < 1 {
		return
	}
	data := *result.Data
	latest := data[len(data)-1]
	val, err := convertor.ToFloat(latest.Close)
	if err != nil || val == 0 {
		return
	}
	date := latest.Day
	if strings.Contains(date, " ") {
		date = strings.Split(date, " ")[0]
	}
	fund := &FollowedFund{
		Code:             code,
		NetUnitValue:     &val,
		NetUnitValueDate: date,
	}
	if len(data) >= 2 {
		prev := data[len(data)-2]
		prevVal, err := convertor.ToFloat(prev.Close)
		if err == nil && prevVal > 0 {
			fund.NetUnitValuePrev = &prevVal
		}
	}
	db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
}

func (f *FundApi) crawlFundNetUnitValueViaEastMoney(code string) {
	history, err := f.GetFundHistoryNetValue(code, 1, 2, "", "")
	if err != nil || len(history) == 0 {
		return
	}
	latest := history[0]
	val := latest.NetValue
	fund := &FollowedFund{
		Code:             code,
		NetUnitValue:     &val,
		NetUnitValueDate: latest.Date,
	}
	if len(history) >= 2 {
		prevVal := history[1].NetValue
		fund.NetUnitValuePrev = &prevVal
	}
	db.Dao.Model(fund).Where("code=?", fund.Code).Updates(fund)
}

type FundHistoryNetValue struct {
	Date        string  `json:"date"`
	NetValue    float64 `json:"netValue"`
	AccumValue  float64 `json:"accumValue"`
	DailyGrowth float64 `json:"dailyGrowth"`
	BuyStatus   string  `json:"buyStatus"`
	SellStatus  string  `json:"sellStatus"`
}

func (f *FundApi) GetFundHistoryNetValue(fundCode string, pageIndex, pageSize int, startDate, endDate string) ([]FundHistoryNetValue, error) {
	if IsOnExchangeFund(fundCode) {
		return f.getOnExchangeFundHistoryNetValue(fundCode, pageSize)
	}
	url := fmt.Sprintf("http://api.fund.eastmoney.com/f10/lsjz?fundCode=%s&pageIndex=%d&pageSize=%d&startDate=%s&endDate=%s&_%d",
		fundCode, pageIndex, pageSize, startDate, endDate, time.Now().UnixMilli())
	resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", fmt.Sprintf("http://fundf10.eastmoney.com/jjjz_%s.html", fundCode)).
		Get(url)
	if err != nil {
		return nil, fmt.Errorf("请求历史净值失败: %w", err)
	}

	var result struct {
		Data struct {
			LSJZList []struct {
				FSRQ  string `json:"FSRQ"`
				DWJZ  string `json:"DWJZ"`
				LJJZ  string `json:"LJJZ"`
				JZZZL string `json:"JZZZL"`
				SGZT  string `json:"SGZT"`
				SHZT  string `json:"SHZT"`
			} `json:"LSJZList"`
			TotalCount int `json:"TotalCount"`
		} `json:"Data"`
	}
	if err := json.Unmarshal(resp.Body(), &result); err != nil {
		return nil, fmt.Errorf("解析历史净值失败: %w", err)
	}

	var values []FundHistoryNetValue
	for _, item := range result.Data.LSJZList {
		dwjz, _ := convertor.ToFloat(item.DWJZ)
		ljjz, _ := convertor.ToFloat(item.LJJZ)
		jzzzl, _ := convertor.ToFloat(item.JZZZL)
		values = append(values, FundHistoryNetValue{
			Date:        item.FSRQ,
			NetValue:    dwjz,
			AccumValue:  ljjz,
			DailyGrowth: jzzzl,
			BuyStatus:   item.SGZT,
			SellStatus:  item.SHZT,
		})
	}
	return values, nil
}

func IsOnExchangeFund(code string) bool {
	if len(code) < 2 {
		return false
	}
	prefix := code[:2]
	switch prefix {
	case "15", "16", "50", "51", "52":
		return true
	default:
		return false
	}
}

func (f *FundApi) getOnExchangeFundHistoryNetValue(fundCode string, pageSize int) ([]FundHistoryNetValue, error) {
	klineApi := NewFundKLineApi()
	result := klineApi.GetFundKLine(fundCode, "101", pageSize)
	if result == nil || result.Data == nil || len(*result.Data) == 0 {
		return nil, fmt.Errorf("获取场内基金历史行情失败")
	}
	klineData := *result.Data
	var values []FundHistoryNetValue
	for i := len(klineData) - 1; i >= 0; i-- {
		item := klineData[i]
		closePrice, _ := convertor.ToFloat(item.Close)
		var dailyGrowth float64
		if i > 0 {
			prevClose, _ := convertor.ToFloat(klineData[i-1].Close)
			if prevClose > 0 {
				dailyGrowth = (closePrice - prevClose) / prevClose * 100
				dailyGrowth = mathutil.RoundToFloat(dailyGrowth, 2)
			}
		} else {
			dailyGrowth, _ = convertor.ToFloat(item.ChangePercent)
		}
		date := item.Day
		if strings.Contains(date, " ") {
			date = strings.Split(date, " ")[0]
		}
		values = append(values, FundHistoryNetValue{
			Date:        date,
			NetValue:    closePrice,
			AccumValue:  0,
			DailyGrowth: dailyGrowth,
			BuyStatus:   "-",
			SellStatus:  "-",
		})
	}
	return values, nil
}

func fundKLineSecid(code string) string {
	if !IsOnExchangeFund(code) {
		return ""
	}
	if len(code) < 1 {
		return ""
	}
	first := code[0:1]
	switch first {
	case "5":
		return "1." + code
	case "1":
		return "0." + code
	default:
		return ""
	}
}

type FundHoldingStock struct {
	Rank       int      `json:"rank"`
	StockCode  string   `json:"stockCode"`
	StockName  string   `json:"stockName"`
	Ratio      float64  `json:"ratio"`
	Shares     string   `json:"shares"`
	MarketCap  string   `json:"marketCap"`
	Quarter    string   `json:"quarter"`
	Price      *float64 `json:"price"`
	ChangeRate *float64 `json:"changeRate"`
	Market     string   `json:"market"`
}

func (f *FundApi) GetFundTop10Holdings(fundCode string) ([]FundHoldingStock, error) {
	defer func() {
		if r := recover(); r != nil {
			logger.SugaredLogger.Errorf("GetFundTop10Holdings panic: %v", r)
		}
	}()

	holdings, err := f.getTop10HoldingsViaHTML(fundCode)
	if err != nil {
		logger.SugaredLogger.Warnf("getTop10HoldingsViaHTML failed for %s: %v", fundCode, err)
		return nil, fmt.Errorf("获取基金十大持仓股失败: %w", err)
	}

	f.fillHoldingStockQuotes(holdings)

	return holdings, nil
}

func stockSinaPrefix(code string) string {
	for len(code) < 6 {
		code = "0" + code
	}
	switch code[0:1] {
	case "5", "6", "9":
		return "sh" + code
	case "0", "1", "2", "3":
		return "sz" + code
	case "4", "8":
		return "bj" + code
	default:
		return ""
	}
}

func detectStockMarket(href, code string) string {
	if href != "" {
		href = strings.ToLower(href)
		if strings.Contains(href, "/hk/") || strings.Contains(href, "hk0") {
			return "HK"
		}
		if strings.Contains(href, "/us/") || strings.Contains(href, "us0") {
			return "US"
		}
		if strings.Contains(href, "/concept/") || strings.Contains(href, "/sh") || strings.Contains(href, "/sz") || strings.Contains(href, "/bj") {
			return "A"
		}
	}
	if code == "" {
		return ""
	}
	hasAlpha := false
	for _, c := range code {
		if (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') {
			hasAlpha = true
			break
		}
	}
	if hasAlpha {
		return "US"
	}
	if stockSinaPrefix(code) != "" {
		return "A"
	}
	if len(code) >= 4 && len(code) <= 6 {
		allDigit := true
		for _, c := range code {
			if c < '0' || c > '9' {
				allDigit = false
				break
			}
		}
		if allDigit {
			return "HK"
		}
	}
	return ""
}

func stockQuoteCode(code, market string) string {
	padded := code
	switch market {
	case "A":
		return stockSinaPrefix(padded)
	case "HK":
		for len(padded) < 5 {
			padded = "0" + padded
		}
		return "hk" + padded
	case "US":
		return "gb_" + strings.ToLower(padded)
	default:
		return ""
	}
}

type quoteData struct {
	price      float64
	changeRate float64
}

func (f *FundApi) fillHoldingStockQuotes(holdings []FundHoldingStock) {
	if len(holdings) == 0 {
		return
	}

	var aCodes, hkCodes, usCodes []string
	for _, h := range holdings {
		switch h.Market {
		case "A":
			if p := stockSinaPrefix(h.StockCode); p != "" {
				aCodes = append(aCodes, p)
			}
		case "HK":
			if p := stockQuoteCode(h.StockCode, "HK"); p != "" {
				hkCodes = append(hkCodes, p)
			}
		case "US":
			if p := stockQuoteCode(h.StockCode, "US"); p != "" {
				usCodes = append(usCodes, p)
			}
		}
	}

	quoteMap := make(map[string]quoteData)

	if len(aCodes) > 0 {
		url := fmt.Sprintf("http://hq.sinajs.cn/rn=%d&list=%s", time.Now().UnixMilli(), strings.Join(aCodes, ","))
		resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
			SetHeader("Host", "hq.sinajs.cn").
			SetHeader("User-Agent", getRandomUA()).
			SetHeader("Referer", "https://finance.sina.com.cn").
			Get(url)
		if err == nil && resp.StatusCode() == 200 {
			body := string(resp.Body())
			f.parseSinaAShareQuotes(body, quoteMap)
		} else if err != nil {
			logger.SugaredLogger.Warnf("fillHoldingStockQuotes A-share request failed: %v", err)
		}
	}

	if len(hkCodes) > 0 {
		url := fmt.Sprintf("http://hq.sinajs.cn/rn=%d&list=%s", time.Now().UnixMilli(), strings.Join(hkCodes, ","))
		resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
			SetHeader("Host", "hq.sinajs.cn").
			SetHeader("User-Agent", getRandomUA()).
			SetHeader("Referer", "https://finance.sina.com.cn").
			Get(url)
		if err == nil && resp.StatusCode() == 200 {
			body := string(resp.Body())
			f.parseSinaHKQuotes(body, quoteMap)
		} else if err != nil {
			logger.SugaredLogger.Warnf("fillHoldingStockQuotes HK request failed: %v", err)
		}
	}

	if len(usCodes) > 0 {
		url := fmt.Sprintf("http://hq.sinajs.cn/rn=%d&list=%s", time.Now().UnixMilli(), strings.Join(usCodes, ","))
		resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
			SetHeader("Host", "hq.sinajs.cn").
			SetHeader("User-Agent", getRandomUA()).
			SetHeader("Referer", "https://finance.sina.com.cn").
			Get(url)
		if err == nil && resp.StatusCode() == 200 {
			body := string(resp.Body())
			f.parseSinaUSQuotes(body, quoteMap)
		} else if err != nil {
			logger.SugaredLogger.Warnf("fillHoldingStockQuotes US request failed: %v", err)
		}
	}

	for i := range holdings {
		key := holdings[i].StockCode
		switch holdings[i].Market {
		case "A":
			for len(key) < 6 {
				key = "0" + key
			}
		case "HK":
			for len(key) < 5 {
				key = "0" + key
			}
		case "US":
			key = strings.ToLower(key)
		}
		if q, ok := quoteMap[key]; ok {
			holdings[i].Price = &q.price
			holdings[i].ChangeRate = &q.changeRate
		}
	}
}

func (f *FundApi) parseSinaAShareQuotes(body string, quoteMap map[string]quoteData) {
	lines := strings.Split(body, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		eqParts := strings.SplitN(line, "=", 2)
		if len(eqParts) < 2 {
			continue
		}
		sinaCode := strings.TrimSpace(eqParts[0])
		content := strings.Trim(eqParts[1], " \"\n\r;")
		if content == "" {
			continue
		}
		fields := strings.Split(content, ",")
		if len(fields) < 4 {
			continue
		}
		currentPrice, err1 := convertor.ToFloat(fields[3])
		if err1 != nil || currentPrice == 0 {
			continue
		}
		yesterdayPrice, err2 := convertor.ToFloat(fields[2])
		if err2 != nil || yesterdayPrice == 0 {
			continue
		}
		changeRate := mathutil.RoundToFloat((currentPrice-yesterdayPrice)/yesterdayPrice*100, 2)
		pureCode := sinaCode
		if idx := strings.LastIndex(sinaCode, "_"); idx >= 0 {
			pureCode = sinaCode[idx+1:]
		}
		pureCode = strings.TrimPrefix(strings.TrimPrefix(pureCode, "sh"), "sz")
		pureCode = strings.TrimPrefix(pureCode, "bj")
		quoteMap[pureCode] = quoteData{price: currentPrice, changeRate: changeRate}
	}
}

func (f *FundApi) parseSinaHKQuotes(body string, quoteMap map[string]quoteData) {
	lines := strings.Split(body, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		eqParts := strings.SplitN(line, "=", 2)
		if len(eqParts) < 2 {
			continue
		}
		sinaCode := strings.TrimSpace(eqParts[0])
		content := strings.Trim(eqParts[1], " \"\n\r;")
		if content == "" {
			continue
		}
		fields := strings.Split(content, ",")
		if len(fields) < 9 {
			continue
		}
		currentPrice, err1 := convertor.ToFloat(fields[6])
		if err1 != nil || currentPrice == 0 {
			continue
		}
		yesterdayPrice, err2 := convertor.ToFloat(fields[3])
		if err2 != nil || yesterdayPrice == 0 {
			continue
		}
		changeRate := mathutil.RoundToFloat((currentPrice-yesterdayPrice)/yesterdayPrice*100, 2)
		pureCode := sinaCode
		if idx := strings.LastIndex(sinaCode, "_"); idx >= 0 {
			pureCode = sinaCode[idx+1:]
		}
		pureCode = strings.TrimPrefix(pureCode, "hk")
		quoteMap[pureCode] = quoteData{price: currentPrice, changeRate: changeRate}
	}
}

func (f *FundApi) parseSinaUSQuotes(body string, quoteMap map[string]quoteData) {
	lines := strings.Split(body, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		eqParts := strings.SplitN(line, "=", 2)
		if len(eqParts) < 2 {
			continue
		}
		sinaCode := strings.TrimSpace(eqParts[0])
		content := strings.Trim(eqParts[1], " \"\n\r;")
		if content == "" {
			continue
		}
		fields := strings.Split(content, ",")
		if len(fields) < 2 {
			continue
		}
		currentPrice, err1 := convertor.ToFloat(fields[1])
		if err1 != nil || currentPrice == 0 {
			continue
		}
		var yesterdayPrice float64
		var err2 error
		if len(fields) >= 36 {
			yesterdayPrice, err2 = convertor.ToFloat(fields[26])
		} else if len(fields) >= 2 {
			yesterdayPrice, err2 = convertor.ToFloat(fields[len(fields)-1])
		}
		if err2 != nil || yesterdayPrice == 0 {
			continue
		}
		changeRate := mathutil.RoundToFloat((currentPrice-yesterdayPrice)/yesterdayPrice*100, 2)
		pureCode := sinaCode
		if idx := strings.LastIndex(sinaCode, "_"); idx >= 0 {
			pureCode = sinaCode[idx+1:]
		}
		pureCode = strings.TrimPrefix(pureCode, "gb_")
		quoteMap[strings.ToLower(pureCode)] = quoteData{price: currentPrice, changeRate: changeRate}
	}
}

type FundRankingItem struct {
	Code             string   `json:"code"`
	Name             string   `json:"name"`
	Pinyin           string   `json:"pinyin"`
	NetValueDate     string   `json:"netValueDate"`
	NetUnitValue     *float64 `json:"netUnitValue"`
	NetAccumulated   *float64 `json:"netAccumulated"`
	DailyGrowth      *float64 `json:"dailyGrowth"`
	WeekGrowth       *float64 `json:"weekGrowth"`
	MonthGrowth      *float64 `json:"monthGrowth"`
	ThreeMonthGrowth *float64 `json:"threeMonthGrowth"`
	SixMonthGrowth   *float64 `json:"sixMonthGrowth"`
	YearGrowth       *float64 `json:"yearGrowth"`
	TwoYearGrowth    *float64 `json:"twoYearGrowth"`
	ThreeYearGrowth  *float64 `json:"threeYearGrowth"`
	YTDGrowth        *float64 `json:"ytdGrowth"`
	SinceInception   *float64 `json:"sinceInception"`
	EstablishDate    string   `json:"establishDate"`
	Purchasable      bool     `json:"purchasable"`
	Scale            *float64 `json:"scale"`
	PurchaseRate     *float64 `json:"purchaseRate"`
	DiscountRate     *float64 `json:"discountRate"`
	FundTypeDetail   string   `json:"fundTypeDetail"`
}

type FundRankingResult struct {
	Items      []FundRankingItem `json:"items"`
	TotalCount int               `json:"totalCount"`
	PageIndex  int               `json:"pageIndex"`
	PageSize   int               `json:"pageSize"`
	TotalPages int               `json:"totalPages"`
}

func fundParseFloatPtr(s string) *float64 {
	s = strings.TrimSpace(s)
	if s == "" || s == "-" {
		return nil
	}
	val, err := strconv.ParseFloat(s, 64)
	if err == nil {
		return &val
	}
	return nil
}

type FundSearchItem struct {
	Code string `json:"code"`
	Name string `json:"name"`
	Type string `json:"type"`
}

func (f *FundApi) SearchFundCodes(keyword string) []FundSearchItem {
	if keyword == "" {
		return []FundSearchItem{}
	}
	url := fmt.Sprintf("https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx?callback=&m=1&key=%s", keyword)
	resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", "https://fund.eastmoney.com/").
		Get(url)
	if err != nil || resp.StatusCode() != 200 {
		return []FundSearchItem{}
	}
	var result struct {
		Datas []struct {
			Code         string `json:"CODE"`
			Name         string `json:"NAME"`
			FundBaseInfo *struct {
				FCODE     string  `json:"FCODE"`
				SHORTNAME string  `json:"SHORTNAME"`
				FTYPE     string  `json:"FTYPE"`
				DWJZ      float64 `json:"DWJZ"`
			} `json:"FundBaseInfo"`
		} `json:"Datas"`
	}
	if err := json.Unmarshal(resp.Body(), &result); err != nil {
		return []FundSearchItem{}
	}
	var items []FundSearchItem
	for _, item := range result.Datas {
		if item.FundBaseInfo == nil {
			continue
		}
		ftype := item.FundBaseInfo.FTYPE
		items = append(items, FundSearchItem{
			Code: item.Code,
			Name: item.Name,
			Type: ftype,
		})
		var count int64
		db.Dao.Model(&FundBasic{}).Where("code=?", item.Code).Count(&count)
		if count == 0 {
			db.Dao.Create(&FundBasic{Code: item.Code, Name: item.Name, Type: ftype})
		} else {
			db.Dao.Model(&FundBasic{}).Where("code=?", item.Code).Updates(map[string]interface{}{"name": item.Name, "type": ftype})
		}
	}
	if items == nil {
		items = []FundSearchItem{}
	}
	return items
}

func (f *FundApi) GetFundRanking(marketType, fundType, sortField, sortOrder string, pageIndex, pageSize int) (*FundRankingResult, error) {
	defer func() {
		if r := recover(); r != nil {
			logger.SugaredLogger.Errorf("GetFundRanking panic: %v", r)
		}
	}()

	if marketType == "" {
		marketType = "kf"
	}
	if fundType == "" {
		fundType = "all"
	}
	if sortField == "" {
		sortField = "jnzf"
	}
	if sortOrder == "" {
		sortOrder = "desc"
	}
	if pageIndex <= 0 {
		pageIndex = 1
	}
	if pageSize <= 0 {
		pageSize = 50
	}

	referer := "https://fund.eastmoney.com/data/fundranking.html"
	if marketType == "fb" {
		referer = "https://fund.eastmoney.com/data/fbsfundranking.html"
		if fundType == "all" || fundType == "gp" || fundType == "hh" || fundType == "zq" || fundType == "zs" || fundType == "qdii" || fundType == "fof" {
			fundType = "ct"
		}
	}

	apiUrl := "https://fund.eastmoney.com/data/rankhandler.aspx"
	queryParams := map[string]string{
		"op": "ph",
		"dt": marketType,
		"ft": fundType,
		"rs": "",
		"gs": "0",
		"sc": sortField,
		"st": sortOrder,
		"sd": "",
		"ed": "",
		"pi": strconv.Itoa(pageIndex),
		"pn": strconv.Itoa(pageSize),
		"v":  strconv.FormatInt(time.Now().UnixMilli(), 10),
	}
	if marketType == "kf" {
		queryParams["qdii"] = ""
		queryParams["tabSubtype"] = ",,,,"
		queryParams["dx"] = "1"
	}

	resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Referer", referer).
		SetQueryParams(queryParams).
		Get(apiUrl)
	if err != nil {
		return nil, fmt.Errorf("请求基金排行API失败: %w", err)
	}
	if resp.StatusCode() != 200 {
		return nil, fmt.Errorf("HTTP状态码: %d", resp.StatusCode())
	}

	body := string(resp.Body())

	startIdx := strings.Index(body, "datas:[")
	if startIdx == -1 {
		return nil, fmt.Errorf("未找到基金排行数据(datas)")
	}
	startIdx += len("datas:[")
	endIdx := strings.Index(body[startIdx:], "]")
	if endIdx == -1 {
		return nil, fmt.Errorf("基金排行数据格式错误")
	}
	datasContent := body[startIdx : startIdx+endIdx]

	allRecordsRe := regexp.MustCompile(`allRecords:(\d+)`)
	allRecordsMatch := allRecordsRe.FindStringSubmatch(body)
	totalCount := 0
	if len(allRecordsMatch) > 1 {
		totalCount, _ = strconv.Atoi(allRecordsMatch[1])
	}

	allPagesRe := regexp.MustCompile(`allPages:(\d+)`)
	allPagesMatch := allPagesRe.FindStringSubmatch(body)
	totalPages := 0
	if len(allPagesMatch) > 1 {
		totalPages, _ = strconv.Atoi(allPagesMatch[1])
	}

	recordRe := regexp.MustCompile(`"([^"]*)"`)
	records := recordRe.FindAllStringSubmatch(datasContent, -1)

	var items []FundRankingItem
	for _, record := range records {
		if len(record) < 2 {
			continue
		}
		fields := strings.Split(record[1], ",")
		if len(fields) < 17 {
			continue
		}

		item := FundRankingItem{
			Code:             fields[0],
			Name:             fields[1],
			Pinyin:           fields[2],
			NetValueDate:     fields[3],
			NetUnitValue:     fundParseFloatPtr(fields[4]),
			NetAccumulated:   fundParseFloatPtr(fields[5]),
			DailyGrowth:      fundParseFloatPtr(fields[6]),
			WeekGrowth:       fundParseFloatPtr(fields[7]),
			MonthGrowth:      fundParseFloatPtr(fields[8]),
			ThreeMonthGrowth: fundParseFloatPtr(fields[9]),
			SixMonthGrowth:   fundParseFloatPtr(fields[10]),
			YearGrowth:       fundParseFloatPtr(fields[11]),
			TwoYearGrowth:    fundParseFloatPtr(fields[12]),
			ThreeYearGrowth:  fundParseFloatPtr(fields[13]),
			YTDGrowth:        fundParseFloatPtr(fields[14]),
			SinceInception:   fundParseFloatPtr(fields[15]),
			EstablishDate:    fields[16],
		}

		if marketType == "kf" && len(fields) >= 21 {
			item.Purchasable = fields[17] == "1"
			item.Scale = fundParseFloatPtr(fields[18])
			item.PurchaseRate = fundParseFloatPtr(fields[19])
			item.DiscountRate = fundParseFloatPtr(fields[20])
		} else if marketType == "fb" && len(fields) >= 23 {
			item.FundTypeDetail = fields[21]
			item.Scale = fundParseFloatPtr(fields[22])
		}

		items = append(items, item)
	}

	if items == nil {
		items = []FundRankingItem{}
	}

	return &FundRankingResult{
		Items:      items,
		TotalCount: totalCount,
		PageIndex:  pageIndex,
		PageSize:   pageSize,
		TotalPages: totalPages,
	}, nil
}

func (f *FundApi) getTop10HoldingsViaHTML(fundCode string) ([]FundHoldingStock, error) {
	url := fmt.Sprintf("https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=jjcc&code=%s&topline=10&year=&month=&rt=%f",
		fundCode, float64(time.Now().UnixMilli())/1000.0)

	resp, err := f.client.SetTimeout(time.Duration(f.config.CrawlTimeOut)*time.Second).R().
		SetHeader("User-Agent", getRandomUA()).
		SetHeader("Accept", "*/*").
		SetHeader("Referer", fmt.Sprintf("https://fundf10.eastmoney.com/ccmx_%s.html", fundCode)).
		Get(url)
	if err != nil {
		return nil, fmt.Errorf("HTTP请求失败: %w", err)
	}
	if resp.StatusCode() != 200 {
		return nil, fmt.Errorf("HTTP状态码: %d", resp.StatusCode())
	}

	body := string(resp.Body())

	var htmlContent string
	contentMatch := regexp.MustCompile(`(?s)content:"(.*?)",\w`).FindStringSubmatch(body)
	if len(contentMatch) > 1 {
		htmlContent = contentMatch[1]
	}

	if htmlContent == "" {
		return nil, fmt.Errorf("未找到持仓数据内容")
	}

	quarter := ""
	quarterMatch := regexp.MustCompile(`(\d{4})[年-](\d{1,2})[月-](\d{1,2})日?`).FindStringSubmatch(htmlContent)
	if len(quarterMatch) > 0 {
		quarter = quarterMatch[0]
	}

	doc, err := goquery.NewDocumentFromReader(strings.NewReader(htmlContent))
	if err != nil {
		return nil, fmt.Errorf("解析HTML失败: %w", err)
	}

	var holdings []FundHoldingStock
	dataRowCount := 0
	doc.Find("table.tzpgtab tbody tr, table.tzxq tbody tr, table.tzpgtab tr, table.tzxq tr").Each(func(i int, s *goquery.Selection) {
		tds := s.Find("td")
		if tds.Length() < 7 {
			return
		}
		if dataRowCount >= 10 {
			return
		}
		dataRowCount++

		rankStr := strings.TrimSpace(tds.Eq(0).Text())
		rank, _ := strconv.Atoi(rankStr)
		if rank == 0 {
			rank = i + 1
		}

		stockCode := strings.TrimSpace(tds.Eq(1).Text())
		stockName := strings.TrimSpace(tds.Eq(2).Text())
		href, _ := tds.Eq(1).Find("a").Attr("href")
		market := detectStockMarket(href, stockCode)
		ratioStr := strings.TrimSpace(tds.Eq(6).Text())
		ratioStr = strings.TrimSuffix(ratioStr, "%")
		ratio, _ := strconv.ParseFloat(ratioStr, 64)

		var price *float64
		var changeRate *float64
		if tds.Length() >= 5 {
			priceStr := strings.TrimSpace(tds.Eq(3).Text())
			changeStr := strings.TrimSpace(tds.Eq(4).Text())
			changeStr = strings.TrimSuffix(changeStr, "%")
			if p, err := strconv.ParseFloat(priceStr, 64); err == nil && p > 0 {
				price = &p
			}
			if c, err := strconv.ParseFloat(changeStr, 64); err == nil {
				changeRate = &c
			}
		}

		shares := ""
		marketCap := ""
		if tds.Length() >= 9 {
			shares = strings.TrimSpace(tds.Eq(7).Text())
			marketCap = strings.TrimSpace(tds.Eq(8).Text())
		}

		if stockCode == "" && stockName == "" {
			return
		}

		holdings = append(holdings, FundHoldingStock{
			Rank:       rank,
			StockCode:  stockCode,
			StockName:  stockName,
			Ratio:      ratio,
			Shares:     shares,
			MarketCap:  marketCap,
			Quarter:    quarter,
			Price:      price,
			ChangeRate: changeRate,
			Market:     market,
		})
	})

	if len(holdings) == 0 {
		fallbackCount := 0
		doc.Find("table tr").Each(func(i int, s *goquery.Selection) {
			tds := s.Find("td")
			if tds.Length() < 4 {
				return
			}
			if fallbackCount >= 10 {
				return
			}
			fallbackCount++

			rank := i
			stockCode := strings.TrimSpace(tds.Eq(1).Text())
			stockName := strings.TrimSpace(tds.Eq(2).Text())
			href, _ := tds.Eq(1).Find("a").Attr("href")
			market := detectStockMarket(href, stockCode)

			var price *float64
			var changeRate *float64
			if tds.Length() >= 5 {
				priceStr := strings.TrimSpace(tds.Eq(3).Text())
				changeStr := strings.TrimSpace(tds.Eq(4).Text())
				changeStr = strings.TrimSuffix(changeStr, "%")
				if p, err := strconv.ParseFloat(priceStr, 64); err == nil && p > 0 {
					price = &p
				}
				if c, err := strconv.ParseFloat(changeStr, 64); err == nil {
					changeRate = &c
				}
			}

			ratioIdx := 6
			if tds.Length() < 7 {
				ratioIdx = tds.Length() - 1
			}
			ratioStr := strings.TrimSpace(tds.Eq(ratioIdx).Text())
			ratioStr = strings.TrimSuffix(ratioStr, "%")
			ratio, _ := strconv.ParseFloat(ratioStr, 64)

			if stockCode == "" && stockName == "" {
				return
			}

			shares := ""
			marketCap := ""
			if tds.Length() >= 9 {
				shares = strings.TrimSpace(tds.Eq(7).Text())
				marketCap = strings.TrimSpace(tds.Eq(8).Text())
			}

			holdings = append(holdings, FundHoldingStock{
				Rank:       rank,
				StockCode:  stockCode,
				StockName:  stockName,
				Ratio:      ratio,
				Shares:     shares,
				MarketCap:  marketCap,
				Quarter:    quarter,
				Price:      price,
				ChangeRate: changeRate,
				Market:     market,
			})
		})
	}

	return holdings, nil
}
