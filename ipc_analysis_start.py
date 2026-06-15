#!/usr/bin/env python
#-*- coding:utf-8 -*-
"""
IPC性能分析系统启动器

功能概述:
1. 依赖管理:
   - 自动检查并安装streamlit、pandas、plotly等必要依赖
   - 确保环境配置完整后才允许后续操作

2. 数据验证:
   - 检查CSV数据文件是否存在
   - 提供数据生成指引(如果数据不存在)

3. 系统启动界面:
   - Streamlit Web界面提供图形化操作入口
   - 清晰的按钮控制分析器启动
   - 实时显示操作进度和状态信息

4. 流程自动化:
   - 自动处理依赖安装和分析器启动的完整流程
   - 错误处理和状态管理,确保系统稳定运行
   - 会话状态管理,避免重复安装依赖

5. 项目集成:
   - 作为整个IPC性能分析项目的入口点
   - 协调数据加载和分析器的运行
   - 提供用户友好的操作说明和功能介绍
"""

import streamlit as st
import subprocess
import sys
import os
from pathlib import Path

def install_requirements():
    """安装项目依赖"""
    req_file = Path("requirements.txt")
    if req_file.exists():
        st.info("正在安装项目依赖...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            st.success("依赖安装完成!")
        except subprocess.CalledProcessError:
            st.error("依赖安装失败,请手动安装")
            return False
    else:
        # 如果没有requirements.txt,直接安装必要的包
        st.info("正在安装必要的依赖包...")
        try:
            packages = ['streamlit', 'pandas', 'plotly']
            for package in packages:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            st.success("依赖安装完成!")
        except subprocess.CalledProcessError:
            st.error("依赖安装失败,请手动安装: pip install streamlit pandas plotly")
            return False
    return True

def check_csv_files():
    """检查CSV数据文件是否存在"""
    csv_dir = Path("csv")
    if not csv_dir.exists():
        return False, "CSV数据目录不存在"
    
    csv_files = list(csv_dir.glob("ipc_performance_*.csv"))
    if not csv_files:
        return False, f"未找到IPC性能测试数据文件 (在 {csv_dir} 目录下)"
    
    return True, f"找到 {len(csv_files)} 个数据文件"

def run_analyzer():
    """提供运行分析器的指令"""
    st.success("✅ 数据文件验证通过!")
    st.markdown("""
    ### 🚀 启动分析器
    
    打开新的终端窗口,运行:
    ```bash
    streamlit run ipc_analyzer.py --server.port 8502
    ```
    
    ---
    
    **💡 提示:**
    - 分析器将在 http://localhost:8502 运行
    - 浏览器会自动打开新标签页
    - 如果端口8502被占用,可以使用其他端口如 8503、8504等
    - 按 Ctrl+C 可以停止分析器
    """)
    
    # 提供一键复制命令的功能
    st.code("streamlit run ipc_analyzer.py --server.port 8502", language="bash")
    
    return True

def main():
    st.set_page_config(
        page_title="IPC性能分析系统",
        page_icon="🚀",
        layout="wide"
    )
    
    st.title("🚀 进程间通信(IPC)性能分析系统")
    st.markdown("""
    本系统用于分析和可视化Go、C++、Java、Python四种编程语言的进程间通信性能测试结果,包括:
    - **横向对比**: 同一语言下不同IPC方式(共享内存、Socket、TCP)的性能比较
    - **纵向对比**: 跨语言相同IPC方式的性能比较
    - **综合排名**: 识别最佳性能场景和推荐配置
    - **数据可视化**: 丰富的图表展示吞吐量、延迟等关键指标
    """)
    
    # 检查依赖
    if 'deps_installed' not in st.session_state:
        st.session_state.deps_installed = False

    if not st.session_state.deps_installed:
        if install_requirements():
            st.session_state.deps_installed = True
            st.rerun()
        else:
            st.stop()
    
    # 检查数据文件
    st.header("📊 数据状态")
    data_exists, data_message = check_csv_files()
    
    if data_exists:
        st.success(f"✅ {data_message}")
        
        # 显示找到的文件列表
        csv_dir = Path("csv")
        csv_files = sorted(csv_dir.glob("ipc_performance_*.csv"))
        st.markdown("**可用的数据文件:**")
        for file in csv_files:
            lang_name = file.stem.replace('ipc_performance_', '').upper()
            st.markdown(f"- `{file.name}` ({lang_name})")
    else:
        st.warning(f"⚠️ {data_message}")
        st.info("""
        **如何生成测试数据?**
    
        请在各语言目录下运行对应的测试程序，具体请查看各程序的说明文件。
        测试完成后,数据将自动保存到 `csv/` 目录
        """)
    
    # 启动分析器
    st.header("🎯 数据分析")
    
    if data_exists:
        if st.button("📖 查看启动分析器的方法", type="primary", use_container_width=True):
            run_analyzer()
    else:
        st.error("⚠️ 请先运行测试程序生成数据文件!")
        st.info("生成数据后,刷新此页面即可看到启动选项")
    
    # 项目说明
    st.header("📖 使用说明")
    
    st.markdown("""
    ### 功能特性:
    
    #### 1. 横向对比 (同语言不同IPC)
    - 展示每种语言内部不同IPC方式的性能差异
    - 吞吐量、延迟的柱状图对比
    - 吞吐量与延迟关系的散点图
    
    #### 2. 纵向对比 (跨语言相同IPC)
    - 跨语言比较相同IPC方式的性能表现
    - 箱线图展示各语言性能分布
    - 分组柱状图对比不同并发模式
    
    #### 3. 综合性能排名
    - 最高吞吐量和最低延迟TOP 10排名
    - 各语言最佳IPC方式推荐
    - 多维度性能雷达图
    
    #### 4. 详细数据表
    - 灵活选择显示的列
    - 支持排序和筛选
    - 可下载CSV格式数据
    
    ### 使用步骤:
    
    1. **准备数据**: 确保已运行各语言的IPC性能测试程序,生成了CSV数据文件
    2. **启动分析器**:按照指引启动数据分析器
    3. **配置筛选**: 在左侧边栏选择要分析的语言、消息大小、并发数等参数
    4. **查看结果**: 在四个Tab页签中查看不同类型的分析结果
    5. **导出数据**: 在"详细数据表"中可以下载筛选后的数据
    
    ### 技术指标说明:
    
    - **吞吐量 (Throughput)**: 每秒处理的消息数量 (msg/s),越高越好
    - **平均延迟 (Avg Latency)**: 消息传输的平均耗时 (μs),越低越好
    - **P95/P99延迟**: 95%/99%的消息在此延迟内完成,反映尾部延迟
    - **Pattern**: 生产者_消费者数量配置,如 "4_4" 表示4个生产者和4个消费者
    """)
    
    # 技术栈信息
    st.header("🛠️ 技术栈")
    st.markdown("""
    - **前端框架**: Streamlit
    - **数据处理**: Pandas
    - **可视化**: Plotly
    - **数据源**: CSV格式性能测试结果
    - **支持语言**: Go、C++、Java、Python
    """)

if __name__ == "__main__":
    main()
