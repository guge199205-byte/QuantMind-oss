package data

import (
	"encoding/json"
	"fmt"
	"go-stock/backend/db"
	"go-stock/backend/logger"
	"go-stock/backend/models"
	"go-stock/backend/util"
	"io"
	"net/http"
	"regexp"
	"strconv"
	"strings"
	"time"
)

type StockChangeItem struct {
	Time       string  `json:"time" md:"时间"`
	Code       string  `json:"code" md:"股票代码"`
	Name       string  `json:"name" md:"股票名称"`
	Market     int     `json:"market" md:"-"`
	ChangeType int     `json:"changeType" md:"-"`
	TypeName   string  `json:"typeName" md:"异动类型"`
	Volume     int64   `json:"volume" md:"数量"`
	Price      float64 `json:"price" md:"价格"`
	ChangeRate float64 `json:"changeRate" md:"涨跌幅(%)"`
	Amount     float64 `json:"amount" md:"金额"`
	Industry   string  `json:"industry" md:"所属行业"`
	Concept    string  `json:"concept" md:"所属概念"`
}

type StockChangesResponse struct {
	TotalCount int               `json:"totalCount"`
	Data       []StockChangeItem `json:"data"`
}

type stockChangesAPIResponse struct {
	Data struct {
		Tc       int `json:"tc"`
		Allstock []struct {
			Tm int    `json:"tm"`
			C  string `json:"c"`
			M  int    `json:"m"`
			N  string `json:"n"`
			T  int    `json:"t"`
			I  string `json:"i"`
		} `json:"allstock"`
	} `json:"data"`
}

type StockChangesApi struct {
}

func NewStockChangesApi() *StockChangesApi {
	return &StockChangesApi{}
}

var changeTypeNames = map[int]string{
	8201: "火箭发射",
	8202: "快速反弹",
	8193: "大笔买入",
	4:    "封涨停板",
	32:   "打开跌停板",
	64:   "有大买盘",
	8207: "竞价上涨",
	8209: "高开5日线",
	8211: "向上缺口",
	8213: "60日新高",
	8215: "60日大幅上涨",
	8204: "加速下跌",
	8203: "高台跳水",
	8194: "大笔卖出",
	8:    "封跌停板",
	16:   "打开涨停板",
	128:  "有大卖盘",
	8208: "竞价下跌",
	8210: "低开5日线",
	8212: "向下缺口",
	8214: "60日新低",
	8216: "60日大幅下跌",
}

func (a *StockChangesApi) GetStockChanges(changeTypes []int, pageIndex, pageSize int) *StockChangesResponse {
	//if len(changeTypes) == 0 {
	//	changeTypes = []int{8201, 8202, 8193, 4, 8204, 8203, 8194, 8}
	//}

	typeStrs := make([]string, len(changeTypes))
	for i, t := range changeTypes {
		typeStrs[i] = strconv.Itoa(t)
	}

	url := fmt.Sprintf(
		"https://push2ex.eastmoney.com/getAllStockChanges?type=%s&ut=7eea3edcaed734bea9cbfc24409ed989&pageindex=%d&pagesize=%d&dpt=wzchanges&_=%d",
		strings.Join(typeStrs, ","),
		pageIndex,
		pageSize,
		time.Now().UnixMilli(),
	)

	//logger.SugaredLogger.Infof("请求URL: %s", url)

	client := &http.Client{Timeout: 10 * time.Second}
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		logger.SugaredLogger.Errorf("创建请求失败: %v", err)
		return nil
	}
	req.Header.Set("User-Agent", getRandomUA())

	resp, err := client.Do(req)
	if err != nil {
		logger.SugaredLogger.Errorf("获取股票异动数据失败: %v", err)
		return nil
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		logger.SugaredLogger.Errorf("读取响应失败: %v", err)
		return nil
	}

	jsonStr := extractJSON(string(body))
	if jsonStr == "" {
		logger.SugaredLogger.Error("解析JSON失败")
		return nil
	}

	var apiResp stockChangesAPIResponse
	if err := json.Unmarshal([]byte(jsonStr), &apiResp); err != nil {
		logger.SugaredLogger.Errorf("解析JSON失败: %v", err)
		return nil
	}

	result := &StockChangesResponse{
		TotalCount: apiResp.Data.Tc,
		Data:       make([]StockChangeItem, 0, len(apiResp.Data.Allstock)),
	}

	stockCodes := make([]string, 0, len(apiResp.Data.Allstock))
	for _, item := range apiResp.Data.Allstock {
		stockCodes = append(stockCodes, item.C)
	}

	stockInfoMap := a.getStockInfoMap(stockCodes)

	for _, item := range apiResp.Data.Allstock {
		changeItem := StockChangeItem{
			Time:       formatTime(item.Tm),
			Code:       item.C,
			Name:       item.N,
			Market:     item.M,
			ChangeType: item.T,
			TypeName:   getChangeTypeName(item.T),
		}

		if info, ok := stockInfoMap[item.C]; ok {
			changeItem.Industry = info.INDUSTRY
			changeItem.Concept = info.CONCEPT
		}

		parseItemData(item.I, &changeItem, item.T)
		result.Data = append(result.Data, changeItem)
	}

	return result
}

func (a *StockChangesApi) getStockInfoMap(stockCodes []string) map[string]models.AllStockInfo {
	result := make(map[string]models.AllStockInfo)
	if len(stockCodes) == 0 {
		return result
	}

	var stockInfos []models.AllStockInfo
	if err := db.Dao.Model(&models.AllStockInfo{}).Where("sec_uri_tycode IN ?", stockCodes).Find(&stockInfos).Error; err != nil {
		logger.SugaredLogger.Errorf("查询股票信息失败: %v", err)
		return result
	}

	for _, info := range stockInfos {
		result[info.SECURITYCODE] = info
	}
	return result
}

func (a *StockChangesApi) GetStockChangesReadable(changeTypes []int, pageIndex, pageSize int) string {
	result := a.GetStockChanges(changeTypes, pageIndex, pageSize)
	if result == nil || len(result.Data) == 0 {
		return "暂无股票异动数据"
	}

	summary := fmt.Sprintf("共发现 %d 条股票异动记录", result.TotalCount)
	return summary + "\n\n" + util.MarkdownTableWithTitle("股票异动数据", result.Data)
}

func (a *StockChangesApi) GetStockAllChanges(pageIndex, pageSize int) *StockChangesResponse {
	var allTypes []int
	return a.GetStockChanges(allTypes, pageIndex, pageSize)
}

func (a *StockChangesApi) GetAllStockChangesWithPaging(pageSize int) *StockChangesResponse {
	if pageSize <= 0 {
		pageSize = 500
	}

	allTypes := []int{
		8201, 8202, 8193, 4, 32, 64, 8207, 8209, 8211, 8213, 8215, 16,
		8204, 8203, 8194, 8, 128, 8208, 8210, 8212, 8214, 8216,
	}

	firstPage := a.GetStockChanges(allTypes, 0, pageSize)
	if firstPage == nil {
		return nil
	}

	if firstPage.TotalCount <= pageSize {
		return firstPage
	}

	allData := make([]StockChangeItem, 0, firstPage.TotalCount)
	totalPages := (firstPage.TotalCount)/pageSize + 1
	if firstPage.TotalCount%pageSize == 0 {
		totalPages--
	}

	for page := 0; page <= totalPages; page++ {
		logger.SugaredLogger.Infof("获取第 %d 页数据,共 %d 页", page, totalPages)
		nextPage := a.GetStockChanges(allTypes, page, pageSize)
		if nextPage == nil || len(nextPage.Data) == 0 {
			break
		}
		allData = append(allData, nextPage.Data...)
	}

	return &StockChangesResponse{
		TotalCount: firstPage.TotalCount,
		Data:       allData,
	}
}

func extractJSON(jsonp string) string {
	re := regexp.MustCompile(`^\w+\((.*)\)$`)
	matches := re.FindStringSubmatch(jsonp)
	if len(matches) > 1 {
		return matches[1]
	}
	return jsonp
}

func formatTime(tm int) string {
	hour := tm / 10000
	minute := (tm % 10000) / 100
	second := tm % 100
	return fmt.Sprintf("%02d:%02d:%02d", hour, minute, second)
}

func getChangeTypeName(t int) string {
	if name, ok := changeTypeNames[t]; ok {
		return name
	}
	return fmt.Sprintf("类型%d", t)
}

func parseItemData(data string, item *StockChangeItem, changeType int) {
	parts := strings.Split(data, ",")
	switch changeType {
	case 8201, 8202, 8203, 8204, 8207, 8208, 8209, 8210:
		if len(parts) >= 1 {
			if rate, err := strconv.ParseFloat(parts[0], 64); err == nil {
				item.ChangeRate = rate * 100
			}
		}
		if len(parts) >= 2 {
			if price, err := strconv.ParseFloat(parts[1], 64); err == nil {
				item.Price = price
			}
		}
	case 8193, 8194:
		if len(parts) >= 1 {
			if vol, err := strconv.ParseInt(parts[0], 10, 64); err == nil {
				item.Volume = vol
			}
		}
		if len(parts) >= 2 {
			if price, err := strconv.ParseFloat(parts[1], 64); err == nil {
				item.Price = price
			}
		}
		if len(parts) >= 3 {
			if rate, err := strconv.ParseFloat(parts[2], 64); err == nil {
				item.ChangeRate = rate * 100
			}
		}
		if len(parts) >= 4 {
			if amount, err := strconv.ParseFloat(parts[3], 64); err == nil {
				item.Amount = amount
			}
		}
	case 4, 8:
		if len(parts) >= 1 {
			if price, err := strconv.ParseFloat(parts[0], 64); err == nil {
				item.Price = price
			}
		}
		if len(parts) >= 2 {
			if vol, err := strconv.ParseInt(parts[1], 10, 64); err == nil {
				item.Volume = vol
			}
		}
		if len(parts) >= 4 {
			if rate, err := strconv.ParseFloat(parts[3], 64); err == nil {
				item.ChangeRate = rate * 100
			}
		}
	case 16, 32:
		if len(parts) >= 1 {
			if price, err := strconv.ParseFloat(parts[0], 64); err == nil {
				item.Price = price
			}
		}
		if len(parts) >= 2 {
			if rate, err := strconv.ParseFloat(parts[1], 64); err == nil {
				item.ChangeRate = rate * 100
			}
		}
	case 64, 128:
		if len(parts) >= 1 {
			if vol, err := strconv.ParseInt(parts[0], 10, 64); err == nil {
				item.Volume = vol
			}
		}
		if len(parts) >= 2 {
			if price, err := strconv.ParseFloat(parts[1], 64); err == nil {
				item.Price = price
			}
		}
		if len(parts) >= 3 {
			if rate, err := strconv.ParseFloat(parts[2], 64); err == nil {
				item.ChangeRate = rate * 100
			}
		}
		if len(parts) >= 4 {
			if amount, err := strconv.ParseFloat(parts[3], 64); err == nil {
				item.Amount = amount
			}
		}
	case 8213, 8214:
		if len(parts) >= 1 {
			if price, err := strconv.ParseFloat(parts[0], 64); err == nil {
				item.Price = price
			}
		}
		if len(parts) >= 3 {
			if rate, err := strconv.ParseFloat(parts[2], 64); err == nil {
				item.ChangeRate = rate * 100
			}
		}
	case 8215, 8216:
		if len(parts) >= 1 {
			if rate, err := strconv.ParseFloat(parts[0], 64); err == nil {
				item.ChangeRate = rate * 100
			}
		}
		if len(parts) >= 2 {
			if price, err := strconv.ParseFloat(parts[1], 64); err == nil {
				item.Price = price
			}
		}
	default:
		if len(parts) >= 1 {
			if vol, err := strconv.ParseInt(parts[0], 10, 64); err == nil {
				item.Volume = vol
			}
		}
		if len(parts) >= 2 {
			if price, err := strconv.ParseFloat(parts[1], 64); err == nil {
				item.Price = price
			}
		}
		if len(parts) >= 3 {
			if rate, err := strconv.ParseFloat(parts[2], 64); err == nil {
				item.ChangeRate = rate * 100
			}
		}
		if len(parts) >= 4 {
			if amount, err := strconv.ParseFloat(parts[3], 64); err == nil {
				item.Amount = amount
			}
		}
	}
}

func formatVolume(vol int64) string {
	if vol >= 100000000 {
		return fmt.Sprintf("%.2f亿", float64(vol)/100000000)
	} else if vol >= 10000 {
		return fmt.Sprintf("%.2f万", float64(vol)/10000)
	}
	return fmt.Sprintf("%d", vol)
}

func formatAmount(amount float64) string {
	if amount >= 100000000 {
		return fmt.Sprintf("%.2f亿", amount/100000000)
	} else if amount >= 10000 {
		return fmt.Sprintf("%.2f万", amount/10000)
	}
	return fmt.Sprintf("%.2f", amount)
}
