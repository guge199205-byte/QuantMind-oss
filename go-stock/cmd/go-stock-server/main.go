package main

import (
	"encoding/json"
	"go-stock/backend/data"
	"go-stock/backend/db"
	"go-stock/backend/logger"
	"go-stock/backend/models"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/duke-git/lancet/v2/slice"
)

func main() {
	os.MkdirAll("data", 0o755)
	db.Init("")
	data.InitAnalyzeSentiment()

	// Auto-migrate tables
	autoMigrate()

	// Load stock basic data from JSON files
	go initStockData()

	mux := http.NewServeMux()

	// Health
	mux.HandleFunc("/api/health", healthHandler)

	// News & Telegraph
	mux.HandleFunc("/api/v1/news/telegraph", telegraphHandler)
	mux.HandleFunc("/api/v1/news/sina", sinaNewsHandler)
	mux.HandleFunc("/api/v1/news/tradingview", tradingViewNewsHandler)
	mux.HandleFunc("/api/v1/news/list", newsListHandler)

	// Global Indexes
	mux.HandleFunc("/api/v1/indexes/global", globalIndexesHandler)
	mux.HandleFunc("/api/v1/indexes/cached", cachedIndexesHandler)

	// Industry
	mux.HandleFunc("/api/v1/industry/rank", industryRankHandler)
	mux.HandleFunc("/api/v1/industry/money", industryMoneyHandler)

	// Rankings
	mux.HandleFunc("/api/v1/rank/longtiger", longTigerHandler)
	mux.HandleFunc("/api/v1/rank/money", moneyRankHandler)

	// Hot
	mux.HandleFunc("/api/v1/hot/stocks", hotStocksHandler)
	mux.HandleFunc("/api/v1/hot/events", hotEventsHandler)
	mux.HandleFunc("/api/v1/hot/topics", hotTopicsHandler)

	// K-Line
	mux.HandleFunc("/api/v1/kline", klineHandler)

	// Stock
	mux.HandleFunc("/api/v1/stock/realtime", stockRealtimeHandler)
	mux.HandleFunc("/api/v1/stock/search", stockSearchHandler)

	// Research
	mux.HandleFunc("/api/v1/research/stock", stockResearchHandler)
	mux.HandleFunc("/api/v1/research/industry", industryResearchHandler)
	mux.HandleFunc("/api/v1/research/notice", stockNoticeHandler)

	// EastMoney AI Tools
	mux.HandleFunc("/api/v1/em/earnings", earningsReviewHandler)
	mux.HandleFunc("/api/v1/em/qa", financialQAHandler)
	mux.HandleFunc("/api/v1/em/industry", emIndustryResearchHandler)
	mux.HandleFunc("/api/v1/em/tracking", trackingReportHandler)
	mux.HandleFunc("/api/v1/em/search", financeSearchHandler)
	mux.HandleFunc("/api/v1/em/comparable", comparableCompanyHandler)
	mux.HandleFunc("/api/v1/em/hotspot", hotspotHandler)

	// Money Flow
	mux.HandleFunc("/api/v1/money/trend", moneyTrendHandler)

	// Stock Changes
	mux.HandleFunc("/api/v1/changes", stockChangesHandler)

	// Market Statistics
	mux.HandleFunc("/api/v1/statistics/today", todayStatisticsHandler)
	mux.HandleFunc("/api/v1/statistics/recent", recentStatisticsHandler)

	// Fund
	mux.HandleFunc("/api/v1/fund/list", fundListHandler)
	mux.HandleFunc("/api/v1/fund/followed", followedFundHandler)

	// Calendar
	mux.HandleFunc("/api/v1/calendar/invest", investCalendarHandler)
	mux.HandleFunc("/api/v1/calendar/cls", clsCalendarHandler)

	addr := ":18080"
	if p := os.Getenv("GO_STOCK_API_PORT"); p != "" {
		addr = ":" + p
	}
	logger.SugaredLogger.Infof("go-stock API server starting at %s", addr)
	if err := http.ListenAndServe(addr, withCORS(mux)); err != nil {
		logger.SugaredLogger.Fatalf("server error: %v", err)
	}
}

// --- Health ---

func healthHandler(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"ok":      true,
		"service": "go-stock",
		"time":    time.Now().Format("2006-01-02 15:04:05"),
	})
}

// --- News ---

func telegraphHandler(w http.ResponseWriter, r *http.Request) {
	timeout := queryInt64(r, "timeout", 30)
	result := data.NewMarketNewsApi().TelegraphList(timeout)
	writeJSON(w, http.StatusOK, result)
}

func sinaNewsHandler(w http.ResponseWriter, r *http.Request) {
	timeout := queryUint(r, "timeout", 30)
	result := data.NewMarketNewsApi().GetSinaNews(timeout)
	writeJSON(w, http.StatusOK, result)
}

func tradingViewNewsHandler(w http.ResponseWriter, _ *http.Request) {
	result := data.NewMarketNewsApi().TradingViewNews()
	writeJSON(w, http.StatusOK, result)
}

func newsListHandler(w http.ResponseWriter, r *http.Request) {
	source := r.URL.Query().Get("source")
	limit := queryInt(r, "limit", 50)
	result := data.NewMarketNewsApi().GetNewsList(source, limit)
	writeJSON(w, http.StatusOK, result)
}

// --- Global Indexes ---

func globalIndexesHandler(w http.ResponseWriter, r *http.Request) {
	timeout := queryUint(r, "timeout", 30)
	result := data.NewMarketNewsApi().GlobalStockIndexes(timeout)
	writeJSON(w, http.StatusOK, result)
}

func cachedIndexesHandler(w http.ResponseWriter, r *http.Request) {
	region := r.URL.Query().Get("region")
	result := data.NewMarketNewsApi().GetCachedGlobalStockIndexes(region)
	writeJSON(w, http.StatusOK, result)
}

// --- Industry ---

func industryRankHandler(w http.ResponseWriter, r *http.Request) {
	sort := r.URL.Query().Get("sort")
	if sort == "" {
		sort = "changepercent"
	}
	cnt := queryInt(r, "cnt", 20)
	result := data.NewMarketNewsApi().GetIndustryRank(sort, cnt)
	writeJSON(w, http.StatusOK, result)
}

func industryMoneyHandler(w http.ResponseWriter, r *http.Request) {
	fenlei := r.URL.Query().Get("fenlei")
	sort := r.URL.Query().Get("sort")
	if sort == "" {
		sort = "changepercent"
	}
	result := data.NewMarketNewsApi().GetIndustryMoneyRankSina(fenlei, sort)
	writeJSON(w, http.StatusOK, result)
}

// --- Rankings ---

func longTigerHandler(w http.ResponseWriter, r *http.Request) {
	date := r.URL.Query().Get("date")
	result := data.NewMarketNewsApi().LongTiger(date)
	writeJSON(w, http.StatusOK, result)
}

func moneyRankHandler(w http.ResponseWriter, r *http.Request) {
	sort := r.URL.Query().Get("sort")
	if sort == "" {
		sort = "changepercent"
	}
	result := data.NewMarketNewsApi().GetMoneyRankSina(sort)
	writeJSON(w, http.StatusOK, result)
}

// --- Hot ---

func hotStocksHandler(w http.ResponseWriter, r *http.Request) {
	size := queryInt(r, "size", 20)
	marketType := r.URL.Query().Get("marketType")
	if marketType == "" {
		marketType = "A"
	}
	result := data.NewMarketNewsApi().XUEQIUHotStock(size, marketType)
	writeJSON(w, http.StatusOK, result)
}

func hotEventsHandler(w http.ResponseWriter, r *http.Request) {
	size := queryInt(r, "size", 20)
	result := data.NewMarketNewsApi().HotEvent(size)
	writeJSON(w, http.StatusOK, result)
}

func hotTopicsHandler(w http.ResponseWriter, r *http.Request) {
	size := queryInt(r, "size", 20)
	result := data.NewMarketNewsApi().HotTopic(size)
	writeJSON(w, http.StatusOK, result)
}

// --- K-Line ---

func klineHandler(w http.ResponseWriter, r *http.Request) {
	code := r.URL.Query().Get("code")
	if code == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "code is required"})
		return
	}
	ktype := r.URL.Query().Get("type")
	if ktype == "" {
		ktype = "day"
	}
	days := queryInt(r, "days", 120)
	adjustType := r.URL.Query().Get("adjust")

	api := data.NewEastMoneyKLineApi(data.GetSettingConfig())

	var result *[]data.KLineData
	switch ktype {
	case "1min":
		result = api.GetMinuteKLine(code, data.KLineType1Min, days)
	case "5min":
		result = api.GetMinuteKLine(code, data.KLineType5Min, days)
	case "15min":
		result = api.GetMinuteKLine(code, data.KLineType15Min, days)
	case "30min":
		result = api.GetMinuteKLine(code, data.KLineType30Min, days)
	case "60min":
		result = api.GetMinuteKLine(code, data.KLineType60Min, days)
	case "week":
		result = api.GetWeekKLine(code, days)
	case "month":
		result = api.GetMonthKLine(code, days)
	case "quarter":
		result = api.GetQuarterKLine(code, days)
	case "year":
		result = api.GetYearKLine(code, days)
	case "adjust":
		result = api.GetAdjustedKLine(code, adjustType, days)
	default:
		result = api.GetDayKLine(code, days)
	}
	writeJSON(w, http.StatusOK, result)
}

// --- Stock ---

func stockRealtimeHandler(w http.ResponseWriter, r *http.Request) {
	codes := r.URL.Query().Get("codes")
	if codes == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "codes is required"})
		return
	}
	codeList := strings.Split(codes, ",")
	result, err := data.NewStockDataApi().GetStockCodeRealTimeData(codeList...)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, result)
}

func stockSearchHandler(w http.ResponseWriter, r *http.Request) {
	key := r.URL.Query().Get("key")
	if key == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "key is required"})
		return
	}
	result := data.NewStockDataApi().GetStockList(key)
	writeJSON(w, http.StatusOK, result)
}

// --- Research ---

func stockResearchHandler(w http.ResponseWriter, r *http.Request) {
	code := r.URL.Query().Get("code")
	if code == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "code is required"})
		return
	}
	days := queryInt(r, "days", 30)
	result := data.NewMarketNewsApi().StockResearchReport(code, days)
	writeJSON(w, http.StatusOK, result)
}

func industryResearchHandler(w http.ResponseWriter, r *http.Request) {
	code := r.URL.Query().Get("code")
	if code == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "code is required"})
		return
	}
	days := queryInt(r, "days", 30)
	result := data.NewMarketNewsApi().IndustryResearchReport(code, days)
	writeJSON(w, http.StatusOK, result)
}

func stockNoticeHandler(w http.ResponseWriter, r *http.Request) {
	stockList := r.URL.Query().Get("stocks")
	if stockList == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "stocks is required"})
		return
	}
	result := data.NewMarketNewsApi().StockNotice(stockList)
	writeJSON(w, http.StatusOK, result)
}

// --- EastMoney AI Tools ---

func earningsReviewHandler(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("query")
	reportDate := r.URL.Query().Get("reportDate")
	if query == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query is required"})
		return
	}
	result := data.NewEmAPI().EarningsReviewToMarkdown(query, reportDate)
	writeJSON(w, http.StatusOK, map[string]string{"result": result})
}

func financialQAHandler(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("query")
	deepThink := r.URL.Query().Get("deepThink") == "true"
	if query == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query is required"})
		return
	}
	result := data.NewEmAPI().FinancialQAToMarkdown(query, deepThink)
	writeJSON(w, http.StatusOK, map[string]string{"result": result})
}

func emIndustryResearchHandler(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("query")
	if query == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query is required"})
		return
	}
	result := data.NewEmAPI().IndustryResearchToMarkdown(query)
	writeJSON(w, http.StatusOK, map[string]string{"result": result})
}

func trackingReportHandler(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("query")
	if query == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query is required"})
		return
	}
	result := data.NewEmAPI().TrackingReportToMarkdown(query)
	writeJSON(w, http.StatusOK, map[string]string{"result": result})
}

func financeSearchHandler(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("query")
	if query == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query is required"})
		return
	}
	result := data.NewEmAPI().FinanceSearchToMarkdown(query)
	writeJSON(w, http.StatusOK, map[string]string{"result": result})
}

func comparableCompanyHandler(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("query")
	if query == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query is required"})
		return
	}
	result := data.NewEmAPI().ComparableCompanyAnalysisToMarkdown(query)
	writeJSON(w, http.StatusOK, map[string]string{"result": result})
}

func hotspotHandler(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("query")
	if query == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "query is required"})
		return
	}
	result := data.NewEmAPI().HotspotDiscoveryToMarkdown(query)
	writeJSON(w, http.StatusOK, map[string]string{"result": result})
}

// --- Money Flow ---

func moneyTrendHandler(w http.ResponseWriter, r *http.Request) {
	code := r.URL.Query().Get("code")
	if code == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "code is required"})
		return
	}
	days := queryInt(r, "days", 10)
	result := data.NewMarketNewsApi().GetStockMoneyTrendByDay(code, days)
	writeJSON(w, http.StatusOK, result)
}

// --- Stock Changes ---

func stockChangesHandler(w http.ResponseWriter, r *http.Request) {
	changeTypesStr := r.URL.Query().Get("changeTypes")
	pageIndex := queryInt(r, "pageIndex", 1)
	pageSize := queryInt(r, "pageSize", 50)

	api := data.NewStockChangesApi()
	if changeTypesStr == "" {
		result := api.GetStockAllChanges(pageIndex, pageSize)
		writeJSON(w, http.StatusOK, result)
		return
	}

	var changeTypes []int
	for _, s := range strings.Split(changeTypesStr, ",") {
		if v, err := strconv.Atoi(strings.TrimSpace(s)); err == nil {
			changeTypes = append(changeTypes, v)
		}
	}
	result := api.GetStockChanges(changeTypes, pageIndex, pageSize)
	writeJSON(w, http.StatusOK, result)
}

// --- Market Statistics ---

func todayStatisticsHandler(w http.ResponseWriter, _ *http.Request) {
	result := data.NewMarketStatisticApi().GetTodayData()
	writeJSON(w, http.StatusOK, result)
}

func recentStatisticsHandler(w http.ResponseWriter, r *http.Request) {
	days := queryInt(r, "days", 7)
	result := data.NewMarketStatisticApi().GetRecentDaysData(days)
	writeJSON(w, http.StatusOK, result)
}

// --- Fund ---

func fundListHandler(w http.ResponseWriter, r *http.Request) {
	key := r.URL.Query().Get("key")
	if key == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "key is required"})
		return
	}
	result := data.NewFundApi().GetFundList(key)
	writeJSON(w, http.StatusOK, result)
}

func followedFundHandler(w http.ResponseWriter, _ *http.Request) {
	result := data.NewFundApi().GetFollowedFund()
	writeJSON(w, http.StatusOK, result)
}

// --- Calendar ---

func investCalendarHandler(w http.ResponseWriter, r *http.Request) {
	yearMonth := r.URL.Query().Get("yearMonth")
	result := data.NewMarketNewsApi().InvestCalendar(yearMonth)
	writeJSON(w, http.StatusOK, result)
}

func clsCalendarHandler(w http.ResponseWriter, _ *http.Request) {
	result := data.NewMarketNewsApi().ClsCalendar()
	writeJSON(w, http.StatusOK, result)
}

// --- Helpers ---

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		w.Header().Set("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func queryInt(r *http.Request, key string, defaultVal int) int {
	s := r.URL.Query().Get(key)
	if s == "" {
		return defaultVal
	}
	v, err := strconv.Atoi(s)
	if err != nil {
		return defaultVal
	}
	return v
}

func queryInt64(r *http.Request, key string, defaultVal int64) int64 {
	s := r.URL.Query().Get(key)
	if s == "" {
		return defaultVal
	}
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		return defaultVal
	}
	return v
}

func queryUint(r *http.Request, key string, defaultVal uint) uint {
	s := r.URL.Query().Get(key)
	if s == "" {
		return defaultVal
	}
	v, err := strconv.ParseUint(s, 10, 64)
	if err != nil {
		return defaultVal
	}
	return uint(v)
}

func autoMigrate() {
	db.Dao.AutoMigrate(&data.StockBasic{})
	db.Dao.AutoMigrate(&data.IndexBasic{})
	db.Dao.AutoMigrate(&models.StockInfoHK{})
	db.Dao.AutoMigrate(&models.StockInfoUS{})
	db.Dao.AutoMigrate(&models.AllStockInfo{})
	db.Dao.AutoMigrate(&models.Telegraph{})
	db.Dao.AutoMigrate(&models.GlobalStockIndex{})
	db.Dao.AutoMigrate(&models.LongTigerRankData{})
	db.Dao.AutoMigrate(&models.HotItem{})
	db.Dao.AutoMigrate(&models.HotEvent{})
	db.Dao.AutoMigrate(&data.FollowedFund{})
	db.Dao.AutoMigrate(&data.FundBasic{})
	db.Dao.AutoMigrate(&models.MarketStatistic{})
	logger.SugaredLogger.Info("auto-migrate done")
}

func initStockData() {
	// Load A-stock basic data
	loadStockBasic("build/stock_basic.json")
	// Load HK stock data
	loadStockDataHK("build/stock_base_info_hk.json")
	// Load US stock data
	loadStockDataUS("build/stock_base_info_us.json")
}

func loadStockBasic(path string) {
	raw, err := os.ReadFile(path)
	if err != nil {
		logger.SugaredLogger.Warnf("skip stock_basic: %v", err)
		return
	}
	fields := "ts_code,symbol,name,area,industry,cnspell,market,list_date,act_name,act_ent_type,fullname,exchange,list_status,curr_type,enname,delist_date,is_hs"
	res := &data.TushareStockBasicResponse{}
	if err := json.Unmarshal(raw, res); err != nil {
		logger.SugaredLogger.Errorf("parse stock_basic.json: %v", err)
		return
	}
	count := 0
	for _, item := range res.Data.Items {
		stock := &data.StockBasic{}
		stockData := map[string]any{}
		for _, field := range strings.Split(fields, ",") {
			idx := slice.IndexOf(res.Data.Fields, field)
			if idx == -1 {
				continue
			}
			stockData[field] = item[idx]
		}
		jsonData, _ := json.Marshal(stockData)
		if err := json.Unmarshal(jsonData, stock); err != nil {
			continue
		}
		stock.ID = 0
		var cnt int64
		db.Dao.Model(&data.StockBasic{}).Where("ts_code = ?", stock.TsCode).Count(&cnt)
		if cnt > 0 {
			continue
		}
		db.Dao.Create(stock)
		count++
	}
	logger.SugaredLogger.Infof("loaded %d A-stock basics", count)
}

func loadStockDataHK(path string) {
	raw, err := os.ReadFile(path)
	if err != nil {
		logger.SugaredLogger.Warnf("skip HK stock data: %v", err)
		return
	}
	var v []models.StockInfoHK
	if err := json.Unmarshal(raw, &v); err != nil {
		logger.SugaredLogger.Errorf("parse HK stock json: %v", err)
		return
	}
	count := 0
	for _, item := range v {
		var cnt int64
		db.Dao.Model(&models.StockInfoHK{}).Where("code = ?", item.Code).Count(&cnt)
		if cnt > 0 {
			continue
		}
		db.Dao.Create(&item)
		count++
	}
	logger.SugaredLogger.Infof("loaded %d HK stocks", count)
}

func loadStockDataUS(path string) {
	raw, err := os.ReadFile(path)
	if err != nil {
		logger.SugaredLogger.Warnf("skip US stock data: %v", err)
		return
	}
	var v []models.StockInfoUS
	if err := json.Unmarshal(raw, &v); err != nil {
		logger.SugaredLogger.Errorf("parse US stock json: %v", err)
		return
	}
	count := 0
	for _, item := range v {
		var cnt int64
		db.Dao.Model(&models.StockInfoUS{}).Where("code = ?", item.Code).Count(&cnt)
		if cnt > 0 {
			continue
		}
		db.Dao.Create(&item)
		count++
	}
	logger.SugaredLogger.Infof("loaded %d US stocks", count)
}
