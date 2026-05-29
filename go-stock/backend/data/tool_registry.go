package data

import "strings"

// ToolContext 封装一次工具调用时需要用到的上下文
type ToolContext struct {
	Question             string
	Messages             *[]map[string]any
	CurrentAIContent     *strings.Builder
	ReasoningContentText *strings.Builder
	CurrentCallID        string
	FuncName             string
	Ch                   chan map[string]any
	StreamResponseID     string
	Model                string
	Source               string
}

// ToolHandler 统一的工具处理函数签名
type ToolHandler func(o *OpenAi, args string, ctx *ToolContext) error

var toolHandlers = map[string]ToolHandler{}

// registerToolHandler 注册一个工具处理函数
func registerToolHandler(name string, handler ToolHandler) {
	toolHandlers[name] = handler
}
