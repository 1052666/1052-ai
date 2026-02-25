import os
import json
from typing import List, Dict, Optional
from .models import Memory, Experience, DiaryEntry

class Storage:
    def __init__(self, root_dir: str):
        # Ensure root_dir is absolute if possible, but caller usually handles this
        self.root_dir = root_dir
        self.memory_dir = os.path.join(root_dir, "memory")
        self.experience_dir = os.path.join(root_dir, "experience")
        self.diaries_dir = os.path.join(root_dir, "diaries")
        self._ensure_dirs()

    def _ensure_dirs(self):
        os.makedirs(self.memory_dir, exist_ok=True)
        os.makedirs(self.experience_dir, exist_ok=True)
        os.makedirs(self.diaries_dir, exist_ok=True)

    def _save_json(self, path: str, data: Dict):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_json(self, path: str) -> Optional[Dict]:
        if not os.path.exists(path):
            return None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_memory(self, memory: Memory):
        filename = f"1052_memory_{memory.user_id}.json"
        path = os.path.join(self.memory_dir, filename)
        # Convert dataclass to dict, handling nested dataclasses
        # Since we used asdict in to_dict method of Memory class, we rely on that or use asdict here
        # But we need to make sure to_dict handles nested objects recursively if they are dataclasses
        # dataclasses.asdict does this automatically.
        from dataclasses import asdict
        self._save_json(path, asdict(memory))

    def load_memory(self, user_id: str) -> Optional[Dict]:
        filename = f"1052_memory_{user_id}.json"
        path = os.path.join(self.memory_dir, filename)
        return self._load_json(path)

    def save_experience(self, experience: Experience):
        filename = f"1052_exp_{experience.exp_id}.json"
        path = os.path.join(self.experience_dir, filename)
        from dataclasses import asdict
        self._save_json(path, asdict(experience))

    def load_experience(self, exp_id: str) -> Optional[Dict]:
        filename = f"1052_exp_{exp_id}.json"
        path = os.path.join(self.experience_dir, filename)
        return self._load_json(path)
    
    def list_experiences(self) -> List[Dict]:
        exps = []
        if not os.path.exists(self.experience_dir):
            return exps
        for filename in os.listdir(self.experience_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.experience_dir, filename)
                data = self._load_json(path)
                if data:
                    exps.append(data)
        return exps

    def save_diary(self, diary: DiaryEntry):
        filename = f"1052_diary_{diary.date}.json"
        path = os.path.join(self.diaries_dir, filename)
        from dataclasses import asdict
        self._save_json(path, asdict(diary))

    def load_diary(self, date: str) -> Optional[Dict]:
        filename = f"1052_diary_{date}.json"
        path = os.path.join(self.diaries_dir, filename)
        return self._load_json(path)
