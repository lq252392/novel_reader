import json
import os
import sys

class ConfigManager:
    def __init__(self, filename="reader_settings.json"):
        self.path = os.path.join(
            os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), 
            filename
        )
        self.settings = self.load()

    def load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {"files": {}}

    def save(self, settings):
        self.settings.update(settings)
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Save config error: {e}")
