package data

import (
	"fmt"
	"go-stock/backend/db"
	"go-stock/backend/models"
	"strings"
)

type SkillApi struct{}

func NewSkillApi() *SkillApi {
	return &SkillApi{}
}

func (a *SkillApi) Create(skill *models.Skill) error {
	return db.Dao.Create(skill).Error
}

func (a *SkillApi) Update(skill *models.Skill) error {
	if skill == nil || skill.ID == 0 {
		return fmt.Errorf("无效的技能ID")
	}

	updates := map[string]any{
		"name":             skill.Name,
		"description":      skill.Description,
		"category":         skill.Category,
		"system_prompt":    skill.SystemPrompt,
		"examples":         skill.Examples,
		"trigger_keywords": skill.TriggerKeywords,
		"mcp_server_ids":   skill.MCPServerIDs,
		"enable":           skill.Enable,
		"sort_order":       skill.SortOrder,
	}

	return db.Dao.Model(&models.Skill{}).Where("id = ?", skill.ID).Updates(updates).Error
}

func (a *SkillApi) Delete(id uint) error {
	return db.Dao.Delete(&models.Skill{}, id).Error
}

func (a *SkillApi) GetByID(id uint) (*models.Skill, error) {
	var skill models.Skill
	err := db.Dao.First(&skill, id).Error
	if err != nil {
		return nil, err
	}
	return &skill, nil
}

func (a *SkillApi) List(query *models.SkillQuery) *models.SkillPageResp {
	var skills []models.Skill
	var total int64

	q := db.Dao.Model(&models.Skill{})

	if query.Name != "" {
		q = q.Where("name LIKE ?", "%"+query.Name+"%")
	}
	if query.Category != "" {
		q = q.Where("category = ?", query.Category)
	}
	if query.Enable != nil {
		q = q.Where("enable = ?", *query.Enable)
	}

	q.Count(&total)

	offset := (query.Page - 1) * query.PageSize
	q.Order("sort_order ASC, created_at DESC").Offset(offset).Limit(query.PageSize).Find(&skills)

	return &models.SkillPageResp{
		Total: int(total),
		Data:  skills,
	}
}

func (a *SkillApi) GetAll() []models.Skill {
	var skills []models.Skill
	db.Dao.Where("enable = ?", true).Order("sort_order ASC, created_at DESC").Find(&skills)
	return skills
}

func (a *SkillApi) EnableSkill(id uint, enable bool) error {
	return db.Dao.Model(&models.Skill{}).Where("id = ?", id).Update("enable", enable).Error
}

func (a *SkillApi) GetEnabledSkills() []models.Skill {
	var skills []models.Skill
	db.Dao.Where("enable = ?", true).Order("sort_order ASC, created_at DESC").Find(&skills)
	return skills
}

func (a *SkillApi) GetMCPServerIDs(skill *models.Skill) []uint {
	if skill.MCPServerIDs == "" {
		return nil
	}
	parts := strings.Split(skill.MCPServerIDs, ",")
	var ids []uint
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		var id uint
		fmt.Sscanf(p, "%d", &id)
		if id > 0 {
			ids = append(ids, id)
		}
	}
	return ids
}
