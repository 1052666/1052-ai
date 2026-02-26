# 1052 AI

1052 AI is a powerful local AI chat application built on Flask. It integrates advanced features such as the Model Context Protocol (MCP) and a custom Skill System, enabling the AI to interact with your local file system, run commands, and execute custom Python functions, while also supporting Feishu robot integration. It is the Chinese version of Open Claw, deeply adapted for the domestic environment and Windows environment. The project is currently in the early stages and will successively complete version updates as well as the 1052 Protocol (LLM Memory Mechanism and Experience Mechanism).

[🇨🇳 中文文档 (README.md)](README.md)

## Key Features

*   **Intelligent Chat Interface**: Modern, responsive web chat interface with Markdown rendering support.
*   **One-Click Exe Run**: Provides a packaged `.exe` version that runs with a double-click, no Python environment configuration required.
*   **MCP Integration**: Full support for Model Context Protocol (MCP). You can connect any MCP-compliant server (such as `filesystem`, `github`, etc.) to empower the AI to access external tools and data.
*   **Custom Skill System**: Extend AI capabilities by writing simple Python functions. Just place `.py` files or `.zip` archives into the `skills` folder, and the AI can immediately use them as tools.
*   **Built-in CMD Control**: Pre-installed Windows CMD control skill, allowing the AI to execute system commands and open applications.
*   **Feishu Robot Integration**: Supports configuring a Feishu robot to access AI capabilities within Feishu chat.
*   **QQ Bot Integration**: Supports OneBot V11 (NapCatQQ/go-cqhttp) for QQ integration.
*   **Skill Management**: Upload, view lists, and delete skills directly in the settings interface. Supports organizing skills into folders (packages).
*   **Conversation Management**: Supports creating multiple conversations, switching between different conversations, and deleting old chat records.
*   **Flexible Configuration**: Easily configure your Large Language Model provider (compatible with OpenAI interface), API key, and model name.

## Quick Start (Exe Version)

1.  Download `1052AI.exe`.
2.  Place it in an empty folder (e.g., `MyBot`).
3.  Double-click to run `1052AI.exe`.
    *   The program will automatically generate the `skills` folder, `chat.db` database, and configuration files in the current directory.
    *   The program will automatically open the default browser to visit `http://127.0.0.1:10052`.
4.  Start chatting!

## Quick Start (Source Code Version)

### Prerequisites

*   Python 3.8+
*   Node.js & npm (only if you plan to use MCP servers that require Node.js environment, e.g., `@modelcontextprotocol/server-filesystem`)

### Installation Steps

1.  **Clone the repository** (or download the source code):
    ```bash
    git clone <repository-url>
    cd 1052-ai
    ```

2.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application**:
    ```bash
    python app.py
    ```

4.  **Open browser**:
    Visit `http://localhost:10052` to start chatting.

## Configuration Guide

1.  Click the **Settings** icon at the bottom of the left sidebar.
2.  **Model Configuration**: Enter your API Key, Base URL (e.g., `https://api.openai.com/v1`), and Model Name (e.g., `gpt-4o`, `gpt-3.5-turbo`).
3.  Save the configuration.

## Using MCP (Model Context Protocol)

MCP allows AI to use standardized external tools.

1.  Go to **Settings** -> **MCP Servers**.
2.  Click **Add Server**.
3.  Enter a name (e.g., "Filesystem") and paste the configuration JSON.
    *   *Filesystem Server Configuration Example:*
        ```json
        {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/YourName/Desktop"]
        }
        ```
4.  Click **Confirm**. The system will automatically test the connection and save it.

## Using Custom Skills (Skills)

Skills are Python functions that the AI can call.

1.  Go to **Settings** -> **Skills**.
2.  **Upload Skill**: Click the upload icon to select a `.py` file or a `.zip` file containing a Python package.
    *   *Zip Upload*: If you upload `my_tools.zip`, it will be automatically extracted to the `skills/my_tools/` directory, and all `.py` files inside will be loaded.
3.  **Automatic Loading**: You can also manually create files in the `skills/` directory.
    *   For example, create file `skills/math_tools.py`:
        ```python
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b
        ```
    *   The AI will immediately recognize and be able to use the `add` tool.

## Social Platform Integration

### Feishu Robot

1.  Go to **Settings** -> **Social Platform Integration**.
2.  Configure the Feishu App ID, App Secret, and Verification Token according to the guide on the page.
3.  Fill the generated Webhook URL into the Feishu backend.
4.  Now you can talk to the AI directly in Feishu.

### QQ Bot (OneBot V11)

1.  Go to **Settings** -> **Social Platform Integration** -> **QQ**.
2.  Configure the **HTTP API URL** (e.g., `http://127.0.0.1:3000`).
3.  Configure your OneBot client (NapCatQQ/go-cqhttp) to send events to the **Webhook URL** shown in the settings.

## Project Structure

*   `app.py`: Flask main program and API interface.
*   `qq_utils.py`: **QQ Bot Implementation** (OneBot V11).
*   `skill_manager.py`: Core logic for loading and executing Python skills.
*   `skills/`: Directory for storing custom skills.
*   `static/`: CSS style and JavaScript script files.
*   `templates/`: HTML template files.
*   `chat.db`: SQLite database for storing conversation records and settings.

## License

[MIT License](LICENSE)

## Disclaimer

1052 AI is a powerful tool that allows the execution of local commands and file operations.
*   **User Responsibility**: Please ensure you fully understand the actions you ask the AI to perform. The developer assumes no responsibility for any data loss, system damage, or other consequences resulting from the use of this software (including but not limited to executing dangerous commands or modifying system files).
*   **Security Notice**: Do not run this software in untrusted environments and grant sensitive permissions to the AI with caution.
*   **No Warranty**: This software is provided "as is", without warranty of any kind, express or implied.

