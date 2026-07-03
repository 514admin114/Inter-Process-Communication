#!/usr/bin/env python
#-*- coding:utf-8 -*-
"""
IPC性能分析系统启动器 v2.0

三大功能模块:
1. 参数配置 — 编辑共享 config.json，四种语言公平对比
2. 启动测试 — 分别编译运行 C++/Go/Java/Python 的性能测试
3. 数据分析 — 检查 Python 环境依赖并启动 ipc_analyzer.py
"""

import streamlit as st
import subprocess
import sys
import os
import json
import re
from pathlib import Path

# 项目根目录（此脚本所在目录）
PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
REQ_PATH = PROJECT_ROOT / "requirements.txt"


# ═══════════════════════════════════════════════
# 共享工具函数
# ═══════════════════════════════════════════════

def load_config():
    """加载 config.json"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {
        "message_sizes": [64, 1024],
        "producer_counts": [1, 2, 4],
        "consumer_counts": [1, 2, 4],
        "messages_per_producer": 500
    }


def save_config(data):
    """保存 config.json"""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(data, f, indent=4)
    return True


def parse_int_list(text):
    """将逗号分隔的字符串解析为整数列表，如 '64, 256, 1024' -> [64, 256, 1024]"""
    items = re.split(r'[,;\s]+', text.strip())
    result = []
    for item in items:
        item = item.strip()
        if item:
            try:
                result.append(int(item))
            except ValueError:
                pass
    return result if result else None


# ═══════════════════════════════════════════════
# Tab 1: 参数配置
# ═══════════════════════════════════════════════

def tab_config():
    st.header("IPC 参数配置")
    st.markdown("修改以下参数后点击保存，四种语言的测试程序将共享同一份配置，确保公平对比。")

    cfg = load_config()

    with st.form("config_form"):
        col1, col2 = st.columns(2)

        with col1:
            msg_sizes_str = st.text_input(
                "消息大小 (字节, 逗号分隔)",
                value=", ".join(str(x) for x in cfg.get("message_sizes", [64, 1024])),
                help="例如: 64, 256, 1024, 4096"
            )
            prod_counts_str = st.text_input(
                "生产者数量 (逗号分隔)",
                value=", ".join(str(x) for x in cfg.get("producer_counts", [1, 2, 4])),
                help="例如: 1, 2, 4, 8"
            )

        with col2:
            cons_counts_str = st.text_input(
                "消费者数量 (逗号分隔)",
                value=", ".join(str(x) for x in cfg.get("consumer_counts", [1, 2, 4])),
                help="例如: 1, 2, 4, 8"
            )
            msg_per_prod = st.number_input(
                "每个生产者消息数",
                min_value=10, max_value=100000,
                value=cfg.get("messages_per_producer", 500),
                step=100
            )

        submitted = st.form_submit_button("保存配置", type="primary", use_container_width=True)

        if submitted:
            msg_sizes = parse_int_list(msg_sizes_str)
            prod_counts = parse_int_list(prod_counts_str)
            cons_counts = parse_int_list(cons_counts_str)

            errors = []
            if msg_sizes is None:
                errors.append("消息大小格式无效")
            if prod_counts is None:
                errors.append("生产者数量格式无效")
            if cons_counts is None:
                errors.append("消费者数量格式无效")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                new_cfg = {
                    "message_sizes": msg_sizes,
                    "producer_counts": prod_counts,
                    "consumer_counts": cons_counts,
                    "messages_per_producer": msg_per_prod
                }
                save_config(new_cfg)
                st.success("配置已保存到 config.json！")
                st.json(new_cfg)

    # 显示当前配置
    st.divider()
    st.subheader("当前配置内容")
    if CONFIG_PATH.exists():
        st.code(CONFIG_PATH.read_text(encoding="utf-8"), language="json")
    else:
        st.warning("config.json 尚未创建，请先保存配置。")

    st.caption(f"配置文件路径: {CONFIG_PATH}")


# ═══════════════════════════════════════════════
# Tab 2: 启动测试
# ═══════════════════════════════════════════════

def run_command(lang_name, commands, cwd):
    """在指定目录执行命令并返回结果"""
    output_lines = []
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        for cmd in commands:
            output_lines.append(f">>> {cmd}")
            result = subprocess.run(
                cmd, shell=True, cwd=str(cwd),
                capture_output=True, encoding='utf-8', errors='replace', timeout=600,
                env=env
            )
            if result.stdout:
                output_lines.append(result.stdout)
            if result.stderr:
                output_lines.append(result.stderr)
            if result.returncode != 0:
                output_lines.append(f"[退出码: {result.returncode}]")
                return "\n".join(output_lines), False, result.returncode
        return "\n".join(output_lines), True, 0
    except subprocess.TimeoutExpired:
        output_lines.append(f"[超时: 命令执行超过600秒]")
        return "\n".join(output_lines), False, -1
    except Exception as e:
        output_lines.append(f"[异常: {e}]")
        return "\n".join(output_lines), False, -1


def tab_launch():
    st.header("启动 Benchmark 测试")
    st.markdown("点击下方按钮，分别编译并运行各语言的性能测试。建议按顺序逐个运行，避免资源冲突。")

    # 确保 config.json 存在
    if not CONFIG_PATH.exists():
        st.warning("config.json 尚未创建，将使用默认配置。可先在「参数配置」页签中设置。")
        save_config(load_config())

    # 显示当前配置摘要
    cfg = load_config()
    st.caption(f"当前配置: {len(cfg['message_sizes'])}种消息大小 x "
               f"{len(cfg['producer_counts'])}种生产者 x "
               f"{len(cfg['consumer_counts'])}种消费者 x 3种IPC")

    st.divider()

    # 初始化 session_state 存储输出
    for key in ["cpp_output", "go_output", "java_output", "py_output"]:
        if key not in st.session_state:
            st.session_state[key] = None

    def show_output(session_key, lang_name):
        """从 session_state 读取并显示持久化的输出"""
        data = st.session_state.get(session_key)
        if data is None:
            return
        output, ok, code = data
        if ok:
            st.success(f"{lang_name} 测试完成!")
        else:
            st.error(f"{lang_name} 测试异常 (退出码: {code})")
        with st.expander("查看输出", expanded=True):
            st.code(output, language="text")

    # -- C++ --
    st.subheader("C++")
    cpp_dir = PROJECT_ROOT / "Cpp"
    cpp_compile = "g++ main.cpp -o main.exe -lws2_32"
    cpp_run = "main.exe"

    col_cpp1, col_cpp2 = st.columns([1, 3])
    with col_cpp1:
        if st.button("编译并运行 C++", type="primary", key="cpp_btn"):
            with col_cpp2:
                with st.spinner("正在编译运行 C++ 测试..."):
                    result = run_command("C++", [cpp_compile, cpp_run], cpp_dir)
                    st.session_state["cpp_output"] = result
                    st.rerun()
    with col_cpp2:
        show_output("cpp_output", "C++")

    st.divider()

    # -- Go --
    st.subheader("Go")
    go_dir = PROJECT_ROOT / "Go"

    col_go1, col_go2 = st.columns([1, 3])
    with col_go1:
        if st.button("编译并运行 Go", type="primary", key="go_btn"):
            with col_go2:
                with st.spinner("正在编译运行 Go 测试..."):
                    result = run_command("Go", ["go run main.go"], go_dir)
                    st.session_state["go_output"] = result
                    st.rerun()
    with col_go2:
        show_output("go_output", "Go")

    st.divider()

    # -- Java --
    st.subheader("Java")
    java_dir = PROJECT_ROOT / "Java"
    java_compile = (
        'javac -d bin src/Main.java src/ipc/utils/*.java '
        'src/ipc/shared_memory/*.java src/ipc/socket/*.java '
        'src/ipc/tcp_ipc/*.java'
    )
    java_run = "java -cp bin Main"

    col_java1, col_java2 = st.columns([1, 3])
    with col_java1:
        if st.button("编译并运行 Java", type="primary", key="java_btn"):
            with col_java2:
                with st.spinner("正在编译运行 Java 测试..."):
                    result = run_command("Java", [java_compile, java_run], java_dir)
                    st.session_state["java_output"] = result
                    st.rerun()
    with col_java2:
        show_output("java_output", "Java")

    st.divider()

    # -- Python --
    st.subheader("Python")
    py_dir = PROJECT_ROOT / "Python"

    col_py1, col_py2 = st.columns([1, 3])
    with col_py1:
        if st.button("运行 Python", type="primary", key="py_btn"):
            with col_py2:
                with st.spinner("正在运行 Python 测试..."):
                    result = run_command("Python", ["py main.py"], py_dir)
                    st.session_state["py_output"] = result
                    st.rerun()
    with col_py2:
        show_output("py_output", "Python")

    st.divider()
    st.caption(f"项目根目录: {PROJECT_ROOT}")


# ═══════════════════════════════════════════════
# Tab 3: 数据分析
# ═══════════════════════════════════════════════

def parse_requirements(req_path):
    """解析 requirements.txt，返回 {package_name: version_spec}"""
    pkgs = {}
    if not req_path.exists():
        return pkgs
    with open(req_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # 处理 package>=version 格式
            match = re.match(r'^([a-zA-Z0-9_\-\.]+)\s*([><=!].*)?$', line)
            if match:
                name = match.group(1).lower()
                spec = match.group(2) or ""
                pkgs[name] = spec
    return pkgs


def check_dependencies():
    """检查 requirements.txt 中的依赖是否已安装"""
    required = parse_requirements(REQ_PATH)
    if not required:
        return [], [], "requirements.txt 为空或不存在"

    # 获取已安装的包
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format", "columns"],
            capture_output=True, text=True
        )
        installed = {}
        for line in result.stdout.strip().split('\n')[2:]:  # 跳过前两行标题
            parts = line.split()
            if len(parts) >= 2:
                installed[parts[0].lower()] = parts[1]
    except Exception:
        installed = {}

    satisfied = []
    missing = []
    for pkg, spec in required.items():
        if pkg in installed:
            satisfied.append((pkg, installed[pkg], spec))
        else:
            missing.append((pkg, spec))

    return satisfied, missing, None


def tab_analysis():
    st.header("数据分析")
    st.markdown("检查 Python 环境依赖，然后启动 IPC 数据分析器。")

    st.divider()

    # 依赖检查
    st.subheader("环境依赖检查")

    if 'dep_check_done' not in st.session_state:
        st.session_state.dep_check_done = False
        st.session_state.dep_satisfied = []
        st.session_state.dep_missing = []

    col_chk1, col_chk2 = st.columns([1, 3])
    with col_chk1:
        if st.button("检查依赖", type="primary", key="check_deps"):
            satisfied, missing, err = check_dependencies()
            if err:
                st.error(err)
            else:
                st.session_state.dep_check_done = True
                st.session_state.dep_satisfied = satisfied
                st.session_state.dep_missing = missing
                st.rerun()

    if st.session_state.dep_check_done:
        satisfied = st.session_state.dep_satisfied
        missing = st.session_state.dep_missing

        total = len(satisfied) + len(missing)
        st.metric("依赖满足率", f"{len(satisfied)}/{total}")

        if satisfied:
            st.success(f"已安装 ({len(satisfied)}):")
            for pkg, ver, spec in satisfied:
                st.text(f"  {pkg} {ver} {'(需要' + spec + ')' if spec else ''}")

        if missing:
            st.error(f"缺失 ({len(missing)}):")
            for pkg, spec in missing:
                st.text(f"  {pkg} {'(需要' + spec + ')' if spec else ''}")

            if st.button("安装缺失依赖", type="secondary"):
                with st.spinner("正在安装..."):
                    try:
                        subprocess.check_call(
                            [sys.executable, "-m", "pip", "install", "-r", str(REQ_PATH)]
                        )
                        st.success("依赖安装完成!")
                        st.session_state.dep_check_done = False
                        st.rerun()
                    except subprocess.CalledProcessError as e:
                        st.error(f"安装失败: {e}")
        else:
            st.success("所有依赖已满足!")

    st.divider()

    # 启动分析器
    st.subheader("启动分析器")

    analyzer_path = PROJECT_ROOT / "ipc_analyzer.py"
    if not analyzer_path.exists():
        st.error(f"未找到 ipc_analyzer.py (路径: {analyzer_path})")
        return

    col_ana1, col_ana2 = st.columns([1, 3])
    with col_ana1:
        if st.button("启动 ipc_analyzer.py", type="primary", key="launch_analyzer"):
            with col_ana2:
                st.info("正在启动数据分析器，请在弹出的浏览器窗口中查看...")
                try:
                    subprocess.Popen(
                        [sys.executable, "-m", "streamlit", "run",
                         str(analyzer_path), "--server.port", "8502"],
                        cwd=str(PROJECT_ROOT)
                    )
                    st.success("分析器已启动! 访问 http://localhost:8502")
                    st.caption("如果浏览器未自动打开，请手动访问上述地址。")
                    st.caption("在终端中按 Ctrl+C 可停止分析器。")
                except Exception as e:
                    st.error(f"启动失败: {e}")

    st.caption(f"分析器路径: {analyzer_path}")


# ═══════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="IPC 性能分析系统",
        page_icon="\U0001f680",
        layout="wide"
    )

    st.title("\U0001f680 进程间通信 (IPC) 性能分析系统")
    st.markdown("统一管理 benchmark 参数配置、多语言测试启动、数据分析和可视化。")

    tab1, tab2, tab3 = st.tabs([
        "参数配置",
        "启动测试",
        "数据分析"
    ])

    with tab1:
        tab_config()

    with tab2:
        tab_launch()

    with tab3:
        tab_analysis()


if __name__ == "__main__":
    main()
