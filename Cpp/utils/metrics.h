#ifndef METRICS_H
#define METRICS_H

#include <string>
#include <vector>
#include <algorithm>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <chrono>
#include <ctime>
#include <sys/stat.h>

#ifdef _WIN32
    #include <direct.h>
    #define MKDIR(path) _mkdir(path)
#else
    #include <sys/stat.h>
    #define MKDIR(path) mkdir(path, 0755)
#endif

struct PerformanceMetrics {
    std::string ipcType;        // IPC type: shared_memory, socket, tcp
    std::string pattern;        // Pattern: 1_1, N_1, 1_N, N_N
    int producerCount;          // Number of producers
    int consumerCount;          // Number of consumers
    int messageCount;           // Total message count
    int messageSize;            // Message size in bytes
    double totalTime;           // Total time in seconds
    double throughput;          // Throughput (messages/sec)
    double avgLatency;          // Average latency in microseconds
    double p95Latency;          // P95 latency in microseconds
    double p99Latency;          // P99 latency in microseconds
    std::string timestamp;      // Timestamp
    bool success;               // Whether test succeeded
};

class MetricsUtils {
public:
    // Ensure data directory exists
    static bool ensureDataDir() {
        std::string dataDir = "../csv";
        
#ifdef _WIN32
        if (_mkdir(dataDir.c_str()) != 0 && errno != EEXIST) {
            return false;
        }
#else
        if (mkdir(dataDir.c_str(), 0755) != 0 && errno != EEXIST) {
            return false;
        }
#endif
        
        return true;
    }
    
    // Get current timestamp as string
    static std::string getCurrentTimestamp() {
        auto now = std::chrono::system_clock::now();
        auto time_t_now = std::chrono::system_clock::to_time_t(now);
        std::tm tm_now;
        
#ifdef _WIN32
        localtime_s(&tm_now, &time_t_now);
#else
        localtime_r(&time_t_now, &tm_now);
#endif
        
        std::ostringstream oss;
        oss << std::put_time(&tm_now, "%Y-%m-%d %H:%M:%S");
        return oss.str();
    }
    
    // Calculate percentile from sorted latencies
    static double calculatePercentile(std::vector<double>& latencies, double percentile) {
        if (latencies.empty()) {
            return 0.0;
        }
        
        // Sort latencies
        std::sort(latencies.begin(), latencies.end());
        
        size_t index = static_cast<size_t>(latencies.size() * percentile / 100.0);
        if (index >= latencies.size()) {
            index = latencies.size() - 1;
        }
        
        return latencies[index];
    }
    
    // Save metrics to CSV file
    static bool saveToCSV(const PerformanceMetrics& metrics, const std::string& filename) {
        if (!ensureDataDir()) {
            return false;
        }
        
        std::string filePath = "../csv/" + filename;
        
        // Check if file exists
        bool fileExists = true;
        std::ifstream testFile(filePath);
        if (!testFile.good()) {
            fileExists = false;
        }
        testFile.close();
        
        // Open file in append mode
        std::ofstream file(filePath, std::ios::app);
        if (!file.is_open()) {
            return false;
        }
        
        // Write header if file is new
        if (!fileExists) {
            file << "Timestamp,IPC_Type,Pattern,Producer_Count,Consumer_Count,"
                 << "Message_Count,Message_Size,Total_Time_Seconds,Throughput_Msg_Per_Sec,"
                 << "Avg_Latency_Microseconds,P95_Latency_Microseconds,P99_Latency_Microseconds,Success\n";
        }
        
        // Write data row
        file << metrics.timestamp << ","
             << metrics.ipcType << ","
             << metrics.pattern << ","
             << metrics.producerCount << ","
             << metrics.consumerCount << ","
             << metrics.messageCount << ","
             << metrics.messageSize << ","
             << std::fixed << std::setprecision(6) << metrics.totalTime << ","
             << std::fixed << std::setprecision(2) << metrics.throughput << ","
             << std::fixed << std::setprecision(2) << metrics.avgLatency << ","
             << std::fixed << std::setprecision(2) << metrics.p95Latency << ","
             << std::fixed << std::setprecision(2) << metrics.p99Latency << ","
             << (metrics.success ? "true" : "false") << "\n";
        
        file.close();
        return true;
    }
    
    // Append statistics to end of CSV file
    static bool appendStatistics(const std::string& filename, 
                                 int totalTests, 
                                 int successTests, 
                                 int failedTests) {
        if (!ensureDataDir()) {
            return false;
        }
        
        std::string filePath = "../csv/" + filename;
        
        std::ofstream file(filePath, std::ios::app);
        if (!file.is_open()) {
            return false;
        }
        
        // Write blank line separator
        file << "\n";
        
        // Write statistics in English
        double successRate = (totalTests > 0) ? 
            (static_cast<double>(successTests) / totalTests * 100.0) : 0.0;
        
        file << "=== Test Statistics ===\n";
        file << "Total Tests," << totalTests << "\n";
        file << "Successful Tests," << successTests << "\n";
        file << "Failed Tests," << failedTests << "\n";
        file << "Success Rate," << std::fixed << std::setprecision(2) << successRate << "%\n";
        
        file.close();
        return true;
    }
};

#endif // METRICS_H
