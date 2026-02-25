# 1052 AI

> **The Chinese Version of OpenClaw | 本地优先的 AI 智能体框架**  
> 深度适配国内环境与 Windows 系统，内置记忆协议与自我进化机制。

1052 AI 是一个基于 Flask 构建的强大本地 AI 聊天应用。它不仅是一个聊天机器人，更是一个能够操作计算机、管理记忆并自我进化的智能体。

[🇺🇸 English Documentation (README_EN.md)](README_EN.md)

## 核心特性 (Key Features)

### 🧠 1052 协议 (Memory & Experience)
内置 **[1052 协议](1052_Protocol/README.md)**，赋予 AI 长期记忆与经验积累能力。
*   **记住偏好**：AI 会记住你的称呼、语言习惯和工作偏好。
*   **经验学习**：AI 会自动总结解决问题的经验，并在下次遇到类似问题时自动调取。

### 🔌 全面集成 MCP (Model Context Protocol)
支持标准化的 MCP 协议，轻松连接外部世界。
*   **文件系统**：直接读写本地文件。
*   **GitHub**：管理代码仓库。
*   **更多工具**：支持任何符合 MCP 标准的 Server。

### 🛠️ 自定义技能与自我进化
*   **Python 技能**：只需将 `.py` 文件放入 `skills` 文件夹，AI 即可获得新能力。
*   **自我进化**：AI 可以（在授权下）编写新的技能代码来扩展自己的能力，甚至修改自身的系统提示词。

### 💻 深度适配 Windows
*   **CMD 控制**：内置 Windows CMD 控制技能，可执行系统命令、打开应用。
*   **一键运行**：提供 `.exe` 版本，无需 Python 环境，开箱即用。

### 🤖 多模型支持与社交接入
*   **模型支持**：兼容 OpenAI 接口，默认配置 **SiliconFlow (硅基流动)** 的 DeepSeek-V3 模型，国内访问极速稳定。
*   **本地模型**：一键切换 Ollama 等本地模型。
*   **飞书接入**：支持配置飞书机器人，将 AI 能力接入团队协作。

## 快速开始 (Exe 版本) - 推荐

1.  下载最新版本的 `1052AI.exe`。
2.  将其放入一个空文件夹（例如 `MyBot`）。
3.  双击运行 `1052AI.exe`。
    *   程序会自动初始化环境，生成 `skills` 目录和配置文件。
    *   自动打开浏览器访问 `http://127.0.0.1:10052`。
4.  **开始使用**：默认配置 DeepSeek 模型，填写您的 SiliconFlow API Key 即可直接开始对话！

## 快速开始 (源码版本)

### 前置要求
*   Python 3.8+
*   Node.js & npm (仅当使用基于 Node 的 MCP Server 时需要)

### 安装步骤

1.  **克隆仓库**：
    ```bash
    git clone https://github.com/1052666/1052-ai
    cd 1052-ai
    ```

2.  **安装依赖**：
    ```bash
    pip install -r requirements.txt
    ```

3.  **运行应用**：
    ```bash
    python app.py
    ```

4.  **访问**：打开浏览器访问 `http://localhost:10052`。

## 功能指南

### ⚙️ 系统设置
点击左下角 **设置 (Settings)** 图标：
*   **模型配置**：切换 OpenAI/Local 模式，配置 API Key。
*   **系统控制权限**：**安全开关**。开启后 AI 才能执行 CMD 命令和修改系统文件。默认关闭。

### 🧠 记忆与经验
无需额外配置，直接在对话中使用：
*   "请记住我是一名 Python 程序员。" -> AI 会调用 `protocol_remember`。
*   "刚才这个报错的解决方法是..." -> AI 会调用 `protocol_learn_experience`。

### 🔌 添加 MCP Server
1.  进入 **设置** -> **MCP Servers**。
2.  点击 **添加 Server**。
3.  粘贴 JSON 配置。例如连接本地文件系统：
    ```json
    {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/YourName/Desktop"]
    }
    ```

## 项目结构

*   `app.py`: 核心服务端。
*   `protocol1052/`: **1052 协议** 核心实现 (记忆与经验)。
*   `skills/`: **技能目录**。在此处添加 `.py` 文件即可扩展能力。
*   `1052_data/`: 存储记忆和经验数据。
*   `templates/` & `static/`: 前端界面。

## 许可证 & 免责声明

[MIT License](LICENSE)

**免责声明**：
1052 AI 是一个强大的工具，允许执行本地命令和文件操作。
*   **用户责任**：请确保您完全理解您让 AI 执行的操作。
*   **安全提示**：请勿在不受信任的环境中运行本软件，并谨慎授予 AI 敏感权限（特别是系统控制权限）。
*   **无担保**：本软件按“原样”提供，开发者不承担任何因使用导致的损失责任。
