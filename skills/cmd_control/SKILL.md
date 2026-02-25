---
name: "cmd_control"
description: "A skill to execute CMD commands on the local Windows machine. Use this skill when the user explicitly asks to run a system command, check system info, or open an application."
---

# Windows CMD Control Skill

This skill allows the AI assistant to interact with the local Windows command line.

## Capabilities

- **Execute Command**: Run any shell command (e.g., `dir`, `ipconfig`, `systeminfo`, `mkdir`).
- **Open Application**: Launch common applications (e.g., `notepad`, `calc`).

## Usage Examples

- "List files in the current directory" -> execute_command("dir")
- "Check my IP address" -> execute_command("ipconfig")
- "Open Calculator" -> open_application("calc")
- "Create a folder named 'test'" -> execute_command("mkdir test")

## Important Notes

- Commands are executed with the permissions of the user running the AI application.
- Be careful with destructive commands (e.g., `del`, `rmdir`).
- Output encoding is handled as UTF-8, but some legacy Windows commands might output in GBK/CP936, which might cause decoding issues (replaced with ?).
