
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
