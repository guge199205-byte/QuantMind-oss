package agent

import (
	"go-stock/backend/logger"
	"strings"
	"unicode"

	"github.com/cloudwego/eino/schema"
)

const (
	chineseCharsPerToken = 1.5
	englishCharsPerToken = 4.0
	// 以下预留用于 estimateMessagesTokens 之外的系统/工具/ReAct 开销，过大会过早压缩用户上下文。
	// PlanExecute 中「已完成步骤」另见 agent.go 的 compressExecutedStepResult。
	toolsTokenReserve  = 8000
	skillPromptReserve = 4000
	reactLoopReserve   = 8000
	safetyMargin       = 0.85
)

func estimateTokens(text string) int {
	if text == "" {
		return 0
	}
	chineseCount := 0
	nonChineseCount := 0
	for _, r := range text {
		if unicode.Is(unicode.Han, r) {
			chineseCount++
		} else {
			nonChineseCount++
		}
	}
	tokens := float64(chineseCount)/chineseCharsPerToken + float64(nonChineseCount)/englishCharsPerToken
	return int(tokens) + 1
}

func estimateMessagesTokens(messages []*schema.Message) int {
	total := 0
	for _, msg := range messages {
		if msg == nil {
			continue
		}
		total += estimateTokens(msg.Content)
		for _, tc := range msg.ToolCalls {
			total += estimateTokens(tc.Function.Name)
			total += estimateTokens(tc.Function.Arguments)
		}
		total += 4
	}
	return total
}

func getMaxInputTokens(maxTokens int) int {
	if maxTokens <= 0 {
		return 120000
	}
	availableTokens := int(float64(maxTokens) * safetyMargin)
	reserved := toolsTokenReserve + skillPromptReserve + reactLoopReserve
	result := availableTokens - reserved
	if result < 4000 {
		result = 4000
	}
	return result
}

func trimHistoryMessages(historyMessages []*schema.Message, maxTokens int) []*schema.Message {
	if len(historyMessages) == 0 {
		return historyMessages
	}

	currentTokens := estimateMessagesTokens(historyMessages)
	if currentTokens <= maxTokens {
		return historyMessages
	}

	halfLen := len(historyMessages) / 2
	if halfLen > 0 {
		trimmed := historyMessages[halfLen:]
		trimmedTokens := estimateMessagesTokens(trimmed)
		if trimmedTokens <= maxTokens {
			return trimmed
		}
	}

	result := []*schema.Message{}
	tokenSum := 0
	for i := len(historyMessages) - 1; i >= 0; i-- {
		msgTokens := estimateTokens(historyMessages[i].Content) + 4
		if tokenSum+msgTokens > maxTokens {
			break
		}
		tokenSum += msgTokens
		result = append([]*schema.Message{historyMessages[i]}, result...)
	}

	if len(result) == 0 && len(historyMessages) > 0 {
		lastMsg := historyMessages[len(historyMessages)-1]
		content := lastMsg.Content
		maxChars := maxTokens * 2
		if len(content) > maxChars {
			lastMsg = &schema.Message{
				Role:    lastMsg.Role,
				Content: content[len(content)-maxChars:] + "\n...(更早的内容已省略)",
			}
		}
		result = []*schema.Message{lastMsg}
	}

	return result
}

func trimToolResult(content string, maxTokens int) string {
	if content == "" {
		return content
	}
	estimatedTokens := estimateTokens(content)
	if estimatedTokens <= maxTokens {
		return content
	}
	maxChars := int(float64(maxTokens) * englishCharsPerToken * 0.8)
	if maxChars > len(content) {
		maxChars = len(content)
	}

	lines := strings.Split(content, "\n")
	var result []string
	charCount := 0
	for i := len(lines) - 1; i >= 0; i-- {
		lineLen := len(lines[i]) + 1
		if charCount+lineLen > maxChars {
			break
		}
		charCount += lineLen
		result = append([]string{lines[i]}, result...)
	}

	if len(result) == 0 && len(lines) > 0 {
		lastLine := lines[len(lines)-1]
		if len(lastLine) > maxChars {
			lastLine = lastLine[len(lastLine)-maxChars:]
		}
		result = []string{lastLine}
	}

	return strings.Join(result, "\n") + "\n\n...(内容过长，已截断显示)"
}

func compressMessages(messages []*schema.Message, maxTokens int) []*schema.Message {
	if len(messages) == 0 {
		return messages
	}

	currentTokens := estimateMessagesTokens(messages)
	if currentTokens <= maxTokens {
		return messages
	}

	logger.SugaredLogger.Infof("MessageRewriter: 上下文压缩前 %d 条消息, 估算 %d tokens, 预算 %d tokens",
		len(messages), currentTokens, maxTokens)

	result := make([]*schema.Message, 0, len(messages))

	var systemMsgs []*schema.Message
	var nonSystemMsgs []*schema.Message
	for _, msg := range messages {
		if msg.Role == schema.System {
			systemMsgs = append(systemMsgs, msg)
		} else {
			nonSystemMsgs = append(nonSystemMsgs, msg)
		}
	}

	result = append(result, systemMsgs...)
	systemTokens := estimateMessagesTokens(systemMsgs)

	remainingBudget := maxTokens - systemTokens
	if remainingBudget <= 0 {
		logger.SugaredLogger.Warnf("MessageRewriter: 系统消息已超出预算, 仅保留系统消息")
		return result
	}

	compressed := compressNonSystemMessages(nonSystemMsgs, remainingBudget)
	result = append(result, compressed...)

	result = validateAndFixMessageSequence(result)

	finalTokens := estimateMessagesTokens(result)
	logger.SugaredLogger.Infof("MessageRewriter: 上下文压缩后 %d 条消息, 估算 %d tokens (节省 %d tokens)",
		len(result), finalTokens, currentTokens-finalTokens)

	for i, msg := range result {
		logger.SugaredLogger.Debugf("  [%d] role=%s contentLen=%d toolCalls=%d toolCallID=%s",
			i, msg.Role, len(msg.Content), len(msg.ToolCalls), msg.ToolCallID)
	}

	return result
}

func validateAndFixMessageSequence(messages []*schema.Message) []*schema.Message {
	if len(messages) == 0 {
		return messages
	}

	var fixed []*schema.Message
	for i, msg := range messages {
		if msg.Role == schema.Tool {
			hasParent := false
			for j := i - 1; j >= 0; j-- {
				if fixed[j].Role == schema.Assistant {
					for _, tc := range fixed[j].ToolCalls {
						if msg.ToolCallID == tc.ID {
							hasParent = true
							break
						}
					}
				}
				if hasParent {
					break
				}
			}
			if !hasParent {
				logger.SugaredLogger.Warnf("MessageRewriter: 移除孤立的Tool消息 (toolCallID=%s)", msg.ToolCallID)
				continue
			}
		}
		fixed = append(fixed, msg)
	}

	if len(fixed) == 0 {
		return messages
	}

	for i := 0; i < len(fixed); i++ {
		if fixed[i].Role == schema.System {
			if i+1 < len(fixed) && fixed[i+1].Role != schema.User {
				logger.SugaredLogger.Warnf("MessageRewriter: System后非User消息(role=%s), 插入占位User", fixed[i+1].Role)
				placeholder := &schema.Message{
					Role:    schema.User,
					Content: "继续",
				}
				fixed = append(fixed[:i+1], append([]*schema.Message{placeholder}, fixed[i+1:]...)...)
				break
			}
		}
	}

	return fixed
}

func compressNonSystemMessages(messages []*schema.Message, maxTokens int) []*schema.Message {
	if len(messages) == 0 {
		return messages
	}

	trimmed := trimLargeToolResults(messages, 4000)

	currentTokens := estimateMessagesTokens(trimmed)
	if currentTokens <= maxTokens {
		return trimmed
	}

	var userMsg *schema.Message
	var afterUser []*schema.Message
	for i, msg := range trimmed {
		if msg.Role == schema.User {
			userMsg = msg
			afterUser = trimmed[i+1:]
			break
		}
	}

	if userMsg == nil {
		return dropOldestMessages(trimmed, maxTokens)
	}

	userTokens := estimateTokens(userMsg.Content) + 4
	afterUserBudget := maxTokens - userTokens
	if afterUserBudget < 0 {
		afterUserBudget = 0
	}

	compressedAfterUser := dropToolCallGroups(afterUser, afterUserBudget)

	result := make([]*schema.Message, 0, len(compressedAfterUser)+1)
	result = append(result, userMsg)
	result = append(result, compressedAfterUser...)
	return result
}

func dropToolCallGroups(messages []*schema.Message, maxTokens int) []*schema.Message {
	if len(messages) == 0 {
		return messages
	}

	type toolGroup struct {
		messages []*schema.Message
		tokens   int
	}
	var groups []toolGroup

	i := 0
	for i < len(messages) {
		msg := messages[i]
		if msg.Role == schema.Assistant && len(msg.ToolCalls) > 0 {
			groupTokens := estimateTokens(msg.Content) + 4
			for _, tc := range msg.ToolCalls {
				groupTokens += estimateTokens(tc.Function.Name) + estimateTokens(tc.Function.Arguments)
			}

			var groupMsgs []*schema.Message
			groupMsgs = append(groupMsgs, msg)

			j := i + 1
			for j < len(messages) {
				if messages[j].Role == schema.Tool {
					matched := false
					for _, tc := range msg.ToolCalls {
						if messages[j].ToolCallID == tc.ID {
							matched = true
							break
						}
					}
					if matched {
						groupMsgs = append(groupMsgs, messages[j])
						groupTokens += estimateTokens(messages[j].Content) + 4
						j++
						continue
					}
				}
				break
			}

			if j < len(messages) && messages[j].Role == schema.Assistant && messages[j].Content != "" && len(messages[j].ToolCalls) == 0 {
				groupMsgs = append(groupMsgs, messages[j])
				groupTokens += estimateTokens(messages[j].Content) + 4
				j++
			}

			groups = append(groups, toolGroup{messages: groupMsgs, tokens: groupTokens})
			i = j
		} else {
			msgTokens := estimateTokens(msg.Content) + 4
			groups = append(groups, toolGroup{messages: []*schema.Message{msg}, tokens: msgTokens})
			i++
		}
	}

	totalTokens := 0
	for _, g := range groups {
		totalTokens += g.tokens
	}
	if totalTokens <= maxTokens {
		return messages
	}

	startIdx := 0
	for startIdx < len(groups) {
		partialTokens := 0
		for k := startIdx; k < len(groups); k++ {
			partialTokens += groups[k].tokens
		}
		if partialTokens <= maxTokens {
			break
		}
		startIdx++
	}

	if startIdx >= len(groups) {
		startIdx = len(groups) - 1
	}

	var result []*schema.Message
	for k := startIdx; k < len(groups); k++ {
		result = append(result, groups[k].messages...)
	}
	return result
}

func trimLargeToolResults(messages []*schema.Message, maxToolResultTokens int) []*schema.Message {
	result := make([]*schema.Message, len(messages))
	for i, msg := range messages {
		if msg.Role == schema.Tool && estimateTokens(msg.Content) > maxToolResultTokens {
			compressed := trimToolResult(msg.Content, maxToolResultTokens)
			cp := *msg
			cp.Content = compressed
			result[i] = &cp
		} else {
			result[i] = msg
		}
	}
	return result
}

func dropOldestMessages(messages []*schema.Message, maxTokens int) []*schema.Message {
	if len(messages) == 0 {
		return messages
	}

	totalTokens := estimateMessagesTokens(messages)
	if totalTokens <= maxTokens {
		return messages
	}

	toolCallIDs := make(map[string]bool)
	for _, msg := range messages {
		if msg.Role == schema.Assistant {
			for _, tc := range msg.ToolCalls {
				toolCallIDs[tc.ID] = true
			}
		}
	}

	kept := make([]*schema.Message, 0, len(messages))
	tokenSum := 0
	started := false

	for i, msg := range messages {
		if !started {
			if msg.Role == schema.Assistant && len(msg.ToolCalls) > 0 {
				assistantTokens := estimateTokens(msg.Content)
				for _, tc := range msg.ToolCalls {
					assistantTokens += estimateTokens(tc.Function.Name) + estimateTokens(tc.Function.Arguments)
				}
				assistantTokens += 4

				var relatedToolMsgs []*schema.Message
				relatedTokens := 0
				for j := i + 1; j < len(messages); j++ {
					if messages[j].Role == schema.Tool {
						for _, tc := range msg.ToolCalls {
							if messages[j].ToolCallID == tc.ID {
								relatedToolMsgs = append(relatedToolMsgs, messages[j])
								relatedTokens += estimateTokens(messages[j].Content) + 4
								break
							}
						}
					}
				}

				groupTokens := assistantTokens + relatedTokens
				if tokenSum+groupTokens <= maxTokens {
					started = true
					kept = append(kept, msg)
					tokenSum += groupTokens
					kept = append(kept, relatedToolMsgs...)
				}
			} else if msg.Role == schema.Tool {
				if toolCallIDs[msg.ToolCallID] {
					continue
				}
			} else {
				msgTokens := estimateTokens(msg.Content) + 4
				if tokenSum+msgTokens <= maxTokens {
					started = true
					kept = append(kept, msg)
					tokenSum += msgTokens
				}
			}
			continue
		}

		msgTokens := estimateTokens(msg.Content) + 4
		for _, tc := range msg.ToolCalls {
			msgTokens += estimateTokens(tc.Function.Name) + estimateTokens(tc.Function.Arguments)
		}

		if msg.Role == schema.Assistant && len(msg.ToolCalls) > 0 {
			var relatedToolMsgs []*schema.Message
			for j := i + 1; j < len(messages); j++ {
				if messages[j].Role == schema.Tool {
					for _, tc := range msg.ToolCalls {
						if messages[j].ToolCallID == tc.ID {
							relatedToolMsgs = append(relatedToolMsgs, messages[j])
							msgTokens += estimateTokens(messages[j].Content) + 4
							break
						}
					}
				}
			}

			if tokenSum+msgTokens > maxTokens {
				break
			}
			kept = append(kept, msg)
			tokenSum += msgTokens
			kept = append(kept, relatedToolMsgs...)
		} else if msg.Role == schema.Tool {
			if !toolCallIDs[msg.ToolCallID] {
				if tokenSum+msgTokens <= maxTokens {
					kept = append(kept, msg)
					tokenSum += msgTokens
				}
			} else {
				kept = append(kept, msg)
				tokenSum += msgTokens
			}
		} else {
			if tokenSum+msgTokens > maxTokens {
				break
			}
			kept = append(kept, msg)
			tokenSum += msgTokens
		}
	}

	if len(kept) == 0 && len(messages) > 0 {
		last := messages[len(messages)-1]
		kept = append(kept, last)
	}

	return kept
}

func isTokenLimitError(err error) bool {
	if err == nil {
		return false
	}
	errMsg := err.Error()
	return strings.Contains(errMsg, "max_prompt_tokens") ||
		strings.Contains(errMsg, "exceeded") ||
		strings.Contains(errMsg, "token limit") ||
		strings.Contains(errMsg, "context_length") ||
		strings.Contains(errMsg, "maximum context") ||
		strings.Contains(errMsg, "too many tokens") ||
		strings.Contains(errMsg, "context window") ||
		strings.Contains(errMsg, "400") && strings.Contains(errMsg, "token")
}
