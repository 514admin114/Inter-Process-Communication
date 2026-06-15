package ipc.shared_memory;

import ipc.utils.PerformanceMetrics;
import ipc.utils.MetricsUtils;

import java.util.*;
import java.util.concurrent.*;

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
    
    public SharedMemory(int messageSize) {
        // 设置缓冲区大小为1000，足够容纳突发消息
        int queueSize = 1000;
        this.queue = new MessageQueue(queueSize);
        this.messageSize = messageSize;
        // 对象池最大容量为2000个缓冲区
        this.bufferPool = new BufferPool(messageSize, 2000);
    }
    
    // 写入数据到共享内存
    public void write(byte[] data) throws InterruptedException {
        // 从对象池获取缓冲区
        byte[] buf = bufferPool.acquire();
        System.arraycopy(data, 0, buf, 0, Math.min(data.length, buf.length));
        queue.send(buf);
    }
    
    // 从共享内存读取数据
    public byte[] read() throws InterruptedException {
        byte[] data = queue.receive();
        // 将缓冲区返回到对象池供后续使用
        bufferPool.release(data);
        // 返回数据副本（避免外部修改影响池中的缓冲区）
        byte[] result = Arrays.copyOf(data, data.length);
        return result;
    }
    
    // 生产者函数
    public static void producer(int id, SharedMemory sm, int messageCount, int messageSize,
                               ConcurrentLinkedQueue<Double> latencies) {
        byte[] data = new byte[messageSize];
        for (int i = 0; i < messageSize; i++) {
            data[i] = (byte) (i % 256);
        }
        
        for (int i = 0; i < messageCount; i++) {
            long start = System.nanoTime();
            
            try {
                sm.write(data);
            } catch (InterruptedException e) {
                System.err.println("Producer " + id + " 写入失败: " + e.getMessage());
                Thread.currentThread().interrupt();
                continue;
            }
            
            long elapsed = (System.nanoTime() - start) / 1000; // 转换为微秒
            
            // 使用无锁的并发集合，避免锁竞争
            latencies.add((double) elapsed);
        }
    }
    
    // 消费者函数
    public static void consumer(int id, SharedMemory sm, int messageCount) {
        for (int i = 0; i < messageCount; i++) {
            try {
                sm.read();
            } catch (InterruptedException e) {
                System.err.println("Consumer " + id + " 读取失败: " + e.getMessage());
                Thread.currentThread().interrupt();
                break;
            }
        }
    }
    
    // 运行共享内存IPC测试
    public static PerformanceMetrics runTest(int producers, int consumers, 
                                            int messagesPerProducer, int messageSize) {
        System.out.println("\n=== 共享内存测试 ===");
        System.out.printf("生产者: %d, 消费者: %d, 每个生产者消息数: %d, 消息大小: %d字节%n",
            producers, consumers, messagesPerProducer, messageSize);
        
        SharedMemory sm = new SharedMemory(messageSize);
        int totalMessages = producers * messagesPerProducer;
        int messagesPerConsumer = totalMessages / consumers;
        
        // 使用线程安全的并发队列，无需额外同步
        ConcurrentLinkedQueue<Double> latencies = new ConcurrentLinkedQueue<>();
        ExecutorService executor = Executors.newFixedThreadPool(producers + consumers);
        
        long startTime = System.nanoTime();
        
        // 启动消费者
        for (int i = 0; i < consumers; i++) {
            final int consumerId = i;
            executor.submit(() -> consumer(consumerId, sm, messagesPerConsumer));
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
                                          latencies));
        }
        
        // 关闭executor并等待所有任务完成
        executor.shutdown();
        try {
            executor.awaitTermination(60, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        
        long endTime = System.nanoTime();
        
        double totalTime = (endTime - startTime) / 1_000_000_000.0; // 转换为秒
        double throughput = totalMessages / totalTime;
        
        // 计算延迟统计
        double avgLatency = 0;
        int latencyCount = latencies.size();
        if (latencyCount > 0) {
            double sum = 0;
            for (double lat : latencies) {
                sum += lat;
            }
            avgLatency = sum / latencyCount;
        }
        
        // 将并发队列转换为列表以便计算百分位数
        List<Double> latencyList = new ArrayList<>(latencies);
        Collections.sort(latencyList);
        
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
