# Python IPC性能测试程序

测试结果将自动保存到 `../csv/ipc_performance_python.csv`

---

## 📊 项目概述

这是一个Python实现的进程间通信(IPC)性能测试框架,使用标准库实现,无需额外依赖。

**核心功能:**
- ✅ 三种IPC技术:共享内存、Socket IPC、TCP Socket
- ✅ 四种生产者-消费者模式:1:1、N:1、1:N、N:N
- ✅ 全面性能指标:吞吐量、平均/P95/P99延迟
- ✅ CSV输出:结果便于分析和对比
- ✅ 跨平台支持:Windows和Linux/Mac

---

## 🏗️ 项目结构

```
Python/
├── main.py                        # 主程序
├── utils/
│   ├── __init__.py
│   └── metrics.py                 # 性能指标工具类
├── shared_memory/
│   ├── __init__.py
│   └── shared_memory.py           # 共享内存IPC实现
├── socket_ipc/                    # 注意:使用socket_ipc避免与标准库冲突
│   ├── __init__.py
│   └── socket_ipc.py              # Socket IPC实现
├── tcp_ipc/
│   ├── __init__.py
│   └── tcp_ipc.py                 # TCP IPC实现
└── README.md                      # 项目说明文档
```

**重要**: `socket_ipc` 目录名添加了 `_ipc` 后缀,避免与Python标准库 `socket` 模块冲突。

---

## 🚀 运行方法

### 前置要求
- Python 3.6或更高版本
- 无需安装额外的依赖包(仅使用标准库)

---

## 📦 依赖

Python版本使用标准库,**无需安装额外的依赖包**。

**使用的标准库模块:**
- `socket` - 网络通信
- `threading` - 多线程
- `queue` - 队列(用于共享内存模拟)
- `struct` - 二进制数据打包
- `time` - 时间测量
- `csv` - CSV文件操作
- `os` - 文件系统操作

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
结果保存到 `../csv/ipc_performance_python.csv`:

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
- **累加和校验**: `compute_checksum()` 对所有数据字节求和模 2^32，用 `struct.pack('>I')` 大端序编码
- **错误注入**: 每条消息 1% 概率随机翻转一个数据字节（`ERROR_RATE = 0.01`）
- **ACK/NACK**: 消费者校验后通过 `conn.sendall()` 回复单字节应答，生产者通过 `conn.recv(1)` 接收
- **最大重传**: 3 次 (`MAX_RETRANSMIT = 3`)，重传时发送正确的原始数据
- **线格式**: `[4B 头 = messageSize+4, 大端序] [数据] [4B 校验和, 大端序]`

### 共享内存IPC
使用 `queue.Queue` 模拟共享内存通信,通过线程安全队列实现生产者-消费者模式。校验和验证在消费端进行，不计重传。

---

## ❓ 常见问题

### Q1: 导入错误 "module has no attribute"
**原因**: 目录名与标准库模块冲突  
**解决方案**: 
- 已修复:使用 `socket_ipc` 而非 `socket` 作为目录名
- 避免创建与标准库同名的目录(如 `socket`、`os`、`json` 等)

### Q2: GIL导致的性能问题
**原因**: Python的全局解释器锁(GIL)限制多线程并发  
**解决方案**: 
- 这是Python的特性,预期性能会比其他语言慢
- 如需更高性能,可考虑使用 `multiprocessing` 模块

### Q3: "Address already in use"错误
**解决方案**: 
- 等待几分钟让端口释放
- 如有必要,重启计算机

### Q4: 高并发下性能下降明显
**原因**: GIL限制 + 线程切换开销  
**解决方案**: 
- 这是正常现象
- 建议使用多进程替代多线程以获得更好性能

---

## 🔄 与其他语言版本对比

| 方面 | Go | C++ | Java | Python |
|------|-----|-----|------|--------|
| **并发模型** | Goroutines+Channels | std::thread | Thread+BlockingQueue | threading+queue |
| **内存管理** | GC | RAII | GC | GC |
| **性能** | 良好 | 最优 | 良好 | 较慢(GIL) |
| **易用性** | 简单 | 复杂 | 中等 | 简单 |

**Python版本特点:**
1. 使用标准库,无需额外依赖
2. 受GIL限制,多线程并发性能受限
3. 代码简洁,易于理解和修改
4. 适合快速原型开发和教学演示

---

## ⚠️ 注意事项

1. **模块命名**: 禁止创建与标准库模块同名的目录或包
2. **GIL限制**: 高并发下性能受限,这是Python的特性
3. **测试环境**: 建议在相对空闲的系统上运行测试
4. **多次测试**: 建议多次运行取平均值以减少误差

---

## 🚀 扩展方向

1. 使用 `multiprocessing` 模块实现真正的多进程并行
2. 添加 `asyncio` 异步IO支持
3. 使用 `numpy` 加速数值计算
4. 集成 `matplotlib` 实时可视化
5. 添加更多IPC机制:管道、消息队列等

---

## 📚 参考资料

- [Python官方文档](https://docs.python.org/)
- [threading模块](https://docs.python.org/3/library/threading.html)
- [queue模块](https://docs.python.org/3/library/queue.html)
- [项目主文档](../README.md)

---

**祝测试顺利!🎉**
