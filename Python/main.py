import sys
import time
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


def print_summary(metrics_list):
    """打印测试总结"""
    print("\n\n========================================")
    print("         测试总结报告")
    print("========================================")
    
    if not metrics_list:
        print("没有可用的测试数据")
        return
    
    # 按IPC类型分组统计
    type_stats = {}
    for m in metrics_list:
        if m.ipc_type not in type_stats:
            type_stats[m.ipc_type] = []
        type_stats[m.ipc_type].append(m)
    
    for ipc_type, type_metrics in type_stats.items():
        print(f"\n【{ipc_type}】性能统计:")
        
        total_throughput = 0
        total_avg_latency = 0
        count = len(type_metrics)
        
        for m in type_metrics:
            total_throughput += m.throughput
            total_avg_latency += m.avg_latency
        
        if count > 0:
            print(f"  平均吞吐量: {total_throughput / count:.2f} 消息/秒")
            print(f"  平均延迟: {total_avg_latency / count:.2f} 微秒")
            print(f"  测试次数: {count}")
    
    # 找出最佳性能
    best_throughput = None
    lowest_latency = None
    
    for m in metrics_list:
        if best_throughput is None or m.throughput > best_throughput.throughput:
            best_throughput = m
        if lowest_latency is None or m.avg_latency < lowest_latency.avg_latency:
            lowest_latency = m
    
    print("\n【最佳性能】")
    if best_throughput:
        print(f"  最高吞吐量: {best_throughput.throughput:.2f} 消息/秒 ({best_throughput.ipc_type}, {best_throughput.pattern}, {best_throughput.message_size}字节)")
    if lowest_latency:
        print(f"  最低延迟: {lowest_latency.avg_latency:.2f} 微秒 ({lowest_latency.ipc_type}, {lowest_latency.pattern}, {lowest_latency.message_size}字节)")


def main():
    print("========================================")
    print("  进程间通信(IPC)性能测试程序")
    print("========================================")
    print(f"开始时间: {get_current_timestamp()}\n")
    
    # 确保数据目录存在
    if not ensure_data_dir():
        print("创建数据目录失败")
        return
    
    # 测试配置 - 简化版用于快速测试
    config = TestConfig()
    config.message_sizes = [64, 1024]           # 64B, 1KB (简化测试)
    config.producer_counts = [1, 2, 4]          # 1, 2, 4个生产者
    config.consumer_counts = [1, 2, 4]          # 1, 2, 4个消费者
    config.messages_per_prod = 500              # 每个生产者发送500条消息(简化)
    
    # 如需完整测试，使用以下配置：
    """
    config.message_sizes = [64, 256, 1024, 4096]  # 64B, 256B, 1KB, 4KB
    config.producer_counts = [1, 2, 4, 8]         # 1, 2, 4, 8个生产者
    config.consumer_counts = [1, 2, 4, 8]         # 1, 2, 4, 8个消费者
    config.messages_per_prod = 1000               # 每个生产者发送1000条消息
    """
    
    print("测试配置:")
    print(f"- 消息大小: {config.message_sizes} 字节")
    print(f"- 生产者数量: {config.producer_counts}")
    print(f"- 消费者数量: {config.consumer_counts}")
    print(f"- 每个生产者消息数: {config.messages_per_prod}\n")
    
    all_metrics = []
    test_count = 0
    total_tests = len(config.message_sizes) * len(config.producer_counts) * \
                  len(config.consumer_counts) * 3
    
    success_count = 0
    failed_count = 0
    
    program_start = time.time_ns()
    
    # 遍历所有测试组合
    for msg_size in config.message_sizes:
        print(f"\n########## 消息大小: {msg_size} 字节 ##########")
        
        for producers in config.producer_counts:
            for consumers in config.consumer_counts:
                # 跳过不合理的组合
                if producers * consumers > 32:
                    continue
                
                print(f"\n--- 测试模式: {producers}生产者 -> {consumers}消费者 ---")
                
                # 测试1: 共享内存
                print("\n[1/3] 测试共享内存IPC...")
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
                    print(f"共享内存测试失败: {e}")
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
                print("[2/3] 测试Socket IPC...")
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
                    print(f"Socket IPC测试失败: {e}")
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
                print("[3/3] 测试TCP Socket...")
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
                    print(f"TCP Socket测试失败: {e}")
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
    print(f"测试完成! 结束时间: {get_current_timestamp()}")
    print(f"总测试数: {actual_total_tests} | 成功: {success_count} | 失败: {failed_count} | 成功率: {success_count / actual_total_tests * 100 if actual_total_tests > 0 else 0:.2f}%")
    print(f"总程序耗时: {total_program_time:.2f} 秒")
    print("数据已保存到: ../csv/ipc_performance_python.csv")
    print("========================================")


if __name__ == "__main__":
    main()
