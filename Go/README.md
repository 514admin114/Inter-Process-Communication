# Go IPC性能测试程序

## 📋 快速开始

```bash
cd Go
go run main.go
```

测试结果将自动保存到 `../csv/ipc_performance_go.csv`

---

## 📊 项目概述

这是一个基于Go语言的进程间通信(IPC)性能测试框架,用于对比不同IPC技术的性能表现。

**核心功能:**
- ✅ 三种IPC技术:共享内存、Socket IPC、TCP Socket
- ✅ 四种生产者-消费者模式:1:1、N:1、1:N、N:N
- ✅ 全面性能指标:吞吐量、平均/P95/P99延迟
- ✅ CSV输出:结果便于分析和对比
- ✅ 跨平台支持:Windows和Linux/Mac

---

## 🏗️ 项目结构

```
Go/
├── main.go                  # 主程序入口
├── go.mod                   # Go模块文件
├── shared_memory/           # 共享内存IPC实现
│   └── shared_memory.go
├── socket/                  # Socket IPC实现
│   └── socket_ipc.go
├── tcp_ipc/                 # TCP Socket IPC实现
│   └── tcp_ipc.go
├── utils/                   # 工具函数
│   └── metrics.go
└── README.md                # 项目说明文档
```

---

## 🚀 运行测试

### 前置条件
- 安装Go 1.21或更高版本
- 确保有足够的系统权限创建临时文件

### 方法1: 直接运行(推荐)
```bash
cd Go
go run main.go
```

### 方法2: 编译后运行
```bash
cd Go
go build -o ipc_test.exe
./ipc_test.exe
```

---

## 📈 测试配置

### 默认配置(简化版)
- **消息大小**: 64字节、1KB (2种)
- **生产者数量**: 1、2、4 (3种)
- **消费者数量**: 1、2、4 (3种)
- **每个生产者消息数**: 500
- **总测试数**: 约54个测试
- **预计时间**: 5-10分钟

### 调整配置

修改项目根目录下的 `config.json`（四种语言共享），或通过 Web UI 编辑：

```bash
# 启动 Web 管理界面，在「参数配置」页签中编辑
streamlit run ipc_analysis_start.py
```

配置文件路径: `../config.json`

---

## 📊 输出结果

### CSV文件格式
结果保存到 `../csv/ipc_performance_go.csv`:

```csv
Timestamp,IPC_Type,Pattern,Producer_Count,Consumer_Count,Message_Count,Message_Size,Total_Time_Seconds,Throughput_Msg_Per_Sec,Avg_Latency_Microseconds,P95_Latency_Microseconds,P99_Latency_Microseconds,Error_Count,Retransmit_Count,Success
```

### 字段说明
- `Timestamp`: 测试时间戳
- `IPC_Type`: IPC类型(shared_memory/socket/tcp)
- `Pattern`: 生产者_消费者模式(如1_1, 4_2等)
- `Producer_Count`: 生产者数量
- `Consumer_Count`: 消费者数量
- `Message_Count`: 总消息数
- `Message_Size`: 消息大小(字节)
- `Total_Time_Seconds`: 总耗时(秒)
- `Throughput_Msg_Per_Sec`: 吞吐量(消息/秒)
- `Avg_Latency_Microseconds`: 平均延迟(微秒)
- `P95/P99_Latency_Microseconds`: P95/P99延迟(微秒)
- `Error_Count`: 校验错误数
- `Retransmit_Count`: 重传次数
- `Success`: 测试是否成功(true/false)

### 统计信息
文件末尾自动追加:
- 总测试数
- 成功/失败测试数
- 成功率

---

## 🎯 数据分析

测试完成后,可以使用Streamlit分析器可视化分析结果:

```bash
# 安装依赖
pip install streamlit pandas plotly numpy

# 启动分析器
streamlit run ipc_analyzer.py
```

详细使用说明:
- 📖 [IPC分析器完整文档](../README_IPC_Analysis.md)

---

## 💡 测试方案

### 生产者-消费者模式
1. **1发1收 (1:1)**: 基准性能测试
2. **多发1收 (N:1)**: 消费者成为瓶颈
3. **1发多收 (1:N)**: 生产者成为瓶颈
4. **多发多收 (N:N)**: 负载均衡测试

### IPC技术对比

| IPC方式 | 吞吐量 | 延迟 | 数据校验 | 适用场景 |
|---------|--------|------|----------|----------|
| **共享内存** | 最高 | 最低 | 校验和 | 同机进程通信 |
| **Socket IPC** | 中等 | 中等 | ACK/NACK重传 | 本地进程隔离通信 |
| **TCP Socket** | 较低 | 较高 | ACK/NACK重传 | 跨网络通信 |

### 数据校验与重传协议
Socket/TCP 通信实现了数据完整性保障：
- **累加和校验**: `ComputeChecksum()` 求和所有字节模 2^32
- **错误注入**: 1% 概率随机字节翻转（`ErrorRate = 0.01`）
- **ACK/NACK**: 消费者返回单字节应答，失败时生产者重传原始正确数据
- **最大重传**: 3 次 (`MaxRetransmit = 3`)
- **线格式**: `[4B 头 = messageSize+4, 大端序] [数据] [4B 校验和, 大端序]`

### 性能排序(通常情况)
1. **共享内存**: 最快,延迟最低(微秒级)
2. **Unix Socket / Named Pipe**: 中等性能
3. **TCP Socket**: 较慢但最通用

---

## 🌐 跨平台支持

- **Windows**: 使用TCP localhost模拟Named Pipe
- **Linux/Mac**: 使用Unix Domain Socket
- 程序自动检测操作系统并选择合适的IPC机制

---

## 🔬 实验建议

### 变量控制实验
1. **固定消息大小,改变进程数量**
   - 观察不同并发度下的性能变化
   - 分析扩展性瓶颈

2. **固定进程数量,改变消息大小**
   - 观察消息大小对吞吐量的影响
   - 分析带宽利用率

3. **不同IPC技术对比**
   - 在相同条件下比较三种IPC技术
   - 选择最适合应用场景的方案

### 数据分析
使用Excel、Python或其他工具分析CSV数据:
- 绘制吞吐量vs进程数量曲线
- 绘制延迟vs消息大小曲线
- 计算不同IPC技术的性能比率

---

## ❓ 常见问题

### Q1: "Address already in use"错误
**解决方案**: 
- 等待几分钟让端口释放
- 如有必要,重启计算机

### Q2: 性能较慢
**解决方案**: 
- 首次运行正常(JIT编译、缓存预热)
- 多次运行取平均值

### Q3: 编译错误
**解决方案**: 
- 确保Go环境变量正确配置
- 检查go.mod文件是否存在

---

## ⚠️ 注意事项

1. **资源竞争**: 高并发时可能出现资源竞争,程序已添加同步机制
2. **系统限制**: 大量并发连接可能受系统文件描述符限制
3. **测试环境**: 建议在相对空闲的系统上运行测试以获得准确结果
4. **多次测试**: 建议多次运行取平均值以减少误差

---

## 🔄 与其他语言版本对比

| 方面 | Go | C++ | Java | Python |
|------|-----|-----|------|--------|
| **并发模型** | Goroutines+Channels | std::thread | Thread | threading |
| **内存管理** | GC | RAII | GC | GC |
| **性能** | 良好 | 最优 | 良好 | 较慢(GIL) |
| **易用性** | 简单 | 复杂 | 中等 | 简单 |

---

## 🚀 扩展方向

1. 添加更多IPC机制:消息队列、信号量、管道等
2. 实现真正的跨进程测试(多个独立进程)
3. 添加实时监控和可视化
4. 支持自定义测试场景配置
5. 添加压力测试和稳定性测试

---

## 📚 参考资料

- [Go官方文档](https://golang.org/doc/)
- [进程间通信维基百科](https://en.wikipedia.org/wiki/Inter-process_communication)
- [Unix域套接字](https://man7.org/linux/man-pages/man7/unix.7.html)
- [项目主文档](../README.md)

---

**祝测试顺利!🎉**
