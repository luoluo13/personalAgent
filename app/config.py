import json
import os
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    def __init__(self):
        self.api_key_path = BASE_DIR / "api_key.json"
        self.prompt_yaml_path = BASE_DIR / "prompt.yaml"
        self.prompt_json_path = BASE_DIR / "prompt.json"
        self.chroma_path = BASE_DIR / "chroma_db"
        self.sqlite_path = BASE_DIR / "app.db"
        
        self.api_key = ""
        self.api_base = ""
        self.bot_name = "Yuki"  # Default
        self.system_prompt = ""
        self.memory_extraction_prompt = ""
        
        self.load_api_config()
        self.load_prompts()

    def load_api_config(self):
        if self.api_key_path.exists():
            with open(self.api_key_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.api_key = data.get("api_key", "")
                self.api_base = data.get("api_base", "https://api.deepseek.com")

    def load_prompts(self):
        # Try YAML first
        if self.prompt_yaml_path.exists():
            try:
                with open(self.prompt_yaml_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    self.bot_name = data.get("name", "Yuki")
                    self.system_prompt = data.get("system_prompt", "")
                    self.memory_extraction_prompt = data.get("memory_extraction_prompt", "")
                return
            except Exception as e:
                print(f"Error loading prompt.yaml: {e}")

        # Fallback to JSON
        if self.prompt_json_path.exists():
            with open(self.prompt_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.bot_name = data.get("name", "Yuki")
                self.system_prompt = data.get("system_prompt", "")
                self.memory_extraction_prompt = data.get("memory_extraction_prompt", "")

    def reload_prompts(self):
        """Reload prompts from file dynamically"""
        self.load_prompts()

settings = Config()
