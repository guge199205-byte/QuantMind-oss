package data

import (
	"strings"
	"sync"

	"github.com/tidwall/gjson"
)

// toolStockParallelWorkers 多只股票并行查询时的并发上限，避免对外部接口造成过大压力。
const toolStockParallelWorkers = 3

func dedupeStockCodesKeepOrder(codes []string) []string {
	seen := make(map[string]struct{}, len(codes))
	out := make([]string, 0, len(codes))
	for _, c := range codes {
		c = strings.TrimSpace(c)
		if c == "" {
			continue
		}
		if _, ok := seen[c]; ok {
			continue
		}
		seen[c] = struct{}{}
		out = append(out, c)
	}
	return out
}

// parseStockCodesFromToolArgs 解析工具参数中的股票代码：
// 优先使用 stockCodes 数组；否则将 singleKey 对应字段按英文逗号拆分为多只。
// 若两者都有内容，合并后按出现顺序去重。
func parseStockCodesFromToolArgs(funcArguments string, singleKey string) []string {
	root := gjson.Parse(funcArguments)
	var raw []string
	if arr := root.Get("stockCodes"); arr.IsArray() {
		for _, item := range arr.Array() {
			s := strings.TrimSpace(item.String())
			if s != "" {
				raw = append(raw, s)
			}
		}
	}
	single := strings.TrimSpace(root.Get(singleKey).String())
	if single != "" {
		for _, p := range strings.Split(single, ",") {
			p = strings.TrimSpace(p)
			if p != "" {
				raw = append(raw, p)
			}
		}
	}
	return dedupeStockCodesKeepOrder(raw)
}

// parallelStockToolSections 对多只股票并行执行 fn，按 codes 原始顺序拼接非空结果。
func parallelStockToolSections(codes []string, fn func(code string) string) string {
	n := len(codes)
	if n == 0 {
		return ""
	}
	if n == 1 {
		return fn(codes[0])
	}
	results := make([]string, n)
	w := toolStockParallelWorkers
	if w > n {
		w = n
	}
	sem := make(chan struct{}, w)
	var wg sync.WaitGroup
	for i := range codes {
		i, code := i, codes[i]
		wg.Add(1)
		go func() {
			defer wg.Done()
			sem <- struct{}{}
			defer func() { <-sem }()
			results[i] = fn(code)
		}()
	}
	wg.Wait()
	var b strings.Builder
	for _, s := range results {
		s = strings.TrimSpace(s)
		if s == "" {
			continue
		}
		if b.Len() > 0 {
			b.WriteString("\r\n\r\n")
		}
		b.WriteString(s)
	}
	return b.String()
}
