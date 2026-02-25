
import subprocess
import os
import shutil
import glob

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
    
    Args:
        app_name (str): Name of the application (e.g., 'notepad', 'calc', 'mspaint').
        
    Returns:
        str: Status message.
    """
    try:
        subprocess.Popen(app_name, shell=True)
        return f"Launched {app_name}"
    except Exception as e:
        return f"Failed to launch {app_name}: {str(e)}"

def write_file(file_path, content, mode='w', encoding='utf-8'):
    """
    Writes content to a file. Supports environment variables (e.g., %USERPROFILE%).
    
    Args:
        file_path (str): The path to the file.
        content (str): The content to write.
        mode (str): 'w' for overwrite, 'a' for append. Defaults to 'w'.
        encoding (str): Encoding to use. Defaults to 'utf-8'.
        
    Returns:
        str: Status message.
    """
    try:
        # Expand environment variables
        file_path = os.path.expandvars(file_path)
        file_path = os.path.abspath(file_path)
        
        # Ensure directory exists
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        with open(file_path, mode, encoding=encoding) as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Failed to write file: {str(e)}"

def read_file(file_path, encoding='utf-8', limit=5000):
    """
    Reads content from a file. Supports environment variables.
    
    Args:
        file_path (str): The path to the file.
        encoding (str): Encoding to use. Defaults to 'utf-8'.
        limit (int): Max number of characters to read. Defaults to 5000.
        
    Returns:
        str: The file content.
    """
    try:
        # Expand environment variables
        file_path = os.path.expandvars(file_path)
        file_path = os.path.abspath(file_path)
        
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
            
        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            content = f.read(limit)
            if len(content) == limit:
                content += "\n...(truncated)"
        return content
    except Exception as e:
        return f"Failed to read file: {str(e)}"

def list_directory(path, recursive=False, limit=100):
    """
    Lists files and directories in a given path.
    
    Args:
        path (str): The directory path.
        recursive (bool): Whether to list recursively (default: False).
        limit (int): Max number of items to return (default: 100).
        
    Returns:
        str: List of files and directories.
    """
    try:
        path = os.path.expandvars(path)
        path = os.path.abspath(path)
        
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
    
    Args:
        file_path (str): The path to delete.
        
    Returns:
        str: Status message.
    """
    try:
        file_path = os.path.expandvars(file_path)
        file_path = os.path.abspath(file_path)
        
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

def move_file(src_path, dest_path):
    """
    Moves or renames a file/directory.
    
    Args:
        src_path (str): Source path.
        dest_path (str): Destination path.
        
    Returns:
        str: Status message.
    """
    try:
        src_path = os.path.expandvars(src_path)
        src_path = os.path.abspath(src_path)
        dest_path = os.path.expandvars(dest_path)
        dest_path = os.path.abspath(dest_path)
        
        if not os.path.exists(src_path):
            return f"Error: Source not found at {src_path}"
            
        # Create dest dir if needed
        dest_dir = os.path.dirname(dest_path)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
            
        shutil.move(src_path, dest_path)
        return f"Successfully moved {src_path} to {dest_path}"
    except Exception as e:
        return f"Failed to move: {str(e)}"

def copy_file(src_path, dest_path):
    """
    Copies a file or directory.
    
    Args:
        src_path (str): Source path.
        dest_path (str): Destination path.
        
    Returns:
        str: Status message.
    """
    try:
        src_path = os.path.expandvars(src_path)
        src_path = os.path.abspath(src_path)
        dest_path = os.path.expandvars(dest_path)
        dest_path = os.path.abspath(dest_path)
        
        if not os.path.exists(src_path):
            return f"Error: Source not found at {src_path}"
            
        # Create dest dir if needed
        dest_dir = os.path.dirname(dest_path)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
            
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path)
            return f"Successfully copied directory {src_path} to {dest_path}"
        else:
            shutil.copy2(src_path, dest_path)
            return f"Successfully copied file {src_path} to {dest_path}"
    except Exception as e:
        return f"Failed to copy: {str(e)}"

def search_files(directory, pattern):
    """
    Searches for files matching a glob pattern.
    
    Args:
        directory (str): Directory to search in.
        pattern (str): Glob pattern (e.g., '*.py', '**/*.txt').
        
    Returns:
        str: List of matching files.
    """
    try:
        directory = os.path.expandvars(directory)
        directory = os.path.abspath(directory)
        
        # Construct full pattern
        # If pattern contains directory separators, use it as is relative to directory
        # Otherwise, assume it's a file pattern
        full_pattern = os.path.join(directory, pattern)
        
        # Use recursive=True if pattern contains **
        recursive = '**' in pattern
        
        matches = glob.glob(full_pattern, recursive=recursive)
        
        if not matches:
            return f"No files found matching {pattern} in {directory}"
            
        output = f"Found {len(matches)} files:\n"
        for match in matches[:100]: # Limit to 100
            output += f"{match}\n"
            
        if len(matches) > 100:
            output += f"... and {len(matches) - 100} more."
            
        return output
    except Exception as e:
        return f"Search failed: {str(e)}"

def execute_python_code(code):
    """
    Executes arbitrary Python code dynamically.
    DANGEROUS: This function allows full access to the Python environment.
    
    Args:
        code (str): The Python code to execute.
        
    Returns:
        str: The stdout captured from the execution.
    """
    import sys
    import io
    import contextlib

    # Create a string buffer to capture stdout
    output_buffer = io.StringIO()
    
    try:
        # Redirect stdout to the buffer
        with contextlib.redirect_stdout(output_buffer):
            # Create a restricted/safe(r) global dictionary if needed, 
            # but for "powerful" mode we give full access to globals()
            # We merge local scope to capture variables defined in the code
            exec_globals = globals().copy()
            exec(code, exec_globals)
            
        return output_buffer.getvalue().strip()
    except Exception as e:
        return f"Python Execution Failed:\n{str(e)}"
