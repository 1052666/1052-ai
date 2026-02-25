import os
import datetime
from typing import List, Optional, Dict
from dataclasses import asdict
from .models import Memory, Experience, DiaryEntry, BasicInfo, Preferences, Permissions, Scene
from .storage import Storage

class Protocol1052:
    def __init__(self, user_id: str, agent_id: str = "agent_001", storage_root: str = "1052"):
        # Make storage_root absolute if it isn't already
        if not os.path.isabs(storage_root):
            storage_root = os.path.abspath(storage_root)
        self.storage = Storage(storage_root)
        self.user_id = user_id
        self.agent_id = agent_id
        self.memory = self._load_or_create_memory()

    def _load_or_create_memory(self) -> Memory:
        data = self.storage.load_memory(self.user_id)
        if data:
            return Memory.from_dict(data)
        else:
            return Memory(user_id=self.user_id, agent_id=self.agent_id)

    def save_memory(self):
        self.memory.updated_at = datetime.datetime.now().isoformat()
        self.storage.save_memory(self.memory)

    def set_preference(self, key: str, value):
        if hasattr(self.memory.preferences, key):
            setattr(self.memory.preferences, key, value)
        else:
            self.memory.preferences.custom[key] = value
        self.save_memory()

    def get_preference(self, key: str):
        if hasattr(self.memory.preferences, key):
            return getattr(self.memory.preferences, key)
        return self.memory.preferences.custom.get(key)

    def add_experience(self, problem: str, solution: List[str], tags: List[str] = None):
        exp = Experience(
            problem=problem,
            solution=solution,
            tags=tags or [],
            scene=Scene(device="pc", system=os.name, env="python_client")
        )
        self.storage.save_experience(exp)
        return exp.exp_id

    def search_experience(self, query: str) -> List[Dict]:
        # Simple keyword search
        all_exps = self.storage.list_experiences()
        results = []
        for exp_data in all_exps:
            # Check problem, tags, solution
            text = (exp_data.get("problem", "") + 
                   " ".join(exp_data.get("tags", [])) + 
                   " ".join(exp_data.get("solution", []))).lower()
            if query.lower() in text:
                results.append(exp_data)
        return results

    def log_diary(self, task: str, summary: str = ""):
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        # Check if diary exists for today in memory or storage
        # Ideally we load from storage first
        existing_diary_data = self.storage.load_diary(today)
        if existing_diary_data:
            diary = DiaryEntry.from_dict(existing_diary_data)
        else:
            diary = DiaryEntry(date=today)

        if task:
            diary.task_list.append(task)
        if summary:
            diary.summary = summary # Overwrite or append? Spec says "summary", let's overwrite or concat.
            # Usually summary is one string.

        self.storage.save_diary(diary)
        
        # Also update memory's daily_diaries list (keep last 7 days maybe?)
        # For simplicity, just append to memory if not present
        found = False
        for d in self.memory.daily_diaries:
            if d.date == today:
                d.task_list = diary.task_list
                d.summary = diary.summary
                found = True
                break
        if not found:
            self.memory.daily_diaries.append(diary)
        
        self.save_memory()

    def get_memory_json(self):
        return asdict(self.memory)
