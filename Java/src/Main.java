import ipc.shared_memory.SharedMemory;
import ipc.socket.SocketIPC;
import ipc.tcp_ipc.TcpIPC;
import ipc.utils.PerformanceMetrics;
import ipc.utils.MetricsUtils;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;

public class Main {
    
    // 测试配置
    static class TestConfig {
        List<Integer> messageSizes;     // 消息大小列表（字节）
        List<Integer> producerCounts;   // 生产者数量列表
        List<Integer> consumerCounts;   // 消费者数量列表
        int messagesPerProd;            // 每个生产者的消息数
        
        public TestConfig() {
            this.messageSizes = new ArrayList<>();
            this.producerCounts = new ArrayList<>();
            this.consumerCounts = new ArrayList<>();
        }
    }
    
    // 从JSON文件加载测试配置（手动解析，无需第三方库）
    private static TestConfig loadConfig(String path) {
        TestConfig config = new TestConfig();
        try {
            String json = new String(Files.readAllBytes(Paths.get(path)));
            config.messageSizes = parseIntArray(json, "message_sizes");
            config.producerCounts = parseIntArray(json, "producer_counts");
            config.consumerCounts = parseIntArray(json, "consumer_counts");
            config.messagesPerProd = parseInt(json, "messages_per_producer");
            return config;
        } catch (IOException e) {
            System.err.println("Warning: cannot open " + path + ", using defaults");
        }
        // 默认配置
        config.messageSizes = Arrays.asList(64, 1024);
        config.producerCounts = Arrays.asList(1, 2, 4);
        config.consumerCounts = Arrays.asList(1, 2, 4);
        config.messagesPerProd = 500;
        return config;
    }
    
    // 从JSON中解析整数数组: "key": [1, 2, 4]
    private static List<Integer> parseIntArray(String json, String key) {
        List<Integer> result = new ArrayList<>();
        int keyIdx = json.indexOf("\"" + key + "\"");
        if (keyIdx < 0) return result;
        int start = json.indexOf("[", keyIdx);
        if (start < 0) return result;
        int end = json.indexOf("]", start);
        if (end < 0) return result;
        String arr = json.substring(start + 1, end);
        for (String token : arr.split(",")) {
            token = token.trim();
            if (!token.isEmpty()) {
                result.add(Integer.parseInt(token));
            }
        }
        return result;
    }
    
    // 从JSON中解析整数: "key": 500
    private static int parseInt(String json, String key) {
        int keyIdx = json.indexOf("\"" + key + "\"");
        if (keyIdx < 0) return 0;
        int colon = json.indexOf(":", keyIdx);
        if (colon < 0) return 0;
        String rest = json.substring(colon + 1).trim();
        StringBuilder num = new StringBuilder();
        for (int i = 0; i < rest.length(); i++) {
            char c = rest.charAt(i);
            if (Character.isDigit(c) || c == '-') {
                num.append(c);
            } else if (num.length() > 0) {
                break;
            }
        }
        return num.length() > 0 ? Integer.parseInt(num.toString()) : 0;
    }
    
    public static void main(String[] args) {
        System.out.println("========================================");
        System.out.println("  Inter-Process Communication (IPC) Performance Testing Program");
        System.out.println("========================================");
        System.out.printf("Start Time: %s%n%n", MetricsUtils.getCurrentTimestamp());
        
        // 确保数据目录存在
        if (!MetricsUtils.ensureDataDir()) {
            System.err.println("Failed to create data directory");
            return;
        }
        
        // Remove old CSV file for clean overwrite
        new File("../csv/ipc_performance_java.csv").delete();
        
        // 从共享配置文件加载测试参数
        TestConfig config = loadConfig("../config.json");
        
        System.out.println("Test Configuration:");
        System.out.println("- Message Sizes: " + config.messageSizes + " bytes");
        System.out.println("- Producer Counts: " + config.producerCounts);
        System.out.println("- Consumer Counts: " + config.consumerCounts);
        System.out.println("- Messages per Producer: " + config.messagesPerProd + "%n");
        
        List<PerformanceMetrics> allMetrics = new ArrayList<>();
        int testCount = 0;
        int totalTests = config.messageSizes.size() * config.producerCounts.size() * 
                        config.consumerCounts.size() * 3;
        
        int successCount = 0;
        int failedCount = 0;
        
        long programStart = System.nanoTime();
        
        // 遍历所有测试组合
        for (int msgSize : config.messageSizes) {
            System.out.printf("%n########## Message Size: %d bytes ##########%n", msgSize);
            
            for (int producers : config.producerCounts) {
                for (int consumers : config.consumerCounts) {
                    // 跳过不合理的组合
                    if (producers * consumers > 32) {
                        continue;
                    }
                    
                    System.out.printf("%n--- Test Pattern: %d Producers -> %d Consumers ---%n", producers, consumers);
                    
                    // 测试1: 共享内存
                    System.out.println("\n[1/3] Testing Shared Memory IPC...");
                    testCount++;
                    System.out.printf("[%d/%d] ", testCount, totalTests);
                    
                    try {
                        PerformanceMetrics metrics = SharedMemory.runTest(producers, consumers, 
                                                                         config.messagesPerProd, msgSize);
                        metrics.success = true;
                        successCount++;
                        allMetrics.add(metrics);
                        MetricsUtils.saveToCSV(metrics, "ipc_performance_java.csv");
                    } catch (Exception e) {
                        failedCount++;
                        System.err.println("Shared Memory test failed: " + e.getMessage());
                        // 保存失败的测试记录
                        PerformanceMetrics failedMetrics = new PerformanceMetrics();
                        failedMetrics.ipcType = "shared_memory";
                        failedMetrics.pattern = producers + "_" + consumers;
                        failedMetrics.producerCount = producers;
                        failedMetrics.consumerCount = consumers;
                        failedMetrics.messageCount = producers * config.messagesPerProd;
                        failedMetrics.messageSize = msgSize;
                        failedMetrics.timestamp = MetricsUtils.getCurrentTimestamp();
                        failedMetrics.success = false;
                        MetricsUtils.saveToCSV(failedMetrics, "ipc_performance_java.csv");
                    }
                    
                    // 短暂等待，避免资源竞争
                    try {
                        Thread.sleep(50);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }

                    // 测试2: Socket IPC
                    System.out.println("[2/3] Testing Socket IPC...");
                    testCount++;
                    System.out.printf("[%d/%d] ", testCount, totalTests);
                    
                    try {
                        PerformanceMetrics metrics = SocketIPC.runTest(producers, consumers, 
                                                                      config.messagesPerProd, msgSize);
                        metrics.success = true;
                        successCount++;
                        allMetrics.add(metrics);
                        MetricsUtils.saveToCSV(metrics, "ipc_performance_java.csv");
                    } catch (Exception e) {
                        failedCount++;
                        System.err.println("Socket IPC test failed: " + e.getMessage());
                        // 保存失败的测试记录
                        PerformanceMetrics failedMetrics = new PerformanceMetrics();
                        failedMetrics.ipcType = "socket";
                        failedMetrics.pattern = producers + "_" + consumers;
                        failedMetrics.producerCount = producers;
                        failedMetrics.consumerCount = consumers;
                        failedMetrics.messageCount = producers * config.messagesPerProd;
                        failedMetrics.messageSize = msgSize;
                        failedMetrics.timestamp = MetricsUtils.getCurrentTimestamp();
                        failedMetrics.success = false;
                        MetricsUtils.saveToCSV(failedMetrics, "ipc_performance_java.csv");
                    }
                    
                    // 短暂等待
                    try {
                        Thread.sleep(50);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }

                    // 测试3: TCP Socket
                    System.out.println("[3/3] Testing TCP Socket...");
                    testCount++;
                    System.out.printf("[%d/%d] ", testCount, totalTests);
                    
                    try {
                        PerformanceMetrics metrics = TcpIPC.runTest(producers, consumers, 
                                                                   config.messagesPerProd, msgSize);
                        metrics.success = true;
                        successCount++;
                        allMetrics.add(metrics);
                        MetricsUtils.saveToCSV(metrics, "ipc_performance_java.csv");
                    } catch (Exception e) {
                        failedCount++;
                        System.err.println("TCP Socket test failed: " + e.getMessage());
                        // 保存失败的测试记录
                        PerformanceMetrics failedMetrics = new PerformanceMetrics();
                        failedMetrics.ipcType = "tcp";
                        failedMetrics.pattern = producers + "_" + consumers;
                        failedMetrics.producerCount = producers;
                        failedMetrics.consumerCount = consumers;
                        failedMetrics.messageCount = producers * config.messagesPerProd;
                        failedMetrics.messageSize = msgSize;
                        failedMetrics.timestamp = MetricsUtils.getCurrentTimestamp();
                        failedMetrics.success = false;
                        MetricsUtils.saveToCSV(failedMetrics, "ipc_performance_java.csv");
                    }
                    
                    // 每次完整测试后短暂等待
                    try {
                        Thread.sleep(100);
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    }
                }
            }
        }
        
        long programEnd = System.nanoTime();
        double totalProgramTime = (programEnd - programStart) / 1_000_000_000.0;
        
        // 在CSV文件末尾添加统计信息
        int actualTotalTests = successCount + failedCount;
        MetricsUtils.appendStatistics("ipc_performance_java.csv", actualTotalTests, successCount, failedCount);
        
        // 打印总结
        printSummary(allMetrics);
        
        System.out.println("\n========================================");
        System.out.printf("Testing Complete! End Time: %s%n", MetricsUtils.getCurrentTimestamp());
        System.out.printf("Total Tests: %d | Successful: %d | Failed: %d | Success Rate: %.2f%%%n",
            actualTotalTests, successCount, failedCount,
            actualTotalTests > 0 ? (double) successCount / actualTotalTests * 100 : 0);
        System.out.printf("Total Program Time: %.2f seconds%n", totalProgramTime);
        System.out.println("Data saved to: ../csv/ipc_performance_java.csv");
        System.out.println("========================================");
    }
    
    // 打印测试总结
    private static void printSummary(List<PerformanceMetrics> metricsList) {
        System.out.println("\n\n========================================");
        System.out.println("         Test Summary Report");
        System.out.println("========================================");
        
        if (metricsList.isEmpty()) {
            System.out.println("No available test data");
            return;
        }
        
        // Group statistics by IPC type
        Map<String, List<PerformanceMetrics>> typeStats = new HashMap<>();
        for (PerformanceMetrics m : metricsList) {
            typeStats.computeIfAbsent(m.ipcType, k -> new ArrayList<>()).add(m);
        }
        
        for (Map.Entry<String, List<PerformanceMetrics>> entry : typeStats.entrySet()) {
            String ipcType = entry.getKey();
            List<PerformanceMetrics> typeMetrics = entry.getValue();
            
            System.out.printf("%n[%s] Performance Statistics:%n", ipcType);
            
            double totalThroughput = 0;
            double totalAvgLatency = 0;
            int count = typeMetrics.size();
            
            for (PerformanceMetrics m : typeMetrics) {
                totalThroughput += m.throughput;
                totalAvgLatency += m.avgLatency;
            }
            
            if (count > 0) {
                System.out.printf("  Average Throughput: %.2f messages/sec%n", totalThroughput / count);
                System.out.printf("  Average Latency: %.2f microseconds%n", totalAvgLatency / count);
                System.out.printf("  Test Count: %d%n", count);
            }
        }
        
        // Find best performance
        PerformanceMetrics bestThroughput = null;
        PerformanceMetrics lowestLatency = null;
        
        for (PerformanceMetrics m : metricsList) {
            if (bestThroughput == null || m.throughput > bestThroughput.throughput) {
                bestThroughput = m;
            }
            if (lowestLatency == null || m.avgLatency < lowestLatency.avgLatency) {
                lowestLatency = m;
            }
        }
        
        System.out.println("\n[Best Performance]");
        if (bestThroughput != null) {
            System.out.printf("  Highest Throughput: %.2f messages/sec (%s, %s, %d bytes)%n",
                bestThroughput.throughput, bestThroughput.ipcType,
                bestThroughput.pattern, bestThroughput.messageSize);
        }
        if (lowestLatency != null) {
            System.out.printf("  Lowest Latency: %.2f microseconds (%s, %s, %d bytes)%n",
                lowestLatency.avgLatency, lowestLatency.ipcType,
                lowestLatency.pattern, lowestLatency.messageSize);
        }
    }
}
