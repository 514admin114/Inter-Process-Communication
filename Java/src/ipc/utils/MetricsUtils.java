package ipc.utils;

import java.io.*;
import java.nio.file.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

public class MetricsUtils {
    
    // Error injection constants
    public static final double ERROR_RATE = 0.01;
    public static final int MAX_RETRANSMIT = 3;
    
    /** Compute additive checksum (sum of all bytes modulo 2^32) */
    public static int computeChecksum(byte[] data, int offset, int len) {
        int sum = 0;
        for (int i = 0; i < len; i++) {
            sum += (data[offset + i] & 0xFF);
        }
        return sum;
    }
    
    /** Compute checksum on entire array */
    public static int computeChecksum(byte[] data) {
        return computeChecksum(data, 0, data.length);
    }
    
    // 确保数据目录存在
    public static boolean ensureDataDir() {
        try {
            Path dataDir = Paths.get("../csv");
            if (!Files.exists(dataDir)) {
                Files.createDirectories(dataDir);
            }
            return true;
        } catch (IOException e) {
            System.err.println("Failed to create data directory: " + e.getMessage());
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
        
        // 创建副本并排序，避免修改原列表
        List<Double> sorted = new ArrayList<>(latencies);
        Collections.sort(sorted);
        
        int index = (int) (sorted.size() * percentile / 100.0);
        if (index >= sorted.size()) {
            index = sorted.size() - 1;
        }
        
        return sorted.get(index);
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
                             "Avg_Latency_Microseconds,P95_Latency_Microseconds,P99_Latency_Microseconds," +
                             "Error_Count,Retransmit_Count,Accuracy,Success");
            }
            
            // 写入数据行
            String successStr = metrics.success ? "true" : "false";
            writer.printf("%s,%s,%s,%d,%d,%d,%d,%.6f,%.2f,%.2f,%.2f,%.2f,%d,%d,%.2f,%s%n",
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
                metrics.errorCount,
                metrics.retransmitCount,
                metrics.accuracy,
                successStr
            );
            
            return true;
        } catch (IOException e) {
            System.err.println("Failed to write CSV file: " + e.getMessage());
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
            System.err.println("Failed to write statistics: " + e.getMessage());
            return false;
        }
    }
}
