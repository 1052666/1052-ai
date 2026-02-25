import os
import sys
import sqlite3
import json
import requests
import datetime
import asyncio
import zipfile
import shutil
import threading
import inspect
import webbrowser
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent
from skill_manager import SkillManager
from feishu_utils import FeishuBot
from protocol1052.client import Protocol1052

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
            conv = conn.execute('SELECT id FROM conversations WHERE title = ?', (conv_title,)).fetchone()
            
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
                
                final_content = ""
                
                while True:
                    payload = {
                        'model': model,
                        'messages': current_messages,
                        'stream': False # Feishu doesn't need stream for backend processing
                    }
                    if tools:
                        payload['tools'] = tools
                        payload['tool_choice'] = 'auto'
                        
                    response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=120)
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
                        func_name = tool_call['function']['name']
                        args_str = tool_call['function']['arguments']
                        call_id = tool_call['id']
                        
                        try:
                            func_args = json.loads(args_str)
                        except:
                            func_args = {}
                            
                        result = ""
                        if func_name in server_map:
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
    enable_system_control = settings.get('enable_system_control') == 'true'
    model_provider = settings.get('model_provider', 'openai')
    
    # Handle Local Model Provider
    if model_provider == 'local':
        if not api_key:
            api_key = 'ollama' # Dummy key often required by clients even for local models
    
    # Get conversation history
    history = conn.execute('SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at ASC', (conversation_id,)).fetchall()
    conn.close()
    
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

    def generate():
        # Async wrapper to run async code in sync generator
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # 1. Discover MCP tools
            mcp_tools, server_map = loop.run_until_complete(get_all_mcp_tools())
            
            # Load local skills (Descriptions only)
            skill_manager.load_skills()
            skills_description = skill_manager.get_all_skills_description()
            
            # Add Generic Skill Executor Tool
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
            }]

            # Merge tools
            tools = mcp_tools + local_tools
            
            # We need a mutable list of messages for the multi-turn tool conversation
            current_messages = messages_payload.copy()
            
            # Inject Skills Description into System Prompt (or first message)
            # Find the system prompt and append, or add new system prompt
            
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
                    msg['content'] += memory_context + "\n\n" + skills_description
                    found_system = True
                    break
            
            if not found_system:
                # If no system prompt found (e.g. file missing), use a default one + skills
                default_system = "You are 1052 AI."
                current_messages.insert(0, {'role': 'system', 'content': default_system + memory_context + "\n\n" + skills_description})

            
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
                    response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, stream=True, timeout=120)
                    response.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    error_content = response.text
                    yield json.dumps({"type": "error", "content": f"LLM API Error: {str(e)}\nDetails: {error_content}"}) + "\n"
                    return

                tool_calls_buffer = {} # index -> tool_call_data
                full_content = ""
                finish_reason = None
                
                for line in response.iter_lines():
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
                    func_name = tool_call['function']['name']
                    func_args_str = tool_call['function']['arguments']
                    call_id = tool_call['id']
                    
                    try:
                        func_args = json.loads(func_args_str)
                    except:
                        func_args = {} # Or handle error

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

                # Loop continues to next iteration to send tool outputs back to OpenAI
                
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            yield json.dumps({"type": "error", "content": error_msg}) + "\n"
        finally:
            loop.close()

    return Response(stream_with_context(generate()), content_type='text/plain')


if __name__ == '__main__':
    port = 10052
    url = f"http://127.0.0.1:{port}"
    print(f"Starting server at {url}...")
    
    # Auto open browser
    def open_browser():
        webbrowser.open_new(url)
    
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        threading.Timer(1.5, open_browser).start()
        
    app.run(debug=False, port=port)