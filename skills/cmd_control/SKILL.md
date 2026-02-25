---
name: "cmd_control"
description: "A skill to execute CMD commands on the local Windows machine. Use this skill when the user explicitly asks to run a system command, check system info, or open an application."
---

# Windows CMD Control Skill

This skill allows the AI assistant to interact with the local Windows command line.

## Capabilities

- **Execute Command**: Run any shell command (e.g., `dir`, `ipconfig`, `systeminfo`, `mkdir`).
- **Open Application**: Launch common applications (e.g., `notepad`, `calc`).

## Tool Information

To use this skill, call `execute_skill_function` with the following parameters:

*   **skill_name**: `cmd_control`
*   **file_name**: `executor.py`

### Available Functions

#### 1. `execute_command(command, cwd=None)`
Executes a shell command.
*   `command` (str): The command to run (e.g., `mkdir "C:\\Users\\User\\Desktop\\TestFolder"`).
*   `cwd` (str, optional): Current working directory.

#### 2. `open_application(app_name)`
Opens an application.
*   `app_name` (str): The application name (e.g., `notepad`).

#### 3. `write_file(file_path, content, mode='w', encoding='utf-8')`
Writes text to a file.
*   `file_path` (str): Absolute path to the file.
*   `content` (str): The text content to write.
*   `mode` (str): 'w' (overwrite) or 'a' (append).
*   `encoding` (str): Defaults to 'utf-8'.

#### 4. `read_file(file_path, encoding='utf-8', limit=5000)`
Reads text from a file.
*   `file_path` (str): Absolute path to the file.
*   `limit` (int): Max characters to read.

#### 5. `list_directory(path, recursive=False, limit=100)`
Lists files and directories.
*   `path` (str): The directory to list.
*   `recursive` (bool): Whether to search recursively (default: False).
*   `limit` (int): Max number of items (default: 100).

#### 6. `delete_file(file_path)`
Deletes a file or directory.
*   `file_path` (str): Absolute path.

#### 7. `move_file(src_path, dest_path)`
Moves or renames a file/directory.
*   `src_path` (str): Source path.
*   `dest_path` (str): Destination path.

#### 8. `copy_file(src_path, dest_path)`
Copies a file or directory.
*   `src_path` (str): Source path.
*   `dest_path` (str): Destination path.

#### 9. `search_files(directory, pattern)`
Searches for files matching a glob pattern.
*   `directory` (str): Search root.
*   `pattern` (str): Glob pattern (e.g., `*.py`, `**/*.txt`).

#### 10. `execute_python_code(code)`
Executes arbitrary Python code.
*   `code` (str): The Python code to run. Use `print()` to output results.
*   **WARNING**: This gives the AI full access to the Python environment.

## Usage Examples (Tool Call)

To calculate a complex math expression:
```json
{
  "skill_name": "cmd_control",
  "file_name": "executor.py",
  "function_name": "execute_python_code",
  "kwargs": {
    "code": "import math\nprint(math.sqrt(12345))"
  }
}
```
```json
{
  "skill_name": "cmd_control",
  "file_name": "executor.py",
  "function_name": "execute_command",
  "kwargs": {
    "command": "mkdir \"%USERPROFILE%\\Desktop\\TestFolder\""
  }
}
```

## Important Notes

- Commands are executed with the permissions of the user running the AI application.
- Be careful with destructive commands (e.g., `del`, `rmdir`).
- Output encoding is handled as UTF-8, but some legacy Windows commands might output in GBK/CP936, which might cause decoding issues (replaced with ?).
