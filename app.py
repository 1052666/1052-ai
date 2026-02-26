import os
import sys
import sqlite3
import json
import requests
import datetime
import asyncio
import aiohttp
import zipfile
import shutil
import threading
import time
import inspect
import webbrowser
import uuid
from telegram_utils import TelegramBot
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent
from skill_manager import SkillManager
from feishu_utils import FeishuBot
import core_skills
from protocol1052.client import Protocol1052

# --- Core Tools Schema ---
CORE_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command on the system (Windows CMD). Use this for system control, running scripts, installing packages, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to run."},
                    "cwd": {"type": "string", "description": "Optional working directory."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file."}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (overwrites by default).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the file."},
                    "content": {"type": "string", "description": "Content to write."}
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a new directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to create."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path."},
                    "recursive": {"type": "boolean", "description": "List recursively?"},
                    "limit": {"type": "integer", "description": "Max items to return."}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file or directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to delete."}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get detailed info (size, date, hash) of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to file."}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_skill",
            "description": "Create a new skill package in the skills directory. Use this to add new capabilities to yourself.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string", "description": "Name of the skill (folder name, no spaces)."},
                    "files": {
                        "type": "object",
                        "description": "Dictionary of filename -> content.",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["skill_name", "files"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_scheduled_task",
            "description": "Schedule a task/reminder for a future time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "What to remind/do."},
                    "time": {"type": "string", "description": "Time (YYYY-MM-DD HH:MM:SS)."}
                },
                "required": ["content", "time"]
            }
        }
    }
]

def execute_core_tool(func_name, func_args):
    """Executes a core tool function."""
    if func_name == 'execute_command':
        return core_skills.execute_command(func_args.get('command'), func_args.get('cwd'))
    elif func_name == 'read_file':
        return core_skills.read_file(func_args.get('file_path'))
    elif func_name == 'write_file':
        return core_skills.write_file(func_args.get('file_path'), func_args.get('content'))
    elif func_name == 'create_directory':
        return core_skills.create_directory(func_args.get('path'))
    elif func_name == 'list_directory':
        return core_skills.list_directory(func_args.get('path'), func_args.get('recursive', False))
    elif func_name == 'delete_file':
        return core_skills.delete_file(func_args.get('file_path'))
    elif func_name == 'get_file_info':
        return core_skills.get_file_info(func_args.get('file_path'))
    elif func_name == 'create_skill':
        return core_skills.create_skill(func_args.get('skill_name'), func_args.get('files'))
    elif func_name == 'add_scheduled_task':
        return core_skills.add_scheduled_task(func_args.get('content'), func_args.get('time'), func_args.get('_conversation_id'))
    return None


# --- Path Configuration for EXE ---
if getattr(sys, 'frozen', False):
    # If running as EXE, base_path is temp folder (_MEI...), data_path is exe directory
    BASE_DIR = sys._MEIPASS
    DATA_DIR = os.path.dirname(sys.executable)
    template_folder = os.path.join(BASE_DIR, 'templates')
    static_folder = os.path.join(BASE_DIR, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    # If running as script
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATA_DIR = BASE_DIR
    app = Flask(__name__)

# Ensure user data directories exist in DATA_DIR (Exe directory)
SKILLS_DIR = os.path.join(DATA_DIR, 'skills')
DB_FILE = os.path.join(DATA_DIR, 'chat.db')
PROTOCOL_DIR = os.path.join(DATA_DIR, '1052_data')

# --- Resource Extraction for EXE ---
def extract_default_resources():
    """
    If running as EXE and skills/system_prompt doesn't exist in DATA_DIR,
    copy them from bundled resources (BASE_DIR) to DATA_DIR.
    """
    if not getattr(sys, 'frozen', False):
        return

    # 1. Extract Skills (Smart Merge)
    bundled_skills = os.path.join(BASE_DIR, 'skills')
    if os.path.exists(bundled_skills):
        if not os.path.exists(SKILLS_DIR):
            print(f"Extracting default skills to {SKILLS_DIR}...")
            try:
                shutil.copytree(bundled_skills, SKILLS_DIR)
            except Exception as e:
                print(f"Failed to extract skills: {e}")
        else:
            # Skills dir exists, merge new skills
            print(f"Merging bundled skills into {SKILLS_DIR}...")
            for item in os.listdir(bundled_skills):
                s_path = os.path.join(bundled_skills, item)
                d_path = os.path.join(SKILLS_DIR, item)
                if not os.path.exists(d_path):
                    try:
                        if os.path.isdir(s_path):
                            shutil.copytree(s_path, d_path)
                        else:
                            shutil.copy2(s_path, d_path)
                        print(f"  + Added new skill: {item}")
                    except Exception as e:
                        print(f"  ! Failed to copy {item}: {e}")

    # 2. Extract System Prompt
    target_prompt = os.path.join(DATA_DIR, 'system_prompt.md')
    bundled_prompt = os.path.join(BASE_DIR, 'system_prompt.md')
    if not os.path.exists(target_prompt) and os.path.exists(bundled_prompt):
        print(f"Extracting system_prompt.md to {target_prompt}...")
        try:
            shutil.copy2(bundled_prompt, target_prompt)
        except Exception as e:
            print(f"Failed to extract system_prompt: {e}")

# Run extraction on startup
extract_default_resources()

# Initialize SkillManager with correct path
skill_manager = SkillManager(skills_dir=SKILLS_DIR)

# Initialize Protocol1052
# For simplicity, we use a single user_id for now, but this could be dynamic per conversation
# In a multi-user environment, we would instantiate this per request/session
DEFAULT_USER_ID = "owner"
protocol_brain = Protocol1052(user_id=DEFAULT_USER_ID, storage_root=PROTOCOL_DIR)

# --- Interruption Signals ---
# Map conversation_id -> current_request_id (UUID)
# When a new request comes in for a conversation, we update this value.
# The running task checks if its request_id matches the current one. If not, it aborts.
CONVERSATION_SIGNALS = {}

class TaskInterrupted(Exception):
    pass

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Settings table
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
    # Conversations table
    c.execute('''CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    # Messages table
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
                )''')
    # MCP Servers table
    c.execute('''CREATE TABLE IF NOT EXISTS mcp_servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL, -- 'stdio' or 'sse'
                    command TEXT, -- for stdio
                    args TEXT, -- for stdio (json list)
                    env TEXT, -- for stdio (json dict)
                    url TEXT, -- for sse
                    enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    # Scheduled Tasks table
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    trigger_time TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    conversation_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    # AI Diary & Evolution Log
    c.execute('''CREATE TABLE IF NOT EXISTS ai_evolution_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    type TEXT DEFAULT 'plan', -- 'plan', 'monologue'
                    status TEXT DEFAULT 'pending', -- 'pending', 'in_progress', 'completed', 'failed'
                    result_summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    conn.commit()
    conn.close()

# Initialize DB on startup
if not os.path.exists(DB_FILE):
    init_db()
else:
    # Ensure tables exist even if file exists
    init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

# --- Settings API ---
@app.route('/api/settings', methods=['GET'])
def get_settings():
    conn = get_db_connection()
    settings = conn.execute('SELECT * FROM settings').fetchall()
    conn.close()
    return jsonify({row['key']: row['value'] for row in settings})

@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.json
    conn = get_db_connection()
    for key, value in data.items():
        conn.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- Conversations API ---
@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    conn = get_db_connection()
    conversations = conn.execute('SELECT * FROM conversations ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(row) for row in conversations])

@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    data = request.json
    title = data.get('title', 'New Chat')
    conn = get_db_connection()
    cursor = conn.execute('INSERT INTO conversations (title) VALUES (?)', (title,))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'id': new_id, 'title': title})

@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# --- Messages API ---
@app.route('/api/conversations/<int:conversation_id>/messages', methods=['GET'])
def get_messages(conversation_id):
    conn = get_db_connection()
    messages = conn.execute('SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC', (conversation_id,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in messages])

# --- MCP Servers API ---
@app.route('/api/mcp_servers', methods=['GET'])
def get_mcp_servers():
    conn = get_db_connection()
    servers = conn.execute('SELECT * FROM mcp_servers ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(row) for row in servers])

@app.route('/api/mcp_servers', methods=['POST'])
def add_mcp_server():
    data = request.json
    name = data.get('name')
    server_type = data.get('type')
    
    if not name or not server_type:
        return jsonify({'error': 'Name and type are required'}), 400

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO mcp_servers (name, type, command, args, env, url, enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        name,
        server_type,
        data.get('command'),
        json.dumps(data.get('args', [])),
        json.dumps(data.get('env', {})),
        data.get('url'),
        1 # enabled by default
    ))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/mcp_servers/<int:server_id>', methods=['PUT'])
def update_mcp_server(server_id):
    data = request.json
    conn = get_db_connection()
    
    # Fetch existing to support partial updates
    existing = conn.execute('SELECT * FROM mcp_servers WHERE id = ?', (server_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({'error': 'Server not found'}), 404
    
    existing_dict = dict(existing)
    
    # Prepare new values, falling back to existing if not provided
    name = data.get('name', existing_dict['name'])
    server_type = data.get('type', existing_dict['type'])
    command = data.get('command', existing_dict['command'])
    
    # For JSON fields, we need to be careful. 
    # If data has 'args', use it. If not, use existing.
    if 'args' in data:
        args = json.dumps(data['args'])
    else:
        args = existing_dict['args']

    if 'env' in data:
        env = json.dumps(data['env'])
    else:
        env = existing_dict['env']
        
    url = data.get('url', existing_dict['url'])
    enabled = data.get('enabled', existing_dict['enabled'])

    conn.execute('''
        UPDATE mcp_servers 
        SET name = ?, type = ?, command = ?, args = ?, env = ?, url = ?, enabled = ?
        WHERE id = ?
    ''', (
        name,
        server_type,
        command,
        args,
        env,
        url,
        enabled,
        server_id
    ))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/mcp_servers/<int:server_id>', methods=['DELETE'])
def delete_mcp_server(server_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM mcp_servers WHERE id = ?', (server_id,))
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/mcp_servers/test', methods=['POST'])
def test_mcp_server():
    data = request.json
    server_type = data.get('type')
    
    # Create a temporary config object
    server_config = {
        'name': 'Test Server',
        'type': server_type,
        'command': data.get('command'),
        'args': json.dumps(data.get('args', [])),
        'env': json.dumps(data.get('env', {})),
        'url': data.get('url')
    }

    if server_type != 'stdio':
        return jsonify({'status': 'error', 'message': 'Only stdio type is supported for testing currently.'})

    try:
        # Run a simple tool list command to verify connection
        # We need to run this in an async loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def run_test():
            command = server_config['command']
            args = json.loads(server_config['args'])
            if not isinstance(args, list):
                raise ValueError("Args must be a list of strings (JSON Array).")
                
            env = json.loads(server_config['env'])
            full_env = os.environ.copy()
            full_env.update(env)

            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=full_env
            )
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    return [t.name for t in tools.tools]

        tool_names = loop.run_until_complete(run_test())
        loop.close()
        
        return jsonify({
            'status': 'success', 
            'message': f'Successfully connected! Found {len(tool_names)} tools: {", ".join(tool_names[:5])}{"..." if len(tool_names)>5 else ""}'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# --- Skills API ---
@app.route('/api/skills', methods=['GET'])
def get_skills():
    skill_manager.load_skills()
    
    # We want to group skills by their module/folder name
    # structure: { "module_name": { "path": "path/to/module", "skills": [ {name, desc} ] } }
    
    # Since we changed SkillManager to store skills by folder/item name
    # self.skills = { item_name: { path, description, type } }
    
    skills_list = []
    
    for name, info in skill_manager.skills.items():
        skills_list.append({
            "name": name,
            "description": info['description'], # This is now MD content
            "type": info['type'],
            "is_folder": info['type'] == 'folder'
        })
            
    return jsonify(skills_list)

@app.route('/api/skills', methods=['POST'])
def upload_skill():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    filename = secure_filename(file.filename)
    
    if filename.endswith('.zip'):
        # Save temp
        temp_path = os.path.join(skill_manager.skills_dir, filename)
        file.save(temp_path)
        
        try:
            # Determine skill folder name (zip name without extension)
            skill_folder_name = os.path.splitext(filename)[0]
            extract_path = os.path.join(skill_manager.skills_dir, skill_folder_name)
            
            # Create subdirectory
            if not os.path.exists(extract_path):
                os.makedirs(extract_path)
            
            # Extract
            with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            
            # Clean up zip
            os.remove(temp_path)
            
            # Reload to verify
            skill_manager.load_skills()
            return jsonify({'status': 'success', 'message': f'Skill "{skill_folder_name}" uploaded and extracted successfully'})
        except Exception as e:
            return jsonify({'error': f'Failed to extract skill: {str(e)}'}), 500
            
    elif filename.endswith('.py'):
        # Allow single python file upload too
        file.save(os.path.join(skill_manager.skills_dir, filename))
        skill_manager.load_skills()
        return jsonify({'status': 'success', 'message': 'Skill file uploaded successfully'})
    
    return jsonify({'error': 'Invalid file type. Please upload a .zip or .py file'}), 400

@app.route('/api/skills/<filename>', methods=['DELETE'])
def delete_skill(filename):
    # Security check: prevent directory traversal
    filename = secure_filename(filename)
    # Ensure filename ends with .py (simple check to avoid deleting other things)
    if not filename.endswith('.py') and not filename.endswith('.zip') and '.' in filename: 
         # It has an extension that is not py or zip, deny? 
         # But if it's a directory (skill folder), it might not have extension.
         pass 

    file_path = os.path.join(skill_manager.skills_dir, filename)
    
    # Check if it's within skills dir
    abs_path = os.path.abspath(file_path)
    abs_skills_dir = os.path.abspath(skill_manager.skills_dir)
    if not abs_path.startswith(abs_skills_dir):
        return jsonify({'error': 'Invalid file path'}), 403

    if os.path.exists(file_path):
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                # Delete entire directory for skill package
                shutil.rmtree(file_path)
            
            skill_manager.load_skills()
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'error': f'Failed to delete skill: {str(e)}'}), 500
    else:
        # Check if it might be a folder without extension that matches
        if os.path.exists(file_path) and os.path.isdir(file_path):
             try:
                shutil.rmtree(file_path)
                skill_manager.load_skills()
                return jsonify({'status': 'success'})
             except Exception as e:
                return jsonify({'error': f'Failed to delete skill folder: {str(e)}'}), 500
        
        return jsonify({'error': 'Skill file/folder not found'}), 404

# --- MCP Client Logic ---
async def run_mcp_tool(server_config, tool_name, tool_args):
    # This is a simplified implementation that only supports stdio for now
    # and creates a new connection for each tool call (not efficient but safe)
    if server_config['type'] != 'stdio':
        return f"Error: Only stdio MCP servers are supported in this demo. (Server: {server_config['name']})"

    command = server_config['command']
    args = json.loads(server_config['args'])
    env = json.loads(server_config['env'])
    
    # Merge current env with provided env
    full_env = os.environ.copy()
    full_env.update(env)

    server_params = StdioServerParameters(
        command=command,
        args=args,
        env=full_env
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Call the tool
                result: CallToolResult = await session.call_tool(tool_name, tool_args)
                
                # Format result
                output = []
                for content in result.content:
                    if isinstance(content, TextContent):
                        output.append(content.text)
                    else:
                        output.append(str(content)) # Fallback for image/embedded
                
                return "\n".join(output)
                
    except Exception as e:
        return f"Error calling MCP tool: {str(e)}"

# Helper to get tool schema from all servers
async def get_all_mcp_tools():
    conn = get_db_connection()
    servers = conn.execute('SELECT * FROM mcp_servers WHERE enabled = 1').fetchall()
    conn.close()
    
    all_tools = []
    server_map = {} # Map tool name to server config for execution later
    
    for server in servers:
        server_dict = dict(server)
        if server_dict['type'] != 'stdio': continue # Skip non-stdio for now

        try:
            command = server_dict['command']
            try:
                args = json.loads(server_dict['args'])
                if not isinstance(args, list):
                    print(f"Skipping server {server_dict['name']}: Args must be a list.")
                    continue
            except:
                print(f"Skipping server {server_dict['name']}: Invalid JSON args.")
                continue
                
            env = json.loads(server_dict['env'])
            full_env = os.environ.copy()
            full_env.update(env)

            server_params = StdioServerParameters(
                command=command,
                args=args,
                env=full_env
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    
                    for tool in tools_result.tools:
                        # Convert MCP tool schema to OpenAI tool schema
                        openai_tool = {
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema
                            }
                        }
                        all_tools.append(openai_tool)
                        server_map[tool.name] = server_dict
                        
        except Exception as e:
            print(f"Error listing tools for server {server_dict['name']}: {e}")
            
    return all_tools, server_map

# --- Feishu Integration ---
@app.route('/api/feishu/event', methods=['POST'])
def feishu_event():
    data = request.json
    print(f"Feishu Event: {json.dumps(data)}")

    # 1. URL Verification
    if data.get('type') == 'url_verification':
        return jsonify({"challenge": data.get('challenge')})
    
    # 2. Check Event
    header = data.get('header', {})
    event_type = header.get('event_type')
    
    # Check Token (Optional, get from DB)
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key='feishu_verification_token'").fetchone()
    conn.close()
    if row and row['value']:
        expected_token = row['value']
        if header.get('token') != expected_token:
             # Just warn for now to avoid breaking if config is messy
             print(f"Warning: Verification token mismatch. Expected {expected_token}, got {header.get('token')}")

    # 3. Handle Message
    if event_type == 'im.message.receive_v1':
        event = data.get('event', {})
        message = event.get('message', {})
        msg_type = message.get('msg_type')
        content_json = message.get('content')
        sender_id = event.get('sender', {}).get('sender_id', {}).get('open_id')
        
        # Only handle text for now
        if msg_type == 'text':
            try:
                content_dict = json.loads(content_json)
                user_text = content_dict.get('text', '')
                
                # Async processing
                threading.Thread(target=process_feishu_message_thread, args=(sender_id, user_text)).start()
            except Exception as e:
                print(f"Error parsing Feishu message: {e}")

    return jsonify({"code": 0, "msg": "success"})

def process_feishu_message_thread(sender_id, user_text):
    with app.app_context():
        try:
            # Load settings
            conn = get_db_connection()
            settings = {row['key']: row['value'] for row in conn.execute('SELECT * FROM settings')}
            
            app_id = settings.get('feishu_app_id')
            app_secret = settings.get('feishu_app_secret')
            
            if not app_id or not app_secret:
                print("Feishu app_id or app_secret not configured.")
                return

            bot = FeishuBot(app_id, app_secret)
            
            # Find or Create Conversation
            conv_title = f"Feishu_{sender_id}"
            
            # Special command handling for new conversation
            if user_text.strip() == "/new":
                # Force create new conversation
                cursor = conn.execute('INSERT INTO conversations (title) VALUES (?)', (conv_title,))
                conversation_id = cursor.lastrowid
                conn.commit()
                bot.send_message("open_id", sender_id, "text", "✅ 已开启新会话，上下文已重置。")
                return

            conv = conn.execute('SELECT id FROM conversations WHERE title = ? ORDER BY created_at DESC LIMIT 1', (conv_title,)).fetchone()
            
            if not conv:
                cursor = conn.execute('INSERT INTO conversations (title) VALUES (?)', (conv_title,))
                conversation_id = cursor.lastrowid
                conn.commit()
            else:
                conversation_id = conv['id']
            
            # Save User Message
            conn.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                         (conversation_id, 'user', user_text))
            conn.commit()
            
            # Prepare LLM Call
            api_key = settings.get('api_key')
            base_url = settings.get('base_url', 'https://api.siliconflow.cn/v1')
            model = settings.get('model', 'deepseek-ai/DeepSeek-V3.2')
            
            if not api_key:
                bot.send_message("open_id", sender_id, "text", "Error: API Key not configured.")
                return

            history = conn.execute('SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC', (conversation_id,)).fetchall()
            conn.close()

            # System Prompt
            system_prompt = ""
            system_prompt_path = os.path.join(DATA_DIR, 'system_prompt.md')
            if os.path.exists(system_prompt_path):
                try:
                    with open(system_prompt_path, 'r', encoding='utf-8') as f:
                        system_prompt = f.read()
                except: pass
            
            messages_payload = []
            if system_prompt:
                messages_payload.append({'role': 'system', 'content': system_prompt})
            
            messages_payload.extend([{'role': row['role'], 'content': row['content']} for row in history])
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            # Run Loop for Tools
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Discover Tools
                mcp_tools, server_map = loop.run_until_complete(get_all_mcp_tools())
                skill_manager.load_skills()
                skills_desc = skill_manager.get_all_skills_description()
                
                local_tools = [{
                    "type": "function",
                    "function": {
                        "name": "execute_skill_function",
                        "description": "Execute a Python function from a local skill. Refer to the 'Available Local Skills' in the system prompt for details on available skills, files, and functions.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "skill_name": {
                                    "type": "string",
                                    "description": "The name of the skill (folder name)."
                                },
                                "file_name": {
                                    "type": "string",
                                    "description": "The python file name (e.g. 'utils.py')."
                                },
                                "function_name": {
                                    "type": "string",
                                    "description": "The function name to call."
                                },
                                "kwargs": {
                                    "type": "object",
                                    "description": "Key-value arguments for the function."
                                }
                            },
                            "required": ["skill_name", "file_name", "function_name"]
                        }
                    }
                }]
                
                tools = mcp_tools + local_tools
                
                # Inject Skills Desc
                found_sys = False
                for msg in messages_payload:
                    if msg['role'] == 'system':
                        msg['content'] += "\n\n" + skills_desc
                        found_sys = True
                        break
                if not found_sys:
                    messages_payload.insert(0, {'role': 'system', 'content': "You are 1052 AI.\n\n" + skills_desc})
                
                current_messages = messages_payload.copy()
                
                # --- Interruption Setup ---
                current_request_id = str(uuid.uuid4())
                CONVERSATION_SIGNALS[conversation_id] = current_request_id
                
                final_content = ""
                
                while True:
                    if CONVERSATION_SIGNALS.get(conversation_id) != current_request_id:
                        bot.send_message("open_id", sender_id, "text", "[Task Interrupted]")
                        break

                    payload = {
                        'model': model,
                        'messages': current_messages,
                        'stream': False # Feishu doesn't need stream for backend processing
                    }
                    if tools:
                        payload['tools'] = tools
                        payload['tool_choice'] = 'auto'
                        
                    response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=300)
                    response.raise_for_status()
                    res_json = response.json()
                    
                    choice = res_json['choices'][0]
                    message = choice['message']
                    finish_reason = choice['finish_reason']
                    
                    if message.get('content'):
                        final_content = message['content'] # Overwrite or append? Usually last message has content.
                    
                    tool_calls = message.get('tool_calls')
                    
                    if not tool_calls:
                        # Done
                        break
                    
                    # Add assistant message to history
                    current_messages.append(message)
                    
                    # Execute Tools
                    for tool_call in tool_calls:
                        if CONVERSATION_SIGNALS.get(conversation_id) != current_request_id:
                            break

                        func_name = tool_call['function']['name']
                        args_str = tool_call['function']['arguments']
                        call_id = tool_call['id']
                        
                        try:
                            func_args = json.loads(args_str)
                        except:
                            func_args = {}
                            
                        result = ""
                        
                        # Try Core Tools First
                        core_result = execute_core_tool(func_name, func_args)
                        if core_result is not None:
                            result = core_result
                        elif func_name in server_map:
                            try:
                                result = loop.run_until_complete(run_mcp_tool(server_map[func_name], func_name, func_args))
                            except Exception as e:
                                result = str(e)
                        
                        elif func_name == 'protocol_remember':
                            try:
                                key = func_args.get('key')
                                value = func_args.get('value')
                                protocol_brain.set_preference(key, value)
                                result = f"Successfully remembered preference: {key} = {value}"
                            except Exception as e:
                                result = f"Error remembering: {str(e)}"

                        elif func_name == 'protocol_learn_experience':
                            try:
                                problem = func_args.get('problem')
                                solution = func_args.get('solution')
                                tags = func_args.get('tags', [])
                                exp_id = protocol_brain.add_experience(problem, solution, tags)
                                result = f"Successfully learned experience. Experience ID: {exp_id}"
                            except Exception as e:
                                result = f"Error learning experience: {str(e)}"
                        
                        elif func_name == 'protocol_recall_experience':
                            try:
                                query = func_args.get('query')
                                results = protocol_brain.search_experience(query)
                                if not results:
                                    result = "No relevant experiences found."
                                else:
                                    # Limit to top 3 to save tokens
                                    top_results = results[:3]
                                    result = json.dumps(top_results, ensure_ascii=False)
                            except Exception as e:
                                result = f"Error recalling experience: {str(e)}"

                        elif func_name == 'execute_skill_function':
                            try:
                                # Parse args
                                skill_name = func_args.get('skill_name')
                                file_name = func_args.get('file_name')
                                function_name = func_args.get('function_name')
                                kwargs = func_args.get('kwargs', {})
                                
                                # Security Check
                                if skill_name == 'cmd_control' and not enable_system_control:
                                    result = "Error: System Control is disabled in settings. You cannot execute commands."
                                else:
                                    result = skill_manager.execute_skill_function(skill_name, file_name, function_name, kwargs)
                            except Exception as e:
                                result = f"Error executing skill: {str(e)}"
                                
                        elif func_name == 'record_improvement_plan':
                            try:
                                content = func_args.get('content')
                                entry_type = func_args.get('type', 'plan')
                                
                                conn = get_db_connection()
                                conn.execute('INSERT INTO ai_evolution_log (content, type, status) VALUES (?, ?, ?)', 
                                            (content, entry_type, 'pending' if entry_type == 'plan' else 'completed'))
                                conn.commit()
                                conn.close()
                                result = f"Successfully recorded {entry_type} into diary."
                            except Exception as e:
                                result = f"Error recording plan: {str(e)}"

                        else:
                            result = f"Error: Tool {func_name} not found."
                            
                        current_messages.append({
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": str(result)
                        })
                        
                # Loop ends when no tool calls
                
                # Save to DB
                conn = get_db_connection()
                conn.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                             (conversation_id, 'assistant', final_content))
                conn.commit()
                conn.close()
                
                # Send to Feishu
                if final_content:
                    bot.send_message("open_id", sender_id, "text", final_content)
                else:
                    bot.send_message("open_id", sender_id, "text", "(No response generated)")

            except Exception as e:
                print(f"Error in Feishu processing loop: {e}")
                bot.send_message("open_id", sender_id, "text", f"Error processing request: {str(e)}")
            finally:
                loop.close()

        except Exception as e:
            print(f"Critical Error in Feishu thread: {e}")

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    conversation_id = data.get('conversation_id')
    user_message = data.get('message')
    
    if not conversation_id or not user_message:
        return jsonify({'error': 'Missing conversation_id or message'}), 400

    conn = get_db_connection()
    
    # Save user message
    conn.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                 (conversation_id, 'user', user_message))
    conn.commit()
    
    # Get settings
    settings_rows = conn.execute('SELECT * FROM settings').fetchall()
    settings = {row['key']: row['value'] for row in settings_rows}
    
    api_key = settings.get('api_key')
    base_url = settings.get('base_url', 'https://api.siliconflow.cn/v1')
    model = settings.get('model', 'deepseek-ai/DeepSeek-V3.2')
    # Default to True if not set (first run)
    enable_system_control = settings.get('enable_system_control', 'true') == 'true'
    enable_self_reflection = settings.get('enable_self_reflection') == 'true'
    model_provider = settings.get('model_provider', 'openai')
    
    # Handle Local Model Provider
    if model_provider == 'local':
        if not api_key:
            api_key = 'ollama' # Dummy key often required by clients even for local models
    
    # Get conversation history
    history = conn.execute('SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC', (conversation_id,)).fetchall()
    conn.close()
    
    # --- Interruption Setup ---
    current_request_id = str(uuid.uuid4())
    CONVERSATION_SIGNALS[conversation_id] = current_request_id
    
    def check_interrupt():
        if CONVERSATION_SIGNALS.get(conversation_id) != current_request_id:
            raise TaskInterrupted("Interrupted by new request")

    # Load system prompt
    system_prompt = ""
    system_prompt_path = os.path.join(DATA_DIR, 'system_prompt.md')
    if os.path.exists(system_prompt_path):
        try:
            with open(system_prompt_path, 'r', encoding='utf-8') as f:
                system_prompt = f.read()
        except Exception as e:
            print(f"Error reading system prompt: {e}")
            
    # Initial messages list
    messages_payload = []
    if system_prompt:
        messages_payload.append({'role': 'system', 'content': system_prompt})
        
    messages_payload.extend([{'role': row['role'], 'content': row['content']} for row in history])
    
    # Append current user message (already saved to DB, but need it in payload for this turn)
    # Wait, history includes it? Yes, we saved it above.
    # history query fetches ALL messages for conversation_id.
    # So messages_payload HAS the latest user message.

    if not api_key:
        return jsonify({'error': '请先配置 API Key'}), 400

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # --- Interruption Setup ---
    current_request_id = str(uuid.uuid4())
    CONVERSATION_SIGNALS[conversation_id] = current_request_id
    
    def check_interrupt():
        if CONVERSATION_SIGNALS.get(conversation_id) != current_request_id:
            raise TaskInterrupted("Interrupted by new request")

    def generate():
        # Async wrapper to run async code in sync generator
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 1. Discover MCP tools
            check_interrupt()
            mcp_tools, server_map = loop.run_until_complete(get_all_mcp_tools())
            
            # Load local skills (Descriptions only)
            skill_manager.load_skills()
            skills_description = skill_manager.get_all_skills_description()
            
            # Add Core Tools & Generic Skill Executor Tool
            local_tools = CORE_TOOLS_SCHEMA + [{
                "type": "function",
                "function": {
                    "name": "execute_skill_function",
                    "description": "Execute a Python function from a local skill. Refer to the 'Available Local Skills' in the system prompt for details on available skills, files, and functions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "description": "The name of the skill (folder name)."
                            },
                            "file_name": {
                                "type": "string",
                                "description": "The python file name (e.g. 'utils.py')."
                            },
                            "function_name": {
                                "type": "string",
                                "description": "The function name to call."
                            },
                            "kwargs": {
                                "type": "object",
                                "description": "Key-value arguments for the function."
                            }
                        },
                        "required": ["skill_name", "file_name", "function_name"]
                    }
                }
            },
            # 1052 Protocol Tools
            {
                "type": "function",
                "function": {
                    "name": "protocol_remember",
                    "description": "Store a user preference or fact into long-term memory. Use this when the user explicitly asks to remember something or when you detect a stable user preference (e.g., 'I like python', 'Call me Master').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {
                                "type": "string",
                                "description": "The key for the preference (e.g., 'language_preference', 'nickname')."
                            },
                            "value": {
                                "type": "string",
                                "description": "The value to store."
                            }
                        },
                        "required": ["key", "value"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "protocol_learn_experience",
                    "description": "Save a solution to a problem as an 'Experience'. Use this when you have successfully solved a complex problem or when the user provides a specific solution they want you to remember.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "problem": {
                                "type": "string",
                                "description": "A short description of the problem."
                            },
                            "solution": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "A list of steps or a description of the solution."
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Tags for easier retrieval (e.g., ['python', 'error', 'network'])."
                            }
                        },
                        "required": ["problem", "solution"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "protocol_recall_experience",
                    "description": "Search for past experiences/solutions related to a query. Use this when you encounter a problem and want to check if you've solved it before.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Keywords to search for."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "record_improvement_plan",
                    "description": "Record a self-improvement plan or internal monologue into your diary. Use this during Self-Reflection when you identify a gap and want to fix it later automatically.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "The detailed plan or monologue. Describe what skill you want to learn or what code you want to write."
                            },
                            "type": {
                                "type": "string",
                                "enum": ["plan", "monologue"],
                                "description": "Type of the entry. Use 'plan' for actionable items that need execution."
                            }
                        },
                        "required": ["content", "type"]
                    }
                }
            }]

            # Merge tools
            tools = mcp_tools + local_tools
            
            # We need a mutable list of messages for the multi-turn tool conversation
            current_messages = messages_payload.copy()
            
            # Inject Skills Description into System Prompt (or first message)
            # Find the system prompt and append, or add new system prompt
            
            # --- Time Context Injection ---
            now = datetime.datetime.now()
            # Force refresh of time context with explicit timezone
            try:
                # Use local system time with offset
                import time
                # Calculate offset in hours
                if time.localtime().tm_isdst and time.daylight:
                    offset_sec = -time.altzone
                else:
                    offset_sec = -time.timezone
                    
                offset_hours = offset_sec / 3600
                sign = '+' if offset_hours >= 0 else ''
                tz_str = f"UTC{sign}{int(offset_hours)}"
            except:
                tz_str = "Local System Time"
            
            time_str = now.strftime('%Y-%m-%d %H:%M:%S')
            weekday = now.strftime('%A')
            time_context = f"Current System Time: {time_str} ({weekday})\n"
            time_context += f"System Timezone: {tz_str}\n\n"
            
            # --- 1052 Protocol Context Injection ---
            # Inject Basic Info & Preferences into System Prompt
            memory_context = ""
            try:
                mem_data = protocol_brain.get_memory_json()
                preferences = mem_data.get('preferences', {})
                basic = mem_data.get('basic', {})
                
                memory_context = f"\n\n## 1052 Protocol Memory Context\n"
                memory_context += f"- **User Nickname**: {basic.get('nickname')}\n"
                memory_context += f"- **Talk Style**: {preferences.get('talk_style')}\n"
                
                custom_prefs = preferences.get('custom', {})
                if custom_prefs:
                    memory_context += "- **Custom Preferences**:\n"
                    for k, v in custom_prefs.items():
                        memory_context += f"  - {k}: {v}\n"
            except Exception as e:
                print(f"Failed to inject memory context: {e}")
            
            found_system = False
            for msg in current_messages:
                if msg['role'] == 'system':
                    # Append skills description to existing system prompt
                    # We assume system_prompt.md is the source of truth for base identity
                    # PREPEND time_context to ensure it's seen first
                    msg['content'] = time_context + msg['content'] + memory_context + "\n\n" + skills_description
                    found_system = True
                    break
            
            if not found_system:
                # If no system prompt found (e.g. file missing), use a default one + skills
                default_system = "You are 1052 AI."
                current_messages.insert(0, {'role': 'system', 'content': time_context + default_system + memory_context + "\n\n" + skills_description})

            
            while True:
                payload = {
                    'model': model,
                    'messages': current_messages,
                    'stream': True
                }
                if tools:
                    payload['tools'] = tools
                    payload['tool_choice'] = 'auto'

                # Call OpenAI
                # print(f"Sending payload to LLM: {json.dumps(payload, indent=2)}")
                try:
                    check_interrupt()
                    response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, stream=True, timeout=300)
                    response.raise_for_status()
                except TaskInterrupted:
                    yield json.dumps({"type": "error", "content": "\n[Task Interrupted by new message]"}) + "\n"
                    return
                except requests.exceptions.HTTPError as e:
                    error_content = response.text
                    yield json.dumps({"type": "error", "content": f"LLM API Error: {str(e)}\nDetails: {error_content}"}) + "\n"
                    return

                tool_calls_buffer = {} # index -> tool_call_data
                full_content = ""
                finish_reason = None
                
                for line in response.iter_lines():
                    check_interrupt()
                    if not line: continue
                    line = line.decode('utf-8')
                    if not line.startswith('data: '): continue
                    data_str = line[6:]
                    if data_str == '[DONE]': break
                    
                    try:
                        chunk = json.loads(data_str)
                        if not chunk['choices']: continue
                        delta = chunk['choices'][0].get('delta', {})
                        finish_reason = chunk['choices'][0].get('finish_reason')

                        # Handle content
                        if 'content' in delta and delta['content']:
                            content = delta['content']
                            full_content += content
                            yield json.dumps({"type": "content", "data": content}) + "\n"

                        # Handle tool calls
                        if 'tool_calls' in delta and delta['tool_calls']:
                            for tool_call in delta['tool_calls']:
                                index = tool_call['index']
                                if index not in tool_calls_buffer:
                                    tool_calls_buffer[index] = {
                                        "id": tool_call.get("id"),
                                        "type": "function",
                                        "function": {
                                            "name": tool_call["function"].get("name", ""),
                                            "arguments": tool_call["function"].get("arguments", "")
                                        }
                                    }
                                else:
                                    if "function" in tool_call:
                                        if "name" in tool_call["function"]:
                                            tool_calls_buffer[index]["function"]["name"] += tool_call["function"]["name"]
                                        if "arguments" in tool_call["function"]:
                                            tool_calls_buffer[index]["function"]["arguments"] += tool_call["function"]["arguments"]
                                            
                                    if "id" in tool_call and tool_call["id"]:
                                        tool_calls_buffer[index]["id"] = tool_call["id"]
                    
                    except json.JSONDecodeError:
                        continue
                
                # Check if we have tool calls
                if not tool_calls_buffer:
                    # No tool calls, we are done. Save assistant message and exit loop.
                    conn = get_db_connection()
                    conn.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                                (conversation_id, 'assistant', full_content))
                    conn.commit()
                    conn.close()
                    break
                
                # Convert buffer to list
                tool_calls = list(tool_calls_buffer.values())
                
                # Append assistant message with tool_calls to history
                assistant_msg = {
                    "role": "assistant",
                    "content": full_content if full_content else None,
                    "tool_calls": tool_calls
                }
                current_messages.append(assistant_msg)
                
                # Execute tools
                for tool_call in tool_calls:
                    check_interrupt()
                    func_name = tool_call['function']['name']
                    func_args_str = tool_call['function']['arguments']
                    call_id = tool_call['id']
                    
                    try:
                        func_args = json.loads(func_args_str)
                    except:
                        func_args = {}

                    # Inject conversation_id for core tools that need it (like scheduler)
                    func_args['_conversation_id'] = conversation_id # Or handle error

                    # Notify frontend
                    yield json.dumps({
                        "type": "tool_start",
                        "tool": func_name,
                        "args": func_args
                    }) + "\n"
                    
                    result = ""
                    if func_name in server_map:
                        try:
                            result = loop.run_until_complete(run_mcp_tool(server_map[func_name], func_name, func_args))
                        except Exception as e:
                            result = f"Error executing tool: {str(e)}"
                    elif func_name == 'execute_skill_function':
                        try:
                            # Parse args
                            skill_name = func_args.get('skill_name')
                            file_name = func_args.get('file_name')
                            function_name = func_args.get('function_name')
                            kwargs = func_args.get('kwargs', {})
                            
                            # Inject context
                            kwargs['_conversation_id'] = conversation_id
                            
                            # Security Check
                            if skill_name == 'cmd_control' and not enable_system_control:
                                result = "Error: System Control is disabled in settings. You cannot execute commands."
                            else:
                                result = skill_manager.execute_skill_function(skill_name, file_name, function_name, kwargs)
                        except Exception as e:
                            result = f"Error executing skill: {str(e)}"
                    else:
                        result = f"Error: Tool {func_name} not found."

                    # Notify frontend
                    yield json.dumps({
                        "type": "tool_end",
                        "tool": func_name,
                        "result": result
                    }) + "\n"

                    # Add result to history
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": str(result) # Ensure string
                    })
                    
                    # For protocol_remember, we also want to inject this into the NEXT turn's system prompt immediately?
                    # Or just wait for next turn.
                    # Wait, if we updated memory, we should probably reload memory_context for subsequent turns in the same session?
                    # But session is stateless in HTTP unless we persist context.
                    # Actually, since `protocol_brain` is a global object in this app context (or re-instantiated), 
                    # and we modify `protocol_brain.memory` in place in `remember` method,
                    # the next turn (next while loop iteration if we had one, but we break after tool calls usually)
                    # Wait, the `generate` function loops over tool calls and then yields.
                    # It does NOT loop back to LLM for a second thought in the SAME request unless we implement multi-turn tool use.
                    # Oh, the `while True` loop in `generate` IS for multi-turn tool use!
                    # So if tool returns, we append result and loop back to LLM.
                    # The LLM sees the tool output.
                    
                    # BUT, the `system_prompt` (with memory_context) was constructed at the BEGINNING of `generate`.
                    # So the LLM still sees the OLD memory context in the system prompt.
                    # However, it sees the "Successfully remembered..." tool output, so it KNOWS it remembered it.
                    # That's sufficient for the current session.
                    # Next time `generate` is called (next user message), memory_context will be re-read from disk.
                    
                # Loop continues to next iteration to send tool outputs back to OpenAI
                pass
                
            # If we are here, it means we finished processing a turn (with or without tool calls)
            # If enable_self_reflection is ON, we should trigger a reflection step
            # But we must be careful not to infinite loop.
            # Reflection should be a separate "system" prompt call that analyzes the LAST turn.
            # However, simpler implementation:
            # If finish_reason is 'stop', and enable_self_reflection is True, we can append a system prompt
            # asking for reflection and continue generation?
            # Or better: Just append a hidden "Thought" block if the model supports it?
            # DeepSeek R1 supports <think>.
            # But user wants "Self-Evolution": "Think what is missing and improve".
            
            # Implementation:
            # After the main response is done (no more tool calls), if enable_self_reflection is True:
            # We trigger a SECOND, invisible LLM call to analyze the situation.
            
        except TaskInterrupted:
            yield json.dumps({"type": "error", "content": "\n[Task Interrupted by new message]"}) + "\n"
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            yield json.dumps({"type": "error", "content": error_msg}) + "\n"
        finally:
            loop.close()
            
            # --- Self-Reflection & Evolution Step ---
            # Only run if enabled and no error occurred in main loop
            if enable_self_reflection and finish_reason == 'stop':
                try:
                    check_interrupt()
                    # We run this in a new loop or just sync since we are already in a generator?
                    # We need to yield output to frontend so user sees the "Evolution".
                    
                    yield json.dumps({"type": "content", "data": "\n\n--- 🧠 **Self-Reflection** ---\n"}) + "\n"
                    
                    reflection_prompt = (
                        "You have just completed a task for the user. Now, engage in **Self-Reflection**.\n"
                        "1. Analyze your performance: Did you satisfy the user's intent? Was there anything missing?\n"
                        "2. Identify gaps: Do you lack any skills or knowledge to do this better?\n"
                        "3. **Self-Improvement**: If you identify a missing skill, use `record_improvement_plan` to write it down into your diary. It will be automatically implemented tonight.\n"
                        "4. Output your thoughts concisely."
                    )
                    
                    # Add reflection instruction
                    reflection_messages = current_messages.copy()
                    reflection_messages.append({'role': 'system', 'content': reflection_prompt})
                    
                    # Call LLM again for reflection
                    # Note: We need a new loop or simple request
                    refl_payload = {
                        'model': model,
                        'messages': reflection_messages,
                        'stream': True
                    }
                    if tools:
                        refl_payload['tools'] = tools
                        refl_payload['tool_choice'] = 'auto'

                    # Add record_improvement_plan to available tools list for reflection
                    # Actually tools already has it because we added it to `local_tools` above
                    
                    # print("Starting Reflection...")
                    # We use a separate synchronous request for Reflection to handle tool calls robustly,
                    # but we simulate streaming for user experience?
                    # Or just stream normally and parse tool calls manually.
                    
                    check_interrupt()
                    refl_response = requests.post(f"{base_url}/chat/completions", headers=headers, json=refl_payload, stream=True, timeout=300)
                    
                    reflection_tool_buffer = {}
                    
                    for line in refl_response.iter_lines():
                        check_interrupt()
                        if not line: continue
                        line = line.decode('utf-8')
                        if not line.startswith('data: '): continue
                        data_str = line[6:]
                        if data_str == '[DONE]': break
                        try:
                            chunk = json.loads(data_str)
                            if not chunk['choices']: continue
                            delta = chunk['choices'][0].get('delta', {})
                            
                            if 'content' in delta and delta['content']:
                                yield json.dumps({"type": "content", "data": delta['content']}) + "\n"
                                
                            if 'tool_calls' in delta and delta['tool_calls']:
                                for tc in delta['tool_calls']:
                                    idx = tc['index']
                                    if idx not in reflection_tool_buffer:
                                        reflection_tool_buffer[idx] = tc
                                    else:
                                        # Merge
                                        if 'function' in tc:
                                            if 'name' in tc['function']:
                                                if 'function' not in reflection_tool_buffer[idx]: reflection_tool_buffer[idx]['function'] = {}
                                                reflection_tool_buffer[idx]['function']['name'] = reflection_tool_buffer[idx]['function'].get('name', '') + tc['function']['name']
                                            if 'arguments' in tc['function']:
                                                if 'function' not in reflection_tool_buffer[idx]: reflection_tool_buffer[idx]['function'] = {}
                                                reflection_tool_buffer[idx]['function']['arguments'] = reflection_tool_buffer[idx]['function'].get('arguments', '') + tc['function']['arguments']
                        except: pass
                    
                    yield json.dumps({"type": "content", "data": "\n\n--------------------------------\n"}) + "\n"

                    # After stream ends, check for tool calls
                    if reflection_tool_buffer:
                        for idx, tool_call in reflection_tool_buffer.items():
                            func_name = tool_call['function']['name']
                            args_str = tool_call['function']['arguments']
                            try:
                                args = json.loads(args_str)
                                if func_name == 'record_improvement_plan':
                                    # Execute it
                                    content = args.get('content')
                                    entry_type = args.get('type', 'plan')
                                    
                                    conn = get_db_connection()
                                    conn.execute('INSERT INTO ai_evolution_log (content, type, status) VALUES (?, ?, ?)', 
                                                (content, entry_type, 'pending' if entry_type == 'plan' else 'completed'))
                                    conn.commit()
                                    conn.close()
                                    
                                    yield json.dumps({"type": "content", "data": f"\n[Diary] Recorded: {entry_type}\n"}) + "\n"
                            except Exception as e:
                                print(f"Failed to execute reflection tool: {e}")

                except Exception as e:
                    print(f"Reflection failed: {e}")

                except Exception as e:
                    print(f"Reflection failed: {e}")

    return Response(stream_with_context(generate()), content_type='text/plain')


    return Response(stream_with_context(generate()), content_type='text/plain')

async def headless_chat_turn(user_id, user_message, reply_func):
    """
    Process a chat turn without Flask context, suitable for Telegram/CLI.
    """
    conn = get_db_connection()
    
    # Special command for new conversation
    if user_message.strip() == "/new":
        conn.execute('INSERT INTO conversations (title) VALUES (?)', (f"Telegram_{user_id}",))
        conn.commit()
        conn.close()
        await reply_func("✅ 已开启新会话，上下文已重置。")
        return

    # Get conversation history
    # We need to find the latest conversation for this user
    # Telegram users don't have explicit conversation IDs in the message, 
    # so we map user_id -> latest conversation
    
    # 1. Find latest conversation for this user
    # We assume conversation title format "Telegram_{user_id}"
    conv = conn.execute('SELECT id FROM conversations WHERE title = ? ORDER BY created_at DESC LIMIT 1', (f"Telegram_{user_id}",)).fetchone()
    
    if not conv:
        # Create new one
        cursor = conn.execute('INSERT INTO conversations (title) VALUES (?)', (f"Telegram_{user_id}",))
        conversation_id = cursor.lastrowid
        conn.commit()
    else:
        conversation_id = conv['id']
    
    # 2. Save User Message
    conn.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                 (conversation_id, 'user', user_message))
    conn.commit()
    
    # Get settings
    settings_rows = conn.execute('SELECT * FROM settings').fetchall()
    settings = {row['key']: row['value'] for row in settings_rows}
    
    api_key = settings.get('api_key')
    base_url = settings.get('base_url', 'https://api.siliconflow.cn/v1')
    model = settings.get('model', 'deepseek-ai/DeepSeek-V3.2')
    # Default to True
    enable_system_control = settings.get('enable_system_control', 'true') == 'true'
    enable_self_reflection = settings.get('enable_self_reflection') == 'true'
    model_provider = settings.get('model_provider', 'openai')
    
    # Handle Local Model Provider
    if model_provider == 'local':
        if not api_key:
            api_key = 'ollama'

    # Get conversation history
    history = conn.execute('SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC', (conversation_id,)).fetchall()
    conn.close()
    
    if not api_key:
        await reply_func("Error: API Key not configured in settings.")
        return

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    # --- Interruption Setup ---
    current_request_id = str(uuid.uuid4())
    CONVERSATION_SIGNALS[conversation_id] = current_request_id
    
    def is_interrupted():
        return CONVERSATION_SIGNALS.get(conversation_id) != current_request_id

    # Load system prompt
    system_prompt = ""
    system_prompt_path = os.path.join(DATA_DIR, 'system_prompt.md')
    if os.path.exists(system_prompt_path):
        try:
            with open(system_prompt_path, 'r', encoding='utf-8') as f:
                system_prompt = f.read()
        except Exception as e:
            print(f"Error reading system prompt: {e}")
            
    # Initial messages list
    messages_payload = []
    if system_prompt:
        messages_payload.append({'role': 'system', 'content': system_prompt})
        
    messages_payload.extend([{'role': row['role'], 'content': row['content']} for row in history])
    
    # --- Context Injection (Time & Memory) ---
    # (Copied from generate)
    now = datetime.datetime.now()
    try:
        import time
        offset = -time.timezone if (time.localtime().tm_isdst == 0) else -time.altzone
        offset_hours = offset / 3600
        tz_str = f"UTC{'+' if offset_hours >= 0 else ''}{int(offset_hours)}"
    except:
        tz_str = "Local System Time"
        
    time_str = now.strftime('%Y-%m-%d %H:%M:%S')
    weekday = now.strftime('%A')
    time_context = f"Current System Time: {time_str} ({weekday})\n"
    time_context += f"System Timezone: {tz_str}\n\n"
    
    # Inject Skills Description
    skill_manager.load_skills()
    skills_description = skill_manager.get_all_skills_description()
    
    memory_context = ""
    try:
        mem_data = protocol_brain.get_memory_json()
        preferences = mem_data.get('preferences', {})
        basic = mem_data.get('basic', {})
        
        memory_context = f"\n\n## 1052 Protocol Memory Context\n"
        memory_context += f"- **User Nickname**: {basic.get('nickname')}\n"
        memory_context += f"- **Talk Style**: {preferences.get('talk_style')}\n"
        
        custom_prefs = preferences.get('custom', {})
        if custom_prefs:
            memory_context += "- **Custom Preferences**:\n"
            for k, v in custom_prefs.items():
                memory_context += f"  - {k}: {v}\n"
    except Exception as e:
        print(f"Failed to inject memory context: {e}")
    
    found_system = False
    for msg in messages_payload:
        if msg['role'] == 'system':
            msg['content'] = time_context + msg['content'] + memory_context + "\n\n" + skills_description
            found_system = True
            break
    
    if not found_system:
        default_system = "You are 1052 AI."
        messages_payload.insert(0, {'role': 'system', 'content': time_context + default_system + memory_context + "\n\n" + skills_description})

    # Prepare Tools
    # (Simplified: assume we can get MCP tools here or reuse a global cache? 
    # For now, let's just use local tools to avoid async loop issues if mcp discovery is slow)
    # Ideally we should call get_all_mcp_tools() but it requires an event loop.
    # We are in an async function, so we can await it? No, get_all_mcp_tools is async but we need to manage loop carefully.
    # Let's assume we are running in an asyncio loop (TG bot runs in asyncio loop).
    
    try:
        mcp_tools, server_map = await get_all_mcp_tools()
    except:
        mcp_tools = []
        server_map = {}

    local_tools = CORE_TOOLS_SCHEMA + [{
        "type": "function",
        "function": {
            "name": "execute_skill_function",
            "description": "Execute a Python function from a local skill.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string"},
                    "file_name": {"type": "string"},
                    "function_name": {"type": "string"},
                    "kwargs": {"type": "object"}
                },
                "required": ["skill_name", "file_name", "function_name"]
            }
        }
    },
    # Add Protocol Tools (Simplified copy)
    {
        "type": "function",
        "function": {
            "name": "protocol_remember",
            "description": "Store a user preference or fact into long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"}
                },
                "required": ["key", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "protocol_learn_experience",
            "description": "Save a solution to a problem as an 'Experience'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "problem": {"type": "string"},
                    "solution": {"type": "array", "items": {"type": "string"}},
                    "tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["problem", "solution"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "protocol_recall_experience",
            "description": "Search for past experiences/solutions related to a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_improvement_plan",
            "description": "Record a self-improvement plan into diary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "type": {"type": "string", "enum": ["plan", "monologue"]}
                },
                "required": ["content", "type"]
            }
        }
    }]
    
    tools = mcp_tools + local_tools
    current_messages = messages_payload
    
    # Turn Loop
    while True:
        if is_interrupted():
            await reply_func("\n[Task Interrupted by new message]")
            break

        payload = {
            'model': model,
            'messages': current_messages,
            'stream': False # Telegram: No streaming for logic simplicity (or implement chunking)
        }
        if tools:
            payload['tools'] = tools
            payload['tool_choice'] = 'auto'

        try:
            if is_interrupted(): raise TaskInterrupted()
            
            # Switch to streaming mode to allow interruption during generation
            payload['stream'] = True
            
            # Use aiohttp for async non-blocking request
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=300) as response:
                    response.raise_for_status()
                    
                    # Manually collect the stream content
                    full_content = ""
                    tool_calls_buffer = {}
                    finish_reason = None
                    
                    async for line in response.content:
                        if is_interrupted(): raise TaskInterrupted()
                        if not line: continue
                        
                        decoded_line = line.decode('utf-8').strip()
                        if not decoded_line.startswith('data: '): continue
                        
                        data_str = decoded_line[6:]
                        if data_str == '[DONE]': break
                        
                        try:
                            chunk = json.loads(data_str)
                            if not chunk['choices']: continue
                            
                            delta = chunk['choices'][0].get('delta', {})
                            finish_reason = chunk['choices'][0].get('finish_reason')
                            
                            # Accumulate content
                            if 'content' in delta and delta['content']:
                                content_chunk = delta['content']
                                full_content += content_chunk
                                
                            # Accumulate tool calls
                            if 'tool_calls' in delta and delta['tool_calls']:
                                for tc in delta['tool_calls']:
                                    idx = tc['index']
                                    if idx not in tool_calls_buffer:
                                        tool_calls_buffer[idx] = tc
                                    else:
                                        # Merge
                                        if 'function' in tc:
                                            if 'name' in tc['function']:
                                                if 'function' not in tool_calls_buffer[idx]: tool_calls_buffer[idx]['function'] = {}
                                                tool_calls_buffer[idx]['function']['name'] = tool_calls_buffer[idx]['function'].get('name', '') + tc['function']['name']
                                            if 'arguments' in tc['function']:
                                                if 'function' not in tool_calls_buffer[idx]: tool_calls_buffer[idx]['function'] = {}
                                                tool_calls_buffer[idx]['function']['arguments'] = tool_calls_buffer[idx]['function'].get('arguments', '') + tc['function']['arguments']
                        except:
                            pass
            
            # Notify User (Optional)
            if tool_calls_buffer:
                # await reply_func(f"✅ 执行完成: {func_name}") # Moved to inside loop
                pass

            # Reconstruct message object for history
            
            # Reconstruct message object for history
            msg = {'role': 'assistant', 'content': full_content}
            tool_calls = []
            if tool_calls_buffer:
                tool_calls = [v for k, v in sorted(tool_calls_buffer.items())]
                msg['tool_calls'] = tool_calls
                
                # Notify User if tool calls are present (but not yet executed)
                tool_names = [v['function']['name'] for k, v in tool_calls_buffer.items() if 'function' in v and 'name' in v['function']]
                if tool_names:
                    tools_str = ", ".join(tool_names)
                    await reply_func(f"⏳ 正在执行任务: {tools_str}...")
            
            # Save assistant message
            current_messages.append(msg)
            
            if full_content:
                await reply_func(full_content)
                # Save to DB
                conn = get_db_connection()
                conn.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                            (conversation_id, 'assistant', full_content))
                conn.commit()
                conn.close()

            # Check if this is a tool use turn
            if not tool_calls:
                # Normal response, done
                break
            
            # If we have tool calls, we execute them and then CONTINUE the loop
            # The next iteration will send the tool outputs back to LLM
            # and LLM will generate the next response (or more tool calls)
            for tc in tool_calls:
                if is_interrupted(): raise TaskInterrupted()
                
                func_name = tc['function']['name']
                args_str = tc['function']['arguments']
                call_id = tc['id']
                
                try:
                    func_args = json.loads(args_str)
                except:
                    func_args = {}
                
                func_args['_conversation_id'] = conversation_id
                
                # Notify User (Optional)
                await reply_func(f"✅ 执行完成: {func_name}")
                
                result = ""
                core_res = execute_core_tool(func_name, func_args)
                if core_res is not None:
                    result = core_res
                elif func_name in server_map:
                    try:
                        result = await run_mcp_tool(server_map[func_name], func_name, func_args)
                    except Exception as e:
                        result = f"Error executing tool: {str(e)}"
                elif func_name == 'execute_skill_function':
                    try:
                        skill_name = func_args.get('skill_name')
                        file_name = func_args.get('file_name')
                        function_name = func_args.get('function_name')
                        kwargs = func_args.get('kwargs', {})
                        kwargs['_conversation_id'] = conversation_id
                        
                        if skill_name == 'cmd_control' and not enable_system_control:
                            result = "Error: System Control is disabled."
                        else:
                            result = skill_manager.execute_skill_function(skill_name, file_name, function_name, kwargs)
                    except Exception as e:
                        result = f"Error executing skill: {str(e)}"
                # ... Handle Protocol Tools (Copy logic from generate) ...
                elif func_name == 'protocol_remember':
                    try:
                        saved_path = protocol_brain.remember(func_args.get('key'), func_args.get('value'))
                        result = f"Successfully remembered: {func_args.get('key')} = {func_args.get('value')}. Saved to {saved_path}"
                    except Exception as e: result = str(e)
                elif func_name == 'protocol_learn_experience':
                    try:
                        saved_path = protocol_brain.learn_experience(func_args.get('problem'), func_args.get('solution'), func_args.get('tags'))
                        result = f"Experience learned and saved to {saved_path}."
                    except Exception as e: result = str(e)
                elif func_name == 'protocol_recall_experience':
                    try:
                        res = protocol_brain.search_experience(func_args.get('query'))
                        result = json.dumps(res, ensure_ascii=False)
                    except Exception as e: result = str(e)
                elif func_name == 'record_improvement_plan':
                    try:
                        content = func_args.get('content')
                        entry_type = func_args.get('type', 'plan')
                        conn = get_db_connection()
                        conn.execute('INSERT INTO ai_evolution_log (content, type, status) VALUES (?, ?, ?)', 
                                    (content, entry_type, 'pending' if entry_type == 'plan' else 'completed'))
                        conn.commit()
                        conn.close()
                        result = f"Recorded {entry_type}."
                    except Exception as e: result = str(e)
                else:
                    result = f"Error: Tool {func_name} not found."
                
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": str(result)
                })

        except TaskInterrupted:
            await reply_func("\n[Task Interrupted by new message]")
            break
        except Exception as e:
            await reply_func(f"Error: {str(e)}")
            break

    # --- Self-Reflection (Simplified for Headless) ---
    if enable_self_reflection:
        # Just trigger it silently or post to DB?
        # For TG, maybe post it as a separate message?
        pass

# Scheduler Thread Function
def scheduler_loop():
    print("Scheduler thread started.")
    last_evolution_check = datetime.datetime.now()
    
    while True:
        try:
            # Use absolute path to DB file
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            
            now = datetime.datetime.now()
            now_str = now.strftime('%Y-%m-%d %H:%M:%S')
            
            # 1. Handle Scheduled Tasks
            # Find pending tasks that are due
            # trigger_time <= now_str works for ISO format strings
            cursor = conn.execute(
                "SELECT * FROM scheduled_tasks WHERE status = 'pending' AND trigger_time <= ?", 
                (now_str,)
            )
            tasks = cursor.fetchall()
            
            if tasks:
                print(f"Found {len(tasks)} due tasks.")
                
            for task in tasks:
                task_id = task['id']
                content = task['content']
                conversation_id = task['conversation_id']
                
                print(f"Executing scheduled task {task_id}: {content}")
                
                # Mark as completed
                conn.execute("UPDATE scheduled_tasks SET status = 'completed' WHERE id = ?", (task_id,))
                
                # Add reminder message to chat
                reminder_msg = f"⏰ **定时提醒**: {content}"
                conn.execute(
                    'INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                    (conversation_id, 'assistant', reminder_msg)
                )
                conn.commit()
                
            # 2. Handle Auto-Evolution (Nightly)
            # Check every 10 minutes to save resources
            if (now - last_evolution_check).total_seconds() > 600:
                last_evolution_check = now
                
                # Condition: Idle for > 2 hours?
                # Find last user message
                last_msg = conn.execute("SELECT created_at FROM messages WHERE role='user' ORDER BY created_at DESC LIMIT 1").fetchone()
                
                should_evolve = False
                if last_msg:
                    last_time_str = last_msg['created_at']
                    try:
                        # created_at is likely YYYY-MM-DD HH:MM:SS
                        last_time = datetime.datetime.strptime(last_time_str, '%Y-%m-%d %H:%M:%S')
                        if (now - last_time).total_seconds() > 7200: # 2 hours
                            should_evolve = True
                    except:
                        pass # Date format error
                else:
                    # No messages ever?
                    should_evolve = True

                # Also check pending plans
                pending_plans = conn.execute("SELECT * FROM ai_evolution_log WHERE status='pending' AND type='plan'").fetchall()
                
                if should_evolve and pending_plans:
                    print(f"Triggering Auto-Evolution for {len(pending_plans)} plans...")
                    
                    # We need to run evolution for each plan
                    # Note: This is running in a thread, so we can do blocking calls.
                    # We need to load settings to get API key
                    settings_rows = conn.execute('SELECT * FROM settings').fetchall()
                    settings = {row['key']: row['value'] for row in settings_rows}
                    api_key = settings.get('api_key')
                    base_url = settings.get('base_url', 'https://api.siliconflow.cn/v1')
                    model = settings.get('model', 'deepseek-ai/DeepSeek-V3.2')
                    # Default to True
                    enable_system_control = settings.get('enable_system_control', 'true') == 'true'
                    
                    if api_key and enable_system_control:
                        headers = {
                            'Authorization': f'Bearer {api_key}',
                            'Content-Type': 'application/json'
                        }
                        
                        # Load tools for evolution (it needs to write code!)
                        # We re-discover tools here
                        # Note: run_until_complete in a thread that might not have loop?
                        # It's better to instantiate a new loop for this thread.
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        try:
                            mcp_tools, server_map = loop.run_until_complete(get_all_mcp_tools())
                            skill_manager.load_skills()
                            skills_desc = skill_manager.get_all_skills_description()
                            
                            # Construct tools list (Reuse definition from main route is hard, let's simplify)
                            # We only need `execute_skill_function` and `protocol_learn_experience` really.
                            # But full power is better.
                            # For simplicity, let's assume `execute_skill_function` is enough for "Evolution".
                            
                            evolve_tools = CORE_TOOLS_SCHEMA + [{
                                "type": "function",
                                "function": {
                                    "name": "execute_skill_function",
                                    "description": "Execute a Python function from a local skill.",
                                    "parameters": {
                                        "type": "object",
                                        "properties": {
                                            "skill_name": {"type": "string"},
                                            "file_name": {"type": "string"},
                                            "function_name": {"type": "string"},
                                            "kwargs": {"type": "object"}
                                        },
                                        "required": ["skill_name", "file_name", "function_name"]
                                    }
                                }
                            },
                            {
                                "type": "function",
                                "function": {
                                    "name": "protocol_remember",
                                    "description": "Store a user preference or fact into long-term memory.",
                                    "parameters": {
                                        "type": "object",
                                        "properties": {
                                            "key": {"type": "string"},
                                            "value": {"type": "string"}
                                        },
                                        "required": ["key", "value"]
                                    }
                                }
                            },
                            {
                                "type": "function",
                                "function": {
                                    "name": "protocol_learn_experience",
                                    "description": "Save a solution to a problem as an 'Experience'.",
                                    "parameters": {
                                        "type": "object",
                                        "properties": {
                                            "problem": {"type": "string"},
                                            "solution": {"type": "array", "items": {"type": "string"}},
                                            "tags": {"type": "array", "items": {"type": "string"}}
                                        },
                                        "required": ["problem", "solution"]
                                    }
                                }
                            }]
                            
                            for plan in pending_plans:
                                plan_id = plan['id']
                                plan_content = plan['content']
                                
                                print(f"Evolving plan {plan_id}: {plan_content}")
                                
                                # 1. Mark as in_progress
                                conn.execute("UPDATE ai_evolution_log SET status='in_progress' WHERE id=?", (plan_id,))
                                conn.commit()
                                
                                # 2. Construct Prompt
                                sys_prompt = (
                                    f"You are 1052 AI in Auto-Evolution Mode.\n"
                                    f"Current Time: {now_str}\n"
                                    f"Objective: Execute the following improvement plan recorded in your diary: '{plan_content}'\n"
                                    f"Available Skills:\n{skills_desc}\n"
                                    f"Instructions:\n"
                                    f"1. Write code or learn experience to fulfill the plan.\n"
                                    f"2. Use `execute_skill_function` to create files or run scripts.\n"
                                    f"3. When done, output a summary of what you achieved."
                                )
                                
                                messages = [{'role': 'system', 'content': sys_prompt}]
                                
                                # 3. Call LLM (Simple non-streaming loop for tool use)
                                # We limit to 3 turns to avoid infinite loops
                                summary = "Evolution attempted."
                                success = False
                                
                                for turn in range(3):
                                    payload = {
                                        'model': model,
                                        'messages': messages,
                                        'tools': evolve_tools,
                                        'tool_choice': 'auto'
                                    }
                                    
                                    try:
                                        resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=300)
                                        resp_json = resp.json()
                                        
                                        if 'choices' in resp_json and resp_json['choices']:
                                            choice = resp_json['choices'][0]
                                            msg = choice['message']
                                            messages.append(msg)
                                            
                                            if msg.get('tool_calls'):
                                                # Execute tools
                                                for tc in msg['tool_calls']:
                                                    func_name = tc['function']['name']
                                                    args_str = tc['function']['arguments']
                                                    call_id = tc['id']
                                                    
                                                    res_str = ""
                                                    try:
                                                        func_args = json.loads(args_str)
                                                    except: func_args = {}
                                                    
                                                    core_res = execute_core_tool(func_name, func_args)
                                                    if core_res is not None:
                                                        res_str = core_res
                                                    elif func_name == 'execute_skill_function':
                                                        try:
                                                            args = func_args
                                                            res_str = skill_manager.execute_skill_function(
                                                                args.get('skill_name'), args.get('file_name'), 
                                                                args.get('function_name'), args.get('kwargs', {})
                                                            )
                                                            success = True # If we executed code, assume some success
                                                        except Exception as e:
                                                            res_str = f"Error: {e}"
                                                    elif func_name == 'protocol_remember':
                                                        try:
                                                            args = json.loads(args_str)
                                                            saved_path = protocol_brain.remember(args.get('key'), args.get('value'))
                                                            res_str = f"Successfully remembered: {args.get('key')} = {args.get('value')}. Saved to {saved_path}"
                                                            success = True
                                                        except Exception as e: res_str = str(e)
                                                    elif func_name == 'protocol_learn_experience':
                                                        try:
                                                            args = json.loads(args_str)
                                                            saved_path = protocol_brain.learn_experience(args.get('problem'), args.get('solution'), args.get('tags'))
                                                            res_str = f"Experience learned and saved to {saved_path}."
                                                            success = True
                                                        except Exception as e: res_str = str(e)
                                                
                                                messages.append({
                                                    "role": "tool",
                                                    "tool_call_id": call_id,
                                                    "content": str(res_str)
                                                })
                                            else:
                                                # Final response
                                                summary = msg.get('content', 'No content')
                                                break
                                        else:
                                            print(f"Evolution LLM Empty Response: {resp.text}")
                                            break
                                    except Exception as e:
                                        print(f"Evolution LLM Error: {e}")
                                        break
                                
                                # 4. Update Log
                                status = 'completed' if success else 'failed'
                                conn.execute("UPDATE ai_evolution_log SET status=?, result_summary=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", 
                                            (status, summary, plan_id))
                                
                                # 5. Notify User
                                # Find a recent conversation to post to? Or the last one?
                                # Use the conversation_id from the last user message if possible
                                # But we don't have it here easily unless we query messages again.
                                # Let's just pick the latest active conversation.
                                last_conv = conn.execute("SELECT conversation_id FROM messages ORDER BY created_at DESC LIMIT 1").fetchone()
                                if last_conv:
                                    notify_msg = f"🌙 **夜间进化报告**\n\n针对计划：_{plan_content}_\n\n执行结果：\n{summary}"
                                    conn.execute('INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
                                                (last_conv['conversation_id'], 'assistant', notify_msg))
                                    conn.commit()
                                
                        finally:
                            loop.close()
                    
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Scheduler error: {e}")
            # traceback.print_exc()
            
        time.sleep(5) # Check every 5 seconds


if __name__ == '__main__':
    port = 10052
    url = f"http://127.0.0.1:{port}"
    print(f"Starting server at {url}...")
    
    # Auto open browser
    def open_browser():
        webbrowser.open_new(url)
    
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        threading.Thread(target=scheduler_loop, daemon=True).start()
        threading.Timer(1.5, open_browser).start()

        # Start Telegram Bot if Token is configured
        try:
            conn = get_db_connection()
            settings_rows = conn.execute('SELECT * FROM settings').fetchall()
            settings = {row['key']: row['value'] for row in settings_rows}
            tg_token = settings.get('telegram_token')
            conn.close()

            if tg_token:
                tg_bot = TelegramBot(tg_token, headless_chat_turn)
                tg_bot.start_in_thread()
            else:
                print("Telegram Token not found in settings.")
        except Exception as e:
            print(f"Failed to start Telegram Bot: {e}")
        
    app.run(debug=False, port=port)