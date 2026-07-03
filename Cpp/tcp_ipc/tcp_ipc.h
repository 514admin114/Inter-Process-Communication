#ifndef TCP_IPC_H
#define TCP_IPC_H

#include <iostream>
#include <vector>
#include <thread>
#include <mutex>
#include <atomic>
#include <chrono>
#include <string>
#include <cstring>
#include <cstdlib>
#include <random>

#ifdef _WIN32
    #include <winsock2.h>
    #include <ws2tcpip.h>
    #pragma comment(lib, "ws2_32.lib")
#else
    #include <sys/socket.h>
    #include <netinet/in.h>
    #include <arpa/inet.h>
    #include <unistd.h>
#endif

#include "../utils/metrics.h"

class TcpIPC {
private:
    std::string address;
    int port;
    
#ifdef _WIN32
    SOCKET serverSocket;
#else
    int serverSocket;
#endif
    
public:
    TcpIPC() : port(0) {
#ifdef _WIN32
        WSADATA wsaData;
        WSAStartup(MAKEWORD(2, 2), &wsaData);
#endif
    }
    
    ~TcpIPC() {
#ifdef _WIN32
        if (serverSocket != INVALID_SOCKET) {
            closesocket(serverSocket);
        }
        WSACleanup();
#else
        if (serverSocket >= 0) {
            close(serverSocket);
        }
#endif
    }
    
    // Start TCP server
    bool startServer() {
#ifdef _WIN32
        serverSocket = socket(AF_INET, SOCK_STREAM, 0);
        if (serverSocket == INVALID_SOCKET) {
            return false;
        }
        
        sockaddr_in serverAddr;
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_addr.s_addr = inet_addr("127.0.0.1");
        serverAddr.sin_port = htons(0); // Let OS assign port
        
        if (bind(serverSocket, (sockaddr*)&serverAddr, sizeof(serverAddr)) == SOCKET_ERROR) {
            return false;
        }
        
        int addrLen = sizeof(serverAddr);
        if (getsockname(serverSocket, (sockaddr*)&serverAddr, &addrLen) == SOCKET_ERROR) {
            return false;
        }
        
        port = ntohs(serverAddr.sin_port);
        address = "127.0.0.1:" + std::to_string(port);
#else
        serverSocket = socket(AF_INET, SOCK_STREAM, 0);
        if (serverSocket < 0) {
            return false;
        }
        
        int opt = 1;
        setsockopt(serverSocket, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
        
        sockaddr_in serverAddr;
        memset(&serverAddr, 0, sizeof(serverAddr));
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        serverAddr.sin_port = htons(0);
        
        if (bind(serverSocket, (sockaddr*)&serverAddr, sizeof(serverAddr)) < 0) {
            return false;
        }
        
        socklen_t addrLen = sizeof(serverAddr);
        if (getsockname(serverSocket, (sockaddr*)&serverAddr, &addrLen) < 0) {
            return false;
        }
        
        port = ntohs(serverAddr.sin_port);
        address = "127.0.0.1:" + std::to_string(port);
#endif
        
        listen(serverSocket, 100);
        return true;
    }

    // Helper: send exact N bytes (handles partial sends)
    bool sendAll(
#ifdef _WIN32
        SOCKET conn, const char* data, int len
#else
        int conn, const void* data, int len
#endif
    ) {
        int totalSent = 0;
        while (totalSent < len) {
#ifdef _WIN32
            int sent = send(conn, data + totalSent, len - totalSent, 0);
            if (sent == SOCKET_ERROR) return false;
#else
            ssize_t sent = send(conn, static_cast<const char*>(data) + totalSent, len - totalSent, 0);
            if (sent < 0) return false;
#endif
            totalSent += sent;
        }
        return true;
    }

    // Helper: receive exact N bytes
    bool recvAll(
#ifdef _WIN32
        SOCKET conn, char* buffer, int len
#else
        int conn, void* buffer, int len
#endif
    ) {
        int totalRead = 0;
        while (totalRead < len) {
#ifdef _WIN32
            int read = recv(conn, buffer + totalRead, len - totalRead, 0);
            if (read <= 0) return false;
#else
            ssize_t read = recv(conn, static_cast<char*>(buffer) + totalRead, len - totalRead, 0);
            if (read <= 0) return false;
#endif
            totalRead += read;
        }
        return true;
    }
    
    // Producer function with long connection, ACK/NACK retransmission
    void producer(int id, int messageCount, int messageSize,
                  std::vector<double>* latencies, std::mutex* latenciesMutex,
                  std::atomic<int>* errorCounter, std::atomic<int>* retransmitCounter) {
        // Create test data (messageSize bytes of payload)
        std::vector<char> data(messageSize);
        for (int i = 0; i < messageSize; i++) {
            data[i] = static_cast<char>(i % 256);
        }
        
#ifdef _WIN32
        SOCKET conn = INVALID_SOCKET;
#else
        int conn = -1;
#endif
        
        // Establish long connection with retry
        int maxRetries = 10;
        for (int retry = 0; retry < maxRetries; retry++) {
#ifdef _WIN32
            conn = socket(AF_INET, SOCK_STREAM, 0);
            if (conn == INVALID_SOCKET) {
                std::this_thread::sleep_for(std::chrono::milliseconds((retry + 1) * 10));
                continue;
            }
            
            sockaddr_in serverAddr;
            serverAddr.sin_family = AF_INET;
            serverAddr.sin_addr.s_addr = inet_addr("127.0.0.1");
            serverAddr.sin_port = htons(port);
            
            if (connect(conn, (sockaddr*)&serverAddr, sizeof(serverAddr)) == SOCKET_ERROR) {
                closesocket(conn);
                conn = INVALID_SOCKET;
                std::this_thread::sleep_for(std::chrono::milliseconds((retry + 1) * 10));
                continue;
            }
#else
            conn = socket(AF_INET, SOCK_STREAM, 0);
            if (conn < 0) {
                std::this_thread::sleep_for(std::chrono::milliseconds((retry + 1) * 10));
                continue;
            }
            
            sockaddr_in serverAddr;
            memset(&serverAddr, 0, sizeof(serverAddr));
            serverAddr.sin_family = AF_INET;
            serverAddr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
            serverAddr.sin_port = htons(port);
            
            if (connect(conn, (sockaddr*)&serverAddr, sizeof(serverAddr)) < 0) {
                close(conn);
                conn = -1;
                std::this_thread::sleep_for(std::chrono::milliseconds((retry + 1) * 10));
                continue;
            }
#endif
            break; // Connection successful
        }
        
        if (
#ifdef _WIN32
            conn == INVALID_SOCKET
#else
            conn < 0
#endif
        ) {
            std::cerr << "Producer " << id << " failed to establish connection" << std::endl;
            return;
        }
        
        // Send all messages using the same connection
        // Thread-safe random number generator (thread-local)
        thread_local std::mt19937 rng(std::random_device{}());
        std::uniform_real_distribution<double> errorDist(0.0, 1.0);
        std::uniform_int_distribution<int> posDist(0, messageSize - 1);
        
        for (int i = 0; i < messageCount; i++) {
            auto startTime = std::chrono::high_resolution_clock::now();
            
            // Compute checksum on original data
            uint32_t checksum = computeChecksum(data.data(), messageSize);
            uint32_t netChecksum = htonl(checksum);
            
            // Wire format: [4B header = messageSize+4] [data] [4B checksum]
            uint32_t totalPayload = static_cast<uint32_t>(messageSize + 4);
            uint32_t netHeader = htonl(totalPayload);
            
            // Error injection: with ERROR_RATE probability, corrupt 1 byte in data
            std::vector<char> sendData = data;  // copy for potential corruption
            if (errorDist(rng) < ERROR_RATE) {
                int corruptPos = posDist(rng);
                sendData[corruptPos] = static_cast<char>(sendData[corruptPos] ^ 0xFF);
            }
            
            // Retransmission loop
            bool delivered = false;
            int retransmits = 0;
            for (int attempt = 0; attempt <= MAX_RETRANSMIT && !delivered; attempt++) {
                if (attempt > 0) {
                    // Retransmit: send ORIGINAL (correct) data
                    sendData = data;
                    retransmits++;
                }
                
                // Send header
                if (!sendAll(conn, reinterpret_cast<const char*>(&netHeader), 4)) {
                    break;
                }
                // Send data
                if (!sendAll(conn, sendData.data(), messageSize)) {
                    break;
                }
                // Send checksum
                if (!sendAll(conn, reinterpret_cast<const char*>(&netChecksum), 4)) {
                    break;
                }
                
                // Receive ACK/NACK (1 byte)
                uint8_t ack;
#ifdef _WIN32
                int ackRead = recv(conn, reinterpret_cast<char*>(&ack), 1, 0);
                if (ackRead <= 0) break;
#else
                ssize_t ackRead = recv(conn, &ack, 1, 0);
                if (ackRead <= 0) break;
#endif
                
                if (ack == 0x01) {
                    delivered = true;
                }
            }
            
            if (retransmits > 0) {
                retransmitCounter->fetch_add(retransmits);
            }
            
            auto endTime = std::chrono::high_resolution_clock::now();
            double elapsed = std::chrono::duration<double, std::micro>(endTime - startTime).count();
            
            {
                std::lock_guard<std::mutex> lock(*latenciesMutex);
                latencies->push_back(elapsed);
            }
        }
        
        // Close connection
#ifdef _WIN32
        closesocket(conn);
#else
        close(conn);
#endif
    }
    
    // Handle connection: receive messages, validate checksum, send ACK/NACK
    void handleConnection(
#ifdef _WIN32
        SOCKET conn
#else
        int conn
#endif
        , int messageSize, std::atomic<int64_t>* receivedCount,
          std::atomic<int>* errorCounter, int expectedMessages) {
        
        int successCount = 0;
        while (successCount < expectedMessages) {
            // Read 4-byte header: total payload size = messageSize + 4
            uint32_t netHeader;
            if (!recvAll(conn, reinterpret_cast<char*>(&netHeader), 4)) {
                break;
            }
            uint32_t totalPayload = ntohl(netHeader);
            int dataLen = static_cast<int>(totalPayload) - 4;
            
            // Read data + checksum as one buffer
            std::vector<char> buffer(totalPayload);
            if (!recvAll(conn, buffer.data(), totalPayload)) {
                break;
            }
            
            // Extract checksum (last 4 bytes) and validate
            uint32_t receivedChecksum;
            std::memcpy(&receivedChecksum, buffer.data() + dataLen, 4);
            receivedChecksum = ntohl(receivedChecksum);
            
            uint32_t computedChecksum = computeChecksum(buffer.data(), dataLen);
            
            uint8_t ack;
            if (computedChecksum == receivedChecksum) {
                ack = 0x01; // ACK
                receivedCount->fetch_add(1);
                successCount++;
            } else {
                ack = 0x00; // NACK
                errorCounter->fetch_add(1);
            }
            
            // Send ACK/NACK
#ifdef _WIN32
            send(conn, reinterpret_cast<const char*>(&ack), 1, 0);
#else
            send(conn, &ack, 1, 0);
#endif
        }
        
        // Close connection
#ifdef _WIN32
        closesocket(conn);
#else
        close(conn);
#endif
    }
    
    // Run test
    PerformanceMetrics runTest(int producers, int consumers, int messagesPerProducer, int messageSize) {
        PerformanceMetrics metrics;
        metrics.ipcType = "tcp";
        metrics.pattern = std::to_string(producers) + "_" + std::to_string(consumers);
        metrics.producerCount = producers;
        metrics.consumerCount = consumers;
        metrics.messageCount = producers * messagesPerProducer;
        metrics.messageSize = messageSize;
        metrics.timestamp = MetricsUtils::getCurrentTimestamp();
        metrics.errorCount = 0;
        metrics.retransmitCount = 0;
        metrics.success = false;
        
        if (!startServer()) {
            std::cerr << "Failed to start TCP server" << std::endl;
            return metrics;
        }
        
        std::cout << "TCP Server listening at: " << address << std::endl;
        
        std::vector<std::thread> producerThreads;
        std::vector<std::thread> consumerThreads;
        std::vector<double> latencies;
        std::mutex latenciesMutex;
        std::atomic<int64_t> receivedCount{0};
        std::atomic<int> errorCounter{0};
        std::atomic<int> retransmitCounter{0};
        
        auto startTime = std::chrono::high_resolution_clock::now();
        
        std::atomic<bool> acceptDone{false};
        std::thread acceptThread([this, producers, messagesPerProducer, messageSize,
                                   &receivedCount, &errorCounter, &acceptDone, &consumerThreads]() {
            for (int i = 0; i < producers; i++) {
#ifdef _WIN32
                SOCKET conn = accept(serverSocket, nullptr, nullptr);
                if (conn == INVALID_SOCKET) {
                    break;
                }
#else
                int conn = accept(serverSocket, nullptr, nullptr);
                if (conn < 0) {
                    break;
                }
#endif
                consumerThreads.emplace_back(&TcpIPC::handleConnection, this, conn, 
                                            messageSize, &receivedCount, &errorCounter,
                                            messagesPerProducer);
            }
            acceptDone.store(true);
        });
        
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
        
        for (int i = 0; i < producers; i++) {
            producerThreads.emplace_back(&TcpIPC::producer, this, i,
                                        messagesPerProducer, messageSize,
                                        &latencies, &latenciesMutex,
                                        &errorCounter, &retransmitCounter);
        }
        
        for (auto& t : producerThreads) {
            t.join();
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        
#ifdef _WIN32
        closesocket(serverSocket);
        serverSocket = INVALID_SOCKET;
#else
        close(serverSocket);
        serverSocket = -1;
#endif
        
        acceptThread.join();
        
        for (auto& t : consumerThreads) {
            t.join();
        }
        
        auto endTime = std::chrono::high_resolution_clock::now();
        double totalTime = std::chrono::duration<double>(endTime - startTime).count();
        
        metrics.totalTime = totalTime;
        metrics.throughput = (totalTime > 0) ? (metrics.messageCount / totalTime) : 0;
        metrics.errorCount = errorCounter.load();
        metrics.retransmitCount = retransmitCounter.load();
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

#endif // TCP_IPC_H
