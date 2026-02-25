# 1052 AI

1052 AI 是一个基于 Flask 构建的强大本地 AI 聊天应用。它集成了模型上下文协议 (MCP) 和自定义技能系统 (Skill System) 等高级功能，使 AI 能够与您的本地文件系统交互、运行命令并执行自定义 Python 函数，同时支持飞书机器人接入。中国版的open claw，针对国内环境以及Windows的环境做了深度适配，项目目前处于早期阶段，将会陆续完成版本更新以及1052协议(LLM记忆机制与经验机制)

[🇺🇸 English Documentation (README_EN.md)](README_EN.md)

## 主要特性

*   **智能聊天界面**：现代化、响应式的网页聊天界面，支持 Markdown 渲染。
*   **Exe 一键运行**：提供打包好的 `.exe` 版本，双击即可运行，无需配置 Python 环境。
*   **MCP 集成**：全面支持模型上下文协议 (MCP)。您可以连接任何符合 MCP 标准的服务器（如 `filesystem`、`github` 等），赋予 AI 访问外部工具和数据的能力。
*   **自定义技能系统**：通过编写简单的 Python 函数来扩展 AI 的能力。只需将 `.py` 文件或 `.zip` 压缩包放入 `skills` 文件夹，AI 即可立即将其作为工具使用。
*   **内置 CMD 控制**：预装 Windows CMD 控制技能，允许 AI 执行系统命令和打开应用程序。
*   **飞书机器人接入**：支持配置飞书机器人，将 AI 能力接入飞书聊天。
*   **技能管理**：直接在设置界面中上传、查看列表和删除技能。支持将技能整理到文件夹（包）中。
*   **对话管理**：支持创建多个对话、在不同对话间切换以及删除旧的聊天记录。
*   **灵活配置**：轻松配置您的大语言模型提供商（兼容 OpenAI 接口）、API 密钥和模型名称。

## 快速开始 (Exe 版本)

1.  下载 `1052AI.exe`。
2.  将其放入一个空文件夹（例如 `MyBot`）。
3.  双击运行 `1052AI.exe`。
    *   程序会自动在当前目录下生成 `skills` 文件夹、`chat.db` 数据库和配置文件。
    *   程序会自动打开默认浏览器访问 `http://127.0.0.1:10052`。
4.  开始聊天！

## 快速开始 (源码版本)

### 前置要求

*   Python 3.8+
*   Node.js & npm (仅当您计划使用需要 Node.js 环境的 MCP 服务器时，例如 `@modelcontextprotocol/server-filesystem`)

### 安装步骤

1.  **克隆仓库** (或下载源代码)：
    ```bash
    cd 1052-ai
    ```

2.  **安装 Python 依赖**：
    ```bash
    pip install -r requirements.txt
    ```

3.  **运行应用程序**：
    ```bash
    python app.py
    ```

4.  **打开浏览器**：
    访问 `http://localhost:10052` 开始聊天。

## 配置指南

1.  点击左侧边栏底部的 **设置 (Settings)** 图标。
2.  **模型配置**：输入您的 API Key、Base URL (例如 `https://api.openai.com/v1`) 和模型名称 (例如 `gpt-4o`, `gpt-3.5-turbo`)。
3.  保存配置。

## 使用 MCP (Model Context Protocol)

MCP 允许 AI 使用标准化的外部工具。

1.  进入 **设置** -> **MCP Servers**。
2.  点击 **添加 Server**。
3.  输入名称 (例如 "Filesystem") 并粘贴配置 JSON。
    *   *Filesystem Server 配置示例:*
        ```json
        {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/YourName/Desktop"]
        }
        ```
4.  点击 **确定**。系统会自动测试连接并保存。

## 使用自定义技能 (Skills)

技能是 AI 可以调用的 Python 函数。

1.  进入 **设置** -> **技能 (Skills)**。
2.  **上传技能**：点击上传图标，选择 `.py` 文件或包含 Python 包的 `.zip` 文件。
    *   *Zip 上传*：如果您上传 `my_tools.zip`，它会被自动解压到 `skills/my_tools/` 目录，里面的所有 `.py` 文件都会被加载。
3.  **自动加载**：您也可以手动在 `skills/` 目录下创建文件。
    *   例如创建文件 `skills/math_tools.py`：
        ```python
        def add(a: int, b: int) -> int:
            """两数相加。"""
            return a + b
        ```
    *   AI 将立即识别并能够使用 `add` 工具。

## 社交平台接入

### 飞书机器人

1.  进入 **设置** -> **社交平台接入**。
2.  按照页面上的指南配置飞书 App ID、App Secret 和 Verification Token。
3.  将生成的 Webhook URL 填入飞书后台。
4.  现在您可以在飞书中直接与 AI 对话。

## 项目结构

*   `app.py`: Flask 主程序和 API 接口。
*   `skill_manager.py`: 加载和执行 Python 技能的核心逻辑。
*   `skills/`: 存放自定义技能的目录。
*   `static/`: CSS 样式和 JavaScript 脚本文件。
*   `templates/`: HTML 模板文件。
*   `chat.db`: 存储对话记录和设置的 SQLite 数据库。

## 许可证

[MIT License](LICENSE)

## 免责声明

1052 AI 是一个强大的工具，允许执行本地命令和文件操作。
*   **用户责任**：请确保您完全理解您让 AI 执行的操作。对于因使用本软件（包括但不限于执行危险命令、修改系统文件等）而导致的任何数据丢失、系统损坏或其他后果，开发者不承担任何责任。
*   **安全提示**：请勿在不受信任的环境中运行本软件，并谨慎授予 AI 敏感权限。
*   **无担保**：本软件按“原样”提供，不包含任何明示或暗示的担保。

