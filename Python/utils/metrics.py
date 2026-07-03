import os
import csv
import random
import struct
from datetime import datetime

# Error injection constants
ERROR_RATE = 0.01
MAX_RETRANSMIT = 3


class PerformanceMetrics:
    """性能指标类"""
    
    def __init__(self):
        self.ipc_type = ""        # IPC类型: shared_memory, socket, tcp
        self.pattern = ""         # 模式: 1_1, N_1, 1_N, N_N
        self.producer_count = 0   # 生产者数量
        self.consumer_count = 0   # 消费者数量
        self.message_count = 0    # 总消息数
        self.message_size = 0     # 消息大小(字节)
        self.total_time = 0.0     # 总耗时(秒)
        self.throughput = 0.0     # 吞吐量(消息/秒)
        self.avg_latency = 0.0    # 平均延迟(微秒)
        self.p95_latency = 0.0    # P95延迟(微秒)
        self.p99_latency = 0.0    # P99延迟(微秒)
        self.error_count = 0      # 检测到的错误消息数
        self.retransmit_count = 0 # 重传次数
        self.accuracy = 0.0      # 数据传输准确率(%): 无错误传输的消息百分比
        self.timestamp = ""       # 时间戳
        self.success = False      # 测试是否成功


def compute_checksum(data):
    """Compute additive checksum (sum of all bytes modulo 2^32)"""
    return sum(data) & 0xFFFFFFFF


def ensure_data_dir():
    """确保数据目录存在"""
    data_dir = "../csv"
    try:
        os.makedirs(data_dir, exist_ok=True)
        return True
    except Exception as e:
        print(f"创建数据目录失败: {e}")
        return False


def get_current_timestamp():
    """获取当前时间戳"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def calculate_percentile(latencies, percentile):
    """计算百分位数"""
    if not latencies:
        return 0.0
    
    sorted_latencies = sorted(latencies)
    
    index = int(len(sorted_latencies) * percentile / 100.0)
    if index >= len(sorted_latencies):
        index = len(sorted_latencies) - 1
    
    return sorted_latencies[index]


def save_to_csv(metrics, filename):
    """将性能指标保存到CSV文件"""
    if not ensure_data_dir():
        return False
    
    file_path = os.path.join("../csv", filename)
    file_exists = os.path.exists(file_path)
    
    try:
        with open(file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            if not file_exists:
                writer.writerow([
                    "Timestamp", "IPC_Type", "Pattern",
                    "Producer_Count", "Consumer_Count",
                    "Message_Count", "Message_Size",
                    "Total_Time_Seconds", "Throughput_Msg_Per_Sec",
                    "Avg_Latency_Microseconds", "P95_Latency_Microseconds",
                    "P99_Latency_Microseconds", "Error_Count", "Retransmit_Count",
                    "Accuracy", "Success"
                ])
            
            success_str = "true" if metrics.success else "false"
            writer.writerow([
                metrics.timestamp,
                metrics.ipc_type,
                metrics.pattern,
                metrics.producer_count,
                metrics.consumer_count,
                metrics.message_count,
                metrics.message_size,
                f"{metrics.total_time:.6f}",
                f"{metrics.throughput:.2f}",
                f"{metrics.avg_latency:.2f}",
                f"{metrics.p95_latency:.2f}",
                f"{metrics.p99_latency:.2f}",
                str(metrics.error_count),
                str(metrics.retransmit_count),
                f"{metrics.accuracy:.2f}",
                success_str
            ])
        
        return True
    except Exception as e:
        print(f"写入CSV文件失败: {e}")
        return False


def append_statistics(filename, total_tests, success_tests, failed_tests):
    """追加统计信息到CSV文件末尾"""
    if not ensure_data_dir():
        return False
    
    file_path = os.path.join("../csv", filename)
    
    try:
        with open(file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            writer.writerow([])
            
            success_rate = (success_tests / total_tests * 100.0) if total_tests > 0 else 0.0
            
            writer.writerow(["=== Test Statistics ==="])
            writer.writerow(["Total Tests", total_tests])
            writer.writerow(["Successful Tests", success_tests])
            writer.writerow(["Failed Tests", failed_tests])
            writer.writerow(["Success Rate", f"{success_rate:.2f}%"])
        
        return True
    except Exception as e:
        print(f"写入统计信息失败: {e}")
        return False
