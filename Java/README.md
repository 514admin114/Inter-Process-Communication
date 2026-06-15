# Java IPC性能测试程序

测试结果将自动保存到 `../csv/ipc_performance_java.csv`

---

## 📊 项目概述

这是一个Java实现的进程间通信(IPC)性能测试框架,与Go、C++、Python版本保持相同的测试结构和功能。

**核心功能:**
- ✅ 三种IPC技术:共享内存、Socket IPC、TCP Socket
- ✅ 四种生产者-消费者模式:1:1、N:1、1:N、N:N
- ✅ 全面性能指标:吞吐量、平均/P95/P99延迟
- ✅ CSV输出:结果便于分析和对比
- ✅ 跨平台支持:Windows和Linux/Mac

---

## 🏗️ 项目结构

```
Java/
├── src/
│   ├── Main.java                        # 主程序
│   └── ipc/                   
│       ├── utils/
│       │   ├── PerformanceMetrics.java  # 性能指标类
│       │   └── MetricsUtils.java        # 工具函数
│       ├── shared_memory/
│       │   └── SharedMemory.java        # 共享内存IPC实现
│       ├── socket/
│       │   └── SocketIPC.java           # Socket IPC实现
│       └── tcp_ipc/
│           └── TcpIPC.java              # TCP IPC实现
└── README.md                     # 项目说明文档
```

---

## 🔧 编译和运行

### 前置要求
- JDK 8或更高版本
- 确保JAVA_HOME环境变量正确配置

### 手动编译和运行

```bash
# 进入Java目录
cd Java

# 编译所有Java文件
javac -d bin src/Main.java src/ipc/utils/*.java src/ipc/shared_memory/*.java src/ipc/socket/*.java src/ipc/tcp_ipc/*.java

# 运行主程序
java -cp bin Main

```

**注意**: 
- 使用 `-d bin` 参数指定输出目录,生成正确的包结构
- 运行时使用 `-cp bin` 指定类路径

---

## 📈 测试配置

### 默认配置(简化版)
- **消息大小**: 64字节、1KB (2种)
- **生产者数量**: 1、2、4 (3种)
- **消费者数量**: 1、2、4 (3种)
- **每个生产者消息数**: 500
- **总测试数**: 约54个测试
- **预计时间**: 5-10分钟

### 完整配置
修改 `src/Main.java` 中的配置部分:
```java
config.messageSizes = Arrays.asList(64, 256, 1024, 4096); // 4种大小
config.producerCounts = Arrays.asList(1, 2, 4, 8);        // 4种数量
config.consumerCounts = Arrays.asList(1, 2, 4, 8);        // 4种数量
config.messagesPerProd = 1000;                             // 1000条消息
// 总计:约192个测试,20-40分钟
```

---

## 📊 输出结果

### CSV文件格式
结果保存到 `../csv/ipc_performance_java.csv`:

```csv
Timestamp,IPC_Type,Pattern,Producer_Count,Consumer_Count,Message_Count,Message_Size,Total_Time_Seconds,Throughput_Msg_Per_Sec,Avg_Latency_Microseconds,P95_Latency_Microseconds,P99_Latency_Microseconds,Success
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

### 共享内存IPC
使用阻塞队列(`BlockingQueue`)模拟共享内存通信,通过线程安全队列实现生产者-消费者模式。

### Socket IPC
使用TCP Socket进行本地回环通信,支持长连接复用。

### TCP IPC
与Socket IPC类似,但更明确地使用TCP协议进行进程间通信。

---

## ❓ 常见问题

### Q1: 编译错误 "找不到符号"
**原因**: 源文件路径不正确或未编译所有依赖文件  
**解决方案**: 
```bash
# 确保一次性编译所有相关文件
javac -d out src/ipc/*.java src/ipc/utils/*.java src/ipc/shared_memory/*.java src/ipc/socket/*.java src/ipc/tcp_ipc/*.java
```

### Q2: 运行时 "ClassNotFoundException"
**原因**: 类路径设置不正确  
**解决方案**: 
```bash
# 确保使用-cp参数指定输出目录
java -cp out ipc.Main
```

### Q3: "Address already in use"错误
**解决方案**: 
- 等待几分钟让端口释放
- 如有必要,重启计算机

### Q4: 首次运行较慢
**原因**: JVM JIT编译和类加载  
**解决方案**: 
- 首次运行正常,后续运行会更快
- 多次运行取平均值

---

## 🔄 与其他语言版本对比

| 方面 | Go | C++ | Java | Python |
|------|-----|-----|------|--------|
| **并发模型** | Goroutines+Channels | std::thread | Thread+BlockingQueue | threading+queue |
| **内存管理** | GC | RAII | GC | GC |
| **性能** | 良好 | 最优 | 良好 | 较慢(GIL) |
| **易用性** | 简单 | 复杂 | 中等 | 简单 |

**Java版本特点:**
1. 使用`Thread`和`BlockingQueue`实现并发
2. JVM的JIT编译可能在首次运行时较慢
3. 高并发下可通过对象池和无锁集合优化性能

---

## ⚠️ 注意事项

1. **文件组织**: 一个public类必须定义在与其类名相同的独立文件中
2. **包声明**: 所有Java文件的包声明应该以 `ipc` 开头,不包含 `src` 前缀
3. **编译顺序**: 多文件编译时需一次性编译所有相关源文件
4. **类路径**: 运行时需用 `-cp` 参数指定类路径指向输出目录
5. **资源清理**: 正确关闭socket和线程池

---

## 📚 参考资料

- [Java官方文档](https://docs.oracle.com/javase/)
- [Java并发编程](https://docs.oracle.com/javase/tutorial/essential/concurrency/)
- [项目主文档](../README.md)

---

**祝测试顺利!🎉**
