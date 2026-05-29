package data

import (
	"encoding/json"
	"go-stock/backend/db"
	"go-stock/backend/models"
	"time"
)

const maxSavedMessages = 65535 * 10000

// GetAiAssistantSession 获取指定 sessionId 的会话消息列表，若 sessionId 为空则获取最新的
func GetAiAssistantSession(sessionId string) (*models.AiAssistantSessionResp, error) {
	var row models.AiAssistantSession
	var err error
	if sessionId != "" {
		err = db.Dao.Model(&models.AiAssistantSession{}).Where("session_id = ?", sessionId).First(&row).Error
	} else {
		err = db.Dao.Model(&models.AiAssistantSession{}).Order("updated_at DESC").First(&row).Error
	}
	resp := &models.AiAssistantSessionResp{
		Messages:  []models.AiAssistantMessage{},
		SessionId: row.SessionId,
	}
	if err != nil {
		return resp, nil
	}
	if row.Messages == "" {
		return resp, nil
	}
	var list []models.AiAssistantMessage
	if err := json.Unmarshal([]byte(row.Messages), &list); err != nil {
		return resp, nil
	}
	resp.Messages = list
	return resp, nil
}

// SaveAiAssistantSession 保存会话消息到数据库，若 sessionId 已存在则更新，否则创建新记录
func SaveAiAssistantSession(sessionId string, messages []models.AiAssistantMessage) error {
	if len(messages) == 0 {
		return nil
	}
	toSave := messages
	if len(toSave) > maxSavedMessages {
		toSave = toSave[len(toSave)-maxSavedMessages:]
	}
	raw, err := json.Marshal(toSave)
	if err != nil {
		return err
	}
	payload := string(raw)

	var existing models.AiAssistantSession
	err = db.Dao.Model(&models.AiAssistantSession{}).Where("session_id = ?", sessionId).First(&existing).Error
	if err == nil {
		return db.Dao.Model(&models.AiAssistantSession{}).Where("session_id = ?", sessionId).Updates(map[string]interface{}{
			"messages":   payload,
			"updated_at": time.Now(),
		}).Error
	}
	return db.Dao.Create(&models.AiAssistantSession{SessionId: sessionId, Messages: payload}).Error
}
