import json
import os
from appdirs import user_config_dir

APP_NAME = "GameChecklistOverlay"
APP_AUTHOR = "GameChecklistOverlayDev"

DEFAULT_CONFIG = {
    "appearance": {
        "theme": "dark",
        "background_color": "#2E2E2E",
        "text_color": "#FFFFFF",
        "font_family": "Arial",
        "font_size": 10,
        "transparency": 0.85
    },
    "window": {
        "initial_width": 250,
        "initial_height": 200,
        "min_width": 100,
        "min_height": 50,
        "initial_x_offset_from_right": 10,
        "initial_y_offset_from_top": 10,
        "remember_position": True,
        "remember_size": True,
        "last_x": None,
        "last_y": None,
        "last_width": None,
        "last_height": None,
        "always_on_top": True
    },
    "shortcuts": {
        "toggle_visibility": "ctrl+shift+X",
        "peek_visibility": "ctrl+alt+X",
        "peek_duration_seconds": 3,
        "exit_application": "ctrl+shift+Q"
    },
    "behavior": {
        "auto_shrink_to_fit_tasks": True,
        "min_height_one_task": 50
    }
}

class ConfigManager:
    def __init__(self):
        self.config_path = os.path.join(user_config_dir(APP_NAME, APP_AUTHOR), "config.json")
        self.config = {}
        self._load_config()

    def _ensure_config_dir_exists(self):
        if not os.path.exists(os.path.dirname(self.config_path)):
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

    def _load_config(self):
        self._ensure_config_dir_exists()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    self.config = self._deep_merge_dicts(DEFAULT_CONFIG.copy(), loaded_config)
            except json.JSONDecodeError:
                print(f"Warning: Error decoding {self.config_path}. Using default configuration.")
                self.config = DEFAULT_CONFIG.copy()
                self._save_config()
        else:
            print(f"Info: No config file found at {self.config_path}. Creating with default values.")
            self.config = DEFAULT_CONFIG.copy()
            self._save_config()
        
        if self.config["window"]["remember_position"] and self.config["window"]["last_x"] is None:
            pass
        if self.config["window"]["remember_size"] and self.config["window"]["last_width"] is None:
            self.config["window"]["last_width"] = self.config["window"]["initial_width"]

    def _deep_merge_dicts(self, base, new_data):
        for key, value in new_data.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge_dicts(base[key], value)
            else:
                base[key] = value
        return base

    def get(self, key_path, default=None):
        keys = key_path.split('.')
        value = self.config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            print(f"Warning: Config key '{key_path}' not found. Returning default: {default}")
            return default

    def set(self, key_path, value):
        keys = key_path.split('.')
        current_level = self.config
        for i, key in enumerate(keys[:-1]):
            if key not in current_level or not isinstance(current_level[key], dict):
                current_level[key] = {}
            current_level = current_level[key]
        current_level[keys[-1]] = value
        self._save_config()

    def _save_config(self):
        self._ensure_config_dir_exists()
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except IOError as e:
            print(f"Error: Could not save config to {self.config_path}: {e}")

    def get_all_configs(self):
        return self.config.copy()