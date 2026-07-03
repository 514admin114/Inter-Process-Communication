package ipc.shared_memory;

import ipc.utils.PerformanceMetrics;
import ipc.utils.MetricsUtils;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

public class SharedMemory {
    
    // 消息队列，用于生产者和消费者之间的通信
    static class MessageQueue {
        private final BlockingQueue<byte[]> messages;
        private volatile boolean closed = false;
        
        public MessageQueue(int bufferSize) {
            this.messages = new ArrayBlockingQueue<>(bufferSize);
        }
        
        public void send(byte[] data) throws InterruptedException {
            if (closed) {
                throw new IllegalStateException("队列已关闭");
            }
            messages.put(data);
        }
        
        public byte[] receive() throws InterruptedException {
            if (closed && messages.isEmpty()) {
                throw new IllegalStateException("队列已关闭");
            }
            return messages.take();
        }
        
        public void close() {
            closed = true;
        }
    }
    
    // 缓冲区对象池，用于复用字节数组，减少GC压力
    static class BufferPool {
        private final ConcurrentLinkedQueue<byte[]> pool;
        private final int bufferSize;
        private final int maxSize;
        
        public BufferPool(int bufferSize, int maxSize) {
            this.bufferSize = bufferSize;
            this.maxSize = maxSize;
            this.pool = new ConcurrentLinkedQueue<>();
            
            // 预分配一些缓冲区
            for (int i = 0; i < Math.min(100, maxSize); i++) {
                pool.add(new byte[bufferSize]);
            }
        }
        
        public byte[] acquire() {
            byte[] buffer = pool.poll();
            if (buffer == null) {
                buffer = new byte[bufferSize];
            }
            return buffer;
        }
        
        public void release(byte[] buffer) {
            if (buffer != null && buffer.length == bufferSize && pool.size() < maxSize) {
                pool.offer(buffer);
            }
        }
    }
    
    private MessageQueue queue;
    private BufferPool bufferPool;
    private int messageSize;
    private int totalMsgSize;  // messageSize + 4 (checksum)
    
    public SharedMemory(int messageSize) {
        int queueSize = 1000;
        this.queue = new MessageQueue(queueSize);
        this.messageSize = messageSize;
        this.totalMsgSize = messageSize + 4;
        // 对象池最大容量为2000个缓冲区
        this.bufferPool = new BufferPool(totalMsgSize, 2000);
    }
    
    // 写入数据到共享内存 (data should be totalMsgSize bytes)
    public void write(byte[] data) throws InterruptedException {
        byte[] buf = bufferPool.acquire();
        System.arraycopy(data, 0, buf, 0, Math.min(data.length, buf.length));
        queue.send(buf);
    }
    
    // 从共享内存读取数据
    public byte[] read() throws InterruptedException {
        byte[] data = queue.receive();
        bufferPool.release(data);
        byte[] result = Arrays.copyOf(data, totalMsgSize);
        return result;
    }
    
    // 生产者函数
    public static void producer(int id, SharedMemory sm, int messageCount, int messageSize,
                               ConcurrentLinkedQueue<Double> latencies,
                               AtomicInteger errorCounter, AtomicInteger retransmitCounter) {
        byte[] data = new byte[messageSize];
        for (int i = 0; i < messageSize; i++) {
            data[i] = (byte) (i % 256);
        }
        
        Random rand = new Random();
        
        for (int i = 0; i < messageCount; i++) {
            long start = System.nanoTime();
            
            // Compute checksum on original data
            int checksum = MetricsUtils.computeChecksum(data);
            
            // Build message: data + 4-byte checksum (big-endian)
            byte[] msgData = new byte[messageSize + 4];
            System.arraycopy(data, 0, msgData, 0, messageSize);
            msgData[messageSize]     = (byte) (checksum >>> 24);
            msgData[messageSize + 1] = (byte) (checksum >>> 16);
            msgData[messageSize + 2] = (byte) (checksum >>> 8);
            msgData[messageSize + 3] = (byte) (checksum);
            
            // Error injection: with ERROR_RATE probability, corrupt 1 byte in data portion
            if (rand.nextDouble() < MetricsUtils.ERROR_RATE) {
                int corruptPos = rand.nextInt(messageSize);
                msgData[corruptPos] ^= 0xFF;
            }
            
            try {
                sm.write(msgData);
            } catch (InterruptedException e) {
                System.err.println("Producer " + id + " write failed: " + e.getMessage());
                Thread.currentThread().interrupt();
                continue;
            }
            
            long elapsed = (System.nanoTime() - start) / 1000; // 转换为微秒
            latencies.add((double) elapsed);
        }
    }
    
    // 消费者函数 - validates checksum
    public static void consumer(int id, SharedMemory sm, int messageCount, int messageSize,
                               AtomicInteger errorCounter) {
        for (int i = 0; i < messageCount; i++) {
            byte[] msgData;
            try {
                msgData = sm.read();
            } catch (InterruptedException e) {
                System.err.println("Consumer " + id + " read failed: " + e.getMessage());
                Thread.currentThread().interrupt();
                break;
            }
            
            // Validate checksum: last 4 bytes
            int receivedChecksum = ((msgData[messageSize] & 0xFF) << 24) |
                                   ((msgData[messageSize + 1] & 0xFF) << 16) |
                                   ((msgData[messageSize + 2] & 0xFF) << 8) |
                                   (msgData[messageSize + 3] & 0xFF);
            int computedChecksum = MetricsUtils.computeChecksum(msgData, 0, messageSize);
            
            if (computedChecksum != receivedChecksum) {
                errorCounter.incrementAndGet();
            }
        }
    }
    
    // 运行共享内存IPC测试
    public static PerformanceMetrics runTest(int producers, int consumers, 
                                            int messagesPerProducer, int messageSize) {
        System.out.println("\n=== Shared Memory Test ===");
        System.out.printf("Producers: %d, Consumers: %d, Messages per Producer: %d, Message Size: %d bytes%n",
            producers, consumers, messagesPerProducer, messageSize);
        
        SharedMemory sm = new SharedMemory(messageSize);
        int totalMessages = producers * messagesPerProducer;
        int messagesPerConsumer = totalMessages / consumers;
        
        ConcurrentLinkedQueue<Double> latencies = new ConcurrentLinkedQueue<>();
        AtomicInteger errorCounter = new AtomicInteger(0);
        AtomicInteger retransmitCounter = new AtomicInteger(0);
        ExecutorService executor = Executors.newFixedThreadPool(producers + consumers);
        
        long startTime = System.nanoTime();
        
        // 启动消费者
        for (int i = 0; i < consumers; i++) {
            final int consumerId = i;
            executor.submit(() -> consumer(consumerId, sm, messagesPerConsumer, messageSize, errorCounter));
        }
        
        // 短暂等待让消费者准备好
        try {
            Thread.sleep(10);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        
        // 启动生产者
        for (int i = 0; i < producers; i++) {
            final int producerId = i;
            executor.submit(() -> producer(producerId, sm, messagesPerProducer, messageSize, 
                                          latencies, errorCounter, retransmitCounter));
        }
        
        // 关闭executor并等待所有任务完成
        executor.shutdown();
        try {
            executor.awaitTermination(60, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        
        long endTime = System.nanoTime();
        
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
        
        List<Double> latencyList = new ArrayList<>(latencies);
        double p95Latency = MetricsUtils.calculatePercentile(latencyList, 95);
        double p99Latency = MetricsUtils.calculatePercentile(latencyList, 99);
        
        PerformanceMetrics metrics = new PerformanceMetrics();
        metrics.ipcType = "shared_memory";
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
        
        System.out.printf("Total Time: %.6f seconds%n", totalTime);
        System.out.printf("Throughput: %.2f messages/sec%n", throughput);
        System.out.printf("Average Latency: %.2f microseconds%n", avgLatency);
        System.out.printf("P95 Latency: %.2f microseconds%n", p95Latency);
        System.out.printf("P99 Latency: %.2f microseconds%n", p99Latency);
        System.out.printf("Error Count: %d, Retransmit Count: %d%n", metrics.errorCount, metrics.retransmitCount);
        double errorRate = (totalMessages > 0) ? (metrics.errorCount * 100.0 / totalMessages) : 0.0;
        System.out.printf("Error Rate: %.2f%%%n%n", errorRate);
        
        return metrics;
    }
}
