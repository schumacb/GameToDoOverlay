import json
import os
import copy # For deepcopy
from appdirs import user_config_dir

APP_NAME = "GameChecklistOverlay"
APP_AUTHOR = "GameChecklistOverlayDev"

DEFAULT_CONFIG = {
    "appearance": {
        "theme": "dark",
        "background_color": "#1A1A1A",
        "content_background_color": "#1F1F1F",
        "text_color": "#E0E0E0",
        "font_family": "Arial", 
        "font_size": 10,
        "transparency": 0.70
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
    """
    Manages the application's configuration, loading from and saving to a JSON file.
    It ensures that a default configuration is used if no config file exists or if it's corrupted.
    Configuration values are merged with defaults to ensure all expected keys are present.
    """
    def __init__(self):
        """
        Initializes the ConfigManager, sets up the configuration path, and loads the configuration.
        """
        self.config_path = os.path.join(user_config_dir(APP_NAME, APP_AUTHOR), "config.json")
        # self.config is initialized here and populated by _load_config.
        # If _load_config fails before self.config is properly assigned, 
        # it might be an issue if other methods are called.
        # However, _load_config now handles its own errors more gracefully regarding self.config state.
        self.config = {} 
        self._load_config()

    def _ensure_config_dir_exists(self):
        """
        Ensures that the directory for storing the configuration file exists.
        Creates the directory if it's missing.
        """
        config_dir = os.path.dirname(self.config_path)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)

    def _recursive_update(self, base_dict: dict, new_values: dict):
        """
        Recursively updates base_dict with items from new_values.
        If a key exists in both and both values are dictionaries, it recurses.
        Otherwise, the value from new_values overwrites the value in base_dict.
        This modifies base_dict in place.
        """
        for key, value in new_values.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._recursive_update(base_dict[key], value)
            else:
                base_dict[key] = value # Add new key or overwrite existing one

    def _ensure_default_keys(self, current_config: dict, default_template: dict):
        """
        Ensures all keys from default_template are present in current_config.
        If a key is missing, it's added from default_template (deepcopied).
        If a key corresponds to a nested dictionary, it recursively ensures keys there.
        This modifies current_config in place.
        """
        for key, default_value in default_template.items():
            if key not in current_config:
                current_config[key] = copy.deepcopy(default_value)
            elif isinstance(default_value, dict) and isinstance(current_config.get(key), dict):
                self._ensure_default_keys(current_config[key], default_value)
            # If key exists but types differ, loaded value is preserved (handled by _recursive_update).
            # This primarily adds missing keys.

    def _load_config(self):
        """
        Loads the configuration from the JSON file.
        If the file doesn't exist, is empty, or is malformed, it initializes with default settings.
        The loaded configuration is merged with defaults to ensure completeness.
        The potentially updated/repaired configuration is saved back.
        """
        self._ensure_config_dir_exists()
        
        # Initialize self.config with a deep copy of defaults.
        # This ensures that even if loading fails or the file is partial,
        # self.config starts from a known good state.
        current_config_state = copy.deepcopy(DEFAULT_CONFIG)

        if os.path.exists(self.config_path) and os.path.getsize(self.config_path) > 0:
            try:
                with open(self.config_path, 'r') as f:
                    loaded_config_values = json.load(f)
                
                # Update the default state with values from the loaded config file
                if isinstance(loaded_config_values, dict):
                    self._recursive_update(current_config_state, loaded_config_values)
                else:
                    # Loaded config is not a dictionary, which is unexpected.
                    # Log a warning and proceed with defaults (which current_config_state already is).
                    print(f"Warning: Config file {self.config_path} did not contain a valid JSON object. Using defaults.")

            except json.JSONDecodeError:
                print(f"Warning: Error decoding {self.config_path}. Using default configuration.")
                # current_config_state is already a deepcopy of DEFAULT_CONFIG, so no change needed here.
            except Exception as e:
                # Catch any other unexpected errors during load/merge process
                print(f"Error: Unexpected error during config load/merge: {e}. Using default configuration.")
                # Ensure current_config_state is reset to pure defaults in case it was partially modified.
                current_config_state = copy.deepcopy(DEFAULT_CONFIG)
        else:
            print(f"Info: Config file at {self.config_path} not found or empty. Using default values.")
            # current_config_state is already a deepcopy of DEFAULT_CONFIG.

        # Ensure all default keys are present, even if loaded_config was from an older version
        # or if loaded_config was partial.
        self._ensure_default_keys(current_config_state, DEFAULT_CONFIG)
        
        self.config = current_config_state

        # Initialize last known width/height from initial if not set and remember_size is true
        if self.config.get("window", {}).get("remember_size"): # defensive get
            if self.config.get("window", {}).get("last_width") is None:
                initial_width = DEFAULT_CONFIG.get("window", {}).get("initial_width", 250) # get from default
                if "window" not in self.config: self.config["window"] = {}
                self.config["window"]["last_width"] = initial_width
            if self.config.get("window", {}).get("last_height") is None:
                initial_height = DEFAULT_CONFIG.get("window", {}).get("initial_height", 200) # get from default
                if "window" not in self.config: self.config["window"] = {}
                self.config["window"]["last_height"] = initial_height
        
        # Always save the configuration after loading.
        # This ensures that if the file was missing, corrupted, or from an older version,
        # it's updated to the current complete and valid format.
        self._save_config()


    def get(self, key_path: str, default_value_override=None):
        """
        Retrieves a configuration value using a dot-separated key path.

        Args:
            key_path: The dot-separated path to the configuration key (e.g., "window.width").
            default_value_override: The default value to return if the key is not found in current config
                                   AND not found in DEFAULT_CONFIG structure.

        Returns:
            The configuration value or a default.
        """
        keys = key_path.split('.')
        value = self.config
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            # If key not found in current config, try to get it from the DEFAULT_CONFIG structure
            current_default_level = DEFAULT_CONFIG
            try:
                for key in keys:
                    current_default_level = current_default_level[key]
                return current_default_level # Return the structural default
            except (KeyError, TypeError):
                print(f"Warning: Config key '{key_path}' not found in current or default structure. Returning override: {default_value_override}")
                return default_value_override

    def set(self, key_path: str, value):
        """
        Sets a configuration value using a dot-separated key path and saves the configuration.

        Args:
            key_path: The dot-separated path to the configuration key.
            value: The value to set for the key.
        """
        keys = key_path.split('.')
        current_level = self.config
        for i, key in enumerate(keys[:-1]):
            if key not in current_level or not isinstance(current_level[key], dict):
                current_level[key] = {} 
            current_level = current_level[key]
        current_level[keys[-1]] = value
        self._save_config()

    def _save_config(self):
        """
        Saves the current configuration (self.config) to the JSON file.
        Ensures the configuration directory exists before attempting to save.
        """
        self._ensure_config_dir_exists()
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except IOError as e:
            print(f"Error: Could not save config to {self.config_path}: {e}")
        except TypeError as e:
            # This might happen if self.config contains non-serializable data,
            # though it shouldn't with the current structure.
            print(f"Error: Could not serialize configuration for saving: {e}")


    def get_all_configs(self) -> dict:
        """
        Returns a copy of the entire current configuration.

        Returns:
            A dictionary representing the current configuration.
        """
        return copy.deepcopy(self.config)