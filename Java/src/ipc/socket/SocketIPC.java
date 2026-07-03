package ipc.socket;

import ipc.utils.PerformanceMetrics;
import ipc.utils.MetricsUtils;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

public class SocketIPC {
    
    private String network;
    private String address;
    private int messageSize;
    
    public SocketIPC(int messageSize) {
        this.messageSize = messageSize;
        
        String os = System.getProperty("os.name").toLowerCase();
        if (os.contains("win")) {
            this.network = "tcp";
            this.address = "127.0.0.1:0";
        } else {
            this.network = "tcp";
            this.address = "127.0.0.1:0";
        }
    }
    
    // 启动服务器监听
    public ServerSocket startServer() throws IOException {
        ServerSocket listener = new ServerSocket(0);
        this.address = "127.0.0.1:" + listener.getLocalPort();
        System.out.println("服务器监听地址: " + this.address);
        return listener;
    }
    
    // 生产者函数（使用长连接 + ACK/NACK重传）
    public static void producer(int id, String address, int port, int messageCount, 
                               int messageSize, List<Double> latencies, Object latenciesLock,
                               AtomicInteger errorCounter, AtomicInteger retransmitCounter) {
        byte[] data = new byte[messageSize];
        for (int i = 0; i < messageSize; i++) {
            data[i] = (byte) (i % 256);
        }
        
        Random rand = new Random();
        Socket conn = null;
        
        // 带重试的连接
        int maxRetries = 10;
        for (int retry = 0; retry < maxRetries; retry++) {
            try {
                conn = new Socket(address, port);
                break;
            } catch (IOException e) {
                try {
                    Thread.sleep((retry + 1) * 10);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return;
                }
            }
        }
        
        if (conn == null) {
            System.err.println("Producer " + id + " 无法建立连接");
            return;
        }
        
        try {
            OutputStream rawOut = conn.getOutputStream();
            InputStream rawIn = conn.getInputStream();
            
            for (int i = 0; i < messageCount; i++) {
                long start = System.nanoTime();
                
                // Compute checksum on original data
                int checksum = MetricsUtils.computeChecksum(data);
                
                // Wire format: [4B header = messageSize+4] [data] [4B checksum]
                int totalPayload = messageSize + 4;
                int wireLen = 4 + messageSize + 4;
                
                // Error injection: corrupt 1 byte in data with ERROR_RATE probability
                byte[] sendData = Arrays.copyOf(data, messageSize);
                if (rand.nextDouble() < MetricsUtils.ERROR_RATE) {
                    int corruptPos = rand.nextInt(messageSize);
                    sendData[corruptPos] ^= 0xFF;
                }
                
                // Build wire format buffer: [4B header][data][4B checksum]
                // Pre-encode header and checksum as big-endian
                byte[] wireBuf = new byte[wireLen];
                wireBuf[0] = (byte)(totalPayload >> 24);
                wireBuf[1] = (byte)(totalPayload >> 16);
                wireBuf[2] = (byte)(totalPayload >> 8);
                wireBuf[3] = (byte)(totalPayload);
                wireBuf[wireLen - 4] = (byte)(checksum >> 24);
                wireBuf[wireLen - 3] = (byte)(checksum >> 16);
                wireBuf[wireLen - 2] = (byte)(checksum >> 8);
                wireBuf[wireLen - 1] = (byte)(checksum);
                
                // Retransmission loop
                boolean delivered = false;
                int retransmits = 0;
                for (int attempt = 0; attempt <= MetricsUtils.MAX_RETRANSMIT && !delivered; attempt++) {
                    // Put data into wire buffer
                    if (attempt == 0) {
                        System.arraycopy(sendData, 0, wireBuf, 4, messageSize);
                    } else {
                        // Retransmit: send ORIGINAL (correct) data
                        System.arraycopy(data, 0, wireBuf, 4, messageSize);
                        retransmits++;
                    }
                    
                    // Send entire message at once
                    rawOut.write(wireBuf);
                    rawOut.flush();
                    
                    // Receive ACK/NACK (1 byte)
                    int ack = rawIn.read();
                    if (ack < 0) break;
                    
                    if (ack == 0x01) {
                        delivered = true;
                        break;
                    }
                    // If NACK (0x00), loop will retry
                }
                
                if (retransmits > 0) {
                    retransmitCounter.addAndGet(retransmits);
                }
                
                long elapsed = (System.nanoTime() - start) / 1000; // 转换为微秒
                
                synchronized (latenciesLock) {
                    latencies.add((double) elapsed);
                }
            }
        } catch (IOException e) {
            System.err.println("Producer " + id + " 发送失败: " + e.getMessage());
        } finally {
            try {
                if (conn != null) conn.close();
            } catch (IOException e) {
                // 忽略关闭异常
            }
        }
    }
    
    // 处理单个连接：接收消息，校验checksum，发送ACK/NACK
    public static void handleConnection(Socket conn, int messageSize, AtomicLong receivedCount,
                                       AtomicInteger errorCounter, int expectedMessages) {
        try {
            InputStream rawIn = conn.getInputStream();
            OutputStream rawOut = conn.getOutputStream();
            
            int successCount = 0;
            byte[] headerBuf = new byte[4];
            while (successCount < expectedMessages) {
                // Read 4-byte header: total payload size = messageSize + 4 (big-endian)
                int totalRead = 0;
                while (totalRead < 4) {
                    int read = rawIn.read(headerBuf, totalRead, 4 - totalRead);
                    if (read < 0) return;
                    totalRead += read;
                }
                int totalPayload = ((headerBuf[0] & 0xFF) << 24) |
                                   ((headerBuf[1] & 0xFF) << 16) |
                                   ((headerBuf[2] & 0xFF) << 8) |
                                   (headerBuf[3] & 0xFF);
                int dataLen = totalPayload - 4;
                
                // Read data + checksum as one buffer
                byte[] payload = new byte[totalPayload];
                totalRead = 0;
                while (totalRead < totalPayload) {
                    int read = rawIn.read(payload, totalRead, totalPayload - totalRead);
                    if (read < 0) return;
                    totalRead += read;
                }
                
                // Extract checksum (last 4 bytes, big-endian) and validate
                int receivedChecksum = ((payload[dataLen] & 0xFF) << 24) |
                                       ((payload[dataLen + 1] & 0xFF) << 16) |
                                       ((payload[dataLen + 2] & 0xFF) << 8) |
                                       (payload[dataLen + 3] & 0xFF);
                int computedChecksum = MetricsUtils.computeChecksum(payload, 0, dataLen);
                
                byte ack;
                if (computedChecksum == receivedChecksum) {
                    ack = (byte) 0x01; // ACK
                    receivedCount.incrementAndGet();
                    successCount++;
                } else {
                    ack = (byte) 0x00; // NACK
                    errorCounter.incrementAndGet();
                }
                
                // Send ACK/NACK
                rawOut.write(ack);
                rawOut.flush();
            }
        } catch (IOException e) {
            // 连接关闭或错误，退出
        } finally {
            try {
                conn.close();
            } catch (IOException e) {
                // 忽略关闭异常
            }
        }
    }
    
    // 运行Socket IPC测试
    public static PerformanceMetrics runTest(int producers, int consumers, 
                                            int messagesPerProducer, int messageSize) {
        System.out.println("\n=== Socket IPC测试 ===");
        System.out.printf("生产者: %d, 消费者: %d, 每个生产者消息数: %d, 消息大小: %d字节%n",
            producers, consumers, messagesPerProducer, messageSize);
        
        SocketIPC socketIPC = new SocketIPC(messageSize);
        int totalMessages = producers * messagesPerProducer;
        
        ServerSocket listener;
        try {
            listener = socketIPC.startServer();
        } catch (IOException e) {
            System.err.println("启动服务器失败: " + e.getMessage());
            PerformanceMetrics metrics = new PerformanceMetrics();
            metrics.success = false;
            return metrics;
        }
        
        ExecutorService executor = Executors.newCachedThreadPool();
        List<Double> latencies = Collections.synchronizedList(new ArrayList<>());
        AtomicLong receivedCount = new AtomicLong(0);
        AtomicInteger errorCounter = new AtomicInteger(0);
        AtomicInteger retransmitCounter = new AtomicInteger(0);
        
        long startTime = System.nanoTime();
        
        // 启动服务器接受连接
        CountDownLatch acceptDone = new CountDownLatch(1);
        CountDownLatch serverReady = new CountDownLatch(1);
        CountDownLatch producersDone = new CountDownLatch(producers);

        executor.submit(() -> {
            serverReady.countDown();
            
            for (int i = 0; i < producers; i++) {
                try {
                    Socket conn = listener.accept();
                    final int expectedMsgs = messagesPerProducer;
                    executor.submit(() -> handleConnection(conn, messageSize, receivedCount, errorCounter, expectedMsgs));
                } catch (IOException e) {
                    System.err.println("Accept错误 (已接受 " + i + "/" + producers + " 个连接): " + e.getMessage());
                    break;
                }
            }
            acceptDone.countDown();
        });

        // 等待服务器准备好
        try {
            serverReady.await();
            Thread.sleep(50);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // 解析地址获取端口
        String[] parts = socketIPC.address.split(":");
        int port = Integer.parseInt(parts[1]);

        // 启动生产者
        for (int i = 0; i < producers; i++) {
            final int producerId = i;
            executor.submit(() -> {
                try {
                    producer(producerId, "127.0.0.1", port,
                             messagesPerProducer, messageSize,
                             latencies, latencies,
                             errorCounter, retransmitCounter);
                } finally {
                    producersDone.countDown();
                }
            });
        }

        // 等待所有生产者完成
        try {
            producersDone.await(30, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // 短暂等待确保消费者处理完最后的消息
        try {
            Thread.sleep(100);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // 关闭listener
        try {
            listener.close();
        } catch (IOException e) {
            // 忽略
        }

        // 等待Accept线程结束
        try {
            acceptDone.await(30, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        
        long endTime = System.nanoTime();
        
        // 关闭executor
        executor.shutdown();
        try {
            executor.awaitTermination(30, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        
        double totalTime = (endTime - startTime) / 1_000_000_000.0;
        double throughput = totalMessages / totalTime;
        
        // 计算延迟统计
        double avgLatency = 0;
        if (!latencies.isEmpty()) {
            double sum = 0;
            for (double lat : latencies) {
                sum += lat;
            }
            avgLatency = sum / latencies.size();
        }
        
        double p95Latency = MetricsUtils.calculatePercentile(latencies, 95);
        double p99Latency = MetricsUtils.calculatePercentile(latencies, 99);
        
        PerformanceMetrics metrics = new PerformanceMetrics();
        metrics.ipcType = "socket";
        metrics.pattern = producers + "_" + consumers;
        metrics.producerCount = producers;
        metrics.consumerCount = consumers;
        metrics.messageCount = totalMessages;
        metrics.messageSize = messageSize;
        metrics.totalTime = totalTime;
        metrics.throughput = throughput;
        metrics.avgLatency = avgLatency;
        metrics.p95Latency = p95Latency;
        metrics.p99Latency = p99Latency;
        metrics.errorCount = errorCounter.get();
        metrics.retransmitCount = retransmitCounter.get();
        metrics.accuracy = (totalMessages > 0) ? 
            ((totalMessages - metrics.errorCount) * 100.0 / totalMessages) : 100.0;
        metrics.timestamp = MetricsUtils.getCurrentTimestamp();
        metrics.success = true;
        
        System.out.printf("总耗时: %.6f秒%n", totalTime);
        System.out.printf("吞吐量: %.2f 消息/秒%n", throughput);
        System.out.printf("平均延迟: %.2f 微秒%n", avgLatency);
        System.out.printf("P95延迟: %.2f 微秒%n", p95Latency);
        System.out.printf("P99延迟: %.2f 微秒%n", p99Latency);
        System.out.printf("错误数: %d, 重传数: %d%n", metrics.errorCount, metrics.retransmitCount);
        double errorRate = (totalMessages > 0) ? (metrics.errorCount * 100.0 / totalMessages) : 0.0;
        System.out.printf("数据错误率: %.2f%%%n%n", errorRate);
        
        return metrics;
    }
}
