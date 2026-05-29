package data

import (
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strings"
)

// ChipBin 表示某个价位区间的筹码占比/数量（用于筹码图/筹码分布）。
type ChipBin struct {
	Price float64 `json:"price"` // 价位（使用该 bin 的中心价）
	Vol   float64 `json:"vol"`   // 该价位筹码量（相对量，来源于成交量累计）
	Ratio float64 `json:"ratio"` // 占比（Vol / SumVol）
}

// ChipDistributionResult 输出给前端/AI 的筹码分布结果。
type ChipDistributionResult struct {
	StockCode   string    `json:"stockCode"`
	Days        int       `json:"days"`
	Bins        int       `json:"bins"`
	Current     float64   `json:"current"`     // 最新收盘价（取最后一根 K）
	AvgCost     float64   `json:"avgCost"`     // 平均成本（加权均价）
	ProfitRatio float64   `json:"profitRatio"` // 获利筹码占比（价位 <= Current）
	MinPrice    float64   `json:"minPrice"`
	MaxPrice    float64   `json:"maxPrice"`
	SumVol      float64   `json:"sumVol"`
	Items       []ChipBin `json:"items"`
}

// ChipDistributionCalculator 使用历史 K 线 + 换手率近似计算筹码分布：
//   - 用换手率对历史筹码做衰减（保留比例 = 1 - turnover）
//   - 将当日成交量按以「成本中枢」为中心的高斯核落在 [low, high] 与各 bin 的交集上；
//     成本中枢优先为日 VWAP（成交额/成交量），否则典型价 (H+L+C)/3 等，与前端 StockLightweightKlineChart 一致。
//
// 该方法是工程上常用近似（无需依赖第三方“筹码”私有接口）。
type ChipDistributionCalculator struct{}

func NewChipDistributionCalculator() *ChipDistributionCalculator {
	return &ChipDistributionCalculator{}
}

func (c *ChipDistributionCalculator) Calculate(stockCode string, kLines []KLineData, bins int) (*ChipDistributionResult, error) {
	if len(kLines) == 0 {
		return nil, fmt.Errorf("K线数据为空")
	}
	if bins <= 0 {
		bins = 80
	}
	if bins > 300 {
		bins = 300
	}

	minP, maxP := detectMinMaxPrice(kLines)
	if minP <= 0 || maxP <= 0 || maxP < minP {
		return nil, fmt.Errorf("无法从K线推导价格区间")
	}
	// 避免除零
	if maxP == minP {
		maxP = minP * 1.001
	}

	width := (maxP - minP) / float64(bins)
	if width <= 0 {
		return nil, fmt.Errorf("价格分箱宽度无效")
	}

	dist := make([]float64, bins)

	for _, k := range kLines {
		turn := parsePercent(k.TurnoverRate) // 0~1
		if turn < 0 {
			turn = 0
		}
		if turn > 0.98 {
			turn = 0.98
		}

		remain := 1.0 - turn
		for i := range dist {
			dist[i] *= remain
		}

		low := parseFloat(k.Low)
		high := parseFloat(k.High)
		vol := parseFloat(k.Volume)
		if vol <= 0 {
			continue
		}
		if low <= 0 || high <= 0 {
			continue
		}
		if high < low {
			low, high = high, low
		}
		open := parseFloat(k.Open)
		close := parseFloat(k.Close)
		amount := parseFloat(k.Amount)
		center := chipBarCostCenter(low, high, open, close, vol, amount)
		addChipVolumeKernel(dist, bins, minP, width, low, high, vol, center)
	}

	sum := 0.0
	for _, v := range dist {
		sum += v
	}
	cur := parseFloat(kLines[len(kLines)-1].Close)
	if cur <= 0 {
		cur = parseFloat(kLines[len(kLines)-1].High)
	}

	items := make([]ChipBin, 0, bins)
	avgCost := 0.0
	profitVol := 0.0
	for i := 0; i < bins; i++ {
		center := minP + (float64(i)+0.5)*width
		vol := dist[i]
		ratio := 0.0
		if sum > 0 {
			ratio = vol / sum
		}
		items = append(items, ChipBin{
			Price: round(center, 4),
			Vol:   round(vol, 4),
			Ratio: round(ratio, 6),
		})
		avgCost += vol * center
		if center <= cur {
			profitVol += vol
		}
	}
	if sum > 0 {
		avgCost = avgCost / sum
	}
	profitRatio := 0.0
	if sum > 0 {
		profitRatio = profitVol / sum
	}

	return &ChipDistributionResult{
		StockCode:   stockCode,
		Days:        len(kLines),
		Bins:        bins,
		Current:     round(cur, 4),
		AvgCost:     round(avgCost, 4),
		ProfitRatio: round(profitRatio, 6),
		MinPrice:    round(minP, 4),
		MaxPrice:    round(maxP, 4),
		SumVol:      round(sum, 4),
		Items:       items,
	}, nil
}

func (r *ChipDistributionResult) TopN(n int) []ChipBin {
	if r == nil || len(r.Items) == 0 || n <= 0 {
		return nil
	}
	cp := make([]ChipBin, len(r.Items))
	copy(cp, r.Items)
	sort.Slice(cp, func(i, j int) bool { return cp[i].Ratio > cp[j].Ratio })
	if n > len(cp) {
		n = len(cp)
	}
	return cp[:n]
}

func (r *ChipDistributionResult) ToJSON(pretty bool) string {
	if r == nil {
		return "{}"
	}
	var b []byte
	var err error
	if pretty {
		b, err = json.MarshalIndent(r, "", "  ")
	} else {
		b, err = json.Marshal(r)
	}
	if err != nil {
		return "{}"
	}
	return string(b)
}

func chipBarCostCenter(low, high, open, close, vol, amount float64) float64 {
	if low <= 0 || high <= 0 || high < low || !isFinite(low) || !isFinite(high) {
		if isFinite(low) && isFinite(high) {
			return (low + high) / 2
		}
		return 0
	}
	if amount > 0 && vol > 0 {
		vwap := amount / vol
		if isFinite(vwap) && vwap > 0 {
			return clampPrice(vwap, low, high)
		}
	}
	if close > 0 && isFinite(close) {
		tp := (high + low + close) / 3
		if isFinite(tp) {
			return clampPrice(tp, low, high)
		}
	}
	if open > 0 && close > 0 && isFinite(open) && isFinite(close) {
		tp := (high + low + open + close) / 4
		if isFinite(tp) {
			return clampPrice(tp, low, high)
		}
	}
	return (high + low) / 2
}

func clampPrice(x, lo, hi float64) float64 {
	return math.Min(hi, math.Max(lo, x))
}

func isFinite(x float64) bool {
	return !math.IsNaN(x) && !math.IsInf(x, 0)
}

// addChipVolumeKernel 与前端 addChipVolumeKernel 行为对齐：高斯核 + 一字板单档 + 权重为 0 时回退均匀。
func addChipVolumeKernel(dist []float64, bins int, minP, width, low, high, vol, center float64) {
	if vol <= 0 || low <= 0 || high <= 0 {
		return
	}
	lo, hi := low, high
	if hi < lo {
		lo, hi = hi, lo
	}
	span := hi - lo
	loIdx := int(math.Floor((lo - minP) / width))
	hiIdx := int(math.Floor((hi - minP) / width))
	if loIdx < 0 {
		loIdx = 0
	}
	if hiIdx < 0 {
		hiIdx = 0
	}
	if loIdx >= bins {
		loIdx = bins - 1
	}
	if hiIdx >= bins {
		hiIdx = bins - 1
	}
	if hiIdx < loIdx {
		return
	}
	if span < 1e-9*math.Max(1, hi) {
		mid := (lo + hi) / 2
		i := int(math.Floor((mid - minP) / width))
		if i < 0 {
			i = 0
		}
		if i >= bins {
			i = bins - 1
		}
		dist[i] += vol
		return
	}
	m := center
	if !isFinite(m) {
		m = (lo + hi) / 2
	}
	m = clampPrice(m, lo, hi)
	sigma := math.Max(span*0.18, math.Max(hi*1e-6, 1e-6))
	var wsum float64
	for i := loIdx; i <= hiIdx; i++ {
		bc := minP + (float64(i)+0.5)*width
		if bc < lo || bc > hi {
			continue
		}
		d := (bc - m) / sigma
		wsum += math.Exp(-0.5 * d * d)
	}
	if wsum <= 0 {
		cnt := float64(hiIdx - loIdx + 1)
		add := vol / cnt
		for i := loIdx; i <= hiIdx; i++ {
			dist[i] += add
		}
		return
	}
	for i := loIdx; i <= hiIdx; i++ {
		bc := minP + (float64(i)+0.5)*width
		if bc < lo || bc > hi {
			continue
		}
		d := (bc - m) / sigma
		w := math.Exp(-0.5 * d * d)
		dist[i] += vol * w / wsum
	}
}

func detectMinMaxPrice(kLines []KLineData) (minP, maxP float64) {
	minP = math.MaxFloat64
	maxP = 0
	for _, k := range kLines {
		lo := parseFloat(k.Low)
		hi := parseFloat(k.High)
		if lo > 0 && lo < minP {
			minP = lo
		}
		if hi > 0 && hi > maxP {
			maxP = hi
		}
	}
	if minP == math.MaxFloat64 {
		minP = 0
	}
	return minP, maxP
}

func parseFloat(s string) float64 {
	s = strings.TrimSpace(s)
	if s == "" || s == "-" || s == "null" {
		return 0
	}
	var f float64
	_, err := fmt.Sscanf(s, "%f", &f)
	if err != nil {
		return 0
	}
	return f
}

// parsePercent 支持 "12.34"、"12.34%" -> 0.1234
func parsePercent(s string) float64 {
	s = strings.TrimSpace(strings.TrimSuffix(s, "%"))
	if s == "" || s == "-" || s == "null" {
		return 0
	}
	v := parseFloat(s)
	return v / 100.0
}

func round(v float64, digits int) float64 {
	if digits < 0 {
		return v
	}
	p := math.Pow10(digits)
	return math.Round(v*p) / p
}
