# 进程间通信 (IPC) 性能测试

## 项目概述

本项目实现了四种主流编程语言（**Go**、**C++**、**Java**、**Python**）的进程间通信（IPC）性能测试框架，用于对比不同语言在相同IPC场景下的性能表现。

## 🎯 项目目标

1. **性能对比**：横向对比四种语言在不同IPC方式下的性能差异
2. **学习参考**：提供多语言IPC实现的参考代码
3. **基准测试**：建立可重复的IPC性能基准测试框架

## 📋 支持的IPC方式

所有语言版本都实现了以下三种IPC方式：

### 1. 共享内存 (Shared Memory)
- 最快的IPC方式，适合大量数据传输
- 各语言使用各自的并发原语实现

### 2. Socket IPC
- Unix Domain Socket (Linux/Mac) 或 TCP localhost (Windows)
- 适用于本地进程间通信

### 3. TCP Socket
- 标准TCP网络通信
- 适用于分布式系统或跨机器通信

## 🏗️ 项目结构

```
Inter-Process-Communication/
├── 📖 核心文档
│   ├── README.md                    # 项目总览(本文件)
│   └── README_IPC_Analysis.md       # IPC分析器完整文档
│
├── 📊 数据分析器
│   ├── ipc_analyzer.py              # Streamlit分析器主程序
│   ├── ipc_analysis_start.py        # 启动器脚本
│   └── requirements.txt             # Python依赖列表
│
├── 🧪 测试数据
│   └── csv/
│       ├── ipc_performance_go.csv
│       ├── ipc_performance_cpp.csv
│       ├── ipc_performance_java.csv
│       └── ipc_performance_python.csv
│
├── 🔵 Go语言实现
│   ├── main.go                      # 主程序
│   ├── go.mod                       # Go模块文件
│   ├── shared_memory/               # 共享内存IPC
│   ├── socket/                      # Socket IPC
│   ├── tcp_ipc/                     # TCP IPC
│   ├── utils/                       # 工具函数
│   └── README.md                    # Go版本说明
│
├── ⚫ C++语言实现
│   ├── main.cpp                     # 主程序
│   ├── shared_memory/               # 共享内存IPC
│   ├── socket/                      # Socket IPC
│   ├── tcp_ipc/                     # TCP IPC
│   ├── utils/                       # 工具函数
│   └── README.md                    # C++版本说明
│
├── ☕ Java语言实现
│   ├── src/                         # 源代码目录
│   │   ├── Main.java                # 主程序
│   │   └── ipc/                    
│   │       ├── utils/               # 工具类
│   │       ├── shared_memory/       # 共享内存IPC
│   │       ├── socket/              # Socket IPC
│   │       └── tcp_ipc/             # TCP IPC
│   └── README.md                    # Java版本说明
│
└── 🐍 Python语言实现
    ├── main.py                      # 主程序
    ├── shared_memory/               # 共享内存IPC
    ├── socket_ipc/                  # Socket IPC(避免与标准库冲突)
    ├── tcp_ipc/                     # TCP IPC
    ├── utils/                       # 工具函数
    └── README.md                    # Python版本说明
```

---

## 🚀 快速开始

### 🔵 Go版本
```bash
cd Go
go run main.go
```
📖 [Go版本详细说明](Go/README.md)

### ⚫ C++版本

**Windows:**
```bash
g++ main.cpp -o main.exe -lws2_32
.\main.exe
```

**Linux/Mac:**
```bash
g++ -std=c++17 -O2 -I. -pthread -o ipc_test main.cpp
./ipc_test
```

📖 [C++版本详细说明](Cpp/README.md)

### ☕ Java版本

```bash
# 进入Java目录
cd Java

# 编译所有Java文件
javac -d bin src/Main.java src/ipc/utils/*.java src/ipc/shared_memory/*.java src/ipc/socket/*.java src/ipc/tcp_ipc/*.java

# 运行主程序
java -cp bin Main
```
📖 [Java版本详细说明](Java/README.md)

### 🐍 Python版本

**Windows:**
```bash
cd Python
python main.py
```

**Linux/Mac:**
```bash
cd Python
python3 main.py
```
📖 [Python版本详细说明](Python/README.md)

---

## 📊 数据分析器

完成性能测试后，可以使用内置的 Streamlit 数据分析器对结果进行可视化分析。

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动分析器

```bash
streamlit run ipc_analyzer.py
```

### 功能特性
- 📊 **横向对比**: 同语言不同IPC方式性能比较
- 📉 **纵向对比**: 跨语言相同IPC方式性能比较
- 🎯 **综合排名**: TOP 10性能和最佳实践推荐
- 📋 **数据导出**: 灵活的筛选和CSV导出

📖 [查看IPC分析器完整文档](README_IPC_Analysis.md)

---

## 📊 测试配置

### 默认配置（简化版）

- **消息大小**: 64字节, 1024字节
- **生产者数量**: 1, 2, 4
- **消费者数量**: 1, 2, 4
- **每个生产者消息数**: 500
- **总测试数**: 约54个测试
- **预计时间**: 5-10分钟

### 完整配置

如需完整测试，在各语言的main文件中修改配置：

- **消息大小**: 64, 256, 1024, 4096字节
- **生产者数量**: 1, 2, 4, 8
- **消费者数量**: 1, 2, 4, 8
- **每个生产者消息数**: 1000
- **总测试数**: 约192个测试
- **预计时间**: 20-40分钟

## 📈 性能指标

每个测试收集以下指标：

- **吞吐量 (Throughput)**: 每秒处理的消息数 (msg/sec)
- **平均延迟 (Avg Latency)**: 消息处理的平均延迟 (μs)
- **P95延迟**: 95%消息的延迟上限 (μs)
- **P99延迟**: 99%消息的延迟上限 (μs)
- **总耗时 (Total Time)**: 测试执行总时间 (秒)

## 📁 输出结果

测试结果保存到CSV文件：

- Go: `csv/data/ipc_performance_go.csv`
- C++: `csv/data/ipc_performance_cpp.csv`
- Java: `csv/data/ipc_performance_java.csv`
- Python: `csv/data/ipc_performance_python.csv`

### CSV格式

```csv
Timestamp,IPC_Type,Pattern,Producer_Count,Consumer_Count,Message_Count,Message_Size,Total_Time_Seconds,Throughput_Msg_Per_Sec,Avg_Latency_Microseconds,P95_Latency_Microseconds,P99_Latency_Microseconds,Success
```

## 📊 性能数据可视化分析

完成测试后,可以使用Streamlit分析器对结果进行可视化分析:

```bash
# 安装依赖
pip install streamlit pandas plotly numpy

# 启动分析器
streamlit run ipc_analyzer.py
```

详细使用说明请查看:
- 📖 [IPC分析器完整文档](README_IPC_Analysis.md)

分析器功能:
- 📊 **横向对比**: 同语言不同IPC方式性能比较
- 📉 **纵向对比**: 跨语言相同IPC方式性能比较
- 🎯 **综合排名**: TOP 10性能和最佳实践推荐
- 📋 **数据导出**: 灵活的筛选和CSV导出

---

## 🔍 预期性能对比

基于语言特性，预期性能排序：

### 吞吐量（从高到低）
1. **C++** - 最优性能，无GC开销
2. **Go** - 优秀性能，轻量级goroutine
3. **Java** - 良好性能，JVM优化
4. **Python** - 受GIL限制

### 延迟（从低到高）
1. **C++** - 最低延迟
2. **Go** - 低延迟
3. **Java** - 中等延迟
4. **Python** - 较高延迟

### 开发效率（从高到低）
1. **Python** - 最快速开发
2. **Go** - 简洁高效
3. **Java** - 成熟生态
4. **C++** - 复杂度高

## 🛠️ 技术栈

| 语言 | 版本要求 | 主要特性 |
|------|---------|---------|
| Go | 1.16+ | Goroutines, Channels |
| C++ | C++17 | std::thread, RAII |
| Java | JDK 8+ | Threads, BlockingQueue |
| Python | 3.6+ | threading, queue |

## 📖 详细文档

- [Go版本说明](Go/README.md)
- [C++版本说明](Cpp/README.md)
- [Java版本说明](Java/README.md)
- [Python版本说明](Python/README.md)

## ⚠️ 注意事项

1. **环境一致性**: 建议在相同硬件和操作系统环境下运行各版本进行公平对比
2. **首次运行**: 首次运行可能较慢（JIT编译、缓存预热等），建议多次运行取平均值
3. **资源清理**: 程序会自动清理临时文件和socket连接
4. **端口占用**: 如遇"Address already in use"错误，等待片刻后重试

## 🔧 故障排除

### Java编译错误
确保Java环境变量正确配置：
```bash
java -version
javac -version
```

### Python导入错误
确保在Python目录下运行：
```bash
cd Python
python main.py
```

### C++链接错误（Windows）
确保链接ws2_32库：
```bash
g++ main.cpp -o main.exe -lws2_32
```

## 📝 许可证

本项目仅供学习和研究使用。

## 🤝 贡献

欢迎提交Issue和Pull Request来改进项目！

## 📚 参考资料

- [Go官方文档](https://golang.org/doc/)
- [C++参考文档](https://en.cppreference.com/)
- [Java官方文档](https://docs.oracle.com/javase/)
- [Python官方文档](https://docs.python.org/)

## 📧 联系方式

如有问题或建议，请提交Issue。

---

**祝测试顺利！🎉**
