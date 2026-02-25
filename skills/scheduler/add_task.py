import sqlite3
import os
import datetime
import sys

# Get DB Path (relative to this file, assuming standard structure)
# skills/scheduler/add_task.py -> ../../chat.db
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'chat.db'))

def add_scheduled_task(content, time, _conversation_id=None, **kwargs):
    """
    Adds a scheduled task to the database.
    
    Args:
        content (str): The task content or reminder message.
        time (str): The trigger time (YYYY-MM-DD HH:MM:SS or ISO format).
                    Can also be relative time like "+10m" (10 minutes from now) if parsed by AI, 
                    but here we expect absolute time string.
        _conversation_id (str/int, optional): The conversation ID to send the reminder to.
                                              Injected by the system.
    """
    print(f"Adding task: {content} at {time} for conv {_conversation_id}")
    
    # Validate time format (simple check)
    try:
        # Try parsing to ensure valid time
        # Support a few formats
        trigger_dt = None
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                trigger_dt = datetime.datetime.strptime(time, fmt)
                break
            except ValueError:
                continue
        
        if not trigger_dt:
            # Try parsing isoformat
            try:
                trigger_dt = datetime.datetime.fromisoformat(time)
            except:
                return f"Error: Invalid time format '{time}'. Please use YYYY-MM-DD HH:MM:SS."
                
        # Convert to string for storage
        time_str = trigger_dt.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        return f"Error parsing time: {e}"

    if not _conversation_id:
        return "Error: No conversation context found. Cannot schedule reminder."

    try:
        conn = sqlite3.connect(DB_PATH)
        # Ensure table exists (idempotent)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                trigger_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                conversation_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.execute(
            'INSERT INTO scheduled_tasks (content, trigger_time, conversation_id) VALUES (?, ?, ?)',
            (content, time_str, _conversation_id)
        )
        conn.commit()
        conn.close()
        return f"✅ Scheduled task added: '{content}' at {time_str}"
    except Exception as e:
        return f"Database error: {str(e)}"
