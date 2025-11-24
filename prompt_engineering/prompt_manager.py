import json
import time
import os
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

PROMPTS_FILE = "data/prompts_registry.json"

@dataclass
class PromptVersion:
    name: str
    version: str
    prompt_text: str
    description: str
    author: str
    created_at: str

class PromptManager:
    def __init__(self, storage_file=PROMPTS_FILE):
        self.storage_file = storage_file
        self._ensure_storage()

    def _ensure_storage(self):
        if not os.path.exists(os.path.dirname(self.storage_file)):
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
        if not os.path.exists(self.storage_file):
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump({"prompts": {}}, f)

    def _load_db(self):
        with open(self.storage_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_db(self, db):
        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)

    def create_prompt(self, prompt_name, prompt_text, description="", author="admin"):
        db = self._load_db()
        
        if prompt_name not in db["prompts"]:
            db["prompts"][prompt_name] = []
        
        # Versioning: 1.0, 1.1, etc.
        versions = db["prompts"][prompt_name]
        new_version_num = "1.0"
        if versions:
            last_v = float(versions[-1]["version"])
            new_version_num = f"{last_v + 0.1:.1f}"

        new_prompt = PromptVersion(
            name=prompt_name,
            version=new_version_num,
            prompt_text=prompt_text,
            description=description,
            author=author,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S")
        )
        
        db["prompts"][prompt_name].append(asdict(new_prompt))
        self._save_db(db)
        return new_prompt

    def get_prompt(self, prompt_name, version=None):
        db = self._load_db()
        if prompt_name not in db["prompts"]:
            raise ValueError(f"Prompt {prompt_name} not found")
            
        versions = db["prompts"][prompt_name]
        if not version:
            return PromptVersion(**versions[-1]) # Last version
        
        for v in versions:
            if v["version"] == version:
                return PromptVersion(**v)
        
        raise ValueError(f"Version {version} not found for {prompt_name}")

    def list_prompts(self):
        db = self._load_db()
        result = []
        for name, versions in db["prompts"].items():
            last = versions[-1]
            result.append({
                "name": name,
                "current_version": last["version"],
                "total_versions": len(versions),
                "created_at": versions[0]["created_at"]
            })
        return result