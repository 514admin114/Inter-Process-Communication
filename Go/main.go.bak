package main

import (
	"fmt"
	"time"

	"ipc/shared_memory"
	"ipc/socket"
	"ipc/tcp_ipc"
	"ipc/utils"
)

// TestConfig 测试配置
type TestConfig struct {
	MessageSizes     []int // 消息大小列表（字节）
	ProducerCounts   []int // 生产者数量列表
	ConsumerCounts   []int // 消费者数量列表
	MessagesPerProd  int   // 每个生产者的消息数
}

func main() {
	fmt.Println("========================================")
	fmt.Println("  进程间通信(IPC)性能测试程序")
	fmt.Println("========================================")
	fmt.Printf("开始时间: %s\n\n", time.Now().Format("2006-01-02 15:04:05"))

	// 确保数据目录存在
	if err := utils.EnsureDataDir(); err != nil {
		fmt.Printf("创建数据目录失败: %v\n", err)
		return
	}

	// 测试配置 - 简化版用于快速测试
	config := TestConfig{
		MessageSizes:    []int{64, 1024},           // 64B, 1KB (简化测试)
		ProducerCounts:  []int{1, 2, 4},            // 1, 2, 4个生产者
		ConsumerCounts:  []int{1, 2, 4},            // 1, 2, 4个消费者
		MessagesPerProd: 500,                        // 每个生产者发送500条消息(简化)
	}

	// 如需完整测试，使用以下配置：
	/*
	config := TestConfig{
		MessageSizes:    []int{64, 256, 1024, 4096}, // 64B, 256B, 1KB, 4KB
		ProducerCounts:  []int{1, 2, 4, 8},          // 1, 2, 4, 8个生产者
		ConsumerCounts:  []int{1, 2, 4, 8},          // 1, 2, 4, 8个消费者
		MessagesPerProd: 1000,                        // 每个生产者发送1000条消息
	}
	*/

	fmt.Println("测试配置:")
	fmt.Printf("- 消息大小: %v 字节\n", config.MessageSizes)
	fmt.Printf("- 生产者数量: %v\n", config.ProducerCounts)
	fmt.Printf("- 消费者数量: %v\n", config.ConsumerCounts)
	fmt.Printf("- 每个生产者消息数: %d\n\n", config.MessagesPerProd)

	var allMetrics []*utils.PerformanceMetrics
	testCount := 0
	totalTests := len(config.MessageSizes) * len(config.ProducerCounts) * len(config.ConsumerCounts) * 3

	// 遍历所有测试组合
	var successCount int
	var failedCount int
	
	for _, msgSize := range config.MessageSizes {
		fmt.Printf("\n########## 消息大小: %d 字节 ##########\n", msgSize)

		for _, producers := range config.ProducerCounts {
			for _, consumers := range config.ConsumerCounts {
				// 跳过不合理的组合
				if producers*consumers > 32 {
					continue
				}

				fmt.Printf("\n--- 测试模式: %d生产者 -> %d消费者 ---\n", producers, consumers)

				// 测试1: 共享内存
				fmt.Println("\n[1/3] 测试共享内存IPC...")
				testCount++
				fmt.Printf("[%d/%d] ", testCount, totalTests)
				if metrics, err := shared_memory.RunTest(producers, consumers, config.MessagesPerProd, msgSize); err == nil {
					metrics.Success = true
					successCount++
					allMetrics = append(allMetrics, metrics)
					if err := utils.SaveToCSV(metrics, "ipc_performance_go.csv"); err != nil {
						fmt.Printf("保存数据失败: %v\n", err)
					}
				} else {
					failedCount++
					fmt.Printf("共享内存测试失败: %v\n", err)
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
				fmt.Println("[2/3] 测试Socket IPC...")
				testCount++
				fmt.Printf("[%d/%d] ", testCount, totalTests)
				if metrics, err := socket.RunTest(producers, consumers, config.MessagesPerProd, msgSize); err == nil {
					metrics.Success = true
					successCount++
					allMetrics = append(allMetrics, metrics)
					if err := utils.SaveToCSV(metrics, "ipc_performance_go.csv"); err != nil {
						fmt.Printf("保存数据失败: %v\n", err)
					}
				} else {
					failedCount++
					fmt.Printf("Socket IPC测试失败: %v\n", err)
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
				fmt.Println("[3/3] 测试TCP Socket...")
				testCount++
				fmt.Printf("[%d/%d] ", testCount, totalTests)
				if metrics, err := tcp_ipc.RunTest(producers, consumers, config.MessagesPerProd, msgSize); err == nil {
					metrics.Success = true
					successCount++
					allMetrics = append(allMetrics, metrics)
					if err := utils.SaveToCSV(metrics, "ipc_performance_go.csv"); err != nil {
						fmt.Printf("保存数据失败: %v\n", err)
					}
				} else {
					failedCount++
					fmt.Printf("TCP Socket测试失败: %v\n", err)
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
		fmt.Printf("保存统计信息失败: %v\n", err)
	}

	// 打印总结
	printSummary(allMetrics)

	fmt.Printf("\n========================================\n")
	fmt.Printf("测试完成! 结束时间: %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Printf("总测试数: %d | 成功: %d | 失败: %d | 成功率: %.2f%%\n", 
		actualTotalTests, successCount, failedCount, float64(successCount)/float64(actualTotalTests)*100)
	fmt.Printf("数据已保存到: ../csv/ipc_performance_go.csv\n")
	fmt.Println("========================================")
}

// printSummary 打印测试总结
func printSummary(metrics []*utils.PerformanceMetrics) {
	fmt.Println("\n\n========================================")
	fmt.Println("         测试总结报告")
	fmt.Println("========================================")

	if len(metrics) == 0 {
		fmt.Println("没有可用的测试数据")
		return
	}

	// 按IPC类型分组统计
	typeStats := make(map[string][]*utils.PerformanceMetrics)
	for _, m := range metrics {
		typeStats[m.IPCType] = append(typeStats[m.IPCType], m)
	}

	for ipcType, typeMetrics := range typeStats {
		fmt.Printf("\n【%s】性能统计:\n", ipcType)
		
		var totalThroughput float64
		var totalAvgLatency float64
		count := len(typeMetrics)

		for _, m := range typeMetrics {
			totalThroughput += m.Throughput
			totalAvgLatency += m.AvgLatency
		}

		if count > 0 {
			fmt.Printf("  平均吞吐量: %.2f 消息/秒\n", totalThroughput/float64(count))
			fmt.Printf("  平均延迟: %.2f 微秒\n", totalAvgLatency/float64(count))
			fmt.Printf("  测试次数: %d\n", count)
		}
	}

	// 找出最佳性能
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

	fmt.Println("\n【最佳性能】")
	if bestThroughput != nil {
		fmt.Printf("  最高吞吐量: %.2f 消息/秒 (%s, %s, %d字节)\n",
			bestThroughput.Throughput, bestThroughput.IPCType, 
			bestThroughput.Pattern, bestThroughput.MessageSize)
	}
	if lowestLatency != nil {
		fmt.Printf("  最低延迟: %.2f 微秒 (%s, %s, %d字节)\n",
			lowestLatency.AvgLatency, lowestLatency.IPCType,
			lowestLatency.Pattern, lowestLatency.MessageSize)
	}
}
