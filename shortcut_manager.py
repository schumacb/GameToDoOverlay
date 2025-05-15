from pynput import keyboard
import threading # Required for pynput listener thread management

class ShortcutManager:
    def __init__(self, config_manager, app_controls_dict):
        """
        Initializes the ShortcutManager.
        :param config_manager: Instance of ConfigManager.
        :param app_controls_dict: A dictionary where keys are action identifiers (e.g., "toggle_visibility")
                                 and values are the corresponding callable methods from the app.
        """
        self.config_manager = config_manager
        self.app_controls = app_controls_dict # This IS the dictionary of methods
        self.listener_thread = None # pynput's GlobalHotKeys runs its own thread
        self.hotkey_listener_obj = None # To store the GlobalHotKeys object
        self.active_shortcuts_map = {} # For pynput: maps pynput-string to callback
        self._load_and_prepare_shortcuts()

    def _load_and_prepare_shortcuts(self):
        shortcuts_config = self.config_manager.get("shortcuts")
        if not shortcuts_config:
            print("Warning: No shortcuts defined in config.")
            return

        # Maps config key names to the keys expected in app_controls_dict
        config_key_to_action_name_in_app_controls = {
            "toggle_visibility": "toggle_visibility",
            "peek_visibility": "peek_visibility",
            "exit_application": "exit_application"
        }

        for conf_key, action_name in config_key_to_action_name_in_app_controls.items():
            shortcut_str_from_config = shortcuts_config.get(conf_key)
            
            # Correctly get the function from the app_controls dictionary
            action_function = self.app_controls.get(action_name)

            if shortcut_str_from_config and callable(action_function):
                try:
                    # Convert "ctrl+shift+x" to pynput's format e.g., "<ctrl>+<shift>+x"
                    pynput_keys = []
                    parts = shortcut_str_from_config.lower().split('+')
                    for part in parts:
                        if part in ["ctrl", "alt", "shift", "cmd"]:
                            pynput_keys.append(f"<{part}>")
                        elif len(part) == 1: # Single character key
                            pynput_keys.append(part)
                        # Extend for F-keys, special keys if needed, e.g., "f1" -> "<f1>"
                        elif part.startswith("f") and part[1:].isdigit():
                             pynput_keys.append(f"<{part}>")
                        # Add other specific key mappings if necessary
                    
                    if pynput_keys:
                        pynput_format_shortcut = "+".join(pynput_keys)
                        self.active_shortcuts_map[pynput_format_shortcut] = action_function
                        print(f"Prepared shortcut: {pynput_format_shortcut} for action '{action_name}'")
                    else:
                        print(f"Warning: Could not parse keys for shortcut '{shortcut_str_from_config}' for action '{action_name}'")

                except Exception as e:
                    print(f"Warning: Error processing shortcut '{shortcut_str_from_config}' for {action_name}: {e}")
            elif not shortcut_str_from_config:
                print(f"Info: Shortcut for '{conf_key}' (action '{action_name}') not defined in config.")
            elif not callable(action_function):
                print(f"Warning: Action method for '{action_name}' not found or not callable in app_controls.")
        
        if not self.active_shortcuts_map:
            print("No valid shortcuts were prepared to be registered.")


    def start_listening(self):
        if not self.active_shortcuts_map:
            print("ShortcutManager: No active shortcuts to listen for.")
            return

        try:
            # GlobalHotKeys takes a dictionary of {shortcut_string: callback}
            self.hotkey_listener_obj = keyboard.GlobalHotKeys(self.active_shortcuts_map)
            self.hotkey_listener_obj.start() # This starts a new thread
            self.listener_thread = self.hotkey_listener_obj # The listener object is the thread
            print(f"Shortcut listener started. Active shortcuts: {list(self.active_shortcuts_map.keys())}")
        except Exception as e:
            print(f"Error starting global shortcut listener (pynput.keyboard.GlobalHotKeys): {e}")
            print("Global shortcuts may not work. Ensure environment allows pynput (e.g., X11 accessibility).")
            self.hotkey_listener_obj = None
            self.listener_thread = None

    def stop_listening(self):
        if self.hotkey_listener_obj:
            print("Attempting to stop shortcut listener...")
            try:
                self.hotkey_listener_obj.stop()
                # The listener thread should exit once stop() is called.
                # If it's a daemon thread, it will exit when the main program exits.
                # If joinable, you might self.listener_thread.join() but GlobalHotKeys manages its thread.
                print("Shortcut listener stop command issued.")
            except Exception as e:
                print(f"Error stopping shortcut listener: {e}")
        self.hotkey_listener_obj = None
        self.listener_thread = None