---
name: "scheduler"
description: "A skill to add scheduled tasks and reminders. Use this when the user asks to be reminded at a specific time."
---

# Scheduler Skill

## Capabilities
- Add reminders for a specific time.

## Tool Information

### `add_scheduled_task`
Adds a task to be triggered at a specific time.

*   **skill_name**: `scheduler`
*   **file_name**: `add_task.py`
*   **function_name**: `add_scheduled_task`
*   **kwargs**:
    *   `content` (str): The content of the reminder (e.g., "Wake up").
    *   `time` (str): The absolute trigger time in `YYYY-MM-DD HH:MM:SS` format. **You must calculate the absolute time based on the user's relative input (e.g., 'in 10 minutes').**
    *   `_conversation_id` (str, optional): Injected by system. You do NOT need to provide this.

## Usage Example

If user says "Remind me to call John at 2026-10-27 15:30:00":

```json
{
  "skill_name": "scheduler",
  "file_name": "add_task.py",
  "function_name": "add_scheduled_task",
  "kwargs": {
    "content": "Call John",
    "time": "2026-10-27 15:30:00"
  }
}
```
