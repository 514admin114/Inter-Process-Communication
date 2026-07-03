import queue
import threading
import time
import random
import struct
from utils.metrics import PerformanceMetrics, calculate_percentile, get_current_timestamp
from utils.metrics import compute_checksum, ERROR_RATE


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
        return bytearray(data)


def producer(id, sm, message_count, message_size, latencies, latencies_lock,
             error_count, error_lock, retransmit_count, retransmit_lock):
    """生产者函数"""
    data = bytes([i % 256 for i in range(message_size)])
    
    for i in range(message_count):
        start = time.time_ns()
        
        # Compute checksum on original data
        checksum = compute_checksum(data)
        checksum_bytes = struct.pack('>I', checksum)
        
        # Build message: data + checksum
        msg_data = bytearray(data + checksum_bytes)
        
        # Error injection: corrupt 1 byte in data portion with ERROR_RATE probability
        if random.random() < ERROR_RATE:
            corrupt_pos = random.randint(0, message_size - 1)
            msg_data[corrupt_pos] ^= 0xFF
            with error_lock:
                error_count[0] += 1
        
        try:
            sm.write(bytes(msg_data))
        except Exception as e:
            print(f"Producer {id} write failed: {e}")
            continue
        
        elapsed = (time.time_ns() - start) / 1000  # 转换为微秒
        
        with latencies_lock:
            latencies.append(elapsed)


def consumer(id, sm, message_count, message_size, error_count, error_lock):
    """消费者函数 - validates checksum"""
    for i in range(message_count):
        try:
            msg_data = sm.read()
        except Exception as e:
            print(f"Consumer {id} read failed: {e}")
            break
        
        # Validate checksum: last 4 bytes are checksum, rest is data
        data_len = len(msg_data) - 4
        received_checksum = struct.unpack('>I', bytes(msg_data[data_len:]))[0]
        computed_checksum = compute_checksum(bytes(msg_data[:data_len]))
        
        if computed_checksum != received_checksum:
            with error_lock:
                error_count[0] += 1


def run_test(producers, consumers, messages_per_producer, message_size):
    """运行共享内存IPC测试"""
    print("\n=== Shared Memory Test ===")
    print(f"Producers: {producers}, Consumers: {consumers}, Messages per Producer: {messages_per_producer}, Message Size: {message_size} bytes")
    
    sm = SharedMemory(message_size)
    total_messages = producers * messages_per_producer
    messages_per_consumer = total_messages // consumers
    
    latencies = []
    latencies_lock = threading.Lock()
    error_count = [0]  # list for mutability across threads
    error_lock = threading.Lock()
    retransmit_count = [0]
    retransmit_lock = threading.Lock()
    
    start_time = time.time_ns()
    
    # 启动消费者
    consumer_threads = []
    for i in range(consumers):
        t = threading.Thread(target=consumer, args=(i, sm, messages_per_consumer, message_size,
                                                      error_count, error_lock))
        t.start()
        consumer_threads.append(t)
    
    # 短暂等待让消费者准备好
    time.sleep(0.01)
    
    # 启动生产者
    producer_threads = []
    for i in range(producers):
        t = threading.Thread(target=producer, args=(i, sm, messages_per_producer, message_size,
                                                      latencies, latencies_lock,
                                                      error_count, error_lock,
                                                      retransmit_count, retransmit_lock))
        t.start()
        producer_threads.append(t)
    
    # 等待所有生产者完成
    for t in producer_threads:
        t.join()
    
    # 等待所有消费者完成
    for t in consumer_threads:
        t.join()
    
    end_time = time.time_ns()
    
    total_time = (end_time - start_time) / 1_000_000_000.0
    throughput = total_messages / total_time if total_time > 0 else 0
    
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
    metrics.error_count = error_count[0]
    metrics.retransmit_count = retransmit_count[0]
    metrics.accuracy = ((total_messages - error_count[0]) * 100.0 / total_messages) if total_messages > 0 else 100.0
    metrics.timestamp = get_current_timestamp()
    metrics.success = True
    
    print(f"Total Time: {total_time:.6f} seconds")
    print(f"Throughput: {throughput:.2f} messages/sec")
    print(f"Average Latency: {avg_latency:.2f} microseconds")
    print(f"P95 Latency: {p95_latency:.2f} microseconds")
    print(f"P99 Latency: {p99_latency:.2f} microseconds")
    print(f"Error Count: {metrics.error_count}, Retransmit Count: {metrics.retransmit_count}")
    error_rate = (metrics.error_count * 100.0 / total_messages) if total_messages > 0 else 0.0
    print(f"Error Rate: {error_rate:.2f}%\n")
    
    return metrics
