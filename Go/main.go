package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"time"

	"ipc/shared_memory"
	"ipc/socket"
	"ipc/tcp_ipc"
	"ipc/utils"
)

// TestConfig 测试配置
type TestConfig struct {
	MessageSizes    []int `json:"message_sizes"`
	ProducerCounts  []int `json:"producer_counts"`
	ConsumerCounts  []int `json:"consumer_counts"`
	MessagesPerProd int   `json:"messages_per_producer"`
}

// loadConfig loads test configuration from a JSON file
func loadConfig(path string) TestConfig {
	config := TestConfig{
		MessageSizes:    []int{64, 1024},
		ProducerCounts:  []int{1, 2, 4},
		ConsumerCounts:  []int{1, 2, 4},
		MessagesPerProd: 500,
	}
	data, err := ioutil.ReadFile(path)
	if err != nil {
		fmt.Printf("Warning: cannot open %s, using defaults\n", path)
		return config
	}
	if err := json.Unmarshal(data, &config); err != nil {
		fmt.Printf("Warning: failed to parse %s, using defaults\n", path)
	}
	return config
}

func main() {
	fmt.Println("========================================")
	fmt.Println("  Inter-Process Communication (IPC) Performance Testing Program")
	fmt.Println("========================================")
	fmt.Printf("Start Time: %s\n\n", time.Now().Format("2006-01-02 15:04:05"))

	// 确保数据目录存在
	if err := utils.EnsureDataDir(); err != nil {
		fmt.Printf("Failed to create data directory: %v\n", err)
		return
	}

	// Remove old CSV file for clean overwrite
	os.Remove("../csv/ipc_performance_go.csv")

	// 从共享配置文件加载测试参数
	config := loadConfig("../config.json")

	fmt.Println("Test Configuration:")
	fmt.Printf("- Message Sizes: %v bytes\n", config.MessageSizes)
	fmt.Printf("- Producer Counts: %v\n", config.ProducerCounts)
	fmt.Printf("- Consumer Counts: %v\n", config.ConsumerCounts)
	fmt.Printf("- Messages per Producer: %d\n\n", config.MessagesPerProd)

	var allMetrics []*utils.PerformanceMetrics
	testCount := 0
	totalTests := len(config.MessageSizes) * len(config.ProducerCounts) * len(config.ConsumerCounts) * 3

	// 遍历所有测试组合
	var successCount int
	var failedCount int
	
	for _, msgSize := range config.MessageSizes {
		fmt.Printf("\n########## Message Size: %d bytes ##########\n", msgSize)

		for _, producers := range config.ProducerCounts {
			for _, consumers := range config.ConsumerCounts {
				// 跳过不合理的组合
				if producers*consumers > 32 {
					continue
				}

				fmt.Printf("\n--- Test Pattern: %d Producers -> %d Consumers ---\n", producers, consumers)

				// 测试1: 共享内存
				fmt.Println("\n[1/3] Testing Shared Memory IPC...")
				testCount++
				fmt.Printf("[%d/%d] ", testCount, totalTests)
				if metrics, err := shared_memory.RunTest(producers, consumers, config.MessagesPerProd, msgSize); err == nil {
					metrics.Success = true
					successCount++
					allMetrics = append(allMetrics, metrics)
					if err := utils.SaveToCSV(metrics, "ipc_performance_go.csv"); err != nil {
						fmt.Printf("Failed to save data: %v\n", err)
					}
				} else {
					failedCount++
					fmt.Printf("Shared Memory test failed: %v\n", err)
					// 保存失败的测试记录
					failedMetrics := &utils.PerformanceMetrics{
						IPCType:       "shared_memory",
						Pattern:       fmt.Sprintf("%d_%d", producers, consumers),
						ProducerCount: producers,
						ConsumerCount: consumers,
						MessageCount:  producers * config.MessagesPerProd,
						MessageSize:   msgSize,
						Timestamp:     time.Now().Format("2006-01-02 15:04:05"),
						Success:       false,
					}
					utils.SaveToCSV(failedMetrics, "ipc_performance_go.csv")
				}

				// 短暂等待，避免资源竞争
				time.Sleep(200 * time.Millisecond)

				// 测试2: Socket IPC (Unix Socket / Named Pipe)
				fmt.Println("[2/3] Testing Socket IPC...")
				testCount++
				fmt.Printf("[%d/%d] ", testCount, totalTests)
				if metrics, err := socket.RunTest(producers, consumers, config.MessagesPerProd, msgSize); err == nil {
					metrics.Success = true
					successCount++
					allMetrics = append(allMetrics, metrics)
					if err := utils.SaveToCSV(metrics, "ipc_performance_go.csv"); err != nil {
						fmt.Printf("Failed to save data: %v\n", err)
					}
				} else {
					failedCount++
					fmt.Printf("Socket IPC test failed: %v\n", err)
					// 保存失败的测试记录
					failedMetrics := &utils.PerformanceMetrics{
						IPCType:       "socket",
						Pattern:       fmt.Sprintf("%d_%d", producers, consumers),
						ProducerCount: producers,
						ConsumerCount: consumers,
						MessageCount:  producers * config.MessagesPerProd,
						MessageSize:   msgSize,
						Timestamp:     time.Now().Format("2006-01-02 15:04:05"),
						Success:       false,
					}
					utils.SaveToCSV(failedMetrics, "ipc_performance_go.csv")
				}

				// 短暂等待
				time.Sleep(200 * time.Millisecond)

				// 测试3: TCP Socket
				fmt.Println("[3/3] Testing TCP Socket...")
				testCount++
				fmt.Printf("[%d/%d] ", testCount, totalTests)
				if metrics, err := tcp_ipc.RunTest(producers, consumers, config.MessagesPerProd, msgSize); err == nil {
					metrics.Success = true
					successCount++
					allMetrics = append(allMetrics, metrics)
					if err := utils.SaveToCSV(metrics, "ipc_performance_go.csv"); err != nil {
						fmt.Printf("Failed to save data: %v\n", err)
					}
				} else {
					failedCount++
					fmt.Printf("TCP Socket test failed: %v\n", err)
					// 保存失败的测试记录
					failedMetrics := &utils.PerformanceMetrics{
						IPCType:       "tcp",
						Pattern:       fmt.Sprintf("%d_%d", producers, consumers),
						ProducerCount: producers,
						ConsumerCount: consumers,
						MessageCount:  producers * config.MessagesPerProd,
						MessageSize:   msgSize,
						Timestamp:     time.Now().Format("2006-01-02 15:04:05"),
						Success:       false,
					}
					utils.SaveToCSV(failedMetrics, "ipc_performance_go.csv")
				}

				// 每次完整测试后等待
				time.Sleep(500 * time.Millisecond)
			}
		}
	}

	// 在CSV文件末尾添加统计信息
	actualTotalTests := successCount + failedCount
	if err := utils.AppendStatistics("ipc_performance_go.csv", actualTotalTests, successCount, failedCount); err != nil {
		fmt.Printf("Failed to save statistics: %v\n", err)
	}

	// 打印总结
	printSummary(allMetrics)

	fmt.Printf("\n========================================\n")
	fmt.Printf("Testing Complete! End Time: %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Printf("Total Tests: %d | Successful: %d | Failed: %d | Success Rate: %.2f%%\n",
		actualTotalTests, successCount, failedCount, float64(successCount)/float64(actualTotalTests)*100)
	fmt.Printf("Data saved to: ../csv/ipc_performance_go.csv\n")
	fmt.Println("========================================")
}

// printSummary 打印测试总结
func printSummary(metrics []*utils.PerformanceMetrics) {
	fmt.Println("\n\n========================================")
	fmt.Println("         Test Summary Report")
	fmt.Println("========================================")

	if len(metrics) == 0 {
		fmt.Println("No available test data")
		return
	}

	// Group statistics by IPC type
	typeStats := make(map[string][]*utils.PerformanceMetrics)
	for _, m := range metrics {
		typeStats[m.IPCType] = append(typeStats[m.IPCType], m)
	}

	for ipcType, typeMetrics := range typeStats {
		fmt.Printf("\n[%s] Performance Statistics:\n", ipcType)
		
		var totalThroughput float64
		var totalAvgLatency float64
		count := len(typeMetrics)

		for _, m := range typeMetrics {
			totalThroughput += m.Throughput
			totalAvgLatency += m.AvgLatency
		}

		if count > 0 {
			fmt.Printf("  Average Throughput: %.2f messages/sec\n", totalThroughput/float64(count))
			fmt.Printf("  Average Latency: %.2f microseconds\n", totalAvgLatency/float64(count))
			fmt.Printf("  Test Count: %d\n", count)
		}
	}

	// Find best performance
	var bestThroughput *utils.PerformanceMetrics
	var lowestLatency *utils.PerformanceMetrics

	for _, m := range metrics {
		if bestThroughput == nil || m.Throughput > bestThroughput.Throughput {
			bestThroughput = m
		}
		if lowestLatency == nil || m.AvgLatency < lowestLatency.AvgLatency {
			lowestLatency = m
		}
	}

	fmt.Println("\n[Best Performance]")
	if bestThroughput != nil {
		fmt.Printf("  Highest Throughput: %.2f messages/sec (%s, %s, %d bytes)\n",
			bestThroughput.Throughput, bestThroughput.IPCType, 
			bestThroughput.Pattern, bestThroughput.MessageSize)
	}
	if lowestLatency != nil {
		fmt.Printf("  Lowest Latency: %.2f microseconds (%s, %s, %d bytes)\n",
			lowestLatency.AvgLatency, lowestLatency.IPCType,
			lowestLatency.Pattern, lowestLatency.MessageSize)
	}
}
