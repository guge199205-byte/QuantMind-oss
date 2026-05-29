package data

import (
	"context"
	"encoding/json"
	"fmt"
	"go-stock/backend/db"
	"go-stock/backend/logger"
	"go-stock/backend/models"
	"strings"
	"time"

	einomcp "github.com/cloudwego/eino-ext/components/tool/mcp"
	"github.com/mark3labs/mcp-go/client"
	"github.com/mark3labs/mcp-go/mcp"
)

type MCPServerApi struct{}

func NewMCPServerApi() *MCPServerApi {
	return &MCPServerApi{}
}

func (a *MCPServerApi) Create(server *models.MCPServer) error {
	return db.Dao.Create(server).Error
}

func (a *MCPServerApi) Update(server *models.MCPServer) error {
	if server == nil || server.ID == 0 {
		return fmt.Errorf("无效的服务器ID")
	}

	updates := map[string]any{
		"name":        server.Name,
		"description": server.Description,
		"url":         server.URL,
		"command":     server.Command,
		"args":        server.Args,
		"env":         server.Env,
		"enable":      server.Enable,
		"status":      server.Status,
	}

	return db.Dao.Model(&models.MCPServer{}).
		Where("id = ?", server.ID).
		Updates(updates).Error
}

func (a *MCPServerApi) Delete(id uint) error {
	return db.Dao.Delete(&models.MCPServer{}, id).Error
}

func (a *MCPServerApi) GetByID(id uint) (*models.MCPServer, error) {
	var server models.MCPServer
	err := db.Dao.First(&server, id).Error
	if err != nil {
		return nil, err
	}
	return &server, nil
}

func (a *MCPServerApi) List(query *models.MCPServerQuery) *models.MCPServerPageResp {
	var servers []models.MCPServer
	var total int64

	dbQuery := db.Dao.Model(&models.MCPServer{})

	if query.Name != "" {
		dbQuery = dbQuery.Where("name LIKE ?", "%"+query.Name+"%")
	}
	if query.Status != "" {
		dbQuery = dbQuery.Where("status = ?", query.Status)
	}
	if query.Enable != nil {
		dbQuery = dbQuery.Where("enable = ?", *query.Enable)
	}

	dbQuery.Count(&total)

	page := query.Page
	pageSize := query.PageSize
	if page < 1 {
		page = 1
	}
	if pageSize < 1 {
		pageSize = 10
	}

	err := dbQuery.Offset((page - 1) * pageSize).Limit(pageSize).Order("created_at DESC").Find(&servers).Error
	if err != nil {
		logger.SugaredLogger.Errorf("查询MCP服务器列表失败:%s", err.Error())
		return nil
	}

	return &models.MCPServerPageResp{
		Total: int(total),
		Data:  servers,
	}
}

func (a *MCPServerApi) GetAll() []models.MCPServer {
	var servers []models.MCPServer
	db.Dao.Where("enable = ?", true).Order("created_at DESC").Find(&servers)
	return servers
}

func (a *MCPServerApi) EnableServer(id uint, enable bool) error {
	return db.Dao.Model(&models.MCPServer{}).Where("id = ?", id).Updates(map[string]any{
		"enable": enable,
	}).Error
}

func (a *MCPServerApi) UpdateStatus(id uint, status string, testResult string) error {
	return db.Dao.Model(&models.MCPServer{}).Where("id = ?", id).Updates(map[string]any{
		"status":      status,
		"test_result": testResult,
	}).Error
}

func (a *MCPServerApi) SearchServers(keyword string) []models.MCPServer {
	var servers []models.MCPServer
	query := db.Dao.Model(&models.MCPServer{})
	if keyword != "" {
		keyword = strings.TrimSpace(keyword)
		query = query.Where("name LIKE ? OR description LIKE ? OR command LIKE ?",
			"%"+keyword+"%", "%"+keyword+"%", "%"+keyword+"%")
	}
	query.Order("created_at DESC").Limit(20).Find(&servers)
	return servers
}

func (a *MCPServerApi) TestConnection(id uint) (string, error) {
	server, err := a.GetByID(id)
	if err != nil {
		return "", err
	}

	a.UpdateStatus(id, "testing", "")

	if server.URL == "" {
		a.UpdateStatus(id, "unavailable", "URL不能为空")
		return "", fmt.Errorf("URL不能为空")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	cli, err := client.NewStreamableHttpClient(server.URL)
	if err != nil {
		errMsg := fmt.Sprintf("创建MCP客户端失败: %s", err.Error())
		a.UpdateStatus(id, "unavailable", errMsg)
		return "", fmt.Errorf("%s", errMsg)
	}

	initRequest := mcp.InitializeRequest{}
	initRequest.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initRequest.Params.ClientInfo = mcp.Implementation{
		Name:    "go-stock",
		Version: "1.0.0",
	}

	_, err = cli.Initialize(ctx, initRequest)
	if err != nil {
		errMsg := fmt.Sprintf("初始化MCP连接失败: %s", err.Error())
		a.UpdateStatus(id, "unavailable", errMsg)
		return "", fmt.Errorf("%s", errMsg)
	}

	tools, err := einomcp.GetTools(ctx, &einomcp.Config{Cli: cli})
	if err != nil {
		errMsg := fmt.Sprintf("获取工具列表失败: %s", err.Error())
		a.UpdateStatus(id, "unavailable", errMsg)
		return "", fmt.Errorf("%s", errMsg)
	}

	toolCount := len(tools)

	a.UpdateStatus(id, "available", fmt.Sprintf("可用，共 %d 个工具", toolCount))

	db.Dao.Where("mcp_server_id = ?", id).Delete(&models.MCPServerTool{})

	if toolCount == 0 {
		return "连接成功！但未发现可用工具", nil
	}

	var toolNames []string
	for _, t := range tools {
		info, err := t.Info(ctx)
		if err != nil || info == nil {
			continue
		}
		toolNames = append(toolNames, info.Name)

		var paramsJSON string
		if info.ParamsOneOf != nil {
			js, err := info.ParamsOneOf.ToJSONSchema()
			if err == nil && js != nil {
				if data, err := json.Marshal(js); err == nil {
					paramsJSON = string(data)
				}
			}
		}

		toolRecord := models.MCPServerTool{
			MCPServerID:  id,
			ToolName:     info.Name,
			Description:  info.Desc,
			ParamsSchema: paramsJSON,
		}
		if err := db.Dao.Create(&toolRecord).Error; err != nil {
			logger.SugaredLogger.Warnf("保存MCP工具信息失败 [%s]: %v", info.Name, err)
		}
	}

	return fmt.Sprintf("连接成功!发现 %d 个工具: %s", toolCount, strings.Join(toolNames, ", ")), nil
}

func (a *MCPServerApi) GetToolsByServerID(serverID uint) []models.MCPServerTool {
	var tools []models.MCPServerTool
	db.Dao.Where("mcp_server_id = ?", serverID).Order("tool_name ASC").Find(&tools)
	return tools
}

func (a *MCPServerApi) GetAllTools() []models.MCPServerTool {
	var tools []models.MCPServerTool
	db.Dao.Order("mcp_server_id ASC, tool_name ASC").Find(&tools)
	return tools
}
