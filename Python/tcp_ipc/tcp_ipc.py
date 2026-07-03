import socket
import struct
import threading
import time
import random
from utils.metrics import PerformanceMetrics, calculate_percentile, get_current_timestamp
from utils.metrics import compute_checksum, ERROR_RATE, MAX_RETRANSMIT


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
        server_socket.bind(('127.0.0.1', 0))
        server_socket.listen(100)
        self.port = server_socket.getsockname()[1]
        self.address = f"127.0.0.1:{self.port}"
        print(f"TCP服务器监听地址: {self.address}")
        return server_socket


def producer(id, address, port, message_count, message_size, latencies, latencies_lock,
             error_count, error_lock, retransmit_count, retransmit_lock):
    """生产者函数（使用长连接 + ACK/NACK重传）"""
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
                conn = None
            time.sleep((retry + 1) * 0.01)
    
    if conn is None:
        print(f"Producer {id} 无法建立连接")
        return
    
    try:
        for i in range(message_count):
            start = time.time_ns()
            
            # Compute checksum on original data
            checksum = compute_checksum(data)
            checksum_bytes = struct.pack('>I', checksum)
            
            # Wire format: [4B header = messageSize+4] [data] [4B checksum]
            total_payload = message_size + 4
            header_bytes = struct.pack('>I', total_payload)
            
            # Error injection: corrupt 1 byte in data with ERROR_RATE probability
            send_data = bytearray(data)
            if random.random() < ERROR_RATE:
                corrupt_pos = random.randint(0, message_size - 1)
                send_data[corrupt_pos] ^= 0xFF
            
            # Pre-allocate merged wire buffer: [4B header][data][4B checksum]
            wire_buf = bytearray(4 + message_size + 4)
            wire_buf[0:4] = header_bytes
            wire_buf[4 + message_size:] = checksum_bytes
            
            # Retransmission loop
            delivered = False
            retransmits = 0
            for attempt in range(MAX_RETRANSMIT + 1):
                if attempt > 0:
                    # Retransmit: send original (correct) data
                    send_data = bytearray(data)
                    retransmits += 1
                
                # Copy data into merged buffer and send everything at once
                wire_buf[4:4 + message_size] = send_data
                conn.sendall(wire_buf)
                
                # Receive ACK/NACK (1 byte)
                try:
                    ack = conn.recv(1)
                    if len(ack) == 0:
                        break
                    if ack[0] == 0x01:
                        delivered = True
                        break
                except Exception:
                    break
            
            if retransmits > 0:
                with retransmit_lock:
                    retransmit_count[0] += retransmits
            
            elapsed = (time.time_ns() - start) / 1000  # 转换为微秒
            
            with latencies_lock:
                latencies.append(elapsed)
    except Exception as e:
        print(f"Producer {id} 发送失败: {e}")
    finally:
        conn.close()


def handle_connection(conn, message_size, received_count, received_lock,
                      error_count, error_lock, expected_messages):
    """处理单个连接：接收消息，校验checksum，发送ACK/NACK"""
    try:
        success_count = 0
        while success_count < expected_messages:
            # Read 4-byte header: total payload size = messageSize + 4
            header_buf = b''
            while len(header_buf) < 4:
                chunk = conn.recv(4 - len(header_buf))
                if not chunk:
                    return
                header_buf += chunk
            
            total_payload = struct.unpack('>I', header_buf)[0]
            data_len = total_payload - 4
            
            # Read data + checksum
            payload = b''
            while len(payload) < total_payload:
                chunk = conn.recv(total_payload - len(payload))
                if not chunk:
                    return
                payload += chunk
            
            # Extract checksum (last 4 bytes) and validate
            received_checksum = struct.unpack('>I', payload[data_len:])[0]
            computed_checksum = compute_checksum(payload[:data_len])
            
            if computed_checksum == received_checksum:
                ack = b'\x01'  # ACK
                with received_lock:
                    received_count[0] += 1
                success_count += 1
            else:
                ack = b'\x00'  # NACK
                with error_lock:
                    error_count[0] += 1
            
            # Send ACK/NACK
            conn.sendall(ack)
    except Exception:
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
    received_count = [0]
    received_lock = threading.Lock()
    error_count = [0]
    error_lock = threading.Lock()
    retransmit_count = [0]
    retransmit_lock = threading.Lock()
    
    start_time = time.time_ns()
    
    # 启动服务器接受连接
    accept_done = threading.Event()
    server_ready = threading.Event()
    
    def accept_connections():
        server_ready.set()
        
        for i in range(producers):
            try:
                conn, addr = listener.accept()
                t = threading.Thread(target=handle_connection, 
                                   args=(conn, message_size, received_count, received_lock,
                                         error_count, error_lock, messages_per_producer))
                t.start()
            except Exception as e:
                print(f"Accept错误 (已接受 {i}/{producers} 个连接): {e}")
                break
        
        accept_done.set()
    
    accept_thread = threading.Thread(target=accept_connections)
    accept_thread.start()
    
    # 等待服务器准备好
    server_ready.wait()
    time.sleep(0.05)
    
    # 启动生产者
    producer_threads = []
    for i in range(producers):
        t = threading.Thread(target=producer, 
                           args=(i, "127.0.0.1", tcp_ipc.port, 
                                messages_per_producer, message_size, 
                                latencies, latencies_lock,
                                error_count, error_lock,
                                retransmit_count, retransmit_lock))
        t.start()
        producer_threads.append(t)
    
    # 等待所有生产者完成
    for t in producer_threads:
        t.join()
    
    # 给最后的消息一些时间被Accept
    time.sleep(0.1)
    
    # 关闭listener
    listener.close()
    
    # 等待Accept线程结束
    accept_done.wait(timeout=30)
    
    end_time = time.time_ns()
    
    total_time = (end_time - start_time) / 1_000_000_000.0
    throughput = total_messages / total_time if total_time > 0 else 0
    
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
    metrics.error_count = error_count[0]
    metrics.retransmit_count = retransmit_count[0]
    metrics.accuracy = ((total_messages - error_count[0]) * 100.0 / total_messages) if total_messages > 0 else 100.0
    metrics.timestamp = get_current_timestamp()
    metrics.success = True
    
    print(f"总耗时: {total_time:.6f}秒")
    print(f"吞吐量: {throughput:.2f} 消息/秒")
    print(f"平均延迟: {avg_latency:.2f} 微秒")
    print(f"P95延迟: {p95_latency:.2f} 微秒")
    print(f"P99延迟: {p99_latency:.2f} 微秒")
    print(f"错误数: {metrics.error_count}, 重传数: {metrics.retransmit_count}")
    error_rate = (metrics.error_count * 100.0 / total_messages) if total_messages > 0 else 0.0
    print(f"数据错误率: {error_rate:.2f}%\n")
    
    return metrics
