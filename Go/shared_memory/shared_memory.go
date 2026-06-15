package shared_memory

import (
	"fmt"
	"sync"
	"time"
	"unsafe"

	"ipc/utils"
)

// MessageQueue 消息队列，用于生产者和消费者之间的通信
type MessageQueue struct {
	messages chan []byte
	closed   chan struct{}
}

// NewMessageQueue 创建消息队列
func NewMessageQueue(bufferSize int) *MessageQueue {
	return &MessageQueue{
		messages: make(chan []byte, bufferSize),
		closed:   make(chan struct{}),
	}
}

// Send 发送消息
func (mq *MessageQueue) Send(data []byte) error {
	select {
	case mq.messages <- data:
		return nil
	case <-mq.closed:
		return fmt.Errorf("队列已关闭")
	}
}

// Receive 接收消息
func (mq *MessageQueue) Receive() ([]byte, error) {
	select {
	case data, ok := <-mq.messages:
		if !ok {
			return nil, fmt.Errorf("队列已关闭")
		}
		return data, nil
	case <-mq.closed:
		return nil, fmt.Errorf("队列已关闭")
	}
}

// Close 关闭队列
func (mq *MessageQueue) Close() {
	close(mq.closed)
	close(mq.messages)
}

// SharedMemory IPC使用共享内存实现（基于channel的消息队列）
type SharedMemory struct {
	queue       *MessageQueue
	messageSize int
	bufferPool  sync.Pool
}

// NewSharedMemory 创建共享内存实例
func NewSharedMemory(messageSize int) *SharedMemory {
	// 设置缓冲区大小为1000，足够容纳突发消息
	queueSize := 1000
	
	return &SharedMemory{
		queue:       NewMessageQueue(queueSize),
		messageSize: messageSize,
		bufferPool: sync.Pool{
			New: func() interface{} {
				buf := make([]byte, messageSize)
				return buf
			},
		},
	}
}

// Write 写入数据到共享内存
func (sm *SharedMemory) Write(data []byte) error {
	// 从对象池获取缓冲区
	buf := sm.bufferPool.Get().([]byte)
	copy(buf, data)
	
	// 发送到队列
	return sm.queue.Send(buf)
}

// Read 从共享内存读取数据
func (sm *SharedMemory) Read() ([]byte, error) {
	data, err := sm.queue.Receive()
	if err != nil {
		return nil, err
	}
	
	// 将缓冲区返回到对象池
	sm.bufferPool.Put(data)
	
	// 返回数据副本
	result := make([]byte, len(data))
	copy(result, data)
	return result, nil
}

// Producer 生产者函数
func Producer(id int, sm *SharedMemory, messageCount int, messageSize int, wg *sync.WaitGroup, latencies *[]float64, mu *sync.Mutex) {
	defer wg.Done()

	data := make([]byte, messageSize)
	for i := 0; i < messageSize; i++ {
		data[i] = byte(i % 256)
	}

	for i := 0; i < messageCount; i++ {
		start := time.Now()
		
		if err := sm.Write(data); err != nil {
			fmt.Printf("Producer %d 写入失败: %v\n", id, err)
			continue
		}

		elapsed := time.Since(start).Seconds() * 1000000 // 转换为微秒
		
		mu.Lock()
		*latencies = append(*latencies, elapsed)
		mu.Unlock()
	}
}

// Consumer 消费者函数
func Consumer(id int, sm *SharedMemory, messageCount int, wg *sync.WaitGroup) {
	defer wg.Done()

	for i := 0; i < messageCount; i++ {
		if _, err := sm.Read(); err != nil {
			fmt.Printf("Consumer %d 读取失败: %v\n", id, err)
			continue
		}
	}
}

// RunTest 运行共享内存IPC测试
func RunTest(producers, consumers, messagesPerProducer, messageSize int) (*utils.PerformanceMetrics, error) {
	fmt.Printf("\n=== 共享内存测试 ===\n")
	fmt.Printf("生产者: %d, 消费者: %d, 每个生产者消息数: %d, 消息大小: %d字节\n", 
		producers, consumers, messagesPerProducer, messageSize)

	sm := NewSharedMemory(messageSize)
	totalMessages := producers * messagesPerProducer
	messagesPerConsumer := totalMessages / consumers

	var wg sync.WaitGroup
	var latencies []float64
	var mu sync.Mutex

	startTime := time.Now()

	// 启动消费者
	for i := 0; i < consumers; i++ {
		wg.Add(1)
		go Consumer(i, sm, messagesPerConsumer, &wg)
	}

	// 短暂等待让消费者准备好
	time.Sleep(10 * time.Millisecond)

	// 启动生产者
	for i := 0; i < producers; i++ {
		wg.Add(1)
		go Producer(i, sm, messagesPerProducer, messageSize, &wg, &latencies, &mu)
	}

	// 等待所有goroutine完成
	wg.Wait()
	
	endTime := time.Now()

	totalTime := endTime.Sub(startTime).Seconds()
	throughput := float64(totalMessages) / totalTime

	// 计算延迟统计
	var avgLatency float64
	for _, lat := range latencies {
		avgLatency += lat
	}
	if len(latencies) > 0 {
		avgLatency /= float64(len(latencies))
	}

	p95Latency := utils.CalculatePercentile(latencies, 95)
	p99Latency := utils.CalculatePercentile(latencies, 99)

	metrics := &utils.PerformanceMetrics{
		IPCType:        "shared_memory",
		Pattern:        fmt.Sprintf("%d_%d", producers, consumers),
		ProducerCount:  producers,
		ConsumerCount:  consumers,
		MessageCount:   totalMessages,
		MessageSize:    messageSize,
		TotalTime:      totalTime,
		Throughput:     throughput,
		AvgLatency:     avgLatency,
		P95Latency:     p95Latency,
		P99Latency:     p99Latency,
		Timestamp:      time.Now().Format("2006-01-02 15:04:05"),
	}

	fmt.Printf("总耗时: %.6f秒\n", totalTime)
	fmt.Printf("吞吐量: %.2f 消息/秒\n", throughput)
	fmt.Printf("平均延迟: %.2f 微秒\n", avgLatency)
	fmt.Printf("P95延迟: %.2f 微秒\n", p95Latency)
	fmt.Printf("P99延迟: %.2f 微秒\n\n", p99Latency)

	return metrics, nil
}

// GetUnsafeSize 获取unsafe.Pointer的大小（用于验证）
func GetUnsafeSize() uintptr {
	return unsafe.Sizeof(unsafe.Pointer(nil))
}
