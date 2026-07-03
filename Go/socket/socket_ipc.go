package socket

import (
	"encoding/binary"
	"fmt"
	"io"
	"math/rand"
	"net"
	"os"
	"runtime"
	"sync"
	"sync/atomic"
	"time"

	"ipc/utils"
)

// SocketIPC 使用Socket进行进程间通信
type SocketIPC struct {
	network     string
	address     string
	messageSize int
}

// NewSocketIPC 创建Socket IPC实例
func NewSocketIPC(messageSize int) *SocketIPC {
	var network, address string

	if runtime.GOOS == "windows" {
		// Windows使用TCP localhost
		network = "tcp"
		address = "127.0.0.1:0" // 端口0表示自动分配
	} else {
		// Unix/Linux/Mac使用Unix Socket
		network = "unix"
		address = fmt.Sprintf("/tmp/ipc_test_%d.sock", time.Now().UnixNano())
	}

	return &SocketIPC{
		network:     network,
		address:     address,
		messageSize: messageSize,
	}
}

// StartServer 启动服务器监听
func (s *SocketIPC) StartServer() (net.Listener, error) {
	listener, err := net.Listen(s.network, s.address)
	if err != nil {
		return nil, fmt.Errorf("启动监听失败: %v", err)
	}

	// 获取实际监听的地址
	if s.address == "127.0.0.1:0" {
		s.address = listener.Addr().String()
		fmt.Printf("服务器监听地址: %s\n", s.address)
	}

	return listener, nil
}

// sendAll sends exactly len(data) bytes
func sendAll(conn net.Conn, data []byte) error {
	total := 0
	for total < len(data) {
		n, err := conn.Write(data[total:])
		if err != nil {
			return err
		}
		total += n
	}
	return nil
}

// recvAll receives exactly n bytes
func recvAll(conn net.Conn, n int) ([]byte, error) {
	buf := make([]byte, n)
	_, err := io.ReadFull(conn, buf)
	return buf, err
}

// Producer 生产者函数（使用长连接 + ACK/NACK重传）
func Producer(id int, address string, network string, messageCount int, messageSize int,
	wg *sync.WaitGroup, latencies *[]float64, mu *sync.Mutex,
	errorCount *int64, retransmitCount *int64) {
	defer wg.Done()

	data := make([]byte, messageSize)
	for i := 0; i < messageSize; i++ {
		data[i] = byte(i % 256)
	}

	// 建立长连接，复用整个测试过程
	var conn net.Conn
	var err error

	maxRetries := 10
	for retry := 0; retry < maxRetries; retry++ {
		conn, err = net.Dial(network, address)
		if err == nil {
			break
		}
		time.Sleep(time.Duration(retry+1) * 10 * time.Millisecond)
	}

	if err != nil {
		fmt.Printf("Producer %d 无法建立连接: %v\n", id, err)
		return
	}
	defer conn.Close()

	// Per-goroutine random number generator (thread-safe)
	rng := rand.New(rand.NewSource(time.Now().UnixNano()))

	// 复用同一个连接发送所有消息
	for i := 0; i < messageCount; i++ {
		start := time.Now()

		// Compute checksum on original data
		checksum := utils.ComputeChecksum(data)
		totalPayload := uint32(messageSize + 4)

		// Error injection: corrupt 1 byte in data with ErrorRate probability
		sendData := make([]byte, messageSize)
		copy(sendData, data)
		if rng.Float64() < utils.ErrorRate {
			corruptPos := rng.Intn(messageSize)
			sendData[corruptPos] ^= 0xFF
		}

		// Pre-allocate merged wire buffer: [4B header][data][4B checksum]
		wireBuf := make([]byte, 4+messageSize+4)
		// Pre-fill header and checksum (unchanged across retransmissions)
		binary.BigEndian.PutUint32(wireBuf[0:4], totalPayload)
		binary.BigEndian.PutUint32(wireBuf[4+messageSize:], checksum)

		// Retransmission loop
		delivered := false
		retransmits := 0
		for attempt := 0; attempt <= utils.MaxRetransmit && !delivered; attempt++ {
			if attempt > 0 {
				// Retransmit: send original (correct) data
				copy(sendData, data)
				retransmits++
			}

			// Copy data into merged buffer and send everything once
			copy(wireBuf[4:4+messageSize], sendData)
			if err := sendAll(conn, wireBuf); err != nil {
				break
			}

			// Receive ACK/NACK (1 byte)
			ackBuf, err := recvAll(conn, 1)
			if err != nil {
				break
			}

			if ackBuf[0] == 0x01 {
				delivered = true
			}
			// If NACK (0x00), loop will retry
		}

		if retransmits > 0 {
			atomic.AddInt64(retransmitCount, int64(retransmits))
		}

		elapsed := time.Since(start).Seconds() * 1000000 // 转换为微秒

		mu.Lock()
		*latencies = append(*latencies, elapsed)
		mu.Unlock()
	}
}

// handleConnection 处理单个连接：接收消息，校验checksum，发送ACK/NACK
func handleConnection(conn net.Conn, messageSize int, receivedCount *int64,
	errorCount *int64, serverWg *sync.WaitGroup, expectedMessages int) {
	defer conn.Close()
	defer serverWg.Done()

	successCount := 0
	for successCount < expectedMessages {
		// Read 4-byte header: total payload size = messageSize + 4
		headerBuf, err := recvAll(conn, 4)
		if err != nil {
			return
		}
		totalPayload := binary.BigEndian.Uint32(headerBuf)
		dataLen := int(totalPayload) - 4

		// Read data + checksum as one buffer
		payload, err := recvAll(conn, int(totalPayload))
		if err != nil {
			return
		}

		// Extract checksum (last 4 bytes) and validate
		receivedChecksum := binary.BigEndian.Uint32(payload[dataLen:])
		computedChecksum := utils.ComputeChecksum(payload[:dataLen])

		var ack byte
		if computedChecksum == receivedChecksum {
			ack = 0x01 // ACK
			atomic.AddInt64(receivedCount, 1)
			successCount++
		} else {
			ack = 0x00 // NACK
			atomic.AddInt64(errorCount, 1)
		}

		// Send ACK/NACK
		conn.Write([]byte{ack})
	}
}

// RunTest 运行Socket IPC测试
func RunTest(producers, consumers, messagesPerProducer, messageSize int) (*utils.PerformanceMetrics, error) {
	fmt.Printf("\n=== Socket IPC测试 ===\n")
	fmt.Printf("生产者: %d, 消费者: %d, 每个生产者消息数: %d, 消息大小: %d字节\n",
		producers, consumers, messagesPerProducer, messageSize)

	socketIPC := NewSocketIPC(messageSize)
	totalMessages := producers * messagesPerProducer

	listener, err := socketIPC.StartServer()
	if err != nil {
		return nil, err
	}

	// 清理Unix Socket文件
	if runtime.GOOS != "windows" {
		defer os.Remove(socketIPC.address)
	}

	var producerWg sync.WaitGroup
	var serverWg sync.WaitGroup
	var latencies []float64
	var mu sync.Mutex
	var receivedCount int64
	var errorCount int64
	var retransmitCount int64

	startTime := time.Now()

	// 启动服务器接受连接（在单独的goroutine中）
	acceptDone := make(chan struct{})
	serverReady := make(chan struct{}) // 信号：服务器已准备好

	go func() {
		defer close(acceptDone)
		close(serverReady) // 立即发出就绪信号

		// 接受producers个连接（每个Producer一个连接）
		for i := 0; i < producers; i++ {
			conn, err := listener.Accept()
			if err != nil {
				fmt.Printf("Accept错误 (已接受 %d/%d 个连接): %v\n", i, producers, err)
				break
			}
			serverWg.Add(1)
			go handleConnection(conn, messageSize, &receivedCount, &errorCount, &serverWg, messagesPerProducer)
		}
	}()

	// 等待服务器准备好
	<-serverReady
	// 额外等待确保完全就绪
	time.Sleep(50 * time.Millisecond)

	// 启动生产者
	for i := 0; i < producers; i++ {
		producerWg.Add(1)
		go Producer(i, socketIPC.address, socketIPC.network, messagesPerProducer, messageSize,
			&producerWg, &latencies, &mu, &errorCount, &retransmitCount)
	}

	// 等待所有生产者完成
	producerWg.Wait()

	// 给最后的消息一些时间被Accept
	time.Sleep(100 * time.Millisecond)

	// 关闭listener，停止接受新连接
	listener.Close()

	// 等待Accept goroutine结束
	<-acceptDone

	// 等待所有已接受的连接处理完成（带超时）
	done := make(chan struct{})
	go func() {
		serverWg.Wait()
		close(done)
	}()

	select {
	case <-done:
		// 正常完成
	case <-time.After(30 * time.Second):
		fmt.Printf("警告: 超时，仅接收到 %d/%d 条消息\n", atomic.LoadInt64(&receivedCount), totalMessages)
	}

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
		IPCType:         "socket",
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

	fmt.Printf("总耗时: %.6f秒\n", totalTime)
	fmt.Printf("吞吐量: %.2f 消息/秒\n", throughput)
	fmt.Printf("平均延迟: %.2f 微秒\n", avgLatency)
	fmt.Printf("P95延迟: %.2f 微秒\n", p95Latency)
	fmt.Printf("P99延迟: %.2f 微秒\n", p99Latency)
	fmt.Printf("错误数: %d, 重传数: %d\n", metrics.ErrorCount, metrics.RetransmitCount)
	fmt.Printf("数据错误率: %.2f%%\n\n", float64(metrics.ErrorCount)*100.0/float64(totalMessages))

	return metrics, nil
}
