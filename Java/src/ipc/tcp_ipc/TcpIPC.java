package ipc.tcp_ipc;

import ipc.utils.PerformanceMetrics;
import ipc.utils.MetricsUtils;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicLong;

public class TcpIPC {
    
    private String address;
    private int port;
    private int messageSize;
    
    public TcpIPC(int messageSize) {
        this.messageSize = messageSize;
        this.address = "127.0.0.1";
        this.port = 0; // 端口0表示自动分配
    }
    
    // 启动TCP服务器
    public ServerSocket startServer() throws IOException {
        ServerSocket listener = new ServerSocket(0); // 端口0表示自动分配
        this.port = listener.getLocalPort();
        this.address = "127.0.0.1:" + this.port;
        System.out.println("TCP服务器监听地址: " + this.address);
        return listener;
    }
    
    // 生产者函数（使用长连接）
    public static void producer(int id, String address, int port, int messageCount, 
                               int messageSize, List<Double> latencies, Object latenciesLock) {
        byte[] data = new byte[messageSize];
        for (int i = 0; i < messageSize; i++) {
            data[i] = (byte) (i % 256);
        }
        
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
        
        try (DataOutputStream out = new DataOutputStream(conn.getOutputStream())) {
            // 复用同一个连接发送所有消息
            for (int i = 0; i < messageCount; i++) {
                long start = System.nanoTime();
                
                // 发送消息长度（4字节，大端序）
                out.writeInt(messageSize);
                
                // 发送数据
                out.write(data, 0, messageSize);
                out.flush();
                
                long elapsed = (System.nanoTime() - start) / 1000; // 转换为微秒
                
                synchronized (latenciesLock) {
                    latencies.add((double) elapsed);
                }
            }
        } catch (IOException e) {
            System.err.println("Producer " + id + " 发送失败: " + e.getMessage());
        } finally {
            try {
                conn.close();
            } catch (IOException e) {
                // 忽略关闭异常
            }
        }
    }
    
    // 处理单个连接（支持多条消息）
    public static void handleConnection(Socket conn, int messageSize, AtomicLong receivedCount, 
                                       int expectedMessages) {
        try (DataInputStream in = new DataInputStream(conn.getInputStream())) {
            // 循环接收多条消息，直到达到预期数量或连接关闭
            for (int i = 0; i < expectedMessages; i++) {
                // 读取消息长度
                int msgSize = in.readInt();
                
                // 读取数据
                byte[] data = new byte[msgSize];
                int totalRead = 0;
                while (totalRead < msgSize) {
                    int read = in.read(data, totalRead, msgSize - totalRead);
                    if (read == -1) {
                        return;
                    }
                    totalRead += read;
                }
                
                // 原子增加接收计数
                long count = receivedCount.incrementAndGet();
                
                if (count % 1000 == 0) {
                    System.out.println("已接收 " + count + " 条消息");
                }
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
    
    // 运行TCP IPC测试
    public static PerformanceMetrics runTest(int producers, int consumers, 
                                            int messagesPerProducer, int messageSize) {
        System.out.println("\n=== TCP Socket测试 ===");
        System.out.printf("生产者: %d, 消费者: %d, 每个生产者消息数: %d, 消息大小: %d字节%n",
            producers, consumers, messagesPerProducer, messageSize);
        
        TcpIPC tcpIPC = new TcpIPC(messageSize);
        int totalMessages = producers * messagesPerProducer;
        
        ServerSocket listener;
        try {
            listener = tcpIPC.startServer();
        } catch (IOException e) {
            System.err.println("启动TCP服务器失败: " + e.getMessage());
            PerformanceMetrics metrics = new PerformanceMetrics();
            metrics.success = false;
            return metrics;
        }
        
        ExecutorService executor = Executors.newCachedThreadPool();
        List<Double> latencies = Collections.synchronizedList(new ArrayList<>());
        AtomicLong receivedCount = new AtomicLong(0);
        
        long startTime = System.nanoTime();
        
        // 启动服务器接受连接（在单独的线程中）
        CountDownLatch acceptDone = new CountDownLatch(1);
        CountDownLatch serverReady = new CountDownLatch(1);
        CountDownLatch producersDone = new CountDownLatch(producers);

        executor.submit(() -> {
            serverReady.countDown(); // 立即发出就绪信号

            // 接受producers个连接（每个Producer一个连接）
            for (int i = 0; i < producers; i++) {
                try {
                    Socket conn = listener.accept();
                    final int expectedMsgs = messagesPerProducer;
                    executor.submit(() -> handleConnection(conn, messageSize, receivedCount, expectedMsgs));
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
            Thread.sleep(50); // 短暂等待确保 accept 循环已进入阻塞状态
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // 启动生产者，每个生产者完成时调用 producersDone.countDown()
        for (int i = 0; i < producers; i++) {
            final int producerId = i;
            final int port = tcpIPC.port;
            executor.submit(() -> {
                try {
                    producer(producerId, "127.0.0.1", port,
                             messagesPerProducer, messageSize,
                             latencies, latencies);
                } finally {
                    producersDone.countDown();
                }
            });
        }

        // 精确等待所有生产者完成，而非盲等
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

        // 关闭listener，停止接受新连接
        try {
            listener.close();
        } catch (IOException e) {
            // 忽略关闭异常
        }

        // 等待Accept线程结束
        try {
            acceptDone.await(30, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        // 关闭executor
        executor.shutdown();
        try {
            executor.awaitTermination(30, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        
        long endTime = System.nanoTime();
        
        double totalTime = (endTime - startTime) / 1_000_000_000.0; // 转换为秒
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
        metrics.ipcType = "tcp";
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
        metrics.timestamp = MetricsUtils.getCurrentTimestamp();
        metrics.success = true;
        
        System.out.printf("总耗时: %.6f秒%n", totalTime);
        System.out.printf("吞吐量: %.2f 消息/秒%n", throughput);
        System.out.printf("平均延迟: %.2f 微秒%n", avgLatency);
        System.out.printf("P95延迟: %.2f 微秒%n", p95Latency);
        System.out.printf("P99延迟: %.2f 微秒%n%n", p99Latency);
        
        return metrics;
    }
}
