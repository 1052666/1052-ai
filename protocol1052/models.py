from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
import datetime
import uuid

def generate_timestamp():
    return datetime.datetime.now().isoformat()

def generate_uuid():
    return str(uuid.uuid4())

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**{
            k: v for k, v in data.items() 
            if k in cls.__dataclass_fields__
        })

@dataclass
class BasicInfo:
    nickname: str = "Owner"
    first_boot_time: str = field(default_factory=generate_timestamp)
    current_device: str = "unknown"

    @classmethod
    def from_dict(cls, data: Dict):
        # Handle case where data might be None or not a dict
        if not isinstance(data, dict):
            return cls()
        return cls(**{
            k: v for k, v in data.items() 
            if k in cls.__dataclass_fields__
        })

@dataclass
class Preferences:
    talk_style: str = "natural" # "concise/natural/strict"
    common_words: List[str] = field(default_factory=list)
    custom: Dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict):
        if not isinstance(data, dict):
            return cls()
        return cls(**{
            k: v for k, v in data.items() 
            if k in cls.__dataclass_fields__
        })

@dataclass
class DiaryEntry:
    date: str # YYYY-MM-DD
    task_list: List[str] = field(default_factory=list)
    summary: str = ""

    @classmethod
    def from_dict(cls, data: Dict):
        if not isinstance(data, dict):
            return cls(date=datetime.datetime.now().strftime("%Y-%m-%d"))
        return cls(**{
            k: v for k, v in data.items() 
            if k in cls.__dataclass_fields__
        })

@dataclass
class Permissions:
    control_phone: bool = False
    control_pc: bool = False
    access_camera: bool = False
    access_files: bool = False
    allow_upload: bool = False

    @classmethod
    def from_dict(cls, data: Dict):
        if not isinstance(data, dict):
            return cls()
        return cls(**{
            k: v for k, v in data.items() 
            if k in cls.__dataclass_fields__
        })

@dataclass
class Memory:
    user_id: str
    agent_id: str
    protocol: str = "1052-v1.0"
    type: str = "memory"
    basic: BasicInfo = field(default_factory=BasicInfo)
    preferences: Preferences = field(default_factory=Preferences)
    daily_diaries: List[DiaryEntry] = field(default_factory=list)
    permissions: Permissions = field(default_factory=Permissions)
    created_at: str = field(default_factory=generate_timestamp)
    updated_at: str = field(default_factory=generate_timestamp)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict):
        if not isinstance(data, dict):
            # Fallback if data is corrupted
            return cls(user_id="unknown", agent_id="unknown")

        # Filter top-level fields
        filtered_data = {
            k: v for k, v in data.items() 
            if k in cls.__dataclass_fields__
        }
        
        # Handle nested objects
        if 'basic' in filtered_data:
            filtered_data['basic'] = BasicInfo.from_dict(filtered_data['basic'])
        else:
            filtered_data['basic'] = BasicInfo()
            
        if 'preferences' in filtered_data:
            filtered_data['preferences'] = Preferences.from_dict(filtered_data['preferences'])
        else:
            filtered_data['preferences'] = Preferences()
            
        if 'permissions' in filtered_data:
            filtered_data['permissions'] = Permissions.from_dict(filtered_data['permissions'])
        else:
            filtered_data['permissions'] = Permissions()
            
        if 'daily_diaries' in filtered_data and isinstance(filtered_data['daily_diaries'], list):
            filtered_data['daily_diaries'] = [
                DiaryEntry.from_dict(d) for d in filtered_data['daily_diaries'] 
                if isinstance(d, dict)
            ]
        else:
            filtered_data['daily_diaries'] = []
            
        # Ensure user_id and agent_id are present (they are required fields)
        if 'user_id' not in filtered_data:
            filtered_data['user_id'] = "unknown"
        if 'agent_id' not in filtered_data:
            filtered_data['agent_id'] = "unknown"
            
        return cls(**filtered_data)

@dataclass
class Scene:
    device: str = "pc" # pc/phone/iot
    system: str = "unknown"
    env: str = "default"

    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**{
            k: v for k, v in data.items() 
            if k in cls.__dataclass_fields__
        })

@dataclass
class Experience:
    problem: str
    solution: List[str]
    exp_id: str = field(default_factory=generate_uuid)
    protocol: str = "1052-v1.0"
    type: str = "experience"
    scene: Scene = field(default_factory=Scene)
    error_raw: str = ""
    cause: str = ""
    verify_status: bool = False
    tags: List[str] = field(default_factory=list)
    level: str = "normal" # normal/important/critical
    created_at: str = field(default_factory=generate_timestamp)
    updated_at: str = field(default_factory=generate_timestamp)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict):
        filtered_data = {
            k: v for k, v in data.items() 
            if k in cls.__dataclass_fields__
        }
        
        if 'scene' in filtered_data and isinstance(filtered_data['scene'], dict):
            filtered_data['scene'] = Scene.from_dict(filtered_data['scene'])
            
        return cls(**filtered_data)
