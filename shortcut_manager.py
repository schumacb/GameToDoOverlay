# shortcut_manager.py
from pynput import keyboard
from PySide6.QtCore import QObject, Signal # Import QObject and Signal

class ShortcutManager(QObject): # Inherit from QObject to use signals
    # Define signals
    toggle_visibility_requested = Signal()
    peek_visibility_requested = Signal()
    exit_application_requested = Signal()

    def __init__(self, config_manager):
        super().__init__() # Call QObject constructor
        self.config_manager = config_manager
        self.hotkey_listener_obj = None
        self.active_shortcuts_map = {}
        self._load_and_prepare_shortcuts()

    def _load_and_prepare_shortcuts(self):
        shortcuts_config = self.config_manager.get("shortcuts")
        if not shortcuts_config:
            print("Warning: No shortcuts defined in config.")
            return

        # Map config key names to the signals they should emit
        shortcut_actions = {
            "toggle_visibility": self.toggle_visibility_requested,
            "peek_visibility": self.peek_visibility_requested,
            "exit_application": self.exit_application_requested
        }

        for conf_key, signal_to_emit in shortcut_actions.items():
            shortcut_str = shortcuts_config.get(conf_key)
            if shortcut_str:
                try:
                    pynput_keys = []
                    parts = shortcut_str.lower().split('+')
                    for part in parts:
                        if part in ["ctrl", "alt", "shift", "cmd"]:
                            pynput_keys.append(f"<{part}>")
                        elif len(part) == 1:
                            pynput_keys.append(part)
                        elif part.startswith("f") and part[1:].isdigit():
                            pynput_keys.append(f"<{part}>")
                        # Add more key mappings if needed (e.g. <space>, <enter>)
                    
                    if pynput_keys:
                        pynput_format_shortcut = "+".join(pynput_keys)
                        # The callback for pynput will be a lambda that emits the signal
                        self.active_shortcuts_map[pynput_format_shortcut] = lambda s=signal_to_emit: s.emit()
                        print(f"Prepared shortcut: {pynput_format_shortcut} for {conf_key}")
                    else:
                        print(f"Warning: Could not parse keys for shortcut '{shortcut_str}' for {conf_key}")
                except Exception as e:
                    print(f"Warning: Error processing shortcut '{shortcut_str}' for {conf_key}: {e}")
            else:
                print(f"Info: Shortcut for '{conf_key}' not defined.")
        
        if not self.active_shortcuts_map:
            print("No valid shortcuts were prepared.")

    def start_listening(self):
        if not self.active_shortcuts_map:
            print("ShortcutManager: No active shortcuts to listen for.")
            return
        if self.hotkey_listener_obj and self.hotkey_listener_obj.is_alive():
            print("ShortcutManager: Listener already active.")
            return

        try:
            self.hotkey_listener_obj = keyboard.GlobalHotKeys(self.active_shortcuts_map)
            self.hotkey_listener_obj.start() # This starts its own thread
            print(f"Shortcut listener started. Active shortcuts: {list(self.active_shortcuts_map.keys())}")
        except Exception as e:
            # This can happen on Linux if accessibility features are not enabled
            # or if another pynput listener is already running.
            print(f"Error starting global shortcut listener (pynput.keyboard.GlobalHotKeys): {e}")
            print("Global shortcuts may not work. Ensure environment allows pynput (e.g., X11 accessibility, no other listener).")
            self.hotkey_listener_obj = None

    def stop_listening(self):
        if self.hotkey_listener_obj:
            print("ShortcutManager Info: Attempting to stop listener...")
            try:
                self.hotkey_listener_obj.stop()
                # GlobalHotKeys uses a daemon thread, join might not be strictly necessary
                # or might hang if not handled correctly by pynput on all platforms.
                # Let's assume .stop() is sufficient for now.
                # If issues arise, investigate joining self.hotkey_listener_obj if it's a Thread instance.
                print("ShortcutManager Info: Listener stop signal sent.")
            except Exception as e:
                print(f"ShortcutManager Error: Exception during listener stop: {e}")
            finally:
                 self.hotkey_listener_obj = None # Clear reference
        else:
            print("ShortcutManager Info: Listener not active or already stopped.")