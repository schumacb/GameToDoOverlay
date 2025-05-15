import tkinter as tk
import json
import sys
import threading

from config_manager import ConfigManager
from shortcut_manager import ShortcutManager

# --- Constants for Resizing and Cursors ---
RESIZE_MARGIN = 8
CURSOR_RESIZE_H = "sb_h_double_arrow"
CURSOR_RESIZE_V = "sb_v_double_arrow"
CURSOR_RESIZE_TL_BR = "sizing" 
CURSOR_RESIZE_TR_BL = "sizing"
CURSOR_DEFAULT = ""


class GameChecklistApp:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.root = tk.Tk()
        self._exiting_flag = False 

        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._is_dragging = False
        self._is_resizing = False
        self._current_resize_mode = None
        
        self._resize_start_x_root = 0
        self._resize_start_y_root = 0
        self._resize_start_width = 0
        self._resize_start_height = 0
        self._resize_start_win_x = 0
        self._resize_start_win_y = 0

        self.min_width = int(self.config_manager.get("window.min_width", 100))
        self.min_height = int(self.config_manager.get("window.min_height", 50))
        self._peek_timer = None

        # --- Main UI Structure (CREATE UI ELEMENTS FIRST) ---
        self.main_content_frame = tk.Frame(self.root, 
                                          bg=self.config_manager.get("appearance.background_color"))
        self.main_content_frame.pack(fill=tk.BOTH, expand=True)

        exit_shortcut_str = self.config_manager.get("shortcuts.exit_application", "Ctrl+Shift+Q")
        self.main_label = tk.Label(self.main_content_frame, 
                                   text=f"Overlay Initializing... ({exit_shortcut_str} to Exit)",
                                   fg=self.config_manager.get("appearance.text_color"),
                                   bg=self.config_manager.get("appearance.background_color"),
                                   font=(self.config_manager.get("appearance.font_family"),
                                         self.config_manager.get("appearance.font_size"))
                                  )
        self.main_label.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # --- Apply Geometry and Appearance Settings ---
        self._apply_initial_window_geometry()
        self._apply_appearance_settings()
        
        self._setup_window_management()
        self._initial_setup_complete = False

        # --- Shortcut Manager Setup ---
        app_controls = {
            "toggle_visibility": self.toggle_visibility, # Make sure these methods exist
            "peek_visibility": self.peek_visibility,     # Make sure these methods exist
            "exit_application": self.exit_application    # Make sure these methods exist
        }
        self.shortcut_manager = ShortcutManager(self.config_manager, app_controls)
        
        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)

    def _apply_initial_window_geometry(self):
        screen_width = self.root.winfo_screenwidth()
        
        width_conf = self.config_manager.get("window.last_width") \
            if self.config_manager.get("window.remember_size") and \
               self.config_manager.get("window.last_width") is not None \
            else self.config_manager.get("window.initial_width")
        width = max(int(width_conf), self.min_width)
        
        height_conf = self.config_manager.get("window.last_height") \
            if self.config_manager.get("window.remember_size") and \
               self.config_manager.get("window.last_height") is not None \
            else self.config_manager.get("window.initial_height", 200)
        height = max(int(height_conf), self.min_height)

        if self.config_manager.get("window.remember_position") and \
           self.config_manager.get("window.last_x") is not None and \
           self.config_manager.get("window.last_y") is not None:
            x = int(self.config_manager.get("window.last_x"))
            y = int(self.config_manager.get("window.last_y"))
        else:
            x_offset = int(self.config_manager.get("window.initial_x_offset_from_right"))
            y_offset = int(self.config_manager.get("window.initial_y_offset_from_top"))
            x = screen_width - width - x_offset
            y = y_offset
            if self.config_manager.get("window.remember_position"):
                if self.config_manager.get("window.last_x") is None: self.config_manager.set("window.last_x", x)
                if self.config_manager.get("window.last_y") is None: self.config_manager.set("window.last_y", y)

        if self.config_manager.get("window.remember_size"):
            if self.config_manager.get("window.last_width") is None: self.config_manager.set("window.last_width", width)
            if self.config_manager.get("window.last_height") is None: self.config_manager.set("window.last_height", height)
        
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        if self.config_manager.get("window.always_on_top"): self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)

    def _apply_appearance_settings(self):
        self.root.configure(bg=self.config_manager.get("appearance.background_color"))
        alpha = self.config_manager.get("appearance.transparency", 0.85)
        try:
            self.root.attributes("-alpha", float(alpha))
            print(f"Set window -alpha to {alpha}")
        except Exception as e: # Catch broader errors for safety
            print(f"Warning: Could not set window transparency (-alpha): {e}. Using opaque.")
            self.root.attributes("-alpha", 1.0)

        self.main_content_frame.configure(bg=self.config_manager.get("appearance.background_color"))
        self.root.update_idletasks()

    def _get_resize_mode(self, event_x, event_y, win_width, win_height):
        on_left = abs(event_x) < RESIZE_MARGIN; on_right = abs(event_x - win_width) < RESIZE_MARGIN
        on_top = abs(event_y) < RESIZE_MARGIN; on_bottom = abs(event_y - win_height) < RESIZE_MARGIN
        if on_left and on_top: return "top_left"
        if on_right and on_top: return "top_right"
        if on_left and on_bottom: return "bottom_left"
        if on_right and on_bottom: return "bottom_right"
        if on_left: return "left"
        if on_right: return "right"
        if on_top: return "top"
        if on_bottom: return "bottom"
        return None

    def _update_cursor(self, event_x_rel, event_y_rel):
        if self._is_dragging or self._is_resizing: return
        win_width = self.root.winfo_width(); win_height = self.root.winfo_height()
        resize_mode = self._get_resize_mode(event_x_rel, event_y_rel, win_width, win_height)
        new_cursor = CURSOR_DEFAULT
        if resize_mode:
            if resize_mode in ["left", "right"]: new_cursor = CURSOR_RESIZE_H
            elif resize_mode in ["top", "bottom"]: new_cursor = CURSOR_RESIZE_V
            elif resize_mode in ["top_left", "bottom_right"]: new_cursor = CURSOR_RESIZE_TL_BR
            elif resize_mode in ["top_right", "bottom_left"]: new_cursor = CURSOR_RESIZE_TR_BL
        if self.root.cget("cursor") != new_cursor: self.root.config(cursor=new_cursor)

    def _setup_window_management(self):
        self.root.bind("<ButtonPress-1>", self._on_root_mouse_press)
        self.root.bind("<B1-Motion>", self._on_root_mouse_motion)
        self.root.bind("<ButtonRelease-1>", self._on_root_mouse_release)
        self.root.bind("<Motion>", self._on_root_mouse_hover)
        self.root.bind("<Leave>", self._on_root_mouse_leave)

    def _on_root_mouse_hover(self, event): self._update_cursor(event.x, event.y)
    def _on_root_mouse_leave(self, event):
        if not self._is_resizing and not self._is_dragging: self.root.config(cursor=CURSOR_DEFAULT)

    def _on_root_mouse_press(self, event):
        win_width = self.root.winfo_width(); win_height = self.root.winfo_height()
        self._current_resize_mode = self._get_resize_mode(event.x, event.y, win_width, win_height)
        if self._current_resize_mode:
            self._is_resizing = True; self._is_dragging = False
            self._resize_start_x_root, self._resize_start_y_root = event.x_root, event.y_root
            self._resize_start_width, self._resize_start_height = win_width, win_height
            self._resize_start_win_x, self._resize_start_win_y = self.root.winfo_x(), self.root.winfo_y()
        else:
            self._is_dragging = True; self._is_resizing = False
            self._drag_offset_x, self._drag_offset_y = event.x, event.y

    def _on_root_mouse_motion(self, event):
        if self._is_resizing:
            dx_root = event.x_root - self._resize_start_x_root; dy_root = event.y_root - self._resize_start_y_root
            nx, ny = self._resize_start_win_x, self._resize_start_win_y
            nw, nh = self._resize_start_width, self._resize_start_height
            if "left" in self._current_resize_mode: nw = max(self.min_width, self._resize_start_width - dx_root); nx = self._resize_start_win_x + (self._resize_start_width - nw)
            elif "right" in self._current_resize_mode: nw = max(self.min_width, self._resize_start_width + dx_root)
            if "top" in self._current_resize_mode: nh = max(self.min_height, self._resize_start_height - dy_root); ny = self._resize_start_win_y + (self._resize_start_height - nh)
            elif "bottom" in self._current_resize_mode: nh = max(self.min_height, self._resize_start_height + dy_root)
            self.root.geometry(f"{int(nw)}x{int(nh)}+{int(nx)}+{int(ny)}")
        elif self._is_dragging:
            nx = event.x_root - self._drag_offset_x; ny = event.y_root - self._drag_offset_y
            self.root.geometry(f"+{int(nx)}+{int(ny)}")

    def _on_root_mouse_release(self, event):
        action = False
        if self._is_resizing:
            self._is_resizing = False; action = True; self._current_resize_mode = None
            if self.config_manager.get("window.remember_size"):
                self.config_manager.set("window.last_width", self.root.winfo_width())
                self.config_manager.set("window.last_height", self.root.winfo_height())
            if self.config_manager.get("window.remember_position"): # L/T resize moves window
                self.config_manager.set("window.last_x", self.root.winfo_x())
                self.config_manager.set("window.last_y", self.root.winfo_y())
        elif self._is_dragging:
            self._is_dragging = False; action = True
            if self.config_manager.get("window.remember_position"):
                self.config_manager.set("window.last_x", self.root.winfo_x())
                self.config_manager.set("window.last_y", self.root.winfo_y())
        if action: self._update_cursor(event.x, event.y)

    def _schedule_on_main_thread(self, func, *args):
        if threading.current_thread() != threading.main_thread(): self.root.after(0, func, *args)
        else: func(*args)

    def toggle_visibility(self):
        def _toggle():
            if self.root.winfo_viewable(): self.root.withdraw(); print("Overlay hidden.")
            else: self.root.deiconify(); self.root.attributes("-topmost", True); print("Overlay shown.")
        self._schedule_on_main_thread(_toggle)

    def peek_visibility(self):
        def _peek():
            duration_ms = int(self.config_manager.get("shortcuts.peek_duration_seconds", 3) * 1000)
            if self._peek_timer: self.root.after_cancel(self._peek_timer); self._peek_timer = None
            if not self.root.winfo_viewable():
                self.root.deiconify(); self.root.attributes("-topmost", True); print("Overlay peek: shown.")
                self._peek_timer = self.root.after(duration_ms, self._hide_after_peek_action)
            elif self.root.winfo_viewable():
                 print("Overlay peek: already visible, restarting timer.")
                 self._peek_timer = self.root.after(duration_ms, self._hide_after_peek_action)
        self._schedule_on_main_thread(_peek)

    def _hide_after_peek_action(self):
        if self.root.winfo_viewable(): self.root.withdraw(); print("Overlay peek: auto-hidden.")
        self._peek_timer = None # Clear timer ref after it fires and action is done

    def exit_application(self):
        if self._exiting_flag: return
        self._exiting_flag = True
        print("Exit application initiated.")
        def _actual_exit_sequence():
            print("Stopping shortcut listener...")
            if hasattr(self, 'shortcut_manager') and self.shortcut_manager: self.shortcut_manager.stop_listening()
            print("Cancelling Tkinter timers...")
            if hasattr(self, '_peek_timer') and self._peek_timer:
                try:
                    if self.root.winfo_exists(): self.root.after_cancel(self._peek_timer)
                except tk.TclError: pass # Timer might have already fired or root gone
                self._peek_timer = None
            print("Shutting down Tkinter...")
            try:
                if hasattr(self, 'root') and self.root and self.root.winfo_exists():
                    self.root.quit(); self.root.destroy()
                    print("Tkinter shutdown complete.")
            except tk.TclError: print("Error during Tkinter shutdown (already destroyed?).")
            print("Python script exit sequence finished. Forcing process exit.")
            sys.exit(0)
        
        # Try to schedule on main thread, but if root is gone, execute directly critical parts
        if hasattr(self, 'root') and self.root and getattr(self.root, 'after', None) and self.root.winfo_exists():
             self._schedule_on_main_thread(_actual_exit_sequence)
        else:
            print("Tkinter root not fully available for scheduled exit, attempting direct critical cleanup.")
            if hasattr(self, 'shortcut_manager') and self.shortcut_manager: self.shortcut_manager.stop_listening()
            print("Direct cleanup finished. Forcing process exit.")
            sys.exit(0)

    def run(self):
        try:
            self.root.update_idletasks()
            self._initial_setup_complete = True
            if hasattr(self, 'shortcut_manager') and self.shortcut_manager: self.shortcut_manager.start_listening()
            print("Starting Tkinter mainloop...")
            self.root.mainloop()
            print("Tkinter mainloop naturally finished.")
        except KeyboardInterrupt: print("KeyboardInterrupt (Ctrl+C) by main thread.")
        except tk.TclError as e:
            if "application has been destroyed" in str(e).lower(): print(f"Mainloop interrupted (app destroyed): {e}")
            else: print(f"Unexpected TclError in mainloop: {e}")
        except Exception as e: print(f"Unexpected error in run method: {e}")
        finally:
            print("Run method's finally block: ensuring application exit.")
            self.exit_application()

if __name__ == "__main__":
    try:
        import nltk
        nltk.data.find('tokenizers/punkt')
        print("NLTK 'punkt' tokenizer found.")
    except LookupError:
        print("NLTK 'punkt' tokenizer not found. Attempting to download...")
        try: nltk.download('punkt', quiet=True); print("'punkt' tokenizer downloaded.")
        except Exception as e: print(f"Error downloading 'punkt': {e}.")
    except ImportError: print("NLTK library not found. Please install it: pip install nltk")

    app = GameChecklistApp()
    app.run()