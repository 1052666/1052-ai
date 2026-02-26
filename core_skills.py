
import os
import shutil
import glob
import subprocess
import zipfile
import hashlib
import datetime

def resolve_path(path):
    """
    Resolves a path with enhanced logic for user convenience.
    1. Expands environment variables (%USERPROFILE%).
    2. Handles '~' as user home.
    3. If path starts with 'Desktop', 'Documents', 'Downloads' and is not absolute,
       prepends user home directory automatically.
    4. Returns absolute path.
    """
    path = os.path.expandvars(path)
    path = os.path.expanduser(path) # Handles ~
    
    # Normalize separators (allow using / on Windows)
    path = path.replace('/', os.sep)
    
    if not os.path.isabs(path):
        # Check for common user folders
        parts = path.split(os.sep)
        first_part = parts[0].lower()
        
        # Mapping Chinese folder names to English system folders
        folder_map = {
            '桌面': 'Desktop',
            'desktop': 'Desktop',
            '文档': 'Documents',
            'documents': 'Documents',
            '下载': 'Downloads',
            'downloads': 'Downloads',
            '音乐': 'Music',
            'music': 'Music',
            '图片': 'Pictures',
            'pictures': 'Pictures',
            '视频': 'Videos',
            'videos': 'Videos'
        }
        
        if first_part in folder_map:
            # Replace the first part with the correct English folder name
            parts[0] = folder_map[first_part]
            # Reconstruct path relative to user home
            path = os.path.join(*parts)
            
            user_home = os.path.expandvars('%USERPROFILE%')
            path = os.path.join(user_home, path)
            
    return os.path.abspath(path)

def execute_command(command, cwd=None):
    """
    Executes a shell command on the Windows system.
    
    Args:
        command (str): The command to execute (e.g., 'dir', 'ipconfig').
        cwd (str, optional): The directory to execute the command in. Defaults to current working directory.
        
    Returns:
        str: The output of the command (stdout + stderr).
    """
    if not cwd:
        cwd = os.getcwd()
        
    try:
        # Use shell=True to allow shell commands like 'dir'
        # Capture output as text
        result = subprocess.run(
            command, 
            cwd=cwd, 
            shell=True, 
            capture_output=True, 
            text=True,
            encoding='gbk',  # Windows CMD default encoding is often GBK/CP936
            errors='replace'   # Handle decoding errors gracefully
        )
        
        output = result.stdout
        if result.stderr:
            output += "\nError Output:\n" + result.stderr
            
        return output.strip()
    except Exception as e:
        return f"Execution failed: {str(e)}"

def open_application(app_name):
    """
    Opens a common Windows application.
    """
    try:
        subprocess.Popen(app_name, shell=True)
        return f"Launched {app_name}"
    except Exception as e:
        return f"Failed to launch {app_name}: {str(e)}"

def read_file(file_path, encoding='utf-8', limit=5000):
    """
    Reads content from a file. Supports environment variables.
    """
    try:
        file_path = resolve_path(file_path)
        
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
            
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            content = f.read(limit)
            if len(content) == limit:
                content += "\n...(truncated)"
        return content
    except Exception as e:
        return f"Failed to read file: {str(e)}"

def write_file(file_path, content, mode='w', encoding='utf-8'):
    """
    Writes content to a file. Supports environment variables.
    """
    try:
        file_path = resolve_path(file_path)
        
        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        with open(file_path, mode, encoding=encoding) as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Failed to write file: {str(e)}"

def create_directory(path):
    """
    Creates a new directory (and intermediate directories if needed).
    """
    try:
        path = resolve_path(path)
        
        if os.path.exists(path):
            return f"Directory already exists: {path}"
            
        os.makedirs(path)
        return f"Successfully created directory: {path}"
    except Exception as e:
        return f"Failed to create directory: {str(e)}"

def list_directory(path, recursive=False, limit=100):
    """
    Lists files and directories in a given path.
    """
    try:
        path = resolve_path(path)
        
        if not os.path.exists(path):
            return f"Error: Path not found at {path}"
            
        items = []
        if recursive:
            for root, dirs, files in os.walk(path):
                for name in files + dirs:
                    items.append(os.path.join(root, name))
                    if len(items) >= limit:
                        break
                if len(items) >= limit:
                    break
        else:
            items = [os.path.join(path, item) for item in os.listdir(path)]
            
        # Format output
        output = f"Listing for {path} ({len(items[:limit])} items):\n"
        for item in items[:limit]:
            is_dir = os.path.isdir(item)
            type_str = "[DIR]" if is_dir else "[FILE]"
            size_str = ""
            if not is_dir:
                try:
                    size = os.path.getsize(item)
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size/1024:.1f} KB"
                    else:
                        size_str = f"{size/(1024*1024):.1f} MB"
                except: pass
            
            rel_path = os.path.relpath(item, path)
            output += f"{type_str} {rel_path} \t {size_str}\n"
            
        if len(items) > limit:
            output += f"\n... and {len(items) - limit} more items."
            
        return output
    except Exception as e:
        return f"Failed to list directory: {str(e)}"

def delete_file(file_path):
    """
    Deletes a file or directory.
    """
    try:
        file_path = resolve_path(file_path)
        
        if not os.path.exists(file_path):
            return f"Error: Path not found at {file_path}"
            
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
            return f"Successfully deleted directory: {file_path}"
        else:
            os.remove(file_path)
            return f"Successfully deleted file: {file_path}"
    except Exception as e:
        return f"Failed to delete: {str(e)}"

def get_file_info(file_path):
    """
    Get detailed file information (size, created/modified time, permissions).
    """
    try:
        file_path = resolve_path(file_path)
        
        if not os.path.exists(file_path):
            return f"Error: Path not found at {file_path}"
            
        stats = os.stat(file_path)
        created = datetime.datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
        modified = datetime.datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        size = stats.st_size
        
        is_dir = os.path.isdir(file_path)
        type_str = "Directory" if is_dir else "File"
        
        info = f"Path: {file_path}\n"
        info += f"Type: {type_str}\n"
        info += f"Size: {size} bytes\n"
        info += f"Created: {created}\n"
        info += f"Modified: {modified}\n"
        
        if not is_dir:
            # Add MD5 for files
            try:
                with open(file_path, "rb") as f:
                    file_hash = hashlib.md5()
                    while chunk := f.read(8192):
                        file_hash.update(chunk)
                info += f"MD5: {file_hash.hexdigest()}\n"
            except: pass
            
        return info
    except Exception as e:
        return f"Failed to get info: {str(e)}"

def create_skill(skill_name, files):
    """
    Creates a new skill package in the 'skills' directory.
    
    Args:
        skill_name (str): The name of the new skill (folder name).
        files (dict): A dictionary where keys are filenames and values are content.
                      Example: {'__init__.py': '', 'main.py': 'print("Hello")'}
    """
    try:
        # Determine skills directory
        # Assume this file is in project root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        skills_dir = os.path.join(current_dir, 'skills')
        
        if not os.path.exists(skills_dir):
            os.makedirs(skills_dir)
            
        target_dir = os.path.join(skills_dir, skill_name)
        
        if os.path.exists(target_dir):
            return f"Error: Skill '{skill_name}' already exists."
            
        os.makedirs(target_dir)
        
        # Ensure __init__.py
        if '__init__.py' not in files:
            files['__init__.py'] = ""
            
        # Ensure SKILL.md if not provided (basic fallback)
        if 'SKILL.md' not in files:
            files['SKILL.md'] = f"""name: "{skill_name}"\ndescription: "Auto-generated skill"\nfunctions:\n  - name: (auto)\n    description: "See source code."\n"""
            
        results = []
        for filename, content in files.items():
            file_path = os.path.join(target_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            results.append(f"Created {filename}")
            
        return f"Successfully created skill '{skill_name}' in {target_dir}."
    except Exception as e:
        return f"Failed to create skill: {str(e)}"

import sqlite3

def add_scheduled_task(content, time, _conversation_id=None, **kwargs):
    """
    Adds a scheduled task to the database.
    
    Args:
        content (str): The task content or reminder message.
        time (str): The trigger time (YYYY-MM-DD HH:MM:SS or ISO format).
        _conversation_id (str/int, optional): The conversation ID to send the reminder to.
    """
    # DB is in the same directory as this file (root)
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chat.db')
    
    # Validate time format (simple check)
    try:
        # Try parsing to ensure valid time
        trigger_dt = None
        # Try ISO first
        try:
            trigger_dt = datetime.datetime.fromisoformat(time)
        except:
            # Try formats
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M'):
                try:
                    trigger_dt = datetime.datetime.strptime(time, fmt)
                    break
                except ValueError:
                    continue
        
        if not trigger_dt:
             return f"Error: Invalid time format '{time}'. Please use YYYY-MM-DD HH:MM:SS."
                
        # Convert to string for storage
        time_str = trigger_dt.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        return f"Error parsing time: {e}"

    if not _conversation_id:
        return "Error: No conversation context found. Cannot schedule reminder."

    try:
        conn = sqlite3.connect(db_path)
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
