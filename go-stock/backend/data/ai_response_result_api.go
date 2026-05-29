package data

import (
	"go-stock/backend/db"
	"go-stock/backend/models"
	"time"

	"github.com/duke-git/lancet/v2/datetime"
	"github.com/duke-git/lancet/v2/strutil"
)

type AIResponseResultService struct{}

func NewAIResponseResultService() *AIResponseResultService {
	return &AIResponseResultService{}
}

// GetAIResponseResultList 分页查询AI响应结果
func (s *AIResponseResultService) GetAIResponseResultList(query models.AIResponseResultQuery) (*models.AIResponseResultPageData, error) {
	var list []models.AIResponseResult
	var total int64

	q := db.Dao.Model(&models.AIResponseResult{})

	// 构建查询条件
	if query.ChatId != "" {
		q.Where("chat_id LIKE ?", "%"+query.ChatId+"%")
	}
	if query.ModelName != "" {
		q.Or("model_name LIKE ?", "%"+query.ModelName+"%")
	}
	if query.StockCode != "" {
		q.Or("stock_code LIKE ?", "%"+query.StockCode+"%")
	}
	if query.Question != "" {
		q.Or("question LIKE ?", "%"+query.Question+"%")
	}
	if query.StartDate != "" && query.EndDate != "" {
		query.StartDate = strutil.ReplaceWithMap(query.StartDate, map[string]string{
			"T": " ",
			"Z": "",
		})
		query.EndDate = strutil.ReplaceWithMap(query.EndDate, map[string]string{
			"T": " ",
			"Z": "",
		})

		startDate, err := time.Parse("2006-01-02 15:04:05", query.StartDate)
		if err != nil {
			startDate, _ = time.Parse("2006-01-02", query.StartDate)
		}

		endDate, err := time.Parse("2006-01-02 15:04:05", query.EndDate)
		if err != nil {
			endDate, _ = time.Parse("2006-01-02", query.EndDate)
		}
		q = q.Where("created_at BETWEEN ? AND ?", datetime.BeginOfDay(startDate), datetime.EndOfDay(endDate))
		//q = q.Where("created_at BETWEEN ? AND ?", query.StartDate, query.EndDate)
	}

	// 计算总数
	err := q.Count(&total).Error
	if err != nil {
		return nil, err
	}

	// 设置默认分页参数
	page := query.Page
	pageSize := query.PageSize
	if page <= 0 {
		page = 1
	}
	if pageSize <= 0 || pageSize > 100 {
		pageSize = 10
	}

	// 执行分页查询
	offset := (page - 1) * pageSize
	err = q.Offset(offset).Limit(pageSize).Order("created_at DESC").Find(&list).Error
	if err != nil {
		return nil, err
	}

	totalPages := int((total + int64(pageSize) - 1) / int64(pageSize))

	return &models.AIResponseResultPageData{
		List:       list,
		Total:      total,
		Page:       page,
		PageSize:   pageSize,
		TotalPages: totalPages,
	}, nil
}

// DeleteAIResponseResult 根据ID删除AI响应结果
func (s *AIResponseResultService) DeleteAIResponseResult(id uint) error {

	// 使用软删除
	result := db.Dao.Where("id = ?", id).Delete(&models.AIResponseResult{})

	return result.Error
}

// BatchDeleteAIResponseResult 批量删除AI响应结果
func (s *AIResponseResultService) BatchDeleteAIResponseResult(ids []uint) error {
	// 使用软删除
	result := db.Dao.Where("id IN ?", ids).Delete(&models.AIResponseResult{})

	return result.Error
}
