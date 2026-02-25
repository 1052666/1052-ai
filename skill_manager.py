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
        
        Args:
            skill_name (str): Name of the skill (folder name).
            file_name (str): Name of the python file (e.g. 'utils.py').
            function_name (str): Name of the function to call.
            kwargs (dict): Arguments for the function.
        """
        if skill_name not in self.skills:
            return f"Error: Skill '{skill_name}' not found."
            
        skill_info = self.skills[skill_name]
        
        # Determine full file path
        if skill_info['type'] == 'folder':
            file_path = os.path.join(skill_info['path'], file_name)
        else:
            # Single file skill
            # If skill_name is 'math', file is 'math.py'
            # file_name might be ignored or checked
            file_path = skill_info['path']

        if not os.path.exists(file_path):
             return f"Error: File '{file_path}' not found."

        try:
            # Load module
            module_name = f"dynamic_skill_{skill_name}_{os.path.basename(file_name)[:-3]}"
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                
                # Get function
                if not hasattr(module, function_name):
                     return f"Error: Function '{function_name}' not found in {file_name}."
                
                func = getattr(module, function_name)
                
                # Execute
                result = func(**kwargs)
                return str(result)
            else:
                return "Error: Could not load module."
        except Exception as e:
            traceback.print_exc()
            return f"Error executing skill function: {str(e)}"
