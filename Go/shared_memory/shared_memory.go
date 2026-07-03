package shared_memory

import (
	"encoding/binary"
	"fmt"
	"math/rand"
	"sync"
	"sync/atomic"
	"time"

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
	// 消息包含 data(messageSize) + 4字节checksum
	totalMsgSize := messageSize + 4
	queueSize := 1000

	return &SharedMemory{
		queue:       NewMessageQueue(queueSize),
		messageSize: messageSize,
		bufferPool: sync.Pool{
			New: func() interface{} {
				buf := make([]byte, totalMsgSize)
				return buf
			},
		},
	}
}

// Write 写入数据到共享内存 (data should be messageSize+4 bytes: data + checksum)
func (sm *SharedMemory) Write(data []byte) error {
	totalMsgSize := sm.messageSize + 4
	buf := sm.bufferPool.Get().([]byte)
	copy(buf, data[:totalMsgSize])
	return sm.queue.Send(buf)
}

// Read 从共享内存读取数据
func (sm *SharedMemory) Read() ([]byte, error) {
	data, err := sm.queue.Receive()
	if err != nil {
		return nil, err
	}

	totalMsgSize := sm.messageSize + 4
	// 返回数据副本
	result := make([]byte, totalMsgSize)
	copy(result, data[:totalMsgSize])

	// 将缓冲区返回到对象池
	sm.bufferPool.Put(data)
	return result, nil
}

// Producer 生产者函数
func Producer(id int, sm *SharedMemory, messageCount int, messageSize int,
	wg *sync.WaitGroup, latencies *[]float64, mu *sync.Mutex,
	errorCount *int64, retransmitCount *int64) {
	defer wg.Done()

	data := make([]byte, messageSize)
	for i := 0; i < messageSize; i++ {
		data[i] = byte(i % 256)
	}

	// Per-goroutine random number generator (thread-safe)
	rng := rand.New(rand.NewSource(time.Now().UnixNano()))

	for i := 0; i < messageCount; i++ {
		start := time.Now()

		// Compute checksum on original data
		checksum := utils.ComputeChecksum(data)
		checksumBuf := make([]byte, 4)
		binary.BigEndian.PutUint32(checksumBuf, checksum)

		// Build message: data + checksum
		msgData := make([]byte, messageSize+4)
		copy(msgData, data)
		copy(msgData[messageSize:], checksumBuf)

		// Error injection: corrupt 1 byte in data portion with ErrorRate probability
		if rng.Float64() < utils.ErrorRate {
			corruptPos := rng.Intn(messageSize)
			msgData[corruptPos] ^= 0xFF
			atomic.AddInt64(errorCount, 1)
		}

		if err := sm.Write(msgData); err != nil {
			fmt.Printf("Producer %d write failed: %v\n", id, err)
			continue
		}

		elapsed := time.Since(start).Seconds() * 1000000 // 转换为微秒

		mu.Lock()
		*latencies = append(*latencies, elapsed)
		mu.Unlock()
	}
	// retransmitCount stays 0 for shared_memory
}

// Consumer 消费者函数 - validates checksum
func Consumer(id int, sm *SharedMemory, messageCount int, messageSize int,
	wg *sync.WaitGroup, errorCount *int64) {
	defer wg.Done()

	for i := 0; i < messageCount; i++ {
		msgData, err := sm.Read()
		if err != nil {
			fmt.Printf("Consumer %d read failed: %v\n", id, err)
			continue
		}

		// Validate checksum: last 4 bytes are checksum, rest is data
		dataLen := len(msgData) - 4
		receivedChecksum := binary.BigEndian.Uint32(msgData[dataLen:])
		computedChecksum := utils.ComputeChecksum(msgData[:dataLen])

		if computedChecksum != receivedChecksum {
			atomic.AddInt64(errorCount, 1)
		}
	}
}

// RunTest 运行共享内存IPC测试
func RunTest(producers, consumers, messagesPerProducer, messageSize int) (*utils.PerformanceMetrics, error) {
	fmt.Printf("\n=== Shared Memory Test ===\n")
	fmt.Printf("Producers: %d, Consumers: %d, Messages per Producer: %d, Message Size: %d bytes\n",
		producers, consumers, messagesPerProducer, messageSize)

	sm := NewSharedMemory(messageSize)
	totalMessages := producers * messagesPerProducer
	messagesPerConsumer := totalMessages / consumers

	var wg sync.WaitGroup
	var latencies []float64
	var mu sync.Mutex
	var errorCount int64
	var retransmitCount int64

	startTime := time.Now()

	// 启动消费者
	for i := 0; i < consumers; i++ {
		wg.Add(1)
		go Consumer(i, sm, messagesPerConsumer, messageSize, &wg, &errorCount)
	}

	// 短暂等待让消费者准备好
	time.Sleep(10 * time.Millisecond)

	// 启动生产者
	for i := 0; i < producers; i++ {
		wg.Add(1)
		go Producer(i, sm, messagesPerProducer, messageSize, &wg, &latencies, &mu, &errorCount, &retransmitCount)
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
		IPCType:         "shared_memory",
		Pattern:         fmt.Sprintf("%d_%d", producers, consumers),
		ProducerCount:   producers,
		ConsumerCount:   consumers,
		MessageCount:    totalMessages,
		MessageSize:     messageSize,
		TotalTime:       totalTime,
		Throughput:      throughput,
		AvgLatency:      avgLatency,
		P95Latency:      p95Latency,
		P99Latency:      p99Latency,
		ErrorCount:      int(atomic.LoadInt64(&errorCount)),
		RetransmitCount: int(atomic.LoadInt64(&retransmitCount)),
			Accuracy:       float64(totalMessages-int(atomic.LoadInt64(&errorCount)))*100.0/float64(totalMessages),
		Timestamp:       time.Now().Format("2006-01-02 15:04:05"),
	}

	fmt.Printf("Total Time: %.6f seconds\n", totalTime)
	fmt.Printf("Throughput: %.2f messages/sec\n", throughput)
	fmt.Printf("Average Latency: %.2f microseconds\n", avgLatency)
	fmt.Printf("P95 Latency: %.2f microseconds\n", p95Latency)
	fmt.Printf("P99 Latency: %.2f microseconds\n", p99Latency)
	fmt.Printf("Error Count: %d, Retransmit Count: %d\n", metrics.ErrorCount, metrics.RetransmitCount)
	fmt.Printf("Error Rate: %.2f%%\n\n", float64(metrics.ErrorCount)*100.0/float64(totalMessages))

	return metrics, nil
}
