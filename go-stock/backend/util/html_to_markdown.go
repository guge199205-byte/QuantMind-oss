package util

// @Author spark
// @Date 2025/7/15 14:08
// @Desc
//-----------------------------------------------------------------------------------

import (
	"bytes"
	"fmt"
	"golang.org/x/net/html"
	"strings"
)

// HTMLNode 表示HTML文档中的一个节点
type HTMLNode struct {
	Type     html.NodeType
	Data     string
	Attr     []html.Attribute
	Children []*HTMLNode
}

// HTMLToMarkdown 将HTML转换为Markdown
func HTMLToMarkdown(htmlContent string) (string, error) {
	doc, err := html.Parse(strings.NewReader(htmlContent))
	if err != nil {
		return "", err
	}

	root := parseHTMLNode(doc)
	var buf bytes.Buffer
	convertNode(&buf, root, 0)

	return buf.String(), nil
}

// parseHTMLNode 递归解析HTML节点
func parseHTMLNode(n *html.Node) *HTMLNode {
	node := &HTMLNode{
		Type: n.Type,
		Data: n.Data,
		Attr: n.Attr,
	}

	for c := n.FirstChild; c != nil; c = c.NextSibling {
		node.Children = append(node.Children, parseHTMLNode(c))
	}

	return node
}

// convertNode 递归转换节点为Markdown
func convertNode(buf *bytes.Buffer, node *HTMLNode, depth int) {
	switch node.Type {
	case html.ElementNode:
		convertElementNode(buf, node, depth)
	case html.TextNode:
		// 处理文本节点，去除多余的空白
		text := strings.TrimSpace(node.Data)
		if text != "" {
			buf.WriteString(text)
		}
	}

	// 递归处理子节点
	for _, child := range node.Children {
		convertNode(buf, child, depth+1)
	}

	// 处理需要在结束标签后添加内容的元素
	switch node.Data {
	case "p", "h1", "h2", "h3", "h4", "h5", "h6", "li":
		buf.WriteString("\n\n")
	case "blockquote":
		buf.WriteString("\n")
	}
}

// convertElementNode 转换元素节点为Markdown
func convertElementNode(buf *bytes.Buffer, node *HTMLNode, depth int) {
	switch node.Data {
	case "h1":
		buf.WriteString("# ")
	case "h2":
		buf.WriteString("## ")
	case "h3":
		buf.WriteString("### ")
	case "h4":
		buf.WriteString("#### ")
	case "h5":
		buf.WriteString("##### ")
	case "h6":
		buf.WriteString("###### ")
	case "p":
		// 段落标签不需要特殊标记，直接处理内容
	case "strong", "b":
		buf.WriteString("**")
	case "em", "i":
		buf.WriteString("*")
	case "u":
		buf.WriteString("<u>")
	case "s", "del":
		buf.WriteString("~~")
	case "a":
		//href := getAttrValue(node.Attr, "href")
		buf.WriteString("[")
	case "img":
		src := getAttrValue(node.Attr, "src")
		alt := getAttrValue(node.Attr, "alt")
		buf.WriteString(fmt.Sprintf("![%s](%s)", alt, src))
	case "ul":
		// 无序列表不需要特殊标记，子项会处理
	case "ol":
		// 有序列表不需要特殊标记，子项会处理
	case "li":
		if isParentListType(node, "ul") {
			buf.WriteString("- ")
		} else {
			// 计算当前列表项的序号
			index := 1
			if parent := findParentList(node); parent != nil {
				for i, sibling := range parent.Children {
					if sibling == node {
						index = i + 1
						break
					}
				}
			}
			buf.WriteString(fmt.Sprintf("%d. ", index))
		}
	case "blockquote":
		buf.WriteString("> ")
	case "code":
		if isParentPre(node) {
			// 父节点是pre，使用代码块
			buf.WriteString("\n```\n")
		} else {
			// 行内代码
			buf.WriteString("`")
		}
	case "pre":
		// 前置代码块由子节点code处理
	case "br":
		buf.WriteString("\n")
	case "hr":
		buf.WriteString("\n---\n")
	}

	// 处理闭合标签
	if needsClosingTag(node.Data) {
		defer func() {
			switch node.Data {
			case "strong", "b":
				buf.WriteString("**")
			case "em", "i":
				buf.WriteString("*")
			case "u":
				buf.WriteString("</u>")
			case "s", "del":
				buf.WriteString("~~")
			case "a":
				href := getAttrValue(node.Attr, "href")
				buf.WriteString(fmt.Sprintf("](%s)", href))
			case "code":
				if isParentPre(node) {
					buf.WriteString("\n```\n")
				} else {
					buf.WriteString("`")
				}
			}
		}()
	}
}

// getAttrValue 获取属性值
func getAttrValue(attrs []html.Attribute, key string) string {
	for _, attr := range attrs {
		if attr.Key == key {
			return attr.Val
		}
	}
	return ""
}

// isParentListType 检查父节点是否为指定类型的列表
func isParentListType(node *HTMLNode, listType string) bool {
	parent := findParentList(node)
	return parent != nil && parent.Data == listType
}

// findParentList 查找父列表节点
func findParentList(node *HTMLNode) *HTMLNode {
	// 简化实现，实际应该递归查找父节点
	if node.Type == html.ElementNode && (node.Data == "ul" || node.Data == "ol") {
		return node
	}
	return nil
}

// isParentPre 检查父节点是否为pre
func isParentPre(node *HTMLNode) bool {
	if len(node.Children) == 0 {
		return false
	}
	for _, child := range node.Children {
		if child.Type == html.ElementNode && child.Data == "pre" {
			return true
		}
	}
	return false
}

// needsClosingTag 判断元素是否需要闭合标签
func needsClosingTag(tag string) bool {
	switch tag {
	case "img", "br", "hr", "input", "meta", "link":
		return false
	default:
		return true
	}
}
