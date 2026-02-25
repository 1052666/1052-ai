
import subprocess
import os

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

def read_file(file_path, encoding='utf-8', limit=2000):
    """
    Reads content from a file. Supports environment variables.
    
    Args:
        file_path (str): The path to the file.
        encoding (str): Encoding to use. Defaults to 'utf-8'.
        limit (int): Max number of characters to read. Defaults to 2000.
        
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
