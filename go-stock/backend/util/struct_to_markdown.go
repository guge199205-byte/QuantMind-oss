package util

import (
	"fmt"
	"github.com/duke-git/lancet/v2/convertor"
	"github.com/duke-git/lancet/v2/strutil"
	"reflect"
	"strings"
)

// MarkdownTable 生成结构体或结构体切片的Markdown表格表示
func MarkdownTable(v interface{}) string {
	value := reflect.ValueOf(v)
	if value.Kind() == reflect.Ptr {
		value = value.Elem()
	}

	// 处理单个结构体
	if value.Kind() == reflect.Struct {
		return markdownSingleStruct(value)
	}

	// 处理结构体切片/数组
	if value.Kind() == reflect.Slice || value.Kind() == reflect.Array {
		if value.Len() == 0 {
			return "切片/数组为空"
		}
		return markdownStructSlice(value)
	}

	return "输入必须是结构体、结构体指针、结构体切片或数组"
}

func MarkdownTableWithTitle(title string, v interface{}) string {
	value := reflect.ValueOf(v)
	if value.Kind() == reflect.Ptr {
		value = value.Elem()
	}

	// 处理单个结构体
	if value.Kind() == reflect.Struct {
		return markdownSingleStruct(value)
	}

	// 处理结构体切片/数组
	if value.Kind() == reflect.Slice || value.Kind() == reflect.Array {
		if value.Len() == 0 {
			return "\n## " + title + "\n" + "无数据" + "\n"
		}
		return "\n## " + title + "\n" + markdownStructSlice(value) + "\n"
	}

	return "\n## " + title + "\n" + "无数据" + "\n"
}

// 处理单个结构体
func markdownSingleStruct(value reflect.Value) string {
	t := value.Type()
	var b strings.Builder

	// 表头
	b.WriteString("|")
	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		if shouldSkip(field) {
			continue
		}
		b.WriteString(fmt.Sprintf(" %s |", getFieldName(field)))
	}
	b.WriteString("\n")

	// 分隔线
	b.WriteString("|")
	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		if shouldSkip(field) {
			continue
		}
		b.WriteString(" --- |")
	}
	b.WriteString("\n")

	// 数据行
	b.WriteString("|")
	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		if shouldSkip(field) {
			continue
		}
		fieldValue := value.Field(i)
		b.WriteString(fmt.Sprintf(" %s |", formatValue(fieldValue)))
	}
	b.WriteString("\n")

	return b.String()
}

// 处理结构体切片/数组
func markdownStructSlice(value reflect.Value) string {
	if value.Len() == 0 {
		return "切片/数组为空"
	}

	firstElem := value.Index(0)
	if firstElem.Kind() == reflect.Ptr {
		firstElem = firstElem.Elem()
	}
	if firstElem.Kind() != reflect.Struct {
		return "切片/数组元素必须是结构体或结构体指针"
	}

	t := firstElem.Type()
	var b strings.Builder

	// 表头
	b.WriteString("|")
	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		if shouldSkip(field) {
			continue
		}
		b.WriteString(fmt.Sprintf(" %s |", getFieldName(field)))
	}
	b.WriteString("\n")

	// 分隔线
	b.WriteString("|")
	for i := 0; i < t.NumField(); i++ {
		field := t.Field(i)
		if shouldSkip(field) {
			continue
		}
		b.WriteString(" --- |")
	}
	b.WriteString("\n")

	// 多行数据
	for i := 0; i < value.Len(); i++ {
		elem := value.Index(i)
		if elem.Kind() == reflect.Ptr {
			elem = elem.Elem()
		}

		b.WriteString("|")
		for j := 0; j < t.NumField(); j++ {
			field := t.Field(j)
			if shouldSkip(field) {
				continue
			}
			fieldValue := elem.Field(j)
			b.WriteString(fmt.Sprintf(" %s |", formatValue(fieldValue)))
		}
		b.WriteString("\n")
	}

	return b.String()
}

// 判断是否应该跳过该字段
func shouldSkip(field reflect.StructField) bool {
	return field.Tag.Get("md") == "-"
}

// 获取字段的Markdown表头名称
func getFieldName(field reflect.StructField) string {
	name := field.Tag.Get("md")
	if name == "" || name == "-" {
		return field.Name
	}
	return name
}

// 格式化字段值为字符串
func formatValue(value reflect.Value) string {
	if !value.IsValid() {
		return "n/a"
	}

	// 处理指针
	if value.Kind() == reflect.Ptr {
		if value.IsNil() {
			return "nil"
		}
		return formatValue(value.Elem())
	}

	// 处理结构体
	if value.Kind() == reflect.Struct {
		var fields []string
		for i := 0; i < value.NumField(); i++ {
			field := value.Type().Field(i)
			if shouldSkip(field) {
				continue
			}
			fieldValue := value.Field(i)
			fields = append(fields, fmt.Sprintf("%s: %s", getFieldName(field), formatValue(fieldValue)))
		}
		return "{" + strings.Join(fields, ", ") + "}"
	}

	// 处理切片/数组
	if value.Kind() == reflect.Slice || value.Kind() == reflect.Array {
		var items []string
		for i := 0; i < value.Len(); i++ {
			items = append(items, formatValue(value.Index(i)))
		}
		return "[" + strings.Join(items, ", ") + "]"
	}

	// 处理映射
	if value.Kind() == reflect.Map {
		var items []string
		for _, key := range value.MapKeys() {
			keyStr := formatValue(key)
			valueStr := formatValue(value.MapIndex(key))
			items = append(items, fmt.Sprintf("%s: %s", keyStr, valueStr))
		}
		return "{" + strings.Join(items, ", ") + "}"
	}

	// 基本类型
	return fmt.Sprintf("%s", strutil.RemoveNonPrintable(convertor.ToString(value.Interface())))
}

// 示例结构体
type Address struct {
	City    string `md:"城市"`
	Country string `md:"国家"`
}

type User struct {
	Name    string   `md:"姓名"`
	Age     int      `md:"年龄"`
	Email   string   `md:"邮箱"`
	Address Address  `md:"地址"`
	Phones  []string `md:"电话"`
	Active  bool     `md:"活跃状态"`
}

func main() {
	// 示例使用：单个结构体
	user := User{
		Name:  "张三",
		Age:   30,
		Email: "zhangsan@example.com",
		Address: Address{
			City:    "北京",
			Country: "中国",
		},
		Phones: []string{"13800138000", "13900139000"},
		Active: true,
	}

	fmt.Println("单个结构体转换:")
	fmt.Println(MarkdownTable(user))
	fmt.Println()

	// 示例使用：结构体切片
	users := []User{
		{
			Name:  "张三",
			Age:   30,
			Email: "zhangsan@example.com",
			Address: Address{
				City:    "北京",
				Country: "中国",
			},
			Phones: []string{"13800138000"},
			Active: true,
		},
		{
			Name:  "李四",
			Age:   25,
			Email: "lisi@example.com",
			Address: Address{
				City:    "上海",
				Country: "中国",
			},
			Phones: []string{"13900139000", "13700137000"},
			Active: false,
		},
	}

	fmt.Println("结构体切片转换:")
	fmt.Println(MarkdownTable(users))
}
