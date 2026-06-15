package ipc.utils;

import java.io.*;
import java.nio.file.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

public class MetricsUtils {
    
    // 确保数据目录存在
    public static boolean ensureDataDir() {
        try {
            Path dataDir = Paths.get("../csv");
            if (!Files.exists(dataDir)) {
                Files.createDirectories(dataDir);
            }
            return true;
        } catch (IOException e) {
            System.err.println("创建数据目录失败: " + e.getMessage());
            return false;
        }
    }
    
    // 获取当前时间戳
    public static String getCurrentTimestamp() {
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
        return LocalDateTime.now().format(formatter);
    }
    
    // 计算百分位数
    public static double calculatePercentile(List<Double> latencies, double percentile) {
        if (latencies.isEmpty()) {
            return 0.0;
        }
        
        // 排序
        Collections.sort(latencies);
        
        int index = (int) (latencies.size() * percentile / 100.0);
        if (index >= latencies.size()) {
            index = latencies.size() - 1;
        }
        
        return latencies.get(index);
    }
    
    // 保存指标到CSV文件
    public static boolean saveToCSV(PerformanceMetrics metrics, String filename) {
        if (!ensureDataDir()) {
            return false;
        }
        
        String filePath = "../csv/" + filename;
        File file = new File(filePath);
        boolean fileExists = file.exists();
        
        try (FileWriter fw = new FileWriter(file, true);
             BufferedWriter bw = new BufferedWriter(fw);
             PrintWriter writer = new PrintWriter(bw)) {
            
            // 如果文件不存在，写入表头
            if (!fileExists) {
                writer.println("Timestamp,IPC_Type,Pattern,Producer_Count,Consumer_Count," +
                             "Message_Count,Message_Size,Total_Time_Seconds,Throughput_Msg_Per_Sec," +
                             "Avg_Latency_Microseconds,P95_Latency_Microseconds,P99_Latency_Microseconds,Success");
            }
            
            // 写入数据行
            String successStr = metrics.success ? "true" : "false";
            writer.printf("%s,%s,%s,%d,%d,%d,%d,%.6f,%.2f,%.2f,%.2f,%.2f,%s%n",
                metrics.timestamp,
                metrics.ipcType,
                metrics.pattern,
                metrics.producerCount,
                metrics.consumerCount,
                metrics.messageCount,
                metrics.messageSize,
                metrics.totalTime,
                metrics.throughput,
                metrics.avgLatency,
                metrics.p95Latency,
                metrics.p99Latency,
                successStr
            );
            
            return true;
        } catch (IOException e) {
            System.err.println("写入CSV文件失败: " + e.getMessage());
            return false;
        }
    }
    
    // 追加统计信息到CSV文件末尾
    public static boolean appendStatistics(String filename, int totalTests, 
                                          int successTests, int failedTests) {
        if (!ensureDataDir()) {
            return false;
        }
        
        String filePath = "../csv/" + filename;
        
        try (FileWriter fw = new FileWriter(filePath, true);
             BufferedWriter bw = new BufferedWriter(fw);
             PrintWriter writer = new PrintWriter(bw)) {
            
            // 写入空行作为分隔符
            writer.println();
            
            // 写入统计信息（使用英文避免编码问题）
            double successRate = (totalTests > 0) ? 
                ((double) successTests / totalTests * 100.0) : 0.0;
            
            writer.println("=== Test Statistics ===");
            writer.println("Total Tests," + totalTests);
            writer.println("Successful Tests," + successTests);
            writer.println("Failed Tests," + failedTests);
            writer.printf("Success Rate,%.2f%%%n", successRate);
            
            return true;
        } catch (IOException e) {
            System.err.println("写入统计信息失败: " + e.getMessage());
            return false;
        }
    }
}
