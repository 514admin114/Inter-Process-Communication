#!/usr/bin/env python
#-*- coding:utf-8 -*-
"""
IPC性能数据分析系统 - 多语言进程间通信性能对比可视化应用

功能概述:
1. 数据加载与处理:
   - 从csv目录加载Go、C++、Java、Python四种语言的IPC性能测试数据
   - 自动处理数据格式转换和清洗
   - 支持多种IPC类型(共享内存、Socket、TCP)的数据展示

2. 横向对比分析(同语言不同IPC方式):
   - 展示每种语言内部不同IPC方式的性能差异
   - 吞吐量、延迟等关键指标的对比图表
   - 按消息大小、生产者/消费者数量分组对比

3. 纵向对比分析(跨语言相同IPC方式):
   - 跨语言比较相同IPC方式的性能表现
   - 找出各语言在特定场景下的最优IPC方案
   - 综合性能排名和推荐

4. 交互式数据筛选:
   - 按语言、IPC类型、消息大小、并发数等多维度筛选
   - 实时更新的动态图表
   - 灵活的数据视图切换

5. 统计信息展示:
   - 总体测试统计(测试数、成功率等)
   - 各语言平均性能指标
   - 最佳性能场景识别
   - 详细数据表格展示
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import glob
import numpy as np

# ==================== 页面配置 ====================
st.set_page_config(
    page_title="IPC性能分析仪表盘",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #2c3e50;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }
    .info-box {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2196f3;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# 标题
st.markdown('<div class="main-header">🚀 进程间通信(IPC)性能分析仪表盘</div>', unsafe_allow_html=True)
st.markdown("---")

# ==================== 数据加载函数 ====================
@st.cache_data
def load_all_csv_files():
    """加载所有CSV文件"""
    csv_dir = os.path.join(os.path.dirname(__file__), 'csv')
    csv_files = glob.glob(os.path.join(csv_dir, 'ipc_performance_*.csv'))
    
    all_data = {}
    for file_path in csv_files:
        lang_name = os.path.basename(file_path).replace('ipc_performance_', '').replace('.csv', '')
        try:
            df = pd.read_csv(file_path)
            # 转换Success列为布尔值
            if 'Success' in df.columns:
                df['Success'] = df['Success'].map({'true': True, 'false': False, True: True, False: False})
            all_data[lang_name] = df
        except Exception as e:
            st.error(f"加载文件 {file_path} 失败: {str(e)}")
    
    return all_data

# 加载数据
all_data = load_all_csv_files()

if not all_data:
    st.error("未找到任何CSV数据文件!")
    st.stop()

# ==================== 侧边栏配置 ====================
st.sidebar.header("⚙️ 分析配置")

# 选择要分析的语言
available_languages = sorted(all_data.keys())
selected_languages = st.sidebar.multiselect(
    "选择要分析的语言",
    options=available_languages,
    default=available_languages
)

if not selected_languages:
    st.warning("请至少选择一种语言进行分析")
    st.stop()

# 合并选中的数据并添加Language列
language_dfs = []
for lang in selected_languages:
    df = all_data[lang].copy()
    df['Language'] = lang.upper()
    language_dfs.append(df)
combined_df = pd.concat(language_dfs, ignore_index=True)

# 筛选成功的测试
successful_tests = combined_df[combined_df['Success'] == True].copy()

# 获取唯一的配置选项
message_sizes = sorted(successful_tests['Message_Size'].unique())
producer_counts = sorted(successful_tests['Producer_Count'].unique())
consumer_counts = sorted(successful_tests['Consumer_Count'].unique())
ipc_types = sorted(successful_tests['IPC_Type'].unique())

# 过滤器
st.sidebar.subheader("🔍 数据过滤")
selected_msg_size = st.sidebar.selectbox("消息大小 (字节)", options=message_sizes, index=0)
selected_producers = st.sidebar.multiselect("生产者数量", options=producer_counts, default=producer_counts)
selected_consumers = st.sidebar.multiselect("消费者数量", options=consumer_counts, default=consumer_counts)
selected_ipc_type = st.sidebar.multiselect("IPC类型", options=ipc_types, default=ipc_types)

# 应用过滤
filtered_df = successful_tests[
    (successful_tests['Message_Size'] == selected_msg_size) &
    (successful_tests['Producer_Count'].isin(selected_producers)) &
    (successful_tests['Consumer_Count'].isin(selected_consumers)) &
    (successful_tests['IPC_Type'].isin(selected_ipc_type))
]

if filtered_df.empty:
    st.warning("根据当前过滤条件,没有可用的数据")
    st.stop()

# 不受消息大小/并发数/IPC类型过滤的全量数据（用于消息大小影响、并发模式等分析）
all_sizes_df = successful_tests[successful_tests['Language'].isin([l.upper() for l in selected_languages])].copy()

# ==================== 主界面 - 概览统计 ====================
st.markdown('<div class="sub-header">📈 概览统计</div>', unsafe_allow_html=True)

col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
with col1:
    st.metric("总测试数", len(filtered_df))
with col2:
    st.metric("涉及语言数", filtered_df['Language'].nunique())
with col3:
    avg_throughput = filtered_df['Throughput_Msg_Per_Sec'].mean()
    st.metric("平均吞吐量", f"{avg_throughput:.2f} msg/s")
with col4:
    avg_latency = filtered_df['Avg_Latency_Microseconds'].mean()
    st.metric("平均延迟", f"{avg_latency:.2f} μs")
with col5:
    total_errors = filtered_df['Error_Count'].sum() if 'Error_Count' in filtered_df.columns else 0
    st.metric("总错误数", int(total_errors))
with col6:
    total_retransmits = filtered_df['Retransmit_Count'].sum() if 'Retransmit_Count' in filtered_df.columns else 0
    st.metric("总重传数", int(total_retransmits))
with col7:
    avg_accuracy = filtered_df['Accuracy'].mean() if 'Accuracy' in filtered_df.columns else 100.0
    st.metric("平均准确率", f"{avg_accuracy:.2f}%")

st.markdown("---")

# ==================== Tab页签 ====================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 横向对比 (同语言不同IPC)",
    "📉 纵向对比 (跨语言相同IPC)",
    "📏 消息大小影响",
    "👥 并发模式与准确率",
    "🎯 综合性能排名",
    "📋 详细数据表"
])

# ==================== Tab 1: 横向对比 ====================
with tab1:
    st.markdown('<div class="sub-header">横向对比: 同一语言下不同IPC方式的性能比较</div>', unsafe_allow_html=True)
    st.info("💡 **说明**: 此视图展示每种语言内部,不同IPC方式(共享内存、Socket、TCP)的性能差异")
    
    # 为每种语言创建对比图
    for lang in selected_languages:
        lang_data = filtered_df[filtered_df['Language'] == lang.upper()]
        
        if lang_data.empty:
            continue
        
        st.markdown(f"### 🖥️ {lang.upper()} 语言性能对比")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 吞吐量对比
            fig_throughput = px.bar(
                lang_data,
                x='IPC_Type',
                y='Throughput_Msg_Per_Sec',
                color='Pattern',
                title=f'{lang.upper()} - 吞吐量对比',
                labels={'IPC_Type': 'IPC类型', 'Throughput_Msg_Per_Sec': '吞吐量 (msg/s)', 'Pattern': '生产-消费模式'},
                barmode='group',
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_throughput.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig_throughput, use_container_width=True)
        
        with col2:
            # 延迟对比
            fig_latency = px.bar(
                lang_data,
                x='IPC_Type',
                y='Avg_Latency_Microseconds',
                color='Pattern',
                title=f'{lang.upper()} - 平均延迟对比',
                labels={'IPC_Type': 'IPC类型', 'Avg_Latency_Microseconds': '延迟 (μs)', 'Pattern': '生产-消费模式'},
                barmode='group',
                color_discrete_sequence=px.colors.qualitative.Pastel1
            )
            fig_latency.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig_latency, use_container_width=True)
        
        # 散点图:吞吐量 vs 延迟
        fig_scatter = px.scatter(
            lang_data,
            x='Avg_Latency_Microseconds',
            y='Throughput_Msg_Per_Sec',
            color='IPC_Type',
            size='Message_Size',
            hover_data=['Pattern', 'Producer_Count', 'Consumer_Count'],
            title=f'{lang.upper()} - 吞吐量与延迟关系',
            labels={
                'Avg_Latency_Microseconds': '延迟 (μs)',
                'Throughput_Msg_Per_Sec': '吞吐量 (msg/s)',
                'IPC_Type': 'IPC类型'
            },
            color_discrete_sequence=px.colors.qualitative.Dark2
        )
        fig_scatter.update_layout(height=450)
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        # 错误与重传统计图表
        if 'Error_Count' in lang_data.columns and lang_data['Error_Count'].sum() > 0:
            col_err1, col_err2 = st.columns(2)
            
            with col_err1:
                fig_errors = px.bar(
                    lang_data,
                    x='IPC_Type',
                    y='Error_Count',
                    color='Pattern',
                    title=f'{lang.upper()} - 校验错误数',
                    labels={'IPC_Type': 'IPC类型', 'Error_Count': '错误数', 'Pattern': '生产-消费模式'},
                    barmode='group',
                    color_discrete_sequence=px.colors.qualitative.Set2
                )
                fig_errors.update_layout(height=350, xaxis_tickangle=-45)
                st.plotly_chart(fig_errors, use_container_width=True)
            
            with col_err2:
                fig_retrans = px.bar(
                    lang_data,
                    x='IPC_Type',
                    y='Retransmit_Count',
                    color='Pattern',
                    title=f'{lang.upper()} - 重传次数',
                    labels={'IPC_Type': 'IPC类型', 'Retransmit_Count': '重传数', 'Pattern': '生产-消费模式'},
                    barmode='group',
                    color_discrete_sequence=px.colors.qualitative.Pastel1
                )
                fig_retrans.update_layout(height=350, xaxis_tickangle=-45)
                st.plotly_chart(fig_retrans, use_container_width=True)
        
        st.markdown("---")

# ==================== Tab 2: 纵向对比 ====================
with tab2:
    st.markdown('<div class="sub-header">纵向对比: 跨语言相同IPC方式的性能比较</div>', unsafe_allow_html=True)
    st.info("💡 **说明**: 此视图对比不同语言在使用相同IPC方式时的性能表现")
    
    if selected_ipc_type:
        for ipc_type in selected_ipc_type:
            ipc_data = filtered_df[filtered_df['IPC_Type'] == ipc_type]
            
            if ipc_data.empty:
                continue
            
            st.markdown(f"### 🔗 {ipc_type.upper()} IPC - 跨语言性能对比")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 吞吐量对比
                fig_lang_throughput = px.box(
                    ipc_data,
                    x='Language',
                    y='Throughput_Msg_Per_Sec',
                    color='Language',
                    title=f'{ipc_type.upper()} - 各语言吞吐量分布',
                    labels={'Language': '编程语言', 'Throughput_Msg_Per_Sec': '吞吐量 (msg/s)'},
                    points="all",
                    color_discrete_sequence=px.colors.qualitative.Vivid
                )
                fig_lang_throughput.update_layout(height=450)
                st.plotly_chart(fig_lang_throughput, use_container_width=True)
            
            with col2:
                # 延迟对比
                fig_lang_latency = px.box(
                    ipc_data,
                    x='Language',
                    y='Avg_Latency_Microseconds',
                    color='Language',
                    title=f'{ipc_type.upper()} - 各语言延迟分布',
                    labels={'Language': '编程语言', 'Avg_Latency_Microseconds': '延迟 (μs)'},
                    points="all",
                    color_discrete_sequence=px.colors.qualitative.Bold
                )
                fig_lang_latency.update_layout(height=450)
                st.plotly_chart(fig_lang_latency, use_container_width=True)
            
            # 分组柱状图:各语言在不同并发模式下的性能
            fig_grouped = px.bar(
                ipc_data,
                x='Language',
                y='Throughput_Msg_Per_Sec',
                color='Pattern',
                facet_col='IPC_Type',
                title=f'{ipc_type.upper()} - 各语言在不同模式下的吞吐量',
                labels={'Language': '编程语言', 'Throughput_Msg_Per_Sec': '吞吐量 (msg/s)', 'Pattern': '模式'},
                barmode='group',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig_grouped.update_layout(height=500)
            st.plotly_chart(fig_grouped, use_container_width=True)
            
            # 错误与重传跨语言对比
            if 'Error_Count' in ipc_data.columns and ipc_data['Retransmit_Count'].sum() > 0:
                col_err_l1, col_err_l2 = st.columns(2)
                
                with col_err_l1:
                    fig_lang_errors = px.bar(
                        ipc_data,
                        x='Language',
                        y='Error_Count',
                        color='Language',
                        title=f'{ipc_type.upper()} - 各语言校验错误数',
                        labels={'Language': '编程语言', 'Error_Count': '错误数'},
                        color_discrete_sequence=px.colors.qualitative.Vivid
                    )
                    fig_lang_errors.update_layout(height=400)
                    st.plotly_chart(fig_lang_errors, use_container_width=True)
                
                with col_err_l2:
                    fig_lang_retrans = px.bar(
                        ipc_data,
                        x='Language',
                        y='Retransmit_Count',
                        color='Language',
                        title=f'{ipc_type.upper()} - 各语言重传次数',
                        labels={'Language': '编程语言', 'Retransmit_Count': '重传数'},
                        color_discrete_sequence=px.colors.qualitative.Bold
                    )
                    fig_lang_retrans.update_layout(height=400)
                    st.plotly_chart(fig_lang_retrans, use_container_width=True)
            
            st.markdown("---")
    else:
        st.warning("请至少选择一个IPC类型进行纵向对比")

# ==================== Tab 3: 消息大小影响分析 ====================
with tab3:
    st.markdown('<div class="sub-header">消息大小对性能的影响分析</div>', unsafe_allow_html=True)
    st.info("💡 **说明**: 此视图展示不同消息大小下，各语言各IPC方式的吞吐量与延迟变化趋势（不受侧边栏消息大小过滤影响）")

    if not all_sizes_df.empty:
        all_msg_sizes = sorted(all_sizes_df['Message_Size'].unique())

        if len(all_msg_sizes) > 1:
            # 按语言分面展示
            for lang in selected_languages:
                lang_data = all_sizes_df[all_sizes_df['Language'] == lang.upper()]
                if lang_data.empty:
                    continue

                st.markdown(f"### 🖥️ {lang.upper()} - 消息大小 vs 性能")

                # 按消息大小和IPC类型聚合
                agg_data = lang_data.groupby(['Message_Size', 'IPC_Type']).agg({
                    'Throughput_Msg_Per_Sec': 'mean',
                    'Avg_Latency_Microseconds': 'mean'
                }).reset_index()

                col_s1, col_s2 = st.columns(2)

                with col_s1:
                    fig_size_throughput = px.line(
                        agg_data,
                        x='Message_Size',
                        y='Throughput_Msg_Per_Sec',
                        color='IPC_Type',
                        markers=True,
                        title=f'{lang.upper()} - 消息大小 vs 吞吐量',
                        labels={
                            'Message_Size': '消息大小 (字节)',
                            'Throughput_Msg_Per_Sec': '平均吞吐量 (msg/s)',
                            'IPC_Type': 'IPC类型'
                        },
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    fig_size_throughput.update_layout(height=400)
                    st.plotly_chart(fig_size_throughput, use_container_width=True)

                with col_s2:
                    fig_size_latency = px.line(
                        agg_data,
                        x='Message_Size',
                        y='Avg_Latency_Microseconds',
                        color='IPC_Type',
                        markers=True,
                        title=f'{lang.upper()} - 消息大小 vs 延迟',
                        labels={
                            'Message_Size': '消息大小 (字节)',
                            'Avg_Latency_Microseconds': '平均延迟 (μs)',
                            'IPC_Type': 'IPC类型'
                        },
                        color_discrete_sequence=px.colors.qualitative.Pastel1
                    )
                    fig_size_latency.update_layout(height=400)
                    st.plotly_chart(fig_size_latency, use_container_width=True)

                st.markdown("---")

            # 跨语言消息大小对比
            st.markdown("### 🌐 跨语言消息大小对比")
            cross_agg = all_sizes_df.groupby(['Message_Size', 'Language', 'IPC_Type']).agg({
                'Throughput_Msg_Per_Sec': 'mean',
                'Avg_Latency_Microseconds': 'mean'
            }).reset_index()

            col_c1, col_c2 = st.columns(2)

            with col_c1:
                fig_cross_throughput = px.line(
                    cross_agg,
                    x='Message_Size',
                    y='Throughput_Msg_Per_Sec',
                    color='Language',
                    line_dash='IPC_Type',
                    markers=True,
                    title='跨语言 - 消息大小 vs 吞吐量',
                    labels={
                        'Message_Size': '消息大小 (字节)',
                        'Throughput_Msg_Per_Sec': '平均吞吐量 (msg/s)',
                        'Language': '语言',
                        'IPC_Type': 'IPC类型'
                    },
                    color_discrete_sequence=px.colors.qualitative.Vivid
                )
                fig_cross_throughput.update_layout(height=450)
                st.plotly_chart(fig_cross_throughput, use_container_width=True)

            with col_c2:
                fig_cross_latency = px.line(
                    cross_agg,
                    x='Message_Size',
                    y='Avg_Latency_Microseconds',
                    color='Language',
                    line_dash='IPC_Type',
                    markers=True,
                    title='跨语言 - 消息大小 vs 延迟',
                    labels={
                        'Message_Size': '消息大小 (字节)',
                        'Avg_Latency_Microseconds': '平均延迟 (μs)',
                        'Language': '语言',
                        'IPC_Type': 'IPC类型'
                    },
                    color_discrete_sequence=px.colors.qualitative.Bold
                )
                fig_cross_latency.update_layout(height=450)
                st.plotly_chart(fig_cross_latency, use_container_width=True)
        else:
            st.warning("当前数据中只有一种消息大小，无法生成对比趋势图。请先运行多种消息大小的测试。")

# ==================== Tab 4: 并发模式与准确率分析 ====================
with tab4:
    st.markdown('<div class="sub-header">并发模式影响分析</div>', unsafe_allow_html=True)
    st.info("💡 **说明**: 此视图展示不同生产者/消费者数量组合下的性能热力图（不受侧边栏并发数过滤影响）")

    if not all_sizes_df.empty:
        # 并发模式热力图 - 吞吐量
        st.markdown("### 🔥 并发模式热力图")

        # 按生产者x消费者聚合
        concurrency_agg = all_sizes_df.groupby(['Producer_Count', 'Consumer_Count']).agg({
            'Throughput_Msg_Per_Sec': 'mean',
            'Avg_Latency_Microseconds': 'mean',
            'Accuracy': 'mean' if 'Accuracy' in all_sizes_df.columns else 'first'
        }).reset_index()

        # 构建热力图矩阵
        prod_vals = sorted(concurrency_agg['Producer_Count'].unique())
        cons_vals = sorted(concurrency_agg['Consumer_Count'].unique())

        col_h1, col_h2 = st.columns(2)

        with col_h1:
            # 吞吐量热力图
            throughput_matrix = []
            for p in prod_vals:
                row = []
                for c in cons_vals:
                    val = concurrency_agg[
                        (concurrency_agg['Producer_Count'] == p) &
                        (concurrency_agg['Consumer_Count'] == c)
                    ]['Throughput_Msg_Per_Sec']
                    row.append(val.values[0] if len(val) > 0 else 0)
                throughput_matrix.append(row)

            fig_heat_tp = go.Figure(data=go.Heatmap(
                z=throughput_matrix,
                x=[str(c) for c in cons_vals],
                y=[str(p) for p in prod_vals],
                colorscale='Viridis',
                colorbar=dict(title='msg/s'),
                text=[[f'{v:.0f}' for v in row] for row in throughput_matrix],
                texttemplate='%{text}',
                textfont={"size": 10}
            ))
            fig_heat_tp.update_layout(
                title='生产者 x 消费者 - 平均吞吐量热力图',
                xaxis_title='消费者数量',
                yaxis_title='生产者数量',
                height=450
            )
            st.plotly_chart(fig_heat_tp, use_container_width=True)

        with col_h2:
            # 延迟热力图
            latency_matrix = []
            for p in prod_vals:
                row = []
                for c in cons_vals:
                    val = concurrency_agg[
                        (concurrency_agg['Producer_Count'] == p) &
                        (concurrency_agg['Consumer_Count'] == c)
                    ]['Avg_Latency_Microseconds']
                    row.append(val.values[0] if len(val) > 0 else 0)
                latency_matrix.append(row)

            fig_heat_lat = go.Figure(data=go.Heatmap(
                z=latency_matrix,
                x=[str(c) for c in cons_vals],
                y=[str(p) for p in prod_vals],
                colorscale='Plasma',
                colorbar=dict(title='μs'),
                text=[[f'{v:.1f}' for v in row] for row in latency_matrix],
                texttemplate='%{text}',
                textfont={"size": 10}
            ))
            fig_heat_lat.update_layout(
                title='生产者 x 消费者 - 平均延迟热力图',
                xaxis_title='消费者数量',
                yaxis_title='生产者数量',
                height=450
            )
            st.plotly_chart(fig_heat_lat, use_container_width=True)

        # 按语言分并发模式分组柱状图
        st.markdown("### 📊 各语言并发模式分组对比")

        lang_concurrency = all_sizes_df.groupby(['Language', 'Producer_Count', 'Consumer_Count']).agg({
            'Throughput_Msg_Per_Sec': 'mean',
            'Avg_Latency_Microseconds': 'mean'
        }).reset_index()
        lang_concurrency['Concurrency'] = lang_concurrency['Producer_Count'].astype(str) + 'P-' + lang_concurrency['Consumer_Count'].astype(str) + 'C'

        fig_conc_tp = px.bar(
            lang_concurrency,
            x='Concurrency',
            y='Throughput_Msg_Per_Sec',
            color='Language',
            barmode='group',
            title='各语言在不同并发模式下的平均吞吐量',
            labels={
                'Concurrency': '并发模式 (生产者-消费者)',
                'Throughput_Msg_Per_Sec': '平均吞吐量 (msg/s)',
                'Language': '语言'
            },
            color_discrete_sequence=px.colors.qualitative.Vivid
        )
        fig_conc_tp.update_layout(height=450, xaxis_tickangle=-45)
        st.plotly_chart(fig_conc_tp, use_container_width=True)

        st.markdown("---")

        # ==================== 传输准确率分析 ====================
        st.markdown('<div class="sub-header">传输准确率分析</div>', unsafe_allow_html=True)

        if 'Accuracy' in all_sizes_df.columns:
            col_a1, col_a2 = st.columns(2)

            with col_a1:
                # 各语言准确率箱线图
                fig_acc_box = px.box(
                    all_sizes_df,
                    x='Language',
                    y='Accuracy',
                    color='Language',
                    title='各语言传输准确率分布',
                    labels={'Language': '语言', 'Accuracy': '准确率 (%)'},
                    points="all",
                    color_discrete_sequence=px.colors.qualitative.Vivid
                )
                fig_acc_box.update_layout(height=450)
                st.plotly_chart(fig_acc_box, use_container_width=True)

            with col_a2:
                # 各IPC类型准确率箱线图
                fig_acc_ipc = px.box(
                    all_sizes_df,
                    x='IPC_Type',
                    y='Accuracy',
                    color='Language',
                    title='各IPC方式传输准确率分布',
                    labels={'IPC_Type': 'IPC类型', 'Accuracy': '准确率 (%)', 'Language': '语言'},
                    points="all",
                    color_discrete_sequence=px.colors.qualitative.Bold
                )
                fig_acc_ipc.update_layout(height=450)
                st.plotly_chart(fig_acc_ipc, use_container_width=True)

            # 各语言各IPC方式平均准确率柱状图
            acc_agg = all_sizes_df.groupby(['Language', 'IPC_Type'])['Accuracy'].mean().reset_index()
            fig_acc_bar = px.bar(
                acc_agg,
                x='Language',
                y='Accuracy',
                color='IPC_Type',
                barmode='group',
                title='各语言不同IPC方式平均准确率',
                labels={'Language': '语言', 'Accuracy': '平均准确率 (%)', 'IPC_Type': 'IPC类型'},
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_acc_bar.update_layout(height=400)
            st.plotly_chart(fig_acc_bar, use_container_width=True)
        else:
            st.warning("数据中没有 Accuracy 列，无法生成准确率图表")

        st.markdown("---")

        # ==================== 总测试耗时分析 ====================
        st.markdown('<div class="sub-header">总测试耗时分析</div>', unsafe_allow_html=True)

        if 'Total_Time_Seconds' in all_sizes_df.columns:
            col_t1, col_t2 = st.columns(2)

            with col_t1:
                # 各语言总耗时对比
                time_by_lang = all_sizes_df.groupby('Language')['Total_Time_Seconds'].sum().reset_index()
                fig_time_bar = px.bar(
                    time_by_lang,
                    x='Language',
                    y='Total_Time_Seconds',
                    color='Language',
                    title='各语言总测试耗时',
                    labels={'Language': '语言', 'Total_Time_Seconds': '总耗时 (秒)'},
                    color_discrete_sequence=px.colors.qualitative.Vivid,
                    text_auto='.1f'
                )
                fig_time_bar.update_layout(height=450)
                st.plotly_chart(fig_time_bar, use_container_width=True)

            with col_t2:
                # 各语言各IPC方式耗时对比
                time_by_ipc = all_sizes_df.groupby(['Language', 'IPC_Type'])['Total_Time_Seconds'].sum().reset_index()
                fig_time_ipc = px.bar(
                    time_by_ipc,
                    x='Language',
                    y='Total_Time_Seconds',
                    color='IPC_Type',
                    barmode='group',
                    title='各语言不同IPC方式总耗时',
                    labels={'Language': '语言', 'Total_Time_Seconds': '总耗时 (秒)', 'IPC_Type': 'IPC类型'},
                    color_discrete_sequence=px.colors.qualitative.Set2,
                    text_auto='.1f'
                )
                fig_time_ipc.update_layout(height=450)
                st.plotly_chart(fig_time_ipc, use_container_width=True)

            # 各语言耗时箱线图
            fig_time_box = px.box(
                all_sizes_df,
                x='Language',
                y='Total_Time_Seconds',
                color='Language',
                title='各语言单次测试耗时分布',
                labels={'Language': '语言', 'Total_Time_Seconds': '耗时 (秒)'},
                points="all",
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_time_box.update_layout(height=400)
            st.plotly_chart(fig_time_box, use_container_width=True)
        else:
            st.warning("数据中没有 Total_Time_Seconds 列，无法生成耗时图表")

# ==================== Tab 5: 综合性能排名 ====================
with tab5:
    st.markdown('<div class="sub-header">综合性能排名与最佳实践</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🏆 最高吞吐量排名")
        throughput_ranking = filtered_df.nlargest(10, 'Throughput_Msg_Per_Sec')[
            ['Language', 'IPC_Type', 'Pattern', 'Throughput_Msg_Per_Sec', 'Message_Size']
        ]
        st.dataframe(
            throughput_ranking.reset_index(drop=True),
            use_container_width=True,
            hide_index=True
        )
    
    with col2:
        st.markdown("### ⚡ 最低延迟排名")
        latency_ranking = filtered_df.nsmallest(10, 'Avg_Latency_Microseconds')[
            ['Language', 'IPC_Type', 'Pattern', 'Avg_Latency_Microseconds', 'Message_Size']
        ]
        st.dataframe(
            latency_ranking.reset_index(drop=True),
            use_container_width=True,
            hide_index=True
        )
    
    st.markdown("---")
    
    # 各语言最佳IPC方式
    st.markdown("### 💡 各语言最佳IPC方式推荐")
    
    best_configs = []
    for lang in selected_languages:
        lang_data = filtered_df[filtered_df['Language'] == lang.upper()]
        if lang_data.empty:
            continue
        
        # 找最高吞吐量的配置
        best_throughput = lang_data.loc[lang_data['Throughput_Msg_Per_Sec'].idxmax()]
        # 找最低延迟的配置
        best_latency = lang_data.loc[lang_data['Avg_Latency_Microseconds'].idxmin()]
        
        best_configs.append({
            '语言': lang.upper(),
            '最高吞吐量IPC': best_throughput['IPC_Type'],
            '最高吞吐量(msg/s)': f"{best_throughput['Throughput_Msg_Per_Sec']:.2f}",
            '最低延迟IPC': best_latency['IPC_Type'],
            '最低延迟(μs)': f"{best_latency['Avg_Latency_Microseconds']:.2f}"
        })
    
    if best_configs:
        best_df = pd.DataFrame(best_configs)
        st.dataframe(best_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # 性能雷达图
    st.markdown("### 🕸️ 多维度性能雷达图")
    
    # 计算各语言在各IPC类型的平均性能
    radar_data = filtered_df.groupby(['Language', 'IPC_Type']).agg({
        'Throughput_Msg_Per_Sec': 'mean',
        'Avg_Latency_Microseconds': 'mean'
    }).reset_index()
    
    if not radar_data.empty:
        # 归一化数据用于雷达图
        max_throughput = radar_data['Throughput_Msg_Per_Sec'].max()
        min_latency = radar_data['Avg_Latency_Microseconds'].min()
        
        radar_data['Throughput_Normalized'] = radar_data['Throughput_Msg_Per_Sec'] / max_throughput * 100
        radar_data['Latency_Normalized'] = (1 - radar_data['Avg_Latency_Microseconds'] / radar_data['Avg_Latency_Microseconds'].max()) * 100
        
        # 为每种语言创建雷达图
        for lang in selected_languages:
            lang_radar = radar_data[radar_data['Language'] == lang.upper()]
            if lang_radar.empty:
                continue
            
            fig_radar = go.Figure()
            
            for _, row in lang_radar.iterrows():
                fig_radar.add_trace(go.Scatterpolar(
                    r=[row['Throughput_Normalized'], row['Latency_Normalized']],
                    theta=['吞吐量', '低延迟'],
                    name=row['IPC_Type'],
                    fill='toself'
                ))
            
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(angle=90)
                ),
                title=f'{lang.upper()} - 性能雷达图',
                height=500
            )
            
            st.plotly_chart(fig_radar, use_container_width=True)

# ==================== Tab 6: 详细数据表 ====================
with tab6:
    st.markdown('<div class="sub-header">详细数据表格</div>', unsafe_allow_html=True)
    
    # 显示列选择器
    available_columns = [
        'Language', 'IPC_Type', 'Pattern', 'Producer_Count', 'Consumer_Count',
        'Message_Size', 'Throughput_Msg_Per_Sec', 'Avg_Latency_Microseconds',
        'P95_Latency_Microseconds', 'P99_Latency_Microseconds', 'Total_Time_Seconds',
        'Error_Count', 'Retransmit_Count', 'Accuracy'
    ]
    
    selected_columns = st.multiselect(
        "选择要显示的列",
        options=available_columns,
        default=['Language', 'IPC_Type', 'Pattern', 'Throughput_Msg_Per_Sec', 'Avg_Latency_Microseconds']
    )
    
    if selected_columns:
        display_df = filtered_df[selected_columns].copy()
        
        # 排序选项
        sort_column = st.selectbox("按以下列排序", selected_columns, index=0)
        ascending = st.checkbox("升序排列", value=False)
        
        display_df = display_df.sort_values(by=sort_column, ascending=ascending)
        
        st.dataframe(
            display_df.reset_index(drop=True),
            use_container_width=True,
            hide_index=True
        )
        
        # 下载按钮
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 下载当前视图数据 (CSV)",
            data=csv,
            file_name=f'ipc_analysis_{selected_msg_size}bytes.csv',
            mime='text/csv'
        )

# ==================== 底部信息 ====================
st.markdown("---")
st.markdown("*数据来源: Go、C++、Java、Python四种语言的IPC性能测试结果*")
st.markdown("*分析工具: Streamlit + Plotly*")
