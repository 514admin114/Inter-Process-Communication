package ipc.utils;

public class PerformanceMetrics {
    public String ipcType;        // IPC类型: shared_memory, socket, tcp
    public String pattern;        // 模式: 1_1, N_1, 1_N, N_N
    public int producerCount;     // 生产者数量
    public int consumerCount;     // 消费者数量
    public int messageCount;      // 总消息数
    public int messageSize;       // 消息大小(字节)
    public double totalTime;      // 总耗时(秒)
    public double throughput;     // 吞吐量(消息/秒)
    public double avgLatency;     // 平均延迟(微秒)
    public double p95Latency;     // P95延迟(微秒)
    public double p99Latency;     // P99延迟(微秒)
    public String timestamp;      // 时间戳
    public boolean success;       // 测试是否成功

    public PerformanceMetrics() {
        this.success = false;
    }
}
