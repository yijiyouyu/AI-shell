import os
import re
import sys
import shutil
import subprocess
import readline
import logging
import glob
import platform
import pty
from openai import OpenAI

# 初始化 OpenAI 客户端。如果使用 DeepSeek/通义千问，只需替换 Base URL 和 API Key。
# 您可以通过环境变量设置，例如：
# export OPENAI_API_KEY="您的API_KEY"
# export OPENAI_BASE_URL="对应厂商的 API 地址，例如 https://api.deepseek.com"
# export OPENAI_MODEL="使用的模型名字，例如 deepseek-chat"
# 配置日志
log_file = os.path.join(os.path.expanduser("~"), "ai_shell.log")
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.info("=== AI Shell Started ===")

try:
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", "dummy"),
        base_url=os.environ.get("OPENAI_BASE_URL")
    )
    logging.info("OpenAI client initialized.")
except Exception as e:
    print(f"初始化 OpenAI 客户端失败: {e}")
    logging.error(f"Failed to initialize OpenAI client: {e}")
    client = None

MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

# 危险命令正则特征库
DANGEROUS_PATTERNS = [
    r'rm\s+-(rf|rf|fr|r)\s+/',              # 递归删除根目录
    r'rm\s+-(rf|rf|fr|r)\s+\*',              # 递归删除当前目录下所有内容（有误伤风险）
    r'mkfs(\..*)?\s+/dev/',                  # 格式化磁盘
    r'dd\s+if=.*of=/dev/',                   # dd 写入物理磁盘
    r'>\s+/etc/',                            # 覆盖系统配置文件
    r'>\s+/boot/',                           # 覆盖启动引导
    r'chmod\s+777\s+/',                      # 全局提权
    r'chmod\s+-R\s+777\s+/',                 # 递归全局提权
    r':\(\)\{ :\|:& \};:',                   # Fork 炸弹
]

def is_dangerous(cmd):
    """检测命令是否命中危险特征库"""
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd):
            return True
    return False

def get_os_info():
    """获取系统详细信息以丰富 Prompt 上下文"""
    info = {
        "os": platform.system(),
        "arch": platform.machine(),
        "shell": os.environ.get("SHELL", "bash"),
        "user": os.environ.get("USER", "unknown"),
        "is_root": os.getuid() == 0,
    }
    
    # 获取 Linux 发行版信息
    if info["os"] == "Linux":
        try:
            with open("/etc/os-release") as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith("ID="):
                        info["distro"] = line.split("=")[1].strip().strip('"')
                    if line.startswith("PRETTY_NAME="):
                        info["full_name"] = line.split("=")[1].strip().strip('"')
        except:
            info["distro"] = "unknown"
            
        # 探测包管理器
        if shutil.which("apt"): info["pkg_manager"] = "apt"
        elif shutil.which("yum"): info["pkg_manager"] = "yum"
        elif shutil.which("pacman"): info["pkg_manager"] = "pacman"
        elif shutil.which("dnf"): info["pkg_manager"] = "dnf"
    elif info["os"] == "Darwin":
        info["distro"] = "macOS"
        info["pkg_manager"] = "brew"
        
    return info

def has_chinese(text):
    """判断字符串中是否包含中文字符"""
    return bool(re.search(r'[\u4e00-\u9fa5]', text))

def is_local_command(cmd_name):
    """判断是否为标准命令或内置命令"""
    # 常用内置命令列表 (bash built-ins)
    builtins = ["cd", "exit", "quit", "export", "alias", "echo", "pwd", "history", "source"]
    if cmd_name in builtins:
        return True
    
    # 在系统的 PATH 环境变量中查找该命令是否存在
    return shutil.which(cmd_name) is not None

def execute_command(cmd):
    """直接执行命令"""
    try:
        # 特殊处理 cd 命令，因为子进程的 chdir 无法影响 Python 主进程
        if cmd.strip().startswith("cd"):
            parts = cmd.strip().split(maxsplit=1)
            target_dir = parts[1] if len(parts) > 1 else os.path.expanduser("~")
            target_dir = os.path.expanduser(target_dir)
            try:
                os.chdir(target_dir)
                logging.info(f"Changed directory to {os.getcwd()}")
                return 0
            except Exception as e:
                print(f"cd: {e}")
                logging.error(f"cd error: {e}")
                return 1

        # 特殊处理 export 命令，使环境变量在当前 AI Shell 进程中生效
        if cmd.strip().startswith("export "):
            try:
                # 支持 export VAR=value 和 export VAR="value with spaces"
                export_part = cmd.strip()[len("export "):]
                for assignment in export_part.split():
                    if '=' in assignment:
                        key, value = assignment.split('=', 1)
                        # 去除引号
                        value = value.strip('"').strip("'")
                        os.environ[key] = value
                        logging.info(f"Exported environment variable: {key}={value}")
                    else:
                        # export VAR (无赋值，仅标记，在 Python 中忽略)
                        logging.info(f"Export without assignment: {assignment}")
                return 0
            except Exception as e:
                print(f"export: {e}")
                logging.error(f"export error: {e}")
                return 1

        # 特殊处理 alias 命令，在当前会话中管理别名
        if not hasattr(execute_command, '_aliases'):
            execute_command._aliases = {}
        
        if cmd.strip().startswith("alias"):
            try:
                alias_part = cmd.strip()[len("alias"):].strip()
                if not alias_part:
                    # 无参数时，列出所有当前别名
                    if execute_command._aliases:
                        for name, value in execute_command._aliases.items():
                            print(f"alias {name}='{value}'")
                    else:
                        print("(当前没有设置任何别名)")
                    return 0
                if '=' in alias_part:
                    name, value = alias_part.split('=', 1)
                    value = value.strip('"').strip("'")
                    execute_command._aliases[name.strip()] = value
                    logging.info(f"Alias set: {name.strip()}='{value}'")
                return 0
            except Exception as e:
                print(f"alias: {e}")
                logging.error(f"alias error: {e}")
                return 1

        # 特殊处理 source 命令，将文件中的 export 语句应用到当前进程
        if cmd.strip().startswith("source ") or cmd.strip().startswith(". "):
            try:
                parts = cmd.strip().split(maxsplit=1)
                filepath = os.path.expanduser(parts[1])
                if not os.path.isfile(filepath):
                    print(f"source: {filepath}: 没有那个文件或目录")
                    return 1
                with open(filepath, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("export ") and '=' in line:
                            assignment = line[len("export "):]
                            key, value = assignment.split('=', 1)
                            value = value.strip('"').strip("'")
                            os.environ[key.strip()] = value
                            logging.info(f"Source applied: {key.strip()}={value}")
                logging.info(f"Sourced file: {filepath}")
                return 0
            except Exception as e:
                print(f"source: {e}")
                logging.error(f"source error: {e}")
                return 1

        # 别名展开：检查命令是否是已注册的别名
        first_word = cmd.strip().split()[0]
        if first_word in execute_command._aliases:
            expanded_cmd = cmd.strip().replace(first_word, execute_command._aliases[first_word], 1)
            logging.info(f"Alias expanded: '{cmd}' -> '{expanded_cmd}'")
            cmd = expanded_cmd


        # 使用 pty 在真实的伪终端中执行命令
        # 这允许 sudo 正常请求密码、保留彩色输出和进度条
        logging.info(f"Executing command (PTY): {cmd}")
        
        # pty.spawn 执行一个可执行程序。为了支持 Shell 特性（如管道、重定向），
        # 我们启动 /bin/bash 并将原命令作为字符串传入。
        try:
            # 这里的 pty.spawn 会接管当前的 stdin/stdout
            status = pty.spawn(['/bin/bash', '-c', cmd])
            # status 返回的是进程退出状态码，通常左移 8 位是正常的 exit code
            exit_code = os.WEXITSTATUS(status) if os.WIFEXITED(status) else 1
            if exit_code != 0:
                logging.warning(f"Command exited with code {exit_code}")
            return exit_code
        except Exception as pty_err:
            logging.error(f"PTY execution error: {pty_err}")
            # 如果 PTY 失败（例如在非 Unix 环境），回退到 subprocess
            result = subprocess.run(cmd, shell=True, executable="/bin/bash")
            return result.returncode
            
    except Exception as e:
        print(f"执行命令发生错误: {e}")
        logging.error(f"Execution error: {e}")
        return 1

def get_llm_suggestion(user_input, is_error=False, context_messages=None):
    """调用大模型获取修正或翻译后的 bash 命令"""
    if not client:
        print("未正确初始化 OpenAI 客户端。请检查环境变量。")
        return None

    if context_messages is None:
        context_messages = []
        
    cwd = os.getcwd()
    os_info = get_os_info()
    
    # 系统提示词优化：包含 OS 环境信息
    system_prompt = f"""You are an intelligent terminal AI Shell Helper.
ENVIRONMENT:
- OS: {os_info.get('full_name', os_info['os'])}
- Distro/ID: {os_info.get('distro', 'unknown')}
- Default Package Manager: {os_info.get('pkg_manager', 'unknown')}
- Shell: {os_info['shell']}
- Current User: {os_info['user']} ({"ROOT" if os_info['is_root'] else "NON-ROOT"})
- Current Directory: {cwd}

YOUR GOAL:
1. If input is a typo of a bash command, provide the corrected command.
2. If input is natural language, translate it into the most accurate single-line bash command for THIS system.
3. If specific software is needed, use the system's package manager ({os_info.get('pkg_manager', 'apt/brew/etc')}).
4. If a command FAILED (is_error=True), analyze the most likely reason (e.g., permission denied, missing dependency, wrong syntax) and suggest a FIXED command.
5. PRIVILEGE RULES: 
   - If the current user is NON-ROOT and the command typically requires administrative privileges (e.g., installing software, accessing protected logs like /var/log/syslog, modifying system configs), ALWAYS PREPEND 'sudo '.
   - If the current user is ROOT, do NOT use 'sudo'.

OUTPUT RULES:
- ONLY output the pure bash command string.
- NO markdown blocks, NO explanations, NO intro/outro.
- Output ONLY the text that can be directly pasted into a shell.
"""
    
    # 构建消息列表
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(context_messages)
    
    user_prompt = f"User Input: {user_input}"
    if is_error:
        user_prompt = f"The command '{user_input}' failed. Please analyze why and suggest a fix."
        
    messages.append({"role": "user", "content": user_prompt})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.05 # 极低温度减少幻觉
        )
        cmd = response.choices[0].message.content.strip()
        
        # 鲁棒性改进：强制剥离 Markdown
        cmd = re.sub(r'^```[a-zA-Z]*\n', '', cmd)  # 剥离代码块开头的 ```bash
        cmd = re.sub(r'\n```$', '', cmd)          # 剥离代码块结尾的 ```
        cmd = cmd.strip('`').strip()
        
        logging.info(f"LLM suggestion: {cmd}")
        return cmd
    except Exception as e:
        error_msg = str(e)
        logging.error(f"LLM request error: {error_msg}")
        
        # 优雅降级提示
        if "401" in error_msg or "API key" in error_msg:
            print("\n\033[1;31m[AI 错误]\033[0m API Key 无效或未设置。请检查环境变量。")
        elif "connection" in error_msg.lower():
            print("\n\033[1;31m[AI 错误]\033[0m 网络连接失败，请检查网络设置或代理。")
        else:
            print(f"\n\033[1;31m[AI 错误]\033[0m 大模型调用失败: {error_msg[:100]}...")
            
        return None

def process_interaction(suggestion, context_messages=None):
    """处理 y/n/其他的 交互闭环"""
    if context_messages is None:
        context_messages = []
        
    current_suggestion = suggestion

    while True:
        dangerous = is_dangerous(current_suggestion)
        
        if dangerous:
            print("\n\033[1;5;31m⚠️  警告：检测到极高危操作！\033[0m")
            print(f"\033[1;31m建议执行\033[0m: \033[1;4;31m{current_suggestion}\033[0m")
            print("\033[91m由于该命令可能导致系统损坏，请输入 \033[1;33mDANGER\033[0m \033[91m以确认执行。\033[0m")
            choice = input("(输入 DANGER 执行 / n 取消 / 其他输入继续追加条件) > \033[0m").strip()
        else:
            print(f"\n\033[93m💡 建议执行\033[0m: \033[1;32m{current_suggestion}\033[0m")
            choice = input("(Y 执行 / n 取消 / 其他输入继续追加条件) [Y] > \033[0m").strip()
            
        logging.info(f"User interaction choice for '{current_suggestion}': '{choice}'")
        
        if not dangerous and choice.lower() in ('y', 'yes', ''):
            # 普通命令确认
            execute_command(current_suggestion)
            # 将实际执行的命令加入历史记录，方便上箭头回调
            readline.add_history(current_suggestion)
            break
        elif dangerous and choice.upper() == 'DANGER':
            # 危险命令强制确认
            print("🚀 \033[1;31m正在强制执行危险操作...\033[0m")
            execute_command(current_suggestion)
            readline.add_history(current_suggestion)
            break
        elif choice.lower() in ('n', 'no'):
            # 取消执行，退回主循环
            print("❌ 已取消。")
            logging.info("User cancelled execution.")
            break
        else:
            # 情况3: 输入了“其他”内容或危险操作确认失败
            if dangerous and choice.upper() != 'DANGER' and choice.lower() not in ('n', 'no'):
                 print("\033[33m提示：高危命令确认失败。输入 DANGER 执行，或输入 n 取消。\033[0m")
                 if not choice: continue # 防止空输入死循环
            
            if not choice:
                continue
            
            # 将上一轮大模型建议的命令和用户新输入的要求，追加到上下文历史中
            context_messages.append({"role": "assistant", "content": current_suggestion})
            context_messages.append({"role": "user", "content": choice})
            
            print("🤔 正在重新思考...")
            new_suggestion = get_llm_suggestion(choice, context_messages=context_messages)
            
            if new_suggestion:
                current_suggestion = new_suggestion
                # 重新进入循环，询问新的 suggestion 

def process_input(user_input):
    """处理用户外层输入的主要判断逻辑 (状态机)"""
    user_input = user_input.strip()
    if not user_input:
        return
        
    logging.info(f"User Input: {user_input}")
    
    # 退出特殊处理
    if user_input in ['exit', 'quit']:
        print("Bye! 👋")
        logging.info("User requested exit.")
        sys.exit(0)
        
    # 第一层判断：拦截中文自然语言
    if has_chinese(user_input):
        print("🤔 理解自然语言中...")
        logging.info("Mode 3 (Chinese NLP) Triggered.")
        # 从历史记录中移除自然语言输入（它会被实际执行的命令替换）
        try:
            pos = readline.get_current_history_length()
            if pos > 0:
                readline.remove_history_item(pos - 1)
        except Exception:
            pass
        suggestion = get_llm_suggestion(user_input, is_error=False)
        if suggestion:
            process_interaction(suggestion, [{"role": "user", "content": user_input}])
    else:
        # 别名展开：在判断命令类型之前，先检查是否为已注册的别名
        if hasattr(execute_command, '_aliases'):
            first_word = user_input.split()[0]
            if first_word in execute_command._aliases:
                expanded = user_input.replace(first_word, execute_command._aliases[first_word], 1)
                logging.info(f"Alias expanded: '{user_input}' -> '{expanded}'")
                user_input = expanded
        
        # 第二层判断：尝试判定为标准命令
        cmd_name = user_input.split()[0]
        if is_local_command(cmd_name):
            # 模式1: 执行标准命令
            logging.info(f"Mode 1 (Standard Command) Triggered for: {cmd_name}")
            exit_code = execute_command(user_input)
            
            # 针对标准命令执行失败的情况，调用 AI 分析
            if exit_code != 0 and exit_code != 130: # 130 通常是 Ctrl+C
                print(f"\n\033[90m(检测到命令返回退出码 {exit_code}，正在请求 AI 分析失败原因...)\033[0m")
                suggestion = get_llm_suggestion(user_input, is_error=True)
                if suggestion:
                    process_interaction(suggestion, [{"role": "user", "content": user_input}])
        else:
            # 第三层判断：错误命令或英文自然语言兜底
            print(f"🧐 未找到系统命令 '{cmd_name}'，尝试纠错与解析中...")
            logging.info(f"Mode 2 (Error/English NLP) Triggered for: {cmd_name}")
            # 从历史记录中移除错误/NLP 输入（会被实际命令替换）
            try:
                pos = readline.get_current_history_length()
                if pos > 0:
                    readline.remove_history_item(pos - 1)
            except Exception:
                pass
            suggestion = get_llm_suggestion(user_input, is_error=True)
            if suggestion:
                process_interaction(suggestion, [{"role": "user", "content": user_input}])

def setup_readline():
    """配置 readline 用于支持历史和 Tab 自动补全"""
    # 启用历史记录
    histfile = os.path.join(os.path.expanduser("~"), ".ai_shell_history")
    try:
        readline.read_history_file(histfile)
        # 设置历史记录的最大长度
        readline.set_history_length(1000)
    except FileNotFoundError:
        pass
        
    # 配置补全触发键
    # 移除 / 作为分隔符，这样 /etc/ 就会被视为一个完整的 text 传入 completer
    readline.set_completer_delims(readline.get_completer_delims().replace('/', ''))

    def smart_completer(text, state):
        """智能补全：第一个词补全命令名，后续词补全文件路径"""
        if state == 0:
            # 获取当前已输入的完整行
            line = readline.get_line_buffer().lstrip()
            
            # 判断：如果光标在第一个词上（行内没有空格或者text就是整行），则补全命令
            is_first_word = ' ' not in line
            
            completions = []
            
            if is_first_word and text and '/' not in text:
                # === 命令名补全 ===
                # 1. 搜索 bash 内建命令
                builtins = ["cd", "exit", "quit", "export", "alias", "echo", "pwd", "history", "source"]
                completions.extend([b + ' ' for b in builtins if b.startswith(text)])
                
                # 2. 搜索已注册的别名
                if hasattr(execute_command, '_aliases'):
                    completions.extend([a + ' ' for a in execute_command._aliases if a.startswith(text)])
                
                # 3. 搜索 PATH 中的可执行文件
                seen = set()
                for directory in os.environ.get("PATH", "").split(os.pathsep):
                    try:
                        if os.path.isdir(directory):
                            for name in os.listdir(directory):
                                if name.startswith(text) and name not in seen:
                                    full_path = os.path.join(directory, name)
                                    if os.access(full_path, os.X_OK):
                                        completions.append(name + ' ')
                                        seen.add(name)
                    except PermissionError:
                        continue
            else:
                # === 文件路径补全 ===
                if not text:
                    completions = os.listdir('.')
                else:
                    expanded_text = os.path.expanduser(text)
                    
                    if os.path.isdir(expanded_text) and text.endswith('/'):
                        search_dir = expanded_text
                        base_name = ""
                        dir_name = text
                    else:
                        dir_name = os.path.dirname(text)
                        base_name = os.path.basename(text)
                        search_dir = os.path.expanduser(dir_name) if dir_name else '.'

                    try:
                        if os.path.exists(search_dir):
                            for name in os.listdir(search_dir):
                                if name.startswith(base_name):
                                    full_path = os.path.join(search_dir, name)
                                    display_path = os.path.join(dir_name, name)
                                    if os.path.isdir(full_path):
                                        completions.append(display_path + '/')
                                    else:
                                        completions.append(display_path)
                    except Exception:
                        completions = []
            
            smart_completer.completions = sorted(set(completions))

        if state < len(smart_completer.completions):
            return smart_completer.completions[state]
        else:
            return None

    smart_completer.completions = []

    # 配置补全函数和触发键
    readline.set_completer(smart_completer)
    # macOS 如果用的 libedit，触发键配置不同
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")

def main():
    setup_readline()
    print("\033[1;36m====================================================\033[0m")
    print("\033[1;32m                 Welcome to AI Shell 🚀            \033[0m")
    print("\033[1;36m====================================================\033[0m")
    print("\033[90m(提示: 包含中文则视为大模型指令，否则首选系统命令。Type 'exit' or 'quit' to exit)\033[0m\n")
    
    while True:
        try:
            cwd = os.getcwd()
            # 从右往左保留最后两级路径作为美化展示
            cwd_display = '/'.join(cwd.split('/')[-2:]) if len(cwd.split('/')) > 2 else cwd
            
            # 仿 bash/zsh 风格的彩色提示符
            prompt_str = f"\033[1;34mAI-Shell\033[0m:\033[1;36m{cwd_display}\033[0m$ "
            
            user_input = input(prompt_str)
            process_input(user_input)
        except KeyboardInterrupt:
            # 兼容 ctrl+c 中断
            print("\n💡 按下 Ctrl+C 被拦截，输入 'exit' 可以退出。")
        except EOFError:
            print()
            break
        except Exception as e:
            print(f"未预期的异常: {e}")
            
    # 程序退出时保存历史记录
    histfile = os.path.join(os.path.expanduser("~"), ".ai_shell_history")
    try:
        readline.write_history_file(histfile)
    except Exception as e:
        print(f"无法保存历史记录: {e}")

if __name__ == "__main__":
    main()
