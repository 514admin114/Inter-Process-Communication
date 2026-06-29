#include <iostream>
#include <vector>
#include <string>
#include <thread>
#include <chrono>
#include <iomanip>

#include "utils/metrics.h"
#include "shared_memory/shared_memory.h"
#include "socket/socket_ipc.h"
#include "tcp_ipc/tcp_ipc.h"

struct TestConfig {
    std::vector<int> messageSizes;
    std::vector<int> producerCounts;
    std::vector<int> consumerCounts;
    int messagesPerProd;
};

void printMetrics(const PerformanceMetrics& metrics) {
    std::cout << "\n=== " << metrics.ipcType << " Test ===" << std::endl;
    std::cout << "Producers: " << metrics.producerCount 
              << ", Consumers: " << metrics.consumerCount
              << ", Messages per Producer: " << (metrics.messageCount / metrics.producerCount)
              << ", Message Size: " << metrics.messageSize << " bytes" << std::endl;
    std::cout << "Total Time: " << std::fixed << std::setprecision(6) << metrics.totalTime << " seconds" << std::endl;
    std::cout << "Throughput: " << std::fixed << std::setprecision(2) << metrics.throughput << " messages/sec" << std::endl;
    std::cout << "Average Latency: " << std::fixed << std::setprecision(2) << metrics.avgLatency << " microseconds" << std::endl;
    std::cout << "P95 Latency: " << std::fixed << std::setprecision(2) << metrics.p95Latency << " microseconds" << std::endl;
    std::cout << "P99 Latency: " << std::fixed << std::setprecision(2) << metrics.p99Latency << " microseconds" << std::endl;
    std::cout << "Success: " << (metrics.success ? "true" : "false") << std::endl;
}

int main() {
    std::cout << "========================================" << std::endl;
    std::cout << "  Inter-Process Communication (IPC)" << std::endl;
    std::cout << "  Performance Testing Program (C++)" << std::endl;
    std::cout << "========================================\n" << std::endl;
    
    // Ensure data directory exists
    if (!MetricsUtils::ensureDataDir()) {
        std::cerr << "Failed to create data directory" << std::endl;
        return 1;
    }
    
    // Test configuration - simplified version for quick testing
    TestConfig config;
    config.messageSizes = {64, 1024};           // 64B, 1KB (simplified)
    config.producerCounts = {1, 2, 4};          // 1, 2, 4 producers
    config.consumerCounts = {1, 2, 4};          // 1, 2, 4 consumers
    config.messagesPerProd = 500;               // 500 messages per producer (simplified)

    // 如需完整测试，使用以下配置：
    /*
    config.messageSizes = {64, 256, 1024, 4096};  // 4种大小
    config.producerCounts = {1, 2, 4, 8};         // 4种数量
    config.consumerCounts = {1, 2, 4, 8};         // 4种数量
    config.messagesPerProd = 1000;                 // 1000条消息
    */

    std::cout << "Test Configuration:" << std::endl;
    std::cout << "- Message Sizes: ";
    for (size_t i = 0; i < config.messageSizes.size(); i++) {
        std::cout << config.messageSizes[i];
        if (i < config.messageSizes.size() - 1) std::cout << ", ";
    }
    std::cout << " bytes" << std::endl;
    
    std::cout << "- Producer Counts: ";
    for (size_t i = 0; i < config.producerCounts.size(); i++) {
        std::cout << config.producerCounts[i];
        if (i < config.producerCounts.size() - 1) std::cout << ", ";
    }
    std::cout << std::endl;
    
    std::cout << "- Consumer Counts: ";
    for (size_t i = 0; i < config.consumerCounts.size(); i++) {
        std::cout << config.consumerCounts[i];
        if (i < config.consumerCounts.size() - 1) std::cout << ", ";
    }
    std::cout << std::endl;
    
    std::cout << "- Messages per Producer: " << config.messagesPerProd << "\n" << std::endl;
    
    std::vector<PerformanceMetrics> allMetrics;
    int testCount = 0;
    int totalTests = config.messageSizes.size() * config.producerCounts.size() * 
                     config.consumerCounts.size() * 3;
    
    int successCount = 0;
    int failedCount = 0;
    
    auto programStart = std::chrono::high_resolution_clock::now();
    
    // Iterate through all test combinations
    for (int msgSize : config.messageSizes) {
        std::cout << "\n########## Message Size: " << msgSize << " bytes ##########" << std::endl;
        
        for (int producers : config.producerCounts) {
            for (int consumers : config.consumerCounts) {
                // Skip unreasonable combinations
                if (producers * consumers > 32) {
                    continue;
                }
                
                std::cout << "\n--- Test Mode: " << producers << " Producers -> " 
                          << consumers << " Consumers ---" << std::endl;
                
                // Test 1: Shared Memory
                std::cout << "\n[1/3] Testing Shared Memory IPC..." << std::endl;
                testCount++;
                std::cout << "[" << testCount << "/" << totalTests << "] ";
                
                {
                    SharedMemoryIPC sharedMem;
                    PerformanceMetrics metrics = sharedMem.runTest(producers, consumers, 
                                                                  config.messagesPerProd, msgSize);
                    if (metrics.success) {
                        metrics.success = true;
                        successCount++;
                        allMetrics.push_back(metrics);
                        MetricsUtils::saveToCSV(metrics, "ipc_performance_cpp.csv");
                        printMetrics(metrics);
                    } else {
                        failedCount++;
                        std::cerr << "Shared memory test failed" << std::endl;
                        metrics.success = false;
                        MetricsUtils::saveToCSV(metrics, "ipc_performance_cpp.csv");
                    }
                }
                
                // Brief wait to avoid resource contention
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
                
                // Test 2: Socket IPC
                std::cout << "[2/3] Testing Socket IPC..." << std::endl;
                testCount++;
                std::cout << "[" << testCount << "/" << totalTests << "] ";
                
                {
                    SocketIPC socket;
                    PerformanceMetrics metrics = socket.runTest(producers, consumers, 
                                                               config.messagesPerProd, msgSize);
                    if (metrics.success) {
                        metrics.success = true;
                        successCount++;
                        allMetrics.push_back(metrics);
                        MetricsUtils::saveToCSV(metrics, "ipc_performance_cpp.csv");
                        printMetrics(metrics);
                    } else {
                        failedCount++;
                        std::cerr << "Socket IPC test failed" << std::endl;
                        metrics.success = false;
                        MetricsUtils::saveToCSV(metrics, "ipc_performance_cpp.csv");
                    }
                }
                
                // Brief wait
                std::this_thread::sleep_for(std::chrono::milliseconds(200));
                
                // Test 3: TCP Socket
                std::cout << "[3/3] Testing TCP Socket..." << std::endl;
                testCount++;
                std::cout << "[" << testCount << "/" << totalTests << "] ";
                
                {
                    TcpIPC tcp;
                    PerformanceMetrics metrics = tcp.runTest(producers, consumers, 
                                                            config.messagesPerProd, msgSize);
                    if (metrics.success) {
                        metrics.success = true;
                        successCount++;
                        allMetrics.push_back(metrics);
                        MetricsUtils::saveToCSV(metrics, "ipc_performance_cpp.csv");
                        printMetrics(metrics);
                    } else {
                        failedCount++;
                        std::cerr << "TCP Socket test failed" << std::endl;
                        metrics.success = false;
                        MetricsUtils::saveToCSV(metrics, "ipc_performance_cpp.csv");
                    }
                }
                
                // Wait after each complete test
                std::this_thread::sleep_for(std::chrono::milliseconds(500));
            }
        }
    }
    
    auto programEnd = std::chrono::high_resolution_clock::now();
    double totalProgramTime = std::chrono::duration<double>(programEnd - programStart).count();
    
    // Append statistics to CSV file
    int actualTotalTests = successCount + failedCount;
    MetricsUtils::appendStatistics("ipc_performance_cpp.csv", actualTotalTests, successCount, failedCount);
    
    // Print summary
    std::cout << "\n========================================" << std::endl;
    std::cout << "Testing Complete!" << std::endl;
    std::cout << "End Time: " << MetricsUtils::getCurrentTimestamp() << std::endl;
    std::cout << "Total Tests: " << actualTotalTests 
              << " | Successful: " << successCount 
              << " | Failed: " << failedCount 
              << " | Success Rate: " << std::fixed << std::setprecision(2) 
              << (actualTotalTests > 0 ? static_cast<double>(successCount) / actualTotalTests * 100 : 0) 
              << "%" << std::endl;
    std::cout << "Total Program Time: " << std::fixed << std::setprecision(2) << totalProgramTime << " seconds" << std::endl;
    std::cout << "Data saved to: ../csv/ipc_performance_cpp.csv" << std::endl;
    std::cout << "========================================" << std::endl;
    
    return 0;
}
