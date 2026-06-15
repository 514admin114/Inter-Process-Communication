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
    
    // Producer function with long connection (same as SocketIPC)
    void producer(int id, int messageCount, int messageSize,
                  std::vector<double>* latencies, std::mutex* latenciesMutex) {
        std::vector<char> data(messageSize);
        for (int i = 0; i < messageSize; i++) {
            data[i] = static_cast<char>(i % 256);
        }
        
#ifdef _WIN32
        SOCKET conn = INVALID_SOCKET;
#else
        int conn = -1;
#endif
        
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
            break;
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
        
        for (int i = 0; i < messageCount; i++) {
            auto startTime = std::chrono::high_resolution_clock::now();
            
            uint32_t msgSize = static_cast<uint32_t>(messageSize);
            uint32_t netSize = htonl(msgSize);
            
#ifdef _WIN32
            if (send(conn, reinterpret_cast<const char*>(&netSize), 4, 0) == SOCKET_ERROR) {
                break;
            }
            
            int totalSent = 0;
            while (totalSent < messageSize) {
                int sent = send(conn, &data[totalSent], messageSize - totalSent, 0);
                if (sent == SOCKET_ERROR) {
                    break;
                }
                totalSent += sent;
            }
#else
            if (send(conn, &netSize, 4, 0) < 0) {
                break;
            }
            
            int totalSent = 0;
            while (totalSent < messageSize) {
                int sent = send(conn, &data[totalSent], messageSize - totalSent, 0);
                if (sent < 0) {
                    break;
                }
                totalSent += sent;
            }
#endif
            
            auto endTime = std::chrono::high_resolution_clock::now();
            double elapsed = std::chrono::duration<double, std::micro>(endTime - startTime).count();
            
            {
                std::lock_guard<std::mutex> lock(*latenciesMutex);
                latencies->push_back(elapsed);
            }
        }
        
#ifdef _WIN32
        closesocket(conn);
#else
        close(conn);
#endif
    }
    
    // Handle connection (same as SocketIPC)
    void handleConnection(
#ifdef _WIN32
        SOCKET conn
#else
        int conn
#endif
        , int messageSize, std::atomic<int64_t>* receivedCount, int expectedMessages) {
        
        for (int i = 0; i < expectedMessages; i++) {
            uint32_t netSize;
#ifdef _WIN32
            int bytesRead = recv(conn, reinterpret_cast<char*>(&netSize), 4, 0);
            if (bytesRead <= 0) {
                break;
            }
#else
            ssize_t bytesRead = recv(conn, &netSize, 4, 0);
            if (bytesRead <= 0) {
                break;
            }
#endif
            
            uint32_t msgSize = ntohl(netSize);
            
            std::vector<char> buffer(msgSize);
            int totalRead = 0;
            while (totalRead < msgSize) {
#ifdef _WIN32
                int read = recv(conn, &buffer[totalRead], msgSize - totalRead, 0);
                if (read <= 0) {
                    break;
                }
#else
                ssize_t read = recv(conn, &buffer[totalRead], msgSize - totalRead, 0);
                if (read <= 0) {
                    break;
                }
#endif
                totalRead += read;
            }
            
            receivedCount->fetch_add(1);
        }
        
#ifdef _WIN32
        closesocket(conn);
#else
        close(conn);
#endif
    }
    
    // Run test (same logic as SocketIPC)
    PerformanceMetrics runTest(int producers, int consumers, int messagesPerProducer, int messageSize) {
        PerformanceMetrics metrics;
        metrics.ipcType = "tcp";
        metrics.pattern = std::to_string(producers) + "_" + std::to_string(consumers);
        metrics.producerCount = producers;
        metrics.consumerCount = consumers;
        metrics.messageCount = producers * messagesPerProducer;
        metrics.messageSize = messageSize;
        metrics.timestamp = MetricsUtils::getCurrentTimestamp();
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
        
        auto startTime = std::chrono::high_resolution_clock::now();
        
        std::atomic<bool> acceptDone{false};
        std::thread acceptThread([this, producers, messagesPerProducer, messageSize, &receivedCount, &acceptDone, &consumerThreads]() {
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
                                            messageSize, &receivedCount, messagesPerProducer);
            }
            acceptDone.store(true);
        });
        
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
        
        for (int i = 0; i < producers; i++) {
            producerThreads.emplace_back(&TcpIPC::producer, this, i,
                                        messagesPerProducer, messageSize,
                                        &latencies, &latenciesMutex);
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
