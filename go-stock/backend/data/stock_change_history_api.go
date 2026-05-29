package data

import (
	"encoding/json"
	"fmt"
	"go-stock/backend/db"
	"go-stock/backend/models"
	"sort"
	"strings"
	"time"

	"gorm.io/gorm/clause"
)

type StockChangeHistoryService struct{}

func NewStockChangeHistoryService() *StockChangeHistoryService {
	return &StockChangeHistoryService{}
}

func (s *StockChangeHistoryService) SaveStockChanges(items []StockChangeItem) error {
	if len(items) == 0 {
		return nil
	}

	today := time.Now().Format("2006-01-02")
	var histories []models.StockChangeHistory

	for _, item := range items {
		history := models.StockChangeHistory{
			ChangeTime: item.Time,
			ChangeDate: today,
			StockCode:  item.Code,
			StockName:  item.Name,
			Market:     item.Market,
			ChangeType: item.ChangeType,
			TypeName:   item.TypeName,
			Volume:     item.Volume,
			Price:      item.Price,
			ChangeRate: item.ChangeRate,
			Amount:     item.Amount,
		}
		histories = append(histories, history)
	}

	return db.Dao.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "change_date"}, {Name: "stock_code"}, {Name: "change_time"}},
		DoNothing: true,
	}).CreateInBatches(histories, 100).Error
}

func (s *StockChangeHistoryService) SaveStockChangesWithDedup(items []StockChangeItem) (int, error) {
	if len(items) == 0 {
		return 0, nil
	}

	today := time.Now().Format("2006-01-02")
	var histories []models.StockChangeHistory
	for _, item := range items {
		history := models.StockChangeHistory{
			ChangeTime: item.Time,
			ChangeDate: today,
			StockCode:  item.Code,
			StockName:  item.Name,
			Market:     item.Market,
			ChangeType: item.ChangeType,
			TypeName:   item.TypeName,
			Volume:     item.Volume,
			Price:      item.Price,
			ChangeRate: item.ChangeRate,
			Amount:     item.Amount,
			Industry:   item.Industry,
			Concept:    item.Concept,
		}
		histories = append(histories, history)
	}

	if len(histories) == 0 {
		return 0, nil
	}

	result := db.Dao.Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "change_date"}, {Name: "stock_code"}, {Name: "change_time"}, {Name: "change_type"}, {Name: "price"}, {Name: "change_rate"}, {Name: "amount"}, {Name: "volume"}},
		DoNothing: true,
	}).CreateInBatches(histories, 100)

	if result.Error != nil {
		return 0, result.Error
	}

	return int(result.RowsAffected), nil
}

func (s *StockChangeHistoryService) SaveStockChange(item StockChangeItem) error {
	today := time.Now().Format("2006-01-02")
	history := models.StockChangeHistory{
		ChangeTime: item.Time,
		ChangeDate: today,
		StockCode:  item.Code,
		StockName:  item.Name,
		Market:     item.Market,
		ChangeType: item.ChangeType,
		TypeName:   item.TypeName,
		Volume:     item.Volume,
		Price:      item.Price,
		ChangeRate: item.ChangeRate,
		Amount:     item.Amount,
	}
	return db.Dao.Create(&history).Error
}

func (s *StockChangeHistoryService) GetHistoryList(query models.StockChangeHistoryQuery) (*models.StockChangeHistoryPageData, error) {
	if query.Page <= 0 {
		query.Page = 1
	}
	//if query.PageSize <= 0 || query.PageSize > 100 {
	//	query.PageSize = 50
	//}

	dbQuery := db.Dao.Model(&models.StockChangeHistory{})

	if query.StockCode != "" {
		dbQuery = dbQuery.Where("stock_code LIKE ?", "%"+query.StockCode+"%")
	}
	if query.StockName != "" {
		dbQuery = dbQuery.Where("stock_name LIKE ?", "%"+query.StockName+"%")
	}
	if query.ChangeType > 0 {
		dbQuery = dbQuery.Where("change_type = ?", query.ChangeType)
	}
	if len(query.ChangeTypes) > 0 {
		dbQuery = dbQuery.Where("change_type IN ?", query.ChangeTypes)
	}
	if query.TypeName != "" {
		dbQuery = dbQuery.Where("type_name = ?", query.TypeName)
	}
	if query.StartDate != "" {
		dbQuery = dbQuery.Where("change_date >= ?", query.StartDate)
	}
	if query.EndDate != "" {
		dbQuery = dbQuery.Where("change_date <= ?", query.EndDate)
	}
	if query.StartTime != "" {
		dbQuery = dbQuery.Where("change_time >= ?", query.StartTime)
	}
	if query.EndTime != "" {
		dbQuery = dbQuery.Where("change_time <= ?", query.EndTime)
	}
	if query.MinVolume > 0 {
		dbQuery = dbQuery.Where("volume >= ?", query.MinVolume)
	}
	if query.MinAmount > 0 {
		dbQuery = dbQuery.Where("amount >= ?", query.MinAmount)
	}
	if query.MinChangeRate != 0 {
		dbQuery = dbQuery.Where("change_rate >= ?", query.MinChangeRate)
	}
	if query.MaxChangeRate != 0 {
		dbQuery = dbQuery.Where("change_rate <= ?", query.MaxChangeRate)
	}
	if query.Industry != "" {
		dbQuery = dbQuery.Where("industry LIKE ?", "%"+query.Industry+"%")
	}
	if query.Concept != "" {
		dbQuery = dbQuery.Where("concept LIKE ?", "%"+query.Concept+"%")
	}

	var total int64
	if err := dbQuery.Count(&total).Error; err != nil {
		return nil, err
	}

	var list []models.StockChangeHistory
	offset := (query.Page - 1) * query.PageSize
	if err := dbQuery.Order("change_date DESC, change_time DESC").Offset(offset).Limit(query.PageSize).Find(&list).Error; err != nil {
		return nil, err
	}

	totalPages := int(total) / query.PageSize
	if int(total)%query.PageSize > 0 {
		totalPages++
	}

	return &models.StockChangeHistoryPageData{
		List:       list,
		Total:      total,
		Page:       query.Page,
		PageSize:   query.PageSize,
		TotalPages: totalPages,
	}, nil
}

func (s *StockChangeHistoryService) DeleteOldData(days int) error {
	cutoffDate := time.Now().AddDate(0, 0, -days).Format("2006-01-02")
	return db.Dao.Where("change_date < ?", cutoffDate).Delete(&models.StockChangeHistory{}).Error
}

func (s *StockChangeHistoryService) GetStockChangeStats(startDate, endDate string) (map[string]interface{}, error) {
	dbQuery := db.Dao.Model(&models.StockChangeHistory{})
	if startDate != "" {
		dbQuery = dbQuery.Where("change_date >= ?", startDate)
	}
	if endDate != "" {
		dbQuery = dbQuery.Where("change_date <= ?", endDate)
	}

	var totalCount int64
	if err := dbQuery.Count(&totalCount).Error; err != nil {
		return nil, err
	}

	type TypeCount struct {
		TypeName string
		Count    int64
	}
	var typeCounts []TypeCount
	if err := db.Dao.Model(&models.StockChangeHistory{}).
		Select("type_name, count(*) as count").
		Where("change_date >= ? AND change_date <= ?", startDate, endDate).
		Group("type_name").
		Order("count DESC").
		Find(&typeCounts).Error; err != nil {
		return nil, err
	}

	return map[string]interface{}{
		"totalCount": totalCount,
		"typeCounts": typeCounts,
	}, nil
}

type DailyChangeStats struct {
	ChangeDate string `json:"changeDate"`
	TotalCount int64  `json:"totalCount"`
	UpCount    int64  `json:"upCount"`
	DownCount  int64  `json:"downCount"`
	LimitUp    int64  `json:"limitUp"`
	LimitDown  int64  `json:"limitDown"`
}

func (s *StockChangeHistoryService) GetDailyChangeStats(days int) ([]DailyChangeStats, error) {
	startDate := time.Now().AddDate(0, 0, -days).Format("2006-01-02")

	type rawDailyStats struct {
		ChangeDate string
		TotalCount int64
		UpCount    int64
		DownCount  int64
	}

	var rawStats []rawDailyStats
	err := db.Dao.Model(&models.StockChangeHistory{}).
		Select("change_date, count(*) as total_count, sum(case when change_type in (4, 8201, 8202, 8193, 64, 8207, 8209, 8211, 8213, 8215) then 1 else 0 end) as up_count, sum(case when change_type in (8, 8203, 8204, 8194, 128, 8208, 8210, 8212, 8214, 8216) then 1 else 0 end) as down_count").
		Where("change_date >= ?", startDate).
		Group("change_date").
		Order("change_date ASC").
		Find(&rawStats).Error
	if err != nil {
		return nil, err
	}

	type limitStats struct {
		ChangeDate string
		LimitUp    int64
		LimitDown  int64
	}
	var limitData []limitStats
	err = db.Dao.Model(&models.StockChangeHistory{}).
		Select("change_date, sum(case when change_type = 4 then 1 else 0 end) as limit_up, sum(case when change_type = 8 then 1 else 0 end) as limit_down").
		Where("change_date >= ? AND change_type IN (4, 8)", startDate).
		Group("change_date").
		Order("change_date ASC").
		Find(&limitData).Error
	if err != nil {
		return nil, err
	}

	limitMap := make(map[string]limitStats)
	for _, l := range limitData {
		limitMap[l.ChangeDate] = l
	}

	var result []DailyChangeStats
	for _, r := range rawStats {
		l := limitMap[r.ChangeDate]
		result = append(result, DailyChangeStats{
			ChangeDate: r.ChangeDate,
			TotalCount: r.TotalCount,
			UpCount:    r.UpCount,
			DownCount:  r.DownCount,
			LimitUp:    l.LimitUp,
			LimitDown:  l.LimitDown,
		})
	}
	return result, nil
}

type ChangeTypeDailyStats struct {
	ChangeDate string `json:"changeDate"`
	TypeName   string `json:"typeName"`
	Count      int64  `json:"count"`
}

func (s *StockChangeHistoryService) GetChangeTypeDailyStats(days int) ([]ChangeTypeDailyStats, error) {
	startDate := time.Now().AddDate(0, 0, -days).Format("2006-01-02")

	var result []ChangeTypeDailyStats
	err := db.Dao.Model(&models.StockChangeHistory{}).
		Select("change_date, type_name, count(*) as count").
		Where("change_date >= ?", startDate).
		Group("change_date, type_name").
		Order("change_date ASC, count DESC").
		Find(&result).Error
	return result, err
}

type ChangeRankItem struct {
	Name      string `json:"name"`
	Code      string `json:"code,omitempty"`
	Count     int64  `json:"count"`
	UpCount   int64  `json:"upCount"`
	DownCount int64  `json:"downCount"`
}

type ChangeRankResult struct {
	TopStocks     []ChangeRankItem `json:"topStocks"`
	TopIndustries []ChangeRankItem `json:"topIndustries"`
	TopConcepts   []ChangeRankItem `json:"topConcepts"`
}

const (
	upChangeTypes   = "4,8201,8202,8193,64,8207,8209,8211,8213,8215"
	downChangeTypes = "8,8203,8204,8194,128,8208,8210,8212,8214,8216"
)

func (s *StockChangeHistoryService) GetChangeRank(days int, topN int) (*ChangeRankResult, error) {
	startDate := time.Now().AddDate(0, 0, -days).Format("2006-01-02")
	if topN <= 0 {
		topN = 20
	}

	type rankRow struct {
		Name     string
		Code     string
		TotalCnt int
		UpCnt    int
		DownCnt  int
	}

	var stockRows []rankRow
	err := db.Dao.Model(&models.StockChangeHistory{}).
		Select("stock_name as name, stock_code as code, count(*) as total_cnt, sum(case when change_type IN ("+upChangeTypes+") then 1 else 0 end) as up_cnt, sum(case when change_type IN ("+downChangeTypes+") then 1 else 0 end) as down_cnt").
		Where("change_date >= ?", startDate).
		Group("stock_code, stock_name").
		Order("total_cnt DESC").
		Limit(topN).
		Find(&stockRows).Error
	if err != nil {
		return nil, err
	}

	var topStocks []ChangeRankItem
	for _, r := range stockRows {
		topStocks = append(topStocks, ChangeRankItem{Name: r.Name, Code: r.Code, Count: int64(r.TotalCnt), UpCount: int64(r.UpCnt), DownCount: int64(r.DownCnt)})
	}

	var industryRows []rankRow
	err = db.Dao.Model(&models.StockChangeHistory{}).
		Select("industry as name, '' as code, count(*) as total_cnt, sum(case when change_type IN ("+upChangeTypes+") then 1 else 0 end) as up_cnt, sum(case when change_type IN ("+downChangeTypes+") then 1 else 0 end) as down_cnt").
		Where("change_date >= ? AND industry != '' AND industry IS NOT NULL", startDate).
		Group("industry").
		Order("total_cnt DESC").
		Limit(topN).
		Find(&industryRows).Error
	if err != nil {
		return nil, err
	}

	var topIndustries []ChangeRankItem
	for _, r := range industryRows {
		topIndustries = append(topIndustries, ChangeRankItem{Name: r.Name, Count: int64(r.TotalCnt), UpCount: int64(r.UpCnt), DownCount: int64(r.DownCnt)})
	}

	type conceptRow struct {
		Concept string
		Cnt     int
		UpCnt   int
		DownCnt int
	}
	var conceptRows []conceptRow
	err = db.Dao.Model(&models.StockChangeHistory{}).
		Select("concept, count(*) as cnt, sum(case when change_type IN ("+upChangeTypes+") then 1 else 0 end) as up_cnt, sum(case when change_type IN ("+downChangeTypes+") then 1 else 0 end) as down_cnt").
		Where("change_date >= ? AND concept != '' AND concept IS NOT NULL", startDate).
		Group("concept").
		Find(&conceptRows).Error
	if err != nil {
		return nil, err
	}

	type conceptAgg struct {
		Count     int64
		UpCount   int64
		DownCount int64
	}
	conceptAggMap := make(map[string]conceptAgg)
	for _, row := range conceptRows {
		concepts := splitConcepts(row.Concept)
		for _, c := range concepts {
			agg := conceptAggMap[c]
			agg.Count += int64(row.Cnt)
			agg.UpCount += int64(row.UpCnt)
			agg.DownCount += int64(row.DownCnt)
			conceptAggMap[c] = agg
		}
	}

	var topConcepts []ChangeRankItem
	for name, agg := range conceptAggMap {
		topConcepts = append(topConcepts, ChangeRankItem{Name: name, Count: agg.Count, UpCount: agg.UpCount, DownCount: agg.DownCount})
	}
	sort.Slice(topConcepts, func(i, j int) bool {
		return topConcepts[i].Count > topConcepts[j].Count
	})
	if len(topConcepts) > topN {
		topConcepts = topConcepts[:topN]
	}

	return &ChangeRankResult{
		TopStocks:     topStocks,
		TopIndustries: topIndustries,
		TopConcepts:   topConcepts,
	}, nil
}

type DailyDimensionStats struct {
	ChangeDate string `json:"changeDate"`
	UpCount    int64  `json:"upCount"`
	DownCount  int64  `json:"downCount"`
	TotalCount int64  `json:"totalCount"`
}

type TypeCountStats struct {
	TypeName   string `json:"typeName"`
	UpCount    int64  `json:"upCount"`
	DownCount  int64  `json:"downCount"`
	TotalCount int64  `json:"totalCount"`
}

func (s *StockChangeHistoryService) GetDailyDimensionStats(dimension string, name string, days int) ([]DailyDimensionStats, error) {
	startDate := time.Now().AddDate(0, 0, -days).Format("2006-01-02")

	var result []DailyDimensionStats
	query := db.Dao.Model(&models.StockChangeHistory{}).
		Select("change_date, sum(case when change_type IN ("+upChangeTypes+") then 1 else 0 end) as up_count, sum(case when change_type IN ("+downChangeTypes+") then 1 else 0 end) as down_count, count(*) as total_count").
		Where("change_date >= ?", startDate).
		Group("change_date").
		Order("change_date ASC")

	switch dimension {
	case "stock":
		query = query.Where("stock_code = ? OR stock_name = ?", name, name)
	case "industry":
		query = query.Where("industry = ?", name)
	case "concept":
		query = query.Where("concept LIKE ?", "%"+name+"%")
	case "type":
		query = query.Where("type_name = ?", name)
	default:
		return nil, fmt.Errorf("unsupported dimension: %s", dimension)
	}

	err := query.Find(&result).Error
	return result, err
}

func (s *StockChangeHistoryService) GetTypeStatsByDate(date string) ([]TypeCountStats, error) {
	var result []TypeCountStats
	err := db.Dao.Model(&models.StockChangeHistory{}).
		Select("type_name, sum(case when change_type IN ("+upChangeTypes+") then 1 else 0 end) as up_count, sum(case when change_type IN ("+downChangeTypes+") then 1 else 0 end) as down_count, count(*) as total_count").
		Where("change_date = ?", date).
		Group("type_name").
		Order("total_count DESC").
		Find(&result).Error
	return result, err
}

func splitConcepts(conceptStr string) []string {
	conceptStr = strings.TrimSpace(conceptStr)
	if conceptStr == "" {
		return nil
	}
	if strings.HasPrefix(conceptStr, "[") {
		var concepts []string
		if err := json.Unmarshal([]byte(conceptStr), &concepts); err == nil {
			return concepts
		}
	}
	parts := strings.Split(conceptStr, ",")
	var result []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			result = append(result, p)
		}
	}
	return result
}
