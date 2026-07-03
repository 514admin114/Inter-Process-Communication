package utils

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

// Error injection constants
const (
	ErrorRate      = 0.01
	MaxRetransmit  = 3
)

// PerformanceMetrics 性能指标结构
type PerformanceMetrics struct {
	IPCType        string  // IPC类型: shared_memory, socket, tcp
	Pattern        string  // 模式: 1_1, N_1, 1_N, N_N
	ProducerCount  int     // 生产者数量
	ConsumerCount  int     // 消费者数量
	MessageCount   int     // 总消息数
	MessageSize    int     // 消息大小(字节)
	TotalTime      float64 // 总耗时(秒)
	Throughput     float64 // 吞吐量(消息/秒)
	AvgLatency     float64 // 平均延迟(微秒)
	P95Latency     float64 // P95延迟(微秒)
	P99Latency     float64 // P99延迟(微秒)
	ErrorCount     int     // 检测到的错误消息数
	RetransmitCount int    // 重传次数
	Accuracy       float64 // 数据传输准确率(%): 无错误传输的消息百分比
	Timestamp      string  // 时间戳
	Success        bool    // 测试是否成功
}

// ComputeChecksum computes additive checksum (sum of all bytes modulo 2^32)
func ComputeChecksum(data []byte) uint32 {
	var sum uint32
	for _, b := range data {
		sum += uint32(b)
	}
	return sum
}

// EnsureDataDir 确保数据目录存在
func EnsureDataDir() error {
	dataDir := "../csv"
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		return fmt.Errorf("创建数据目录失败: %v", err)
	}
	return nil
}

// SaveToCSV 将性能指标保存到CSV文件
func SaveToCSV(metrics *PerformanceMetrics, filename string) error {
	if err := EnsureDataDir(); err != nil {
		return err
	}

	filePath := filepath.Join("../csv", filename)
	
	// 检查文件是否存在，不存在则创建并写入表头
	fileExists := true
	if _, err := os.Stat(filePath); os.IsNotExist(err) {
		fileExists = false
	}

	file, err := os.OpenFile(filePath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("打开文件失败: %v", err)
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	// 如果文件不存在，写入表头
	if !fileExists {
		headers := []string{
			"Timestamp", "IPC_Type", "Pattern",
			"Producer_Count", "Consumer_Count",
			"Message_Count", "Message_Size",
			"Total_Time_Seconds", "Throughput_Msg_Per_Sec",
			"Avg_Latency_Microseconds", "P95_Latency_Microseconds",
			"P99_Latency_Microseconds", "Error_Count", "Retransmit_Count",
				"Accuracy",
			"Success",
		}
		if err := writer.Write(headers); err != nil {
			return fmt.Errorf("写入表头失败: %v", err)
		}
	}

	// 写入数据行
	successStr := "true"
	if !metrics.Success {
		successStr = "false"
	}

	record := []string{
		metrics.Timestamp,
		metrics.IPCType,
		metrics.Pattern,
		fmt.Sprintf("%d", metrics.ProducerCount),
		fmt.Sprintf("%d", metrics.ConsumerCount),
		fmt.Sprintf("%d", metrics.MessageCount),
		fmt.Sprintf("%d", metrics.MessageSize),
		fmt.Sprintf("%.6f", metrics.TotalTime),
		fmt.Sprintf("%.2f", metrics.Throughput),
		fmt.Sprintf("%.2f", metrics.AvgLatency),
		fmt.Sprintf("%.2f", metrics.P95Latency),
		fmt.Sprintf("%.2f", metrics.P99Latency),
		fmt.Sprintf("%d", metrics.ErrorCount),
		fmt.Sprintf("%d", metrics.RetransmitCount),
			fmt.Sprintf("%.2f", metrics.Accuracy),
		successStr,
	}

	if err := writer.Write(record); err != nil {
		return fmt.Errorf("写入数据失败: %v", err)
	}

	return nil
}

// AppendStatistics appends statistics to the end of CSV file
func AppendStatistics(filename string, totalTests, successTests, failedTests int) error {
	if err := EnsureDataDir(); err != nil {
		return err
	}

	filePath := filepath.Join("../csv", filename)

	file, err := os.OpenFile(filePath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return fmt.Errorf("failed to open file: %v", err)
	}
	defer file.Close()

	writer := csv.NewWriter(file)
	defer writer.Flush()

	// Write blank line as separator
	if err := writer.Write([]string{""}); err != nil {
		return fmt.Errorf("failed to write separator: %v", err)
	}

	// Write statistics in English to avoid encoding issues
	stats := [][]string{
		{"=== Test Statistics ===", "", "", "", "", "", "", "", "", "", "", "", "", "", ""},
		{"Total Tests", fmt.Sprintf("%d", totalTests), "", "", "", "", "", "", "", "", "", "", "", ""},
		{"Successful Tests", fmt.Sprintf("%d", successTests), "", "", "", "", "", "", "", "", "", "", "", ""},
		{"Failed Tests", fmt.Sprintf("%d", failedTests), "", "", "", "", "", "", "", "", "", "", "", ""},
		{"Success Rate", fmt.Sprintf("%.2f%%", float64(successTests)/float64(totalTests)*100), "", "", "", "", "", "", "", "", "", "", "", ""},
	}

	for _, row := range stats {
		if err := writer.Write(row); err != nil {
			return fmt.Errorf("failed to write statistics: %v", err)
		}
	}

	return nil
}

// CalculatePercentile 计算百分位数
func CalculatePercentile(latencies []float64, percentile float64) float64 {
	if len(latencies) == 0 {
		return 0
	}

	// 排序（简单实现）
	for i := 0; i < len(latencies); i++ {
		for j := i + 1; j < len(latencies); j++ {
			if latencies[i] > latencies[j] {
				latencies[i], latencies[j] = latencies[j], latencies[i]
			}
		}
	}

	index := int(float64(len(latencies)) * percentile / 100.0)
	if index >= len(latencies) {
		index = len(latencies) - 1
	}
	return latencies[index]
}

// FormatDuration 格式化时间间隔
func FormatDuration(start, end time.Time) string {
	duration := end.Sub(start)
	return fmt.Sprintf("%.6f", duration.Seconds())
}
