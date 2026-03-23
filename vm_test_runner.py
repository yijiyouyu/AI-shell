import subprocess
import os
import time

# --- 测试场景定义 ---
# 格式: (测试名称, 输入序列, 超时秒数)
# 输入序列说明: 每一行代表一次 input() 的输入
# 超时秒数: 部分涉及 sudo/网络的场景需要更长的等待时间

TEST_SCENARIOS = [
    # ============================
    # 一、基础功能测试 (正向用例)
    # ============================
    
    # 1. Mode 1: 标准命令直接执行
    ("1.1 [正向] 标准命令 - ls",
     "ls\nexit\n", 10),
    
    ("1.2 [正向] 标准命令 - pwd",
     "pwd\nexit\n", 10),
    
    ("1.3 [正向] 标准命令 - echo",
     "echo hello world\nexit\n", 10),
    
    ("1.4 [正向] 标准命令 - 管道与重定向",
     "echo test123 | grep test\nexit\n", 10),
    
    # 2. Mode 2: 英文纠错/NLP
    ("2.1 [正向] 英文命令纠错 - gitt",
     "gitt status\ny\nexit\n", 15),
    
    ("2.2 [正向] 英文自然语言",
     "show my current user name\ny\nexit\n", 15),
    
    ("2.3 [正向] 英文自然语言 - 文件操作",
     "list all python files in current directory\ny\nexit\n", 15),

    # 3. Mode 3: 中文自然语言
    ("3.1 [正向] 中文自然语言 - 简单",
     "帮我查看当前目录下的文件\ny\nexit\n", 15),
    
    ("3.2 [正向] 中文自然语言 - 复杂管道",
     "找到当前目录下最大的3个文件\ny\nexit\n", 15),
    
    ("3.3 [正向] 中文自然语言 - 系统信息",
     "帮我查看当前系统内核版本\ny\nexit\n", 15),

    # ============================
    # 二、交互流程测试
    # ============================
    
    # 4. 取消执行 (反向用例)
    ("4.1 [反向] 用户输入 n 取消执行",
     "帮我查看磁盘使用情况\nn\nexit\n", 15),
    
    ("4.2 [反向] 用户输入 no 取消执行",
     "帮我看看内存使用\nno\nexit\n", 15),

    # 5. 递归追加条件
    ("5.1 [正向] 递归交互 - 追加条件后确认",
     "帮我查看日志\n只要最后5行\ny\ntoor\nexit\n", 30),
    
    ("5.2 [正向] 递归交互 - 多轮追加",
     "帮我列出文件\n只显示隐藏文件\n按大小排序\ny\nexit\n", 30),

    # ============================
    # 三、内建命令测试 (新特性)
    # ============================

    # 6. cd 命令
    ("6.1 [正向] cd - 切换到绝对路径",
     "cd /tmp\npwd\nexit\n", 10),
    
    ("6.2 [正向] cd - 无参数回到 HOME",
     "cd\npwd\nexit\n", 10),
    
    ("6.3 [正向] cd - 使用波浪号",
     "cd ~/Desktop\npwd\nexit\n", 10),
    
    ("6.4 [反向] cd - 不存在的目录",
     "cd /nonexistent_dir_12345\nexit\n", 10),

    # 7. export 命令
    ("7.1 [正向] export - 设置环境变量",
     "export TEST_AI_VAR=hello123\necho $TEST_AI_VAR\nexit\n", 10),
    
    ("7.2 [正向] export - 覆盖已有变量",
     "export TEST_AI_VAR=first\nexport TEST_AI_VAR=second\necho $TEST_AI_VAR\nexit\n", 10),
    
    # 8. alias 命令
    ("8.1 [正向] alias - 设置并使用别名",
     "alias ll='ls -la'\nll\nexit\n", 10),
    
    ("8.2 [正向] alias - 列出所有别名 (空)",
     "alias\nexit\n", 10),

    # ============================
    # 四、错误分析测试 (Error Handling)
    # ============================
    
    # 9. Mode 1 标准命令失败后的 AI 自动分析
    ("9.1 [正向] 权限不足 - cat /etc/shadow",
     "cat /etc/shadow\ny\ntoor\nexit\n", 30),
    
    ("9.2 [正向] 文件不存在触发分析",
     "cat /tmp/nonexistent_file_xyz_999\ny\nexit\n", 15),
    
    ("9.3 [反向] 命令失败后拒绝 AI 建议",
     "cat /etc/shadow\nn\nexit\n", 15),

    # ============================
    # 五、安全拦截测试 (DANGER)
    # ============================
    
    # 10. 高危命令拦截
    ("10.1 [正向] 高危拦截 - 确认 DANGER 执行",
     "帮我格式化整个系统根目录\nDANGER\ntoor\nexit\n", 30),
    
    ("10.2 [反向] 高危拦截 - 输入 n 拒绝",
     "帮我删除根目录下所有文件\nn\nexit\n", 15),
    
    ("10.3 [反向] 高危拦截 - 输入 y 无效 (需 DANGER)",
     "帮我格式化系统磁盘\ny\nn\nexit\n", 15),
    
    ("10.4 [反向] 高危拦截 - 空回车无效",
     "帮我递归删除根目录的所有东西\n\nn\nexit\n", 15),

    # ============================
    # 六、提权与平台适配测试
    # ============================
    
    ("11.1 [正向] 自动 sudo - 查看受保护日志",
     "帮我查看系统 syslog 文件最后10行\ny\ntoor\nexit\n", 30),
    
    ("11.2 [正向] 平台适配 - 使用 apt 安装",
     "帮我安装 git\ny\ntoor\nexit\n", 60),

    # ============================
    # 七、边界条件测试
    # ============================
    
    # 12. 空输入与特殊字符
    ("12.1 [边界] 空输入后正常命令",
     "\nls\nexit\n", 10),
    
    ("12.2 [边界] 纯空格输入",
     "   \nls\nexit\n", 10),
    
    ("12.3 [边界] 含特殊字符的标准命令",
     "echo 'hello \"world\"'\nexit\n", 10),
    
    ("12.4 [边界] 超长输入 (压力测试)",
     "echo " + "A" * 500 + "\nexit\n", 10),

    # 13. 退出命令
    ("13.1 [边界] exit 退出",
     "exit\n", 10),
    
    ("13.2 [边界] quit 退出",
     "quit\n", 10),
]


def run_scenario(name, inputs, timeout=30):
    """运行单个测试场景"""
    print(f"\n\033[1;34m>>> 正在执行测试: {name}\033[0m")
    
    process = subprocess.Popen(
        ['python3', 'ai_shell.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    try:
        stdout_data, _ = process.communicate(input=inputs, timeout=timeout)
        print("\033[90m--- 进程输出 ---\033[0m")
        # 限制输出长度，避免刷屏
        output_lines = stdout_data.strip().split('\n')
        if len(output_lines) > 30:
            for line in output_lines[:15]:
                print(line)
            print(f"\033[90m... (省略 {len(output_lines) - 30} 行) ...\033[0m")
            for line in output_lines[-15:]:
                print(line)
        else:
            print(stdout_data)
        print("\033[90m----------------\033[0m")
        return "PASS"
    except subprocess.TimeoutExpired:
        process.kill()
        print("\033[1;31m[超时] 测试超时！（可能等待 sudo 密码或网络请求）\033[0m")
        return "TIMEOUT"
    except Exception as e:
        print(f"\033[1;31m[错误] 运行失败: {e}\033[0m")
        return "ERROR"


def main():
    print("\033[1;32m" + "=" * 60 + "\033[0m")
    print("\033[1;32m       AI Shell 综合测试工具 (v2.0)\033[0m")
    print("\033[1;32m" + "=" * 60 + "\033[0m")
    print(f"当前目录: {os.getcwd()}")
    print(f"测试场景数: {len(TEST_SCENARIOS)}")
    
    # 检查环境变量
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("\033[1;33m⚠️  警告: 未检测到 OPENAI_API_KEY，AI 模式相关测试将失败。\033[0m")
    else:
        print(f"\033[92m✅ API Key 已配置 (尾四位: ...{api_key[-4:]})\033[0m")
    
    # 清理旧日志
    log_file = os.path.join(os.path.expanduser("~"), "ai_shell.log")
    if os.path.exists(log_file):
        os.remove(log_file)
        print(f"🗑️  已清理旧日志: {log_file}")
    
    # 统计结果
    results = {"PASS": 0, "TIMEOUT": 0, "ERROR": 0}
    failed_tests = []
    
    # 循环运行每个场景
    for name, inputs, timeout in TEST_SCENARIOS:
        result = run_scenario(name, inputs, timeout)
        results[result] += 1
        if result != "PASS":
            failed_tests.append((name, result))
        time.sleep(0.5)
    
    # 打印汇总报告
    total = len(TEST_SCENARIOS)
    print("\n\033[1;32m" + "=" * 60 + "\033[0m")
    print("\033[1;32m                  测试汇总报告\033[0m")
    print("\033[1;32m" + "=" * 60 + "\033[0m")
    print(f"  总计: {total} 个场景")
    print(f"  \033[1;32m通过 (PASS):    {results['PASS']}\033[0m")
    print(f"  \033[1;33m超时 (TIMEOUT): {results['TIMEOUT']}\033[0m")
    print(f"  \033[1;31m失败 (ERROR):   {results['ERROR']}\033[0m")
    
    if failed_tests:
        print(f"\n\033[1;33m⚠️  未通过的测试:\033[0m")
        for name, status in failed_tests:
            color = "\033[1;33m" if status == "TIMEOUT" else "\033[1;31m"
            print(f"  {color}[{status}] {name}\033[0m")
    else:
        print(f"\n\033[1;32m🎉 全部通过！\033[0m")
    
    print(f"\n📄 日志文件: \033[1;36m{log_file}\033[0m")


if __name__ == "__main__":
    main()
