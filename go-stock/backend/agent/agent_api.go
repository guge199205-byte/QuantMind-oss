package agent

import (
	"context"
	"errors"
	"fmt"
	"go-stock/backend/data"
	"go-stock/backend/logger"
	"io"
	"regexp"
	"strings"
	"sync"

	"github.com/cloudwego/eino/adk"
	"github.com/cloudwego/eino/flow/agent"
	"github.com/cloudwego/eino/flow/agent/react"
	"github.com/cloudwego/eino/schema"
	"github.com/samber/lo"
)

type StockAiAgent struct {
	instance  *AgentInstance
	sessionID string
}

func NewStockAiAgentApi() *StockAiAgent {
	return &StockAiAgent{}
}

func (receiver StockAiAgent) newStockAiAgent(ctx *context.Context, aiConfigId int, thinkingMode bool, question string, agentMode string) *StockAiAgent {
	defer func() {
		if r := recover(); r != nil {
			logger.SugaredLogger.Errorf("panic in newStockAiAgent: %v", r)
		}
	}()

	settingConfig := data.GetSettingConfig()
	if settingConfig == nil {
		logger.SugaredLogger.Errorf("settingConfig is nil")
		return nil
	}

	aiConfig, ok := lo.Find(settingConfig.AiConfigs, func(item *data.AIConfig) bool {
		return uint(aiConfigId) == item.ID
	})
	if !ok {
		logger.SugaredLogger.Errorf("ai config not found for id: %d", aiConfigId)
		return nil
	}
	if aiConfig == nil {
		logger.SugaredLogger.Errorf("aiConfig is nil for id: %d", aiConfigId)
		return nil
	}

	aiConfig.Thinking = thinkingMode
	sessionID := aiConfig.SessionId
	if sessionID == "" {
		sessionID = fmt.Sprintf("ai-config-%d", aiConfig.ID)
	}

	agentInstance := GetStockAiAgent(ctx, *aiConfig, question, agentMode)
	if agentInstance == nil {
		logger.SugaredLogger.Errorf("failed to create agent for config id: %d", aiConfigId)
		return nil
	}

	return &StockAiAgent{
		instance:  agentInstance,
		sessionID: sessionID,
	}
}

func (receiver StockAiAgent) Chat(question string, aiConfigId int, sysPromptId *int) chan *schema.Message {
	return receiver.ChatWithContext(context.Background(), question, aiConfigId, sysPromptId, true, 20, false, "")
}

func (receiver StockAiAgent) ChatWithContext(ctx context.Context, question string, aiConfigId int, sysPromptId *int, memoryMode bool, memoryCount int, thinkingMode bool, agentMode string, optsOverride ...string) chan *schema.Message {
	ch := make(chan *schema.Message, 1024)

	go func() {
		defer func() {
			if r := recover(); r != nil {
				logger.SugaredLogger.Errorf("panic in ChatWithContext: %v", r)
				ch <- &schema.Message{
					Role:    schema.Assistant,
					Content: fmt.Sprintf("❌ 内部错误: %v", r),
				}
				close(ch)
			}
		}()

		var sessionIDOverride string
		var sysPromptOverride string
		if len(optsOverride) > 0 && optsOverride[0] != "" {
			sysPromptOverride = optsOverride[0]
		}
		if len(optsOverride) > 1 && optsOverride[1] != "" {
			sessionIDOverride = optsOverride[1]
		}

		stockAiAgent := receiver.newStockAiAgent(&ctx, aiConfigId, thinkingMode, question, agentMode)
		if stockAiAgent == nil {
			logger.SugaredLogger.Errorf("stockAiAgent is nil")
			ch <- &schema.Message{
				Role:    schema.Assistant,
				Content: "❌ AI 配置不存在或无效，请检查 AI 配置",
			}
			close(ch)
			return
		}

		if sessionIDOverride != "" {
			stockAiAgent.sessionID = sessionIDOverride
		}

		var memoryService *ChatMemoryService
		var historyMessages []*schema.Message
		if memoryMode && stockAiAgent.sessionID != "" {
			memoryService = NewChatMemoryService(stockAiAgent.sessionID, memoryCount)
			var err error
			historyMessages, err = memoryService.GetHistoryMessages()
			if err != nil {
				logger.SugaredLogger.Errorf("failed to get history messages: %v", err)
				historyMessages = nil
			}
		}

		sysPrompt := ""
		if sysPromptOverride != "" {
			sysPrompt = sysPromptOverride
		} else if sysPromptId == nil || *sysPromptId == 0 {
			sysPrompt = `你现在扮演一位拥有20年实战经验的顶级股票投资大师，精通价值投资、趋势交易、量化分析等多种策略。你擅长结合宏观经济、行业周期和企业基本面进行全方位、精准的多维分析，尤其对A股、港股、美股市场有深刻理解，始终秉持"风险控制第一"的原则，善于用通俗易懂的方式传授投资智慧。`
		} else {
			sysPrompt = data.NewPromptTemplateApi().GetPromptTemplateByID(*sysPromptId)
		}

		settingConfig := data.GetSettingConfig()
		aiConfig, _ := lo.Find(settingConfig.AiConfigs, func(item *data.AIConfig) bool {
			return uint(aiConfigId) == item.ID
		})
		maxInputTokens := 0
		if aiConfig != nil {
			maxInputTokens = getMaxInputTokens(aiConfig.MaxTokens)
		}

		sysPromptTokens := estimateTokens(sysPrompt)
		questionTokens := estimateTokens(question)
		historyBudget := maxInputTokens - sysPromptTokens - questionTokens
		if historyBudget < 0 {
			historyBudget = 0
		}
		if len(historyMessages) > 0 && historyBudget > 0 {
			historyMessages = trimHistoryMessages(historyMessages, historyBudget)
		}

		var messages []*schema.Message
		messages = append(messages, &schema.Message{
			Role:    schema.System,
			Content: sysPrompt,
		})
		messages = append(messages, historyMessages...)
		messages = append(messages, &schema.Message{
			Role:    schema.User,
			Content: question,
		})

		if memoryService != nil {
			if err := memoryService.AddUserMessage(question); err != nil {
				logger.SugaredLogger.Errorf("failed to save user message: %v", err)
			}
		}

		switch stockAiAgent.instance.Mode {
		case AgentModePlanExecute:
			runPlanExecuteWithFallback(ctx, stockAiAgent, messages, ch, memoryService, historyMessages, sysPrompt, question)
		default:
			runReact(ctx, stockAiAgent, messages, ch, memoryService, historyMessages, sysPrompt, question)
		}
	}()

	return ch
}

func runReact(ctx context.Context, stockAiAgent *StockAiAgent, messages []*schema.Message, ch chan *schema.Message, memoryService *ChatMemoryService, historyMessages []*schema.Message, sysPrompt string, question string) {
	reactAgent := stockAiAgent.instance.ReactAgent
	if reactAgent == nil {
		ch <- &schema.Message{
			Role:    schema.Assistant,
			Content: "❌ React Agent 实例无效",
		}
		close(ch)
		return
	}

	msgFutureOpt, msgFuture := react.WithMessageFuture()
	opts := agent.GetComposeOptions(msgFutureOpt)

	agentOption := []agent.AgentOption{
		agent.WithComposeOptions(opts...),
	}

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer func() {
			if r := recover(); r != nil {
				logger.SugaredLogger.Errorf("panic in processMessageFuture: %v", r)
			}
			wg.Done()
		}()
		processMessageFuture(msgFuture, ch)
	}()

	func() {
		defer close(ch)

		sr, err := reactAgent.Stream(ctx, messages, agentOption...)
		if err != nil {
			logger.SugaredLogger.Errorf("stream error: %v", err)

			if isTokenLimitError(err) && len(historyMessages) > 0 {
				logger.SugaredLogger.Infof("token limit exceeded, retrying with reduced history")
				halfLen := len(historyMessages) / 2
				if halfLen == 0 {
					halfLen = 1
				}
				historyMessages = historyMessages[halfLen:]
				messages = []*schema.Message{}
				messages = append(messages, &schema.Message{
					Role:    schema.System,
					Content: sysPrompt,
				})
				messages = append(messages, historyMessages...)
				messages = append(messages, &schema.Message{
					Role:    schema.User,
					Content: question,
				})

				sr, err = reactAgent.Stream(ctx, messages, agentOption...)
				if err != nil {
					if isTokenLimitError(err) {
						logger.SugaredLogger.Infof("still over token limit after trimming, retrying without history")
						messages = []*schema.Message{}
						messages = append(messages, &schema.Message{
							Role:    schema.System,
							Content: sysPrompt,
						})
						messages = append(messages, &schema.Message{
							Role:    schema.User,
							Content: question,
						})
						sr, err = reactAgent.Stream(ctx, messages, agentOption...)
					}
					if err != nil {
						errMsg := "❌ Agent 调用失败（token 超限）：输入内容超过模型最大上下文长度限制。请尝试缩短对话历史或使用支持更长上下文的模型。"
						ch <- &schema.Message{
							Role:    schema.Assistant,
							Content: errMsg,
						}
						return
					}
				}
			} else {
				errMsg := fmt.Sprintf("❌ Agent 调用失败：%v", err)
				if strings.Contains(err.Error(), "reasoning_content") || strings.Contains(err.Error(), "thinking is enabled") {
					errMsg += "\n\n**可能原因**：当前模型开启了 thinking/reasoning 模式，但该模式与 Agent 工具调用不兼容。\n\n**解决方案**：请在 AI 配置中关闭 thinking 模式，或切换到支持工具调用的模型（如 deepseek-chat、gpt-4o 等）。"
				}
				ch <- &schema.Message{
					Role:    schema.Assistant,
					Content: errMsg,
				}
				return
			}
		}
		if sr == nil {
			logger.SugaredLogger.Errorf("stream result is nil")
			ch <- &schema.Message{
				Role:    schema.Assistant,
				Content: "❌ 流式响应无效",
			}
			return
		}
		defer func() {
			sr.Close()
		}()

		var fullResponse strings.Builder
		for {
			msg, err := sr.Recv()
			if err != nil {
				if errors.Is(err, io.EOF) {
					break
				}
				logger.SugaredLogger.Errorf("failed to recv: %v", err)
				ch <- &schema.Message{
					Role:    schema.Assistant,
					Content: fmt.Sprintf("❌ 接收消息失败：%v", err),
				}
				break
			}
			if msg != nil && msg.Content != "" {
				fullResponse.WriteString(msg.Content)
			}
		}

		if fullResponse.Len() != 0 && memoryService != nil {
			if err := memoryService.AddAssistantMessage(fullResponse.String()); err != nil {
				logger.SugaredLogger.Errorf("failed to save assistant message: %v", err)
			}
		}
	}()

	wg.Wait()
}

func runPlanExecuteWithFallback(ctx context.Context, stockAiAgent *StockAiAgent, messages []*schema.Message, ch chan *schema.Message, memoryService *ChatMemoryService, historyMessages []*schema.Message, sysPrompt string, question string) {
	defer close(ch)

	// 首先尝试 PlanExecute 模式
	planExecuteSuccess := tryPlanExecute(ctx, stockAiAgent, messages, ch, memoryService)

	if !planExecuteSuccess {
		// 如果 PlanExecute 失败，降级到 React 模式
		logger.SugaredLogger.Warnf("PlanExecute 模式失败，降级到 React 模式")

		safeSend(ch, &schema.Message{
			Role:             schema.Assistant,
			Content:          "",
			ReasoningContent: "[FALLBACK]⚠️ 检测到编码问题，切换到标准分析模式...\n",
		})

		// 创建临时的 React Agent
		reactAgent := createFallbackReactAgent(ctx, stockAiAgent)
		if reactAgent != nil {
			runReactWithAgent(ctx, reactAgent, messages, ch, memoryService, historyMessages, sysPrompt, question)
		} else {
			safeSend(ch, &schema.Message{
				Role:    schema.Assistant,
				Content: "❌ 无法创建备用分析引擎，请稍后重试",
			})
		}
	}
}

func tryPlanExecute(ctx context.Context, stockAiAgent *StockAiAgent, messages []*schema.Message, ch chan *schema.Message, memoryService *ChatMemoryService) bool {
	adkAgent := stockAiAgent.instance.AdkAgent
	if adkAgent == nil {
		return false
	}

	runner := adk.NewRunner(ctx, adk.RunnerConfig{
		Agent: adkAgent,
	})

	safeSend(ch, &schema.Message{
		Role:             schema.Assistant,
		Content:          "",
		ReasoningContent: "[STEP]🧠 规划模式启动，正在分析问题并制定执行计划...\n",
	})

	iter := runner.Run(ctx, messages)

	var fullResponse strings.Builder
	stepCount := 0
	lastPhase := ""

	for {
		event, ok := iter.Next()
		if !ok {
			break
		}
		if event == nil {
			continue
		}

		if event.Err != nil {
			logger.SugaredLogger.Errorf("agent event error: %v", event.Err)

			// 检查是否是编码相关错误
			if strings.Contains(event.Err.Error(), "unmarshal plan error") ||
				strings.Contains(event.Err.Error(), "invalid char") ||
				strings.Contains(event.Err.Error(), "UTF-8") {
				logger.SugaredLogger.Warnf("检测到编码错误，触发降级机制")
				return false // 触发降级
			}

			// 处理 exceeds max steps 错误
			if strings.Contains(event.Err.Error(), "exceeds max steps") || strings.Contains(event.Err.Error(), "exceeds max iterations") {
				if fullResponse.Len() > 0 {
					safeSend(ch, &schema.Message{
						Role:    schema.Assistant,
						Content: "\n\n---\n\n⚠️ **分析步骤已达上限，以下为已生成的部分分析结果：**\n\n",
					})
					safeSend(ch, &schema.Message{
						Role:    schema.Assistant,
						Content: fullResponse.String(),
					})
					return true
				}
				errMsg := "⚠️ 分析步骤已达上限，无法完成完整分析。\n\n**建议**：\n1. 简化问题，将复杂分析拆分成多个简单问题\n2. 在 AI 配置中尝试使用支持更长上下文的模型\n3. 减少对话历史或开启新对话"
				safeSend(ch, &schema.Message{
					Role:    schema.Assistant,
					Content: errMsg,
				})
				return true
			}

			// 其他错误按正常处理
			errMsg := fmt.Sprintf("❌ Agent 调用失败：%v", event.Err)
			if isTokenLimitError(event.Err) {
				errMsg = "❌ Agent 调用失败（token 超限）：输入内容超过模型最大上下文长度限制。请尝试缩短对话历史或使用支持更长上下文的模型。"
			} else if strings.Contains(event.Err.Error(), "reasoning_content") || strings.Contains(event.Err.Error(), "thinking is enabled") {
				errMsg += "\n\n**可能原因**：当前模型开启了 thinking/reasoning 模式，但该模式与 Agent 工具调用不兼容。\n\n**解决方案**：请在 AI 配置中关闭 thinking 模式，或切换到支持工具调用的模型（如 deepseek-chat、gpt-4o 等）。"
			} else if strings.Contains(event.Err.Error(), "unmarshal plan error") || strings.Contains(event.Err.Error(), "invalid char") {
				errMsg += "\n\n**可能原因**：计划解析时遇到中文字符编码问题，通常是模型返回的计划内容包含非UTF-8字符。\n\n**解决方案**：请尝试重新提问，或切换到不同的AI模型。"
			}
			safeSend(ch, &schema.Message{
				Role:    schema.Assistant,
				Content: errMsg,
			})
			return true // 非编码错误，不需要降级
		}

		if event.Output != nil && event.Output.MessageOutput != nil {
			mv := event.Output.MessageOutput
			phase := detectPhase(mv.Role, mv.ToolName)
			if phase != "" && phase != lastPhase {
				lastPhase = phase
				if phase == "planning" {
					safeSend(ch, &schema.Message{
						Role:             schema.Assistant,
						Content:          "",
						ReasoningContent: "[STEP]📋 正在制定执行计划...\n",
					})
				} else if phase == "executing" {
					stepCount++
					safeSend(ch, &schema.Message{
						Role:             schema.Assistant,
						Content:          "",
						ReasoningContent: fmt.Sprintf("[STEP]⚡ 执行步骤 %d...\n", stepCount),
					})
				} else if phase == "replanning" {
					safeSend(ch, &schema.Message{
						Role:             schema.Assistant,
						Content:          "",
						ReasoningContent: "[STEP]🔄 评估进度，调整计划...\n",
					})
				}
			}

			if mv.IsStreaming && mv.MessageStream != nil {
				processAdkMessageStream(mv.MessageStream, mv.Role, mv.ToolName, ch, &fullResponse)
			} else if mv.Message != nil {
				processAdkMessage(mv.Message, mv.Role, mv.ToolName, ch, &fullResponse)
			}
		}
	}

	if fullResponse.Len() != 0 && memoryService != nil {
		if err := memoryService.AddAssistantMessage(fullResponse.String()); err != nil {
			logger.SugaredLogger.Errorf("failed to save assistant message: %v", err)
		}
	}

	return true // 成功完成
}

func createFallbackReactAgent(ctx context.Context, stockAiAgent *StockAiAgent) *react.Agent {
	// 从 PlanExecute Agent 中提取原始配置来创建 React Agent
	// 这里需要重新创建，因为我们没有保存原始的 chatModel 和 tools

	// 为了简化，我们返回 nil，让上层处理
	// 在实际生产环境中，应该保存原始配置或重新创建
	logger.SugaredLogger.Warnf("暂不支持降级到 React 模式，需要重新实现")
	return nil
}

func runReactWithAgent(ctx context.Context, reactAgent *react.Agent, messages []*schema.Message, ch chan *schema.Message, memoryService *ChatMemoryService, historyMessages []*schema.Message, sysPrompt string, question string) {
	// 类似于原来的 runReact 函数，但使用指定的 agent
	if reactAgent == nil {
		safeSend(ch, &schema.Message{
			Role:    schema.Assistant,
			Content: "❌ React Agent 实例无效",
		})
		return
	}

	msgFutureOpt, msgFuture := react.WithMessageFuture()
	opts := agent.GetComposeOptions(msgFutureOpt)

	agentOption := []agent.AgentOption{
		agent.WithComposeOptions(opts...),
	}

	var wg sync.WaitGroup
	wg.Add(1)
	go func() {
		defer func() {
			if r := recover(); r != nil {
				logger.SugaredLogger.Errorf("panic in processMessageFuture: %v", r)
			}
			wg.Done()
		}()
		processMessageFuture(msgFuture, ch)
	}()

	func() {
		defer close(ch)

		sr, err := reactAgent.Stream(ctx, messages, agentOption...)
		if err != nil {
			logger.SugaredLogger.Errorf("stream error: %v", err)
			errMsg := fmt.Sprintf("❌ React Agent 调用失败：%v", err)
			safeSend(ch, &schema.Message{
				Role:    schema.Assistant,
				Content: errMsg,
			})
			return
		}
		if sr == nil {
			logger.SugaredLogger.Errorf("stream result is nil")
			safeSend(ch, &schema.Message{
				Role:    schema.Assistant,
				Content: "❌ 流式响应无效",
			})
			return
		}
		defer func() {
			sr.Close()
		}()

		var fullResponse strings.Builder
		for {
			msg, err := sr.Recv()
			if err != nil {
				if errors.Is(err, io.EOF) {
					break
				}
				logger.SugaredLogger.Errorf("failed to recv: %v", err)
				safeSend(ch, &schema.Message{
					Role:    schema.Assistant,
					Content: fmt.Sprintf("❌ 接收消息失败：%v", err),
				})
				break
			}
			if msg != nil && msg.Content != "" {
				fullResponse.WriteString(msg.Content)
				safeSend(ch, &schema.Message{
					Role:    schema.Assistant,
					Content: msg.Content,
				})
			}
		}

		if fullResponse.Len() != 0 && memoryService != nil {
			if err := memoryService.AddAssistantMessage(fullResponse.String()); err != nil {
				logger.SugaredLogger.Errorf("failed to save assistant message: %v", err)
			}
		}
	}()

	wg.Wait()
}

func runPlanExecute(ctx context.Context, stockAiAgent *StockAiAgent, messages []*schema.Message, ch chan *schema.Message, memoryService *ChatMemoryService) {
	defer close(ch)

	adkAgent := stockAiAgent.instance.AdkAgent
	if adkAgent == nil {
		ch <- &schema.Message{
			Role:    schema.Assistant,
			Content: "❌ PlanExecute Agent 实例无效",
		}
		return
	}

	runner := adk.NewRunner(ctx, adk.RunnerConfig{
		Agent: adkAgent,
	})

	safeSend(ch, &schema.Message{
		Role:             schema.Assistant,
		Content:          "",
		ReasoningContent: "[STEP]🧠 规划模式启动，正在分析问题并制定执行计划...\n",
	})

	iter := runner.Run(ctx, messages)

	var fullResponse strings.Builder
	stepCount := 0
	lastPhase := ""

	for {
		event, ok := iter.Next()
		if !ok {
			break
		}
		if event == nil {
			continue
		}

		if event.Err != nil {
			logger.SugaredLogger.Errorf("agent event error: %v", event.Err)

			// 处理 exceeds max steps 错误
			if strings.Contains(event.Err.Error(), "exceeds max steps") || strings.Contains(event.Err.Error(), "exceeds max iterations") {
				if fullResponse.Len() > 0 {
					safeSend(ch, &schema.Message{
						Role:    schema.Assistant,
						Content: "\n\n---\n\n⚠️ **分析步骤已达上限，以下为已生成的部分分析结果：**\n\n",
					})
					safeSend(ch, &schema.Message{
						Role:    schema.Assistant,
						Content: fullResponse.String(),
					})
				} else {
					errMsg := "⚠️ 分析步骤已达上限，无法完成完整分析。\n\n**建议**：\n1. 简化问题，将复杂分析拆分成多个简单问题\n2. 在 AI 配置中尝试使用支持更长上下文的模型\n3. 减少对话历史或开启新对话"
					safeSend(ch, &schema.Message{
						Role:    schema.Assistant,
						Content: errMsg,
					})
				}
				continue
			}

			errMsg := fmt.Sprintf("❌ Agent 调用失败：%v", event.Err)
			if isTokenLimitError(event.Err) {
				errMsg = "❌ Agent 调用失败（token 超限）：输入内容超过模型最大上下文长度限制。请尝试缩短对话历史或使用支持更长上下文的模型。"
			} else if strings.Contains(event.Err.Error(), "reasoning_content") || strings.Contains(event.Err.Error(), "thinking is enabled") {
				errMsg += "\n\n**可能原因**：当前模型开启了 thinking/reasoning 模式，但该模式与 Agent 工具调用不兼容。\n\n**解决方案**：请在 AI 配置中关闭 thinking 模式，或切换到支持工具调用的模型（如 deepseek-chat、gpt-4o 等）。"
			} else if strings.Contains(event.Err.Error(), "unmarshal plan error") || strings.Contains(event.Err.Error(), "invalid char") {
				errMsg += "\n\n**可能原因**：计划解析时遇到中文字符编码问题，通常是模型返回的计划内容包含非UTF-8字符。\n\n**解决方案**：请尝试重新提问，或切换到不同的AI模型。"
			}
			safeSend(ch, &schema.Message{
				Role:    schema.Assistant,
				Content: errMsg,
			})
			continue
		}

		if event.Output != nil && event.Output.MessageOutput != nil {
			mv := event.Output.MessageOutput
			phase := detectPhase(mv.Role, mv.ToolName)
			if phase != "" && phase != lastPhase {
				lastPhase = phase
				if phase == "planning" {
					safeSend(ch, &schema.Message{
						Role:             schema.Assistant,
						Content:          "",
						ReasoningContent: "[STEP]📋 正在制定执行计划...\n",
					})
				} else if phase == "executing" {
					stepCount++
					safeSend(ch, &schema.Message{
						Role:             schema.Assistant,
						Content:          "",
						ReasoningContent: fmt.Sprintf("[STEP]⚡ 执行步骤 %d...\n", stepCount),
					})
				} else if phase == "replanning" {
					safeSend(ch, &schema.Message{
						Role:             schema.Assistant,
						Content:          "",
						ReasoningContent: "[STEP]🔄 评估进度，调整计划...\n",
					})
				}
			}

			if mv.IsStreaming && mv.MessageStream != nil {
				processAdkMessageStream(mv.MessageStream, mv.Role, mv.ToolName, ch, &fullResponse)
			} else if mv.Message != nil {
				processAdkMessage(mv.Message, mv.Role, mv.ToolName, ch, &fullResponse)
			}
		}
	}

	if fullResponse.Len() != 0 && memoryService != nil {
		if err := memoryService.AddAssistantMessage(fullResponse.String()); err != nil {
			logger.SugaredLogger.Errorf("failed to save assistant message: %v", err)
		}
	}
}

func detectPhase(role schema.RoleType, toolName string) string {
	if toolName == "plan" {
		return "planning"
	}
	if toolName == "respond" {
		return "responding"
	}
	if role == schema.Tool {
		return "executing"
	}
	if role == schema.Assistant {
		return "executing"
	}
	return ""
}

func processMessageFuture(msgFuture react.MessageFuture, ch chan *schema.Message) {
	if msgFuture == nil || ch == nil {
		logger.SugaredLogger.Errorf("msgFuture or ch is nil")
		return
	}

	iter := msgFuture.GetMessageStreams()
	if iter == nil {
		logger.SugaredLogger.Errorf("message stream iterator is nil")
		return
	}

	for {
		sr, ok, err := iter.Next()
		if err != nil {
			logger.SugaredLogger.Errorf("failed to get next message stream: %v", err)
			return
		}
		if !ok {
			break
		}
		if sr == nil {
			continue
		}

		var reasoningBuilder strings.Builder
		var contentBuilder strings.Builder
		toolCallsMap := make(map[int]*strings.Builder)
		toolCallNames := make(map[int]string)
		var toolResult *struct {
			name    string
			content string
		}

		for {
			msg, err := sr.Recv()
			if err != nil {
				if errors.Is(err, io.EOF) {
					break
				}
				logger.SugaredLogger.Errorf("failed to recv from message stream: %v", err)
				return
			}
			if msg == nil {
				continue
			}

			if msg.ReasoningContent != "" {
				reasoningBuilder.WriteString(msg.ReasoningContent)
				safeSend(ch, &schema.Message{
					Role:             schema.Assistant,
					Content:          "",
					ReasoningContent: msg.ReasoningContent,
				})
			}

			if len(msg.ToolCalls) > 0 {
				for _, tc := range msg.ToolCalls {
					idx := 0
					if tc.Index != nil {
						idx = *tc.Index
					}
					if _, exists := toolCallsMap[idx]; !exists {
						toolCallsMap[idx] = &strings.Builder{}
					}
					if tc.Function.Name != "" {
						toolCallNames[idx] = tc.Function.Name
					}
					toolCallsMap[idx].WriteString(tc.Function.Arguments)
				}
			}

			if msg.Role == schema.Tool && msg.Content != "" {
				toolResult = &struct {
					name    string
					content string
				}{
					name:    msg.ToolName,
					content: msg.Content,
				}
			}

			if msg.Role == schema.Assistant && msg.Content != "" {
				contentBuilder.WriteString(msg.Content)
				safeSend(ch, &schema.Message{
					Role:    schema.Assistant,
					Content: msg.Content,
				})
			}
		}

		if reasoningBuilder.Len() > 0 {
			fmt.Printf("\n[Reasoning]\n%s\n", reasoningBuilder.String())
		}

		if len(toolCallsMap) > 0 {
			for idx := 0; idx < len(toolCallsMap); idx++ {
				if builder, exists := toolCallsMap[idx]; exists {
					name := toolCallNames[idx]
					fmt.Printf("\n[ToolCall] %s(%s)\n", name, builder.String())
					safeSend(ch, &schema.Message{
						Role:             schema.Assistant,
						Content:          "",
						ReasoningContent: fmt.Sprintf("[STEP]🔧 调用工具：%s(%s)\n", name, builder.String()),
					})
				}
			}
		}

		if toolResult != nil {
			safeSend(ch, &schema.Message{
				Role:             schema.Assistant,
				Content:          "",
				ReasoningContent: fmt.Sprintf("[STEP]✅ %s 返回结果（%d字）\n", toolResult.name, len(toolResult.content)),
			})
			fmt.Printf("\n[ToolResult] %s:\n%s\n", toolResult.name, truncateString(toolResult.content, 300))
		}

		if contentBuilder.Len() > 0 && len(toolCallsMap) == 0 {
			fmt.Printf("\n[FinalAnswer]\n%s\n", contentBuilder.String())
		}
	}
}

func processAdkMessageStream(sr *schema.StreamReader[*schema.Message], role schema.RoleType, toolName string, ch chan *schema.Message, fullResponse *strings.Builder) {
	for {
		msg, err := sr.Recv()
		if err != nil {
			break
		}
		if msg == nil {
			continue
		}
		handleAdkMessage(msg, role, toolName, ch, fullResponse)
	}
}

func processAdkMessage(msg *schema.Message, role schema.RoleType, toolName string, ch chan *schema.Message, fullResponse *strings.Builder) {
	handleAdkMessage(msg, role, toolName, ch, fullResponse)
}

func handleAdkMessage(msg *schema.Message, role schema.RoleType, toolName string, ch chan *schema.Message, fullResponse *strings.Builder) {
	if msg.ReasoningContent != "" {
		safeSend(ch, &schema.Message{
			Role:             schema.Assistant,
			Content:          "",
			ReasoningContent: msg.ReasoningContent,
		})
	}

	if len(msg.ToolCalls) > 0 {
		for _, tc := range msg.ToolCalls {
			if tc.Function.Name != "" {
				safeSend(ch, &schema.Message{
					Role:             schema.Assistant,
					Content:          "",
					ReasoningContent: fmt.Sprintf("[STEP]🔧 调用工具：%s(%s)\n", tc.Function.Name, tc.Function.Arguments),
				})
			}
		}
	}

	if msg.Role == schema.Tool && msg.Content != "" {
		resultPreview := msg.Content
		if len(resultPreview) > 500 {
			resultPreview = resultPreview[:500] + "...(结果已截断)"
		}
		safeSend(ch, &schema.Message{
			Role:             schema.Assistant,
			Content:          "",
			ReasoningContent: fmt.Sprintf("[STEP]✅ %s 返回结果（%d字）\n", toolName, len(msg.Content)),
		})
		fmt.Printf("\n[ToolResult] %s:\n%s\n", toolName, truncateString(msg.Content, 300))
	}

	if msg.Content != "" && (role == schema.Assistant || msg.Role == schema.Assistant) {
		cleanContent := stripPlanJSON(msg.Content)
		if cleanContent != "" {
			fullResponse.WriteString(cleanContent)
			safeSend(ch, &schema.Message{
				Role:    schema.Assistant,
				Content: cleanContent,
			})
		}
	}
}

func stripPlanJSON(content string) string {
	lines := strings.Split(content, "\n")
	var filtered []string
	inJSONBlock := false

	for _, line := range lines {
		trimmed := strings.TrimSpace(line)

		if strings.HasPrefix(trimmed, "```json") {
			inJSONBlock = true
			continue
		}
		if inJSONBlock && strings.HasPrefix(trimmed, "```") {
			inJSONBlock = false
			continue
		}
		if inJSONBlock {
			if strings.Contains(trimmed, `"steps"`) {
				continue
			}
		}

		if strings.HasPrefix(trimmed, "{") && strings.Contains(trimmed, `"steps"`) {
			continue
		}

		filtered = append(filtered, line)
	}

	result := strings.Join(filtered, "\n")

	for strings.Contains(result, "\n\n\n") {
		result = strings.ReplaceAll(result, "\n\n\n", "\n\n")
	}

	return strings.TrimSpace(result)
}

func formatMarkdown(content string) string {
	if content == "" {
		return content
	}

	inCodeBlock := false
	lines := strings.Split(content, "\n")
	var result []string

	for i, line := range lines {
		trimmed := strings.TrimLeft(line, " \t")

		if strings.HasPrefix(trimmed, "```") {
			inCodeBlock = !inCodeBlock
			if !inCodeBlock {
				result = append(result, trimmed)
				continue
			}
		}

		if inCodeBlock {
			result = append(result, line)
			continue
		}

		if trimmed != line && trimmed != "" {
			line = trimmed
		}

		if i > 0 && isBlockElement(trimmed) {
			prev := ""
			if len(result) > 0 {
				prev = result[len(result)-1]
			}
			if prev != "" && !isBlockElement(strings.TrimLeft(prev, " \t")) {
				result = append(result, "")
			}
		}

		line = splitInlineHeading(line)

		result = append(result, line)
	}

	return strings.Join(result, "\n")
}

var headingRe = regexp.MustCompile(`(#{1,6}\s+\S)`)

func splitInlineHeading(line string) string {
	idx := headingRe.FindStringIndex(line)
	if idx == nil {
		return line
	}
	if idx[0] == 0 {
		return line
	}
	prefix := line[:idx[0]]
	if strings.TrimSpace(prefix) == "" {
		return line
	}
	return prefix + "\n\n" + line[idx[0]:]
}

func isBlockElement(line string) bool {
	if len(line) == 0 {
		return false
	}
	if line[0] == '#' {
		return true
	}
	if strings.HasPrefix(line, "- ") || strings.HasPrefix(line, "* ") || strings.HasPrefix(line, "+ ") {
		return true
	}
	if strings.HasPrefix(line, "```") {
		return true
	}
	if strings.HasPrefix(line, "> ") {
		return true
	}
	if len(line) >= 2 && (line[0] >= '1' && line[0] <= '9') && line[1] == '.' {
		return true
	}
	if strings.HasPrefix(line, "---") || strings.HasPrefix(line, "***") || strings.HasPrefix(line, "___") {
		return true
	}
	if strings.HasPrefix(line, "|") {
		return true
	}
	return false
}

func safeSend(ch chan *schema.Message, msg *schema.Message) {
	defer func() {
		if r := recover(); r != nil {
			logger.SugaredLogger.Errorf("panic when sending to channel: %v", r)
		}
	}()
	select {
	case ch <- msg:
	default:
		logger.SugaredLogger.Warnf("channel full, message dropped")
	}
}

func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
