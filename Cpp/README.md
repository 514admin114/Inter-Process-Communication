# C++ IPC性能测试程序


测试结果将自动保存到 `../csv/ipc_performance_cpp.csv`

---

## 📊 项目概述

这是一个C++实现的进程间通信(IPC)性能测试框架,支持三种IPC方式和多种并发模式的性能测试。

**核心功能:**
- ✅ 三种IPC技术:共享内存、Socket IPC、TCP Socket
- ✅ 四种生产者-消费者模式:1:1、N:1、1:N、N:N
- ✅ 全面性能指标:吞吐量、平均/P95/P99延迟
- ✅ CSV输出:结果便于分析和对比
- ✅ 跨平台支持:Windows和Linux/Mac

---

## 🏗️ 项目结构

```
Cpp/
├── main.cpp                      # 主程序入口
├── utils/
│   └── metrics.h                 # 性能指标和CSV工具
├── shared_memory/
│   └── shared_memory.h           # 共享内存IPC实现
├── socket/
│   └── socket_ipc.h              # Socket IPC实现
└── tcp_ipc/
    └── tcp_ipc.h                 # TCP Socket IPC实现
```

---

## 🔧 构建和运行

### 前置要求
- C++17兼容编译器(GCC 7+、Clang 5+、MSVC 2017+)
- Windows用户需要链接ws2_32库


### 手动编译

**Windows (MinGW/GCC):**
```bash
g++ main.cpp -o main.exe -lws2_32
.\main.exe
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
结果保存到 `../csv/ipc_performance_cpp.csv`:

```csv
Timestamp,IPC_Type,Pattern,Producer_Count,Consumer_Count,Message_Count,Message_Size,Total_Time_Seconds,Throughput_Msg_Per_Sec,Avg_Latency_Microseconds,P95_Latency_Microseconds,P99_Latency_Microseconds,Error_Count,Retransmit_Count,Success
```

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

## 💡 实现细节

### 数据校验与重传
Socket/TCP 通信实现了完整的数据完整性保障机制：
- **累加和校验**: `computeChecksum()` 对所有数据字节求和模 2^32，附加到消息末尾
- **错误注入**: 每条消息 1% 概率随机翻转一个数据字节（`ERROR_RATE = 0.01`）
- **ACK/NACK**: 消费者校验后回复单字节应答，生产者根据应答决定重传
- **最大重传**: 3 次 (`MAX_RETRANSMIT = 3`)，重传时发送正确的原始数据
- **线格式**: `[4B 头 = messageSize+4, 大端序] [数据] [4B 校验和, 大端序]`

### 共享内存
使用带互斥锁和条件变量的线程安全队列进行同步。校验和验证在消费端进行，不计重传。

---

## ❓ 常见问题

### Q1: 找不到头文件错误
**解决方案**: 编译时添加 `-I.` 参数
```bash
g++ -I. main.cpp -o main.exe -lws2_32
```

### Q2: Windows链接错误
**错误**: `undefined reference to 'WSAStartup'`  
**解决方案**: 链接ws2_32库
```bash
g++ -I. main.cpp -o main.exe -lws2_32
```

### Q3: "Address already in use"
**解决方案**: 等待几分钟让端口释放,或重启计算机

---

## 🔄 与其他语言版本对比

| 方面 | Go | C++ | Java | Python |
|------|-----|-----|------|--------|
| **并发模型** | Goroutines | std::thread | Thread | threading |
| **内存管理** | GC | RAII | GC | GC |
| **性能** | 良好 | 最优 | 良好 | 较慢 |
| **易用性** | 简单 | 复杂 | 中等 | 简单 |

**预期性能特征:**
1. **共享内存**: C++最快(无GC开销)
2. **Socket/TCP**: 性能相似
3. **延迟**: C++尾部延迟(P99)更低

---

## 📝 注意事项

1. **线程安全**: 所有共享数据都用互斥锁保护
2. **连接复用**: 生产者保持长连接避免端口耗尽
3. **错误处理**: 失败的测试记录为success=false
4. **资源清理**: 正确清理socket和线程

---

## 📚 参考资料

- [C++参考文档](https://en.cppreference.com/)
- [BSD Sockets](https://man7.org/linux/man-pages/man7/socket.7.html)
- [项目主文档](../README.md)

---

**祝测试顺利!🎉**
