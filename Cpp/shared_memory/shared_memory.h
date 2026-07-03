#ifndef SHARED_MEMORY_H
#define SHARED_MEMORY_H

#include <iostream>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <queue>
#include <atomic>
#include <chrono>
#include <functional>
#include <cstring>
#include <cstdlib>
#include <random>
#include "../utils/metrics.h"

class SharedMemoryIPC {
private:
    struct Message {
        std::vector<char> data;  // includes data + 4-byte checksum appended
        std::chrono::high_resolution_clock::time_point sendTime;
    };
    
    std::queue<Message> messageQueue;
    std::mutex queueMutex;
    std::condition_variable cv;
    std::atomic<int> receivedCount{0};
    std::atomic<int> errorCount{0};
    int expectedMessages;
    
public:
    // Producer function
    void producer(int id, int messageCount, int messageSize, 
                  std::vector<double>* latencies, std::mutex* latenciesMutex) {
        // Create test data (messageSize bytes of payload)
        std::vector<char> data(messageSize);
        for (int i = 0; i < messageSize; i++) {
            data[i] = static_cast<char>(i % 256);
        }
        
        // Thread-safe random number generator (thread-local)
        thread_local std::mt19937 rng(std::random_device{}());
        std::uniform_real_distribution<double> errorDist(0.0, 1.0);
        std::uniform_int_distribution<int> posDist(0, messageSize - 1);
        
        for (int i = 0; i < messageCount; i++) {
            auto startTime = std::chrono::high_resolution_clock::now();
            
            // Compute checksum on original data
            uint32_t checksum = computeChecksum(data.data(), messageSize);
            
            // Build message: data + 4-byte checksum
            std::vector<char> msgData(messageSize + 4);
            std::memcpy(msgData.data(), data.data(), messageSize);
            std::memcpy(msgData.data() + messageSize, &checksum, 4);
            
            // Error injection: with ERROR_RATE probability, corrupt 1 byte
            if (errorDist(rng) < ERROR_RATE) {
                int corruptPos = posDist(rng);  // corrupt in data portion only
                msgData[corruptPos] = static_cast<char>(msgData[corruptPos] ^ 0xFF);
            }
            
            Message msg;
            msg.data = std::move(msgData);
            msg.sendTime = startTime;
            
            {
                std::lock_guard<std::mutex> lock(queueMutex);
                messageQueue.push(msg);
            }
            cv.notify_one();
            
            auto endTime = std::chrono::high_resolution_clock::now();
            double elapsed = std::chrono::duration<double, std::micro>(endTime - startTime).count();
            
            {
                std::lock_guard<std::mutex> lock(*latenciesMutex);
                latencies->push_back(elapsed);
            }
        }
    }
    
    // Consumer function
    void consumer(int id, int messageSize, std::atomic<bool>* stopFlag) {
        while (true) {
            Message msg;
            {
                std::unique_lock<std::mutex> lock(queueMutex);
                cv.wait(lock, [this, stopFlag]() {
                    return !messageQueue.empty() || stopFlag->load();
                });
                
                if (stopFlag->load() && messageQueue.empty()) {
                    break;
                }
                if (messageQueue.empty()) {
                    continue;
                }
                
                msg = messageQueue.front();
                messageQueue.pop();
            }
            
            // Validate checksum: last 4 bytes are checksum, rest is data
            size_t totalLen = msg.data.size();
            size_t dataLen = totalLen - 4;
            uint32_t expectedChecksum, receivedChecksum;
            std::memcpy(&receivedChecksum, msg.data.data() + dataLen, 4);
            expectedChecksum = computeChecksum(msg.data.data(), dataLen);
            
            if (expectedChecksum != receivedChecksum) {
                errorCount.fetch_add(1);
            }
            
            // Simulate work
            volatile char sum = 0;
            for (size_t c = 0; c < dataLen; c++) {
                sum += msg.data[c];
            }
            
            receivedCount.fetch_add(1);
        }
    }
    
    // Run test
    PerformanceMetrics runTest(int producers, int consumers, int messagesPerProducer, int messageSize) {
        PerformanceMetrics metrics;
        metrics.ipcType = "shared_memory";
        metrics.pattern = std::to_string(producers) + "_" + std::to_string(consumers);
        metrics.producerCount = producers;
        metrics.consumerCount = consumers;
        metrics.messageCount = producers * messagesPerProducer;
        metrics.messageSize = messageSize;
        metrics.timestamp = MetricsUtils::getCurrentTimestamp();
        metrics.errorCount = 0;
        metrics.retransmitCount = 0;
        metrics.success = false;
        
        expectedMessages = metrics.messageCount;
        errorCount.store(0);
        receivedCount.store(0);
        
        std::vector<std::thread> producerThreads;
        std::vector<std::thread> consumerThreads;
        std::vector<double> latencies;
        std::mutex latenciesMutex;
        std::atomic<bool> stopFlag{false};
        
        auto startTime = std::chrono::high_resolution_clock::now();
        
        // Start consumers
        for (int i = 0; i < consumers; i++) {
            consumerThreads.emplace_back(&SharedMemoryIPC::consumer, this, i, messageSize, &stopFlag);
        }
        
        // Start producers
        for (int i = 0; i < producers; i++) {
            producerThreads.emplace_back(&SharedMemoryIPC::producer, this, i, 
                                        messagesPerProducer, messageSize, 
                                        &latencies, &latenciesMutex);
        }
        
        for (auto& t : producerThreads) {
            t.join();
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        
        stopFlag.store(true);
        cv.notify_all();
        
        for (auto& t : consumerThreads) {
            t.join();
        }
        
        auto endTime = std::chrono::high_resolution_clock::now();
        double totalTime = std::chrono::duration<double>(endTime - startTime).count();
        
        metrics.totalTime = totalTime;
        metrics.throughput = (totalTime > 0) ? (metrics.messageCount / totalTime) : 0;
        metrics.errorCount = errorCount.load();
        metrics.retransmitCount = 0;  // shared_memory has no retransmission
        metrics.accuracy = (metrics.messageCount > 0) ?
            ((metrics.messageCount - metrics.errorCount) * 100.0 / metrics.messageCount) : 100.0;
        
        if (!latencies.empty()) {
            double sum = 0;
            for (double lat : latencies) {
                sum += lat;
            }
            metrics.avgLatency = sum / latencies.size();
            metrics.p95Latency = MetricsUtils::calculatePercentile(latencies, 95.0);
            metrics.p99Latency = MetricsUtils::calculatePercentile(latencies, 99.0);
        }
        
        metrics.success = (receivedCount.load() == metrics.messageCount);
        
        return metrics;
    }
};

#endif // SHARED_MEMORY_H
