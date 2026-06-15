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
#include "../utils/metrics.h"

class SharedMemoryIPC {
private:
    struct Message {
        std::vector<char> data;
        std::chrono::high_resolution_clock::time_point sendTime;
    };
    
    std::queue<Message> messageQueue;
    std::mutex queueMutex;
    std::condition_variable cv;
    std::atomic<int> receivedCount{0};
    int expectedMessages;
    
public:
    // Producer function
    void producer(int id, int messageCount, int messageSize, 
                  std::vector<double>* latencies, std::mutex* latenciesMutex) {
        // Create test data
        std::vector<char> data(messageSize);
        for (int i = 0; i < messageSize; i++) {
            data[i] = static_cast<char>(i % 256);
        }
        
        for (int i = 0; i < messageCount; i++) {
            auto startTime = std::chrono::high_resolution_clock::now();
            
            // Create message
            Message msg;
            msg.data = data;
            msg.sendTime = startTime;
            
            // Add to queue
            {
                std::lock_guard<std::mutex> lock(queueMutex);
                messageQueue.push(msg);
            }
            cv.notify_one();
            
            auto endTime = std::chrono::high_resolution_clock::now();
            double elapsed = std::chrono::duration<double, std::micro>(endTime - startTime).count();
            
            // Record latency
            {
                std::lock_guard<std::mutex> lock(*latenciesMutex);
                latencies->push_back(elapsed);
            }
        }
    }
    
    // Consumer function
    void consumer(int id, std::atomic<bool>* stopFlag) {
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
            
            // Process message (simulate work)
            volatile char sum = 0;
            for (char c : msg.data) {
                sum += c;
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
        metrics.success = false;
        
        expectedMessages = metrics.messageCount;
        
        std::vector<std::thread> producerThreads;
        std::vector<std::thread> consumerThreads;
        std::vector<double> latencies;
        std::mutex latenciesMutex;
        std::atomic<bool> stopFlag{false};
        
        auto startTime = std::chrono::high_resolution_clock::now();
        
        // Start consumers
        for (int i = 0; i < consumers; i++) {
            consumerThreads.emplace_back(&SharedMemoryIPC::consumer, this, i, &stopFlag);
        }
        
        // Start producers
        for (int i = 0; i < producers; i++) {
            producerThreads.emplace_back(&SharedMemoryIPC::producer, this, i, 
                                        messagesPerProducer, messageSize, 
                                        &latencies, &latenciesMutex);
        }
        
        // Wait for all producers to finish
        for (auto& t : producerThreads) {
            t.join();
        }
        
        // Wait a bit for consumers to process remaining messages
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        
        // Signal consumers to stop
        stopFlag.store(true);
        cv.notify_all();
        
        // Wait for all consumers to finish
        for (auto& t : consumerThreads) {
            t.join();
        }
        
        auto endTime = std::chrono::high_resolution_clock::now();
        double totalTime = std::chrono::duration<double>(endTime - startTime).count();
        
        // Calculate metrics
        metrics.totalTime = totalTime;
        metrics.throughput = (totalTime > 0) ? (metrics.messageCount / totalTime) : 0;
        
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
