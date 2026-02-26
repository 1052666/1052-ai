import os
import sys
import inspect
import importlib.util
import json
import traceback

class SkillManager:
    def __init__(self, skills_dir='skills'):
        self.skills_dir = skills_dir
        self.skills = {} # skill_folder_name -> {path, description_md}

    def load_skills(self):
        """
        Load skills from the skills directory.
        Scans for subdirectories and looks for Markdown (.md) files for description.
        Does NOT inspect Python code for schemas anymore.
        """
        self.skills = {}
        
        if not os.path.exists(self.skills_dir):
            print(f"Skills directory '{self.skills_dir}' not found.")
            return

        # Add skills dir to sys.path to allow imports (for execution)
        abs_skills_dir = os.path.abspath(self.skills_dir)
        if abs_skills_dir not in sys.path:
            sys.path.append(abs_skills_dir)

        # Iterate over items in skills_dir
        for item_name in os.listdir(self.skills_dir):
            item_path = os.path.join(self.skills_dir, item_name)
            
            # Case 1: Subdirectory (Skill Package)
            if os.path.isdir(item_path):
                # Look for MD file
                md_content = ""
                md_files = [f for f in os.listdir(item_path) if f.endswith('.md')]
                
                # Prioritize SKILL.md, then README.md, otherwise pick first md
                target_md = None
                if 'SKILL.md' in md_files:
                    target_md = 'SKILL.md'
                elif 'README.md' in md_files:
                    target_md = 'README.md'
                elif md_files:
                    target_md = md_files[0]
                
                if target_md:
                    try:
                        with open(os.path.join(item_path, target_md), 'r', encoding='utf-8') as f:
                            md_content = f.read()
                    except Exception as e:
                        print(f"Error reading MD for skill {item_name}: {e}")
                else:
                    md_content = f"Skill {item_name} (No description found)"

                self.skills[item_name] = {
                    "path": item_path,
                    "description": md_content,
                    "type": "folder"
                }

            # Case 2: Single .py file (Legacy support, maybe treat as skill too?)
            # If user uploads single .py, maybe we just read it as text or require comments?
            # Or assume no description.
            elif item_name.endswith('.py') and not item_name.startswith('__'):
                skill_name = item_name[:-3]
                self.skills[skill_name] = {
                    "path": item_path,
                    "description": f"Python Script: {item_name}",
                    "type": "file"
                }

    def get_all_skills_description(self):
        """
        Return a combined string of all skill descriptions (MD content).
        """
        combined = "Available Local Skills:\n\n"
        for name, info in self.skills.items():
            combined += f"--- Skill: {name} ---\n"
            combined += info['description'] + "\n\n"
        return combined

    def execute_skill_function(self, skill_name, file_name, function_name, kwargs):
        """
        Dynamically load a python module and execute a function.
        Supports hot-reloading: Always re-imports the module to pick up latest code changes.
        """
        # Always reload skills definitions to catch new folders
        self.load_skills()
        
        if skill_name not in self.skills:
            return f"Error: Skill '{skill_name}' not found."
            
        skill_info = self.skills[skill_name]
        
        # Helper to load a module and find a function
        def load_and_execute(f_path, func_name, func_kwargs):
            if not os.path.exists(f_path):
                return None, f"File '{f_path}' not found."
            
            try:
                # Use a unique module name based on file path and timestamp to force reload
                # Or just use importlib.reload if module exists? 
                # Since we want to support 'hot' code changes without restarting app,
                # we should probably just re-load from spec every time.
                # Python caches modules in sys.modules. We need to bypass or update it.
                
                module_name = f"skill_{skill_name}_{os.path.basename(f_path).replace('.', '_')}"
                
                spec = importlib.util.spec_from_file_location(module_name, f_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    
                    # Force reload: Remove old module if exists
                    if module_name in sys.modules:
                        del sys.modules[module_name]
                    
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    if not hasattr(module, func_name):
                        return None, f"Function '{func_name}' not found in {os.path.basename(f_path)}."
                    
                    func = getattr(module, func_name)
                    
                    # Execute
                    # Inspect function signature to handle kwargs mismatch?
                    # For now, assume kwargs match.
                    result = func(**func_kwargs)
                    return str(result), None
                else:
                    return None, f"Error: Could not load module spec for {f_path}"
            except Exception as e:
                # traceback.print_exc()
                return None, f"Error executing {func_name} in {os.path.basename(f_path)}: {str(e)}"

        # 1. Try with specific file_name
        if file_name:
            if not file_name.endswith('.py'):
                file_name += '.py'
            
            target_path = os.path.join(skill_info['path'], file_name)
            res, err = load_and_execute(target_path, function_name, kwargs)
            if res is not None:
                return res
            if err and "Function" in err: # File found but function not found
                return err 
            # If file not found, fall through to auto-discovery? 
            # User might have guessed wrong file name.
        
        # 2. Auto-discovery (scan all .py files)
        if skill_info['type'] == 'folder':
            py_files = [f for f in os.listdir(skill_info['path']) if f.endswith('.py') and not f.startswith('__')]
            
            # Prioritize common names
            priority = [f"{skill_name}.py", "main.py", "executor.py", "utils.py"]
            # Sort: priority files first, then alphabetical
            py_files.sort(key=lambda x: (0 if x in priority else 1, x))
            
            for py_file in py_files:
                target_path = os.path.join(skill_info['path'], py_file)
                # Only try if we haven't tried this specific file yet (if file_name matched it)
                if file_name and py_file == file_name: 
                    continue
                    
                res, err = load_and_execute(target_path, function_name, kwargs)
                if res is not None:
                    return res
            
            return f"Error: Function '{function_name}' not found in any Python file in skill '{skill_name}'."
            
        return f"Error: Could not execute skill {skill_name}"
