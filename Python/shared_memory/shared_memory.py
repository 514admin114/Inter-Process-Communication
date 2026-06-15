import queue
import threading
import time
from utils.metrics import PerformanceMetrics, calculate_percentile, get_current_timestamp


class MessageQueue:
    """消息队列，用于生产者和消费者之间的通信"""
    
    def __init__(self, buffer_size):
        self.messages = queue.Queue(maxsize=buffer_size)
        self.closed = False
    
    def send(self, data):
        """发送消息"""
        if self.closed:
            raise Exception("队列已关闭")
        self.messages.put(data)
    
    def receive(self):
        """接收消息"""
        if self.closed and self.messages.empty():
            raise Exception("队列已关闭")
        return self.messages.get()
    
    def close(self):
        """关闭队列"""
        self.closed = True


class SharedMemory:
    """共享内存IPC实现（基于queue的消息队列）"""
    
    def __init__(self, message_size):
        # 设置缓冲区大小为1000，足够容纳突发消息
        queue_size = 1000
        self.queue = MessageQueue(queue_size)
        self.message_size = message_size
    
    def write(self, data):
        """写入数据到共享内存"""
        buf = bytearray(data)
        self.queue.send(buf)
    
    def read(self):
        """从共享内存读取数据"""
        data = self.queue.receive()
        result = bytearray(data)
        return result


def producer(id, sm, message_count, message_size, latencies, latencies_lock):
    """生产者函数"""
    data = bytes([i % 256 for i in range(message_size)])
    
    for i in range(message_count):
        start = time.time_ns()
        
        try:
            sm.write(data)
        except Exception as e:
            print(f"Producer {id} 写入失败: {e}")
            continue
        
        elapsed = (time.time_ns() - start) / 1000  # 转换为微秒
        
        with latencies_lock:
            latencies.append(elapsed)


def consumer(id, sm, message_count):
    """消费者函数"""
    for i in range(message_count):
        try:
            sm.read()
        except Exception as e:
            print(f"Consumer {id} 读取失败: {e}")
            break


def run_test(producers, consumers, messages_per_producer, message_size):
    """运行共享内存IPC测试"""
    print("\n=== 共享内存测试 ===")
    print(f"生产者: {producers}, 消费者: {consumers}, 每个生产者消息数: {messages_per_producer}, 消息大小: {message_size}字节")
    
    sm = SharedMemory(message_size)
    total_messages = producers * messages_per_producer
    messages_per_consumer = total_messages // consumers
    
    latencies = []
    latencies_lock = threading.Lock()
    
    start_time = time.time_ns()
    
    # 启动消费者
    consumer_threads = []
    for i in range(consumers):
        t = threading.Thread(target=consumer, args=(i, sm, messages_per_consumer))
        t.start()
        consumer_threads.append(t)
    
    # 短暂等待让消费者准备好
    time.sleep(0.01)
    
    # 启动生产者
    producer_threads = []
    for i in range(producers):
        t = threading.Thread(target=producer, args=(i, sm, messages_per_producer, message_size, latencies, latencies_lock))
        t.start()
        producer_threads.append(t)
    
    # 等待所有生产者完成
    for t in producer_threads:
        t.join()
    
    # 等待所有消费者完成
    for t in consumer_threads:
        t.join()
    
    end_time = time.time_ns()
    
    total_time = (end_time - start_time) / 1_000_000_000.0  # 转换为秒
    throughput = total_messages / total_time if total_time > 0 else 0
    
    # 计算延迟统计
    avg_latency = 0
    if latencies:
        avg_latency = sum(latencies) / len(latencies)
    
    p95_latency = calculate_percentile(latencies, 95)
    p99_latency = calculate_percentile(latencies, 99)
    
    metrics = PerformanceMetrics()
    metrics.ipc_type = "shared_memory"
    metrics.pattern = f"{producers}_{consumers}"
    metrics.producer_count = producers
    metrics.consumer_count = consumers
    metrics.message_count = total_messages
    metrics.message_size = message_size
    metrics.total_time = total_time
    metrics.throughput = throughput
    metrics.avg_latency = avg_latency
    metrics.p95_latency = p95_latency
    metrics.p99_latency = p99_latency
    metrics.timestamp = get_current_timestamp()
    metrics.success = True
    
    print(f"总耗时: {total_time:.6f}秒")
    print(f"吞吐量: {throughput:.2f} 消息/秒")
    print(f"平均延迟: {avg_latency:.2f} 微秒")
    print(f"P95延迟: {p95_latency:.2f} 微秒")
    print(f"P99延迟: {p99_latency:.2f} 微秒\n")
    
    return metrics
