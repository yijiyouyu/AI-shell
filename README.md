# AI Shell 🚀

> **不仅仅是一个 Shell，更是命令行的智能大脑。**

AI Shell 是一个旨在革命性提升命令行体验的智能终端代理。它无缝集成了大模型（LLM），能够理解自然语言，自动纠正命令拼写错误，并在命令执行失败时给出智能建议。

---

## 🐣 为什么选择 AI Shell？（初学者必读）

如果你是命令行新手，或者经常记不住复杂的 Linux 参数，AI Shell 就是你的“副驾驶”：

- **告别死记硬背**：直接输入“把当前目录下的图片都压缩成一个 zip”，AI 帮你写好所有的管道符和参数。
- **不再害怕权限报错**：当你看到 `Permission denied` 时，不用查百度，AI 会直接告诉你“需要加 sudo”，并帮你写好新命令。
- **安全第一**：新手最怕误删系统文件。AI Shell 的**安全拦截系统**会在你触发危险操作时“尖叫”提醒你，保护你的数据安全。
- **渐进式学习**：你可以输入简单的要求，看 AI 建议的命令来学习真正的 Bash 语法。

---

## ✨ 核心特性

### 1. 三种智能模式
- **标准执行 (Mode 1)**: 与 Bash/Zsh 体验一致，直接执行标准命令。
- **智能纠错 (Mode 2)**: 当你输错命令（如 `gitt status`）或输入英文自然语言时，AI 会自动分析意图并给出修正建议。
- **全自然语言交互 (Mode 3)**: 直接输入中文（如“帮我找到当前目录下最大的三个文件”），AI 会将其转换为精准的 Linux 指令。

### 2. 对话式交互与追加条件 (Recursive Flow)
当你对 AI 给出的建议不完全满意时，可以输入追加条件（如“只要最后5行”、“排除日志文件”），AI 会根据上下文实时微调命令。

### 3. 环境感知的权限处理 (Sudo Awareness)
AI 能自动识别当前是否为 Root 用户。如果普通用户执行了需要管理权限的命令（如查看受限日志、安装软件），AI 会**自动补全 `sudo`**。

### 4. 高危操作安全拦截 (Safety Interceptor)
内置危险命令拦截库。对于 `rm -rf /` 或格式化磁盘等极端高危操作，系统会触发**闪烁红光报警**，并强制要求手动输入 `DANGER` 确认。

### 5. 原生终端仿真 (PTY Engine)
采用 `pty` 伪终端引擎，完美支持：
- **安全密码掩码**: 输 `sudo` 密码时字符不回显。
- **色彩与动画**: 完美保留 `ls` 彩色高亮和 `apt` 安装进度条。
- **标准交互**: 支持 `Tab` 路径补全和历史记录翻找。

---

## 📸 功能演示

### 1. 自然语言转命令
![自然语言转命令](./%E8%87%AA%E7%84%B6%E8%AF%AD%E8%A8%80%E8%BD%AC%E5%91%BD%E4%BB%A4.png)
> AI 准确地将复杂的中文需求转换为带有管道符和过滤条件的命令。

### 2. 自动纠错与提权建议
![自动纠错](./%E8%87%AA%E5%8A%A8%E7%BA%A0%E9%94%99.png)
![提权建议](./%E6%8F%90%E6%9D%83%E5%BB%BA%E8%AE%AE.png)
> 当标准命令输错或因权限不足失败时，系统自动解析并建议修正版本。

### 3. 高危拦截警报
![高危拦截警报](./%E9%AB%98%E5%8D%B1%E6%8B%A6%E6%88%AA%E8%AD%A6%E6%8A%A5.png)
> 面对危险指令时，强烈的视觉警报和强制单词确认机制。


---

## 🛠️ 安装与配置

### 1. 克隆项目
```bash
git clone https://github.com/your-username/AI_shell.git
cd AI_shell
```

### 2. 安装依赖
```bash
pip install openai
```

### 3. 配置环境变量
AI Shell 兼容 OpenAI API 格式。支持 DeepSeek、通义千问等所有主流模型。
```bash
export OPENAI_API_KEY="您的_API_KEY"
export OPENAI_BASE_URL="https://api.deepseek.com" # 若使用非 OpenAI 原厂模型，请配置 Base URL
export OPENAI_MODEL="deepseek-chat"              # 指定模型名称
```

---

## 🚀 启动使用

只需运行主脚本即可进入智能模式：
```bash
python3 ai_shell.py
```

**(可选) 设置别名以方便调用**:
在您的 `.bashrc` 或 `.zshrc` 中添加：
```bash
alias ais='python3 /absolute/path/to/AI_shell/ai_shell.py'
```
之后只需在终端输入 `ais` 即可随时唤醒。

---

## 📄 开源协议
[GPL-3.0 License](LICENSE)

---

## 🤝 贡献与反馈
欢迎通过 Issue 提供更有创意的提示词（System Prompt）或功能建议！
