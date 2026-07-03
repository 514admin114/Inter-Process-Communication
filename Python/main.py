import sys
import os
import time
import json
from shared_memory.shared_memory import run_test as shared_memory_test
from socket_ipc.socket_ipc import run_test as socket_test
from tcp_ipc.tcp_ipc import run_test as tcp_test
from utils.metrics import PerformanceMetrics, ensure_data_dir, save_to_csv, append_statistics, get_current_timestamp


class TestConfig:
    """测试配置类"""
    
    def __init__(self):
        self.message_sizes = []      # 消息大小列表（字节）
        self.producer_counts = []    # 生产者数量列表
        self.consumer_counts = []    # 消费者数量列表
        self.messages_per_prod = 0   # 每个生产者的消息数


def load_config(path="../config.json"):
    """从JSON文件加载测试配置"""
    config = TestConfig()
    config.message_sizes = [64, 1024]
    config.producer_counts = [1, 2, 4]
    config.consumer_counts = [1, 2, 4]
    config.messages_per_prod = 500
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        config.message_sizes = data.get("message_sizes", config.message_sizes)
        config.producer_counts = data.get("producer_counts", config.producer_counts)
        config.consumer_counts = data.get("consumer_counts", config.consumer_counts)
        config.messages_per_prod = data.get("messages_per_producer", config.messages_per_prod)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: cannot load {path}, using defaults ({e})")
    return config


def print_summary(metrics_list):
    """打印测试总结"""
    print("\n\n========================================")
    print("         Test Summary Report")
    print("========================================")
    
    if not metrics_list:
        print("No available test data")
        return
    
    # Group statistics by IPC type
    type_stats = {}
    for m in metrics_list:
        if m.ipc_type not in type_stats:
            type_stats[m.ipc_type] = []
        type_stats[m.ipc_type].append(m)
    
    for ipc_type, type_metrics in type_stats.items():
        print(f"\n[{ipc_type}] Performance Statistics:")
        
        total_throughput = 0
        total_avg_latency = 0
        count = len(type_metrics)
        
        for m in type_metrics:
            total_throughput += m.throughput
            total_avg_latency += m.avg_latency
        
        if count > 0:
            print(f"  Average Throughput: {total_throughput / count:.2f} messages/sec")
            print(f"  Average Latency: {total_avg_latency / count:.2f} microseconds")
            print(f"  Test Count: {count}")
    
    # Find best performance
    best_throughput = None
    lowest_latency = None
    
    for m in metrics_list:
        if best_throughput is None or m.throughput > best_throughput.throughput:
            best_throughput = m
        if lowest_latency is None or m.avg_latency < lowest_latency.avg_latency:
            lowest_latency = m
    
    print("\n[Best Performance]")
    if best_throughput:
        print(f"  Highest Throughput: {best_throughput.throughput:.2f} messages/sec ({best_throughput.ipc_type}, {best_throughput.pattern}, {best_throughput.message_size} bytes)")
    if lowest_latency:
        print(f"  Lowest Latency: {lowest_latency.avg_latency:.2f} microseconds ({lowest_latency.ipc_type}, {lowest_latency.pattern}, {lowest_latency.message_size} bytes)")


def main():
    print("========================================")
    print("  Inter-Process Communication (IPC) Performance Testing Program")
    print("========================================")
    print(f"Start Time: {get_current_timestamp()}\n")
    
    # 确保数据目录存在
    if not ensure_data_dir():
        print("Failed to create data directory")
        return
    
    # Remove old CSV file for clean overwrite
    csv_path = os.path.join("..", "csv", "ipc_performance_python.csv")
    if os.path.exists(csv_path):
        os.remove(csv_path)
    
    # 从共享配置文件加载测试参数
    config = load_config("../config.json")
    
    print("Test Configuration:")
    print(f"- Message Sizes: {config.message_sizes} bytes")
    print(f"- Producer Counts: {config.producer_counts}")
    print(f"- Consumer Counts: {config.consumer_counts}")
    print(f"- Messages per Producer: {config.messages_per_prod}\n")
    
    all_metrics = []
    test_count = 0
    total_tests = len(config.message_sizes) * len(config.producer_counts) * \
                  len(config.consumer_counts) * 3
    
    success_count = 0
    failed_count = 0
    
    program_start = time.time_ns()
    
    # 遍历所有测试组合
    for msg_size in config.message_sizes:
        print(f"\n########## Message Size: {msg_size} bytes ##########")
        
        for producers in config.producer_counts:
            for consumers in config.consumer_counts:
                # 跳过不合理的组合
                if producers * consumers > 32:
                    continue
                
                print(f"\n--- Test Pattern: {producers} Producers -> {consumers} Consumers ---")
                
                # 测试1: 共享内存
                print("\n[1/3] Testing Shared Memory IPC...")
                test_count += 1
                print(f"[{test_count}/{total_tests}] ", end="")
                
                try:
                    metrics = shared_memory_test(producers, consumers, 
                                                config.messages_per_prod, msg_size)
                    metrics.success = True
                    success_count += 1
                    all_metrics.append(metrics)
                    save_to_csv(metrics, "ipc_performance_python.csv")
                except Exception as e:
                    failed_count += 1
                    print(f"Shared Memory test failed: {e}")
                    # 保存失败的测试记录
                    failed_metrics = PerformanceMetrics()
                    failed_metrics.ipc_type = "shared_memory"
                    failed_metrics.pattern = f"{producers}_{consumers}"
                    failed_metrics.producer_count = producers
                    failed_metrics.consumer_count = consumers
                    failed_metrics.message_count = producers * config.messages_per_prod
                    failed_metrics.message_size = msg_size
                    failed_metrics.timestamp = get_current_timestamp()
                    failed_metrics.success = False
                    save_to_csv(failed_metrics, "ipc_performance_python.csv")
                
                # 短暂等待，避免资源竞争
                time.sleep(0.2)
                
                # 测试2: Socket IPC
                print("[2/3] Testing Socket IPC...")
                test_count += 1
                print(f"[{test_count}/{total_tests}] ", end="")
                
                try:
                    metrics = socket_test(producers, consumers, 
                                         config.messages_per_prod, msg_size)
                    metrics.success = True
                    success_count += 1
                    all_metrics.append(metrics)
                    save_to_csv(metrics, "ipc_performance_python.csv")
                except Exception as e:
                    failed_count += 1
                    print(f"Socket IPC test failed: {e}")
                    # 保存失败的测试记录
                    failed_metrics = PerformanceMetrics()
                    failed_metrics.ipc_type = "socket"
                    failed_metrics.pattern = f"{producers}_{consumers}"
                    failed_metrics.producer_count = producers
                    failed_metrics.consumer_count = consumers
                    failed_metrics.message_count = producers * config.messages_per_prod
                    failed_metrics.message_size = msg_size
                    failed_metrics.timestamp = get_current_timestamp()
                    failed_metrics.success = False
                    save_to_csv(failed_metrics, "ipc_performance_python.csv")
                
                # 短暂等待
                time.sleep(0.2)
                
                # 测试3: TCP Socket
                print("[3/3] Testing TCP Socket...")
                test_count += 1
                print(f"[{test_count}/{total_tests}] ", end="")
                
                try:
                    metrics = tcp_test(producers, consumers, 
                                      config.messages_per_prod, msg_size)
                    metrics.success = True
                    success_count += 1
                    all_metrics.append(metrics)
                    save_to_csv(metrics, "ipc_performance_python.csv")
                except Exception as e:
                    failed_count += 1
                    print(f"TCP Socket test failed: {e}")
                    # 保存失败的测试记录
                    failed_metrics = PerformanceMetrics()
                    failed_metrics.ipc_type = "tcp"
                    failed_metrics.pattern = f"{producers}_{consumers}"
                    failed_metrics.producer_count = producers
                    failed_metrics.consumer_count = consumers
                    failed_metrics.message_count = producers * config.messages_per_prod
                    failed_metrics.message_size = msg_size
                    failed_metrics.timestamp = get_current_timestamp()
                    failed_metrics.success = False
                    save_to_csv(failed_metrics, "ipc_performance_python.csv")
                
                # 每次完整测试后等待
                time.sleep(0.5)
    
    program_end = time.time_ns()
    total_program_time = (program_end - program_start) / 1_000_000_000.0
    
    # 在CSV文件末尾添加统计信息
    actual_total_tests = success_count + failed_count
    append_statistics("ipc_performance_python.csv", actual_total_tests, success_count, failed_count)
    
    # 打印总结
    print_summary(all_metrics)
    
    print("\n========================================")
    print(f"Testing Complete! End Time: {get_current_timestamp()}")
    print(f"Total Tests: {actual_total_tests} | Successful: {success_count} | Failed: {failed_count} | Success Rate: {success_count / actual_total_tests * 100 if actual_total_tests > 0 else 0:.2f}%")
    print(f"Total Program Time: {total_program_time:.2f} seconds")
    print("Data saved to: ../csv/ipc_performance_python.csv")
    print("========================================")


if __name__ == "__main__":
    main()
