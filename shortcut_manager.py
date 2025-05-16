from pynput import keyboard
from PySide6.QtCore import QObject, Signal

class ShortcutManager(QObject):
    """
    Manages global keyboard shortcuts using pynput.
    It loads shortcut definitions from the ConfigManager and emits PySide6 signals
    when registered shortcuts are detected. These signals can then be connected
    to application methods.
    """
    toggle_visibility_requested = Signal()
    peek_visibility_requested = Signal()
    exit_application_requested = Signal()

    def __init__(self, config_manager: 'ConfigManager'):
        """
        Initializes the ShortcutManager.

        Args:
            config_manager: An instance of ConfigManager to load shortcut definitions.
        """
        super().__init__()
        self.config_manager = config_manager
        self.hotkey_listener_obj = None # Stores the pynput.keyboard.GlobalHotKeys listener instance
        self.active_shortcuts_map = {} # Maps pynput-formatted shortcut string to its callback (signal emission)
        self._load_and_prepare_shortcuts()

    def _load_and_prepare_shortcuts(self):
        """
        Loads shortcut definitions from the configuration and prepares them
        for the pynput listener. Converts human-readable shortcut strings
        (e.g., "ctrl+shift+x") into the format required by pynput
        (e.g., "<ctrl>+<shift>+x") and maps them to signal emissions.
        """
        shortcuts_config = self.config_manager.get("shortcuts")
        if not shortcuts_config:
            print("Warning: No shortcuts defined in config.")
            return

        # Maps configuration keys to the corresponding signals to be emitted.
        shortcut_actions = {
            "toggle_visibility": self.toggle_visibility_requested,
            "peek_visibility": self.peek_visibility_requested,
            "exit_application": self.exit_application_requested
        }

        for conf_key, signal_to_emit in shortcut_actions.items():
            shortcut_str = shortcuts_config.get(conf_key) # e.g., "ctrl+shift+X"
            if shortcut_str:
                try:
                    pynput_keys = []
                    parts = shortcut_str.lower().split('+')
                    for part in parts:
                        if part in ["ctrl", "alt", "shift", "cmd"]: # Modifier keys
                            pynput_keys.append(f"<{part}>")
                        elif len(part) == 1: # Regular character keys
                            pynput_keys.append(part)
                        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 12: # F-keys (F1-F12)
                             pynput_keys.append(f"<{part}>")
                        # Add other specific key mappings if necessary (e.g., <space>, <enter>, <caps_lock>)
                    
                    if pynput_keys:
                        pynput_format_shortcut = "+".join(pynput_keys)
                        # The callback for pynput will be a lambda that emits the appropriate signal.
                        # The `s=signal_to_emit` captures the signal_to_emit by value for the lambda.
                        self.active_shortcuts_map[pynput_format_shortcut] = lambda s=signal_to_emit: s.emit()
                        print(f"Prepared shortcut: {pynput_format_shortcut} for action '{conf_key}'")
                    else:
                        print(f"Warning: Could not parse keys for shortcut '{shortcut_str}' for action '{conf_key}'")

                except Exception as e:
                    print(f"Warning: Error processing shortcut '{shortcut_str}' for {conf_key}: {e}")
            else:
                print(f"Info: Shortcut for '{conf_key}' not defined in config.")
        
        if not self.active_shortcuts_map:
            print("No valid shortcuts were prepared to be registered.")


    def start_listening(self):
        """
        Starts the global keyboard shortcut listener.
        If a listener is already active or no shortcuts are defined, it does nothing.
        The listener runs in a separate thread managed by pynput.
        """
        if not self.active_shortcuts_map:
            print("ShortcutManager: No active shortcuts to listen for.")
            return
        # Check if the listener object exists and is alive (pynput specific check)
        if self.hotkey_listener_obj and hasattr(self.hotkey_listener_obj, 'is_alive') and self.hotkey_listener_obj.is_alive():
            print("ShortcutManager: Listener already active.")
            return

        try:
            self.hotkey_listener_obj = keyboard.GlobalHotKeys(self.active_shortcuts_map)
            self.hotkey_listener_obj.start() # This starts a new thread.
            print(f"Shortcut listener started. Active shortcuts: {list(self.active_shortcuts_map.keys())}")
        except Exception as e:
            # This can happen on Linux if accessibility features are not enabled
            # or if another pynput listener is already running from another process.
            print(f"Error starting global shortcut listener (pynput.keyboard.GlobalHotKeys): {e}")
            print("Global shortcuts may not work. Ensure environment allows pynput (e.g., X11 accessibility).")
            self.hotkey_listener_obj = None # Ensure listener is None if start failed

    def stop_listening(self):
        """
        Stops the global keyboard shortcut listener if it is active.
        """
        if self.hotkey_listener_obj:
            print("ShortcutManager Info: Attempting to stop listener...")
            try:
                # Check if listener is a GlobalHotKeys object and if it's running
                if hasattr(self.hotkey_listener_obj, 'stop') and \
                   hasattr(self.hotkey_listener_obj, 'is_alive') and \
                   self.hotkey_listener_obj.is_alive():
                    self.hotkey_listener_obj.stop()
                    # pynput's GlobalHotKeys runs a daemon thread; stop() signals it to terminate.
                    # Joining is generally handled internally or not strictly required for daemon threads to allow app exit.
                    print("ShortcutManager Info: Listener stop signal sent.")
                else:
                    print("ShortcutManager Info: Listener was not active or not a recognized listener object.")
            except Exception as e:
                print(f"ShortcutManager Error: Exception during listener stop: {e}")
            finally:
                 self.hotkey_listener_obj = None # Clear reference regardless of stop success/failure
        else:
            print("ShortcutManager Info: Listener not active or already stopped.")