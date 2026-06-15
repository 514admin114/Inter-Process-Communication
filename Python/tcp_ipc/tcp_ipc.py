import socket
import struct
import threading
import time
from utils.metrics import PerformanceMetrics, calculate_percentile, get_current_timestamp


class TcpIPC:
    """使用TCP Socket进行进程间通信"""
    
    def __init__(self, message_size):
        self.message_size = message_size
        self.address = "127.0.0.1"
        self.port = 0
    
    def start_server(self):
        """启动TCP服务器"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('127.0.0.1', 0))  # 端口0表示自动分配
        server_socket.listen(100)
        self.port = server_socket.getsockname()[1]
        self.address = f"127.0.0.1:{self.port}"
        print(f"TCP服务器监听地址: {self.address}")
        return server_socket


def producer(id, address, port, message_count, message_size, latencies, latencies_lock):
    """生产者函数（使用长连接）"""
    data = bytes([i % 256 for i in range(message_size)])
    
    conn = None
    
    # 带重试的连接
    max_retries = 10
    for retry in range(max_retries):
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((address, port))
            break
        except Exception as e:
            if conn:
                conn.close()
            time.sleep((retry + 1) * 0.01)
    
    if conn is None:
        print(f"Producer {id} 无法建立连接")
        return
    
    try:
        # 复用同一个连接发送所有消息
        for i in range(message_count):
            start = time.time_ns()
            
            # 发送消息长度（4字节，大端序）
            conn.sendall(struct.pack('>I', message_size))
            
            # 发送数据
            conn.sendall(data)
            
            elapsed = (time.time_ns() - start) / 1000  # 转换为微秒
            
            with latencies_lock:
                latencies.append(elapsed)
    except Exception as e:
        print(f"Producer {id} 发送失败: {e}")
    finally:
        conn.close()


def handle_connection(conn, message_size, received_count, expected_messages):
    """处理单个连接（支持多条消息）"""
    try:
        # 循环接收多条消息，直到达到预期数量或连接关闭
        for i in range(expected_messages):
            # 读取消息长度
            len_buf = b''
            while len(len_buf) < 4:
                chunk = conn.recv(4 - len(len_buf))
                if not chunk:
                    return
                len_buf += chunk
            
            msg_size = struct.unpack('>I', len_buf)[0]
            
            # 读取数据
            data = b''
            while len(data) < msg_size:
                chunk = conn.recv(msg_size - len(data))
                if not chunk:
                    return
                data += chunk
            
            # 原子增加接收计数
            with received_count['lock']:
                received_count['value'] += 1
                count = received_count['value']
                
                if count % 1000 == 0:
                    print(f"已接收 {count} 条消息")
    except Exception as e:
        # 连接关闭或错误，退出
        pass
    finally:
        conn.close()


def run_test(producers, consumers, messages_per_producer, message_size):
    """运行TCP IPC测试"""
    print("\n=== TCP Socket测试 ===")
    print(f"生产者: {producers}, 消费者: {consumers}, 每个生产者消息数: {messages_per_producer}, 消息大小: {message_size}字节")
    
    tcp_ipc = TcpIPC(message_size)
    total_messages = producers * messages_per_producer
    
    listener = tcp_ipc.start_server()
    
    latencies = []
    latencies_lock = threading.Lock()
    received_count = {'value': 0, 'lock': threading.Lock()}
    
    start_time = time.time_ns()
    
    # 启动服务器接受连接（在单独的线程中）
    accept_done = threading.Event()
    server_ready = threading.Event()
    
    def accept_connections():
        server_ready.set()  # 立即发出就绪信号
        
        # 接受producers个连接（每个Producer一个连接）
        for i in range(producers):
            try:
                conn, addr = listener.accept()
                t = threading.Thread(target=handle_connection, 
                                   args=(conn, message_size, received_count, messages_per_producer))
                t.start()
            except Exception as e:
                print(f"Accept错误 (已接受 {i}/{producers} 个连接): {e}")
                break
        
        accept_done.set()
    
    accept_thread = threading.Thread(target=accept_connections)
    accept_thread.start()
    
    # 等待服务器准备好
    server_ready.wait()
    time.sleep(0.3)  # 额外等待确保完全就绪
    
    # 启动生产者
    producer_threads = []
    for i in range(producers):
        t = threading.Thread(target=producer, 
                           args=(i, "127.0.0.1", tcp_ipc.port, 
                                messages_per_producer, message_size, 
                                latencies, latencies_lock))
        t.start()
        producer_threads.append(t)
    
    # 等待所有生产者完成
    for t in producer_threads:
        t.join()
    
    # 给最后的消息一些时间被Accept
    time.sleep(0.5)
    
    # 关闭listener，停止接受新连接
    listener.close()
    
    # 等待Accept线程结束
    accept_done.wait(timeout=30)
    
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
    metrics.ipc_type = "tcp"
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
