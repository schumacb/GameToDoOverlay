import sys
import uuid
from datetime import datetime
import nltk # For sentence tokenization

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QPoint, QTimer, QRect, QEvent
from PySide6.QtGui import QFont, QScreen, QCursor, QKeyEvent, QClipboard, QMouseEvent

from config_manager import ConfigManager
from shortcut_manager import ShortcutManager

# Constants for window resizing behavior
RESIZE_MARGIN = 8 # Pixel margin around edges for detecting resize intent
CURSOR_MAP = { # Mapping of resize edge identifiers to Qt.CursorShape
    "arrow": Qt.ArrowCursor,
    "size_h": Qt.SizeHorCursor,
    "size_v": Qt.SizeVerCursor,
    "size_tl_br": Qt.SizeFDiagCursor,
    "size_tr_bl": Qt.SizeBDiagCursor,
}

class OverlayWindow(QWidget):
    """
    Main application window for the game checklist overlay.
    This window is frameless, always on top (configurable), and semi-transparent.
    It supports dragging, resizing, and visibility control via global shortcuts,
    and task input via Ctrl+V when focused.
    """
    def __init__(self, config_manager: ConfigManager, shortcut_manager: ShortcutManager):
        """
        Initializes the OverlayWindow.

        Args:
            config_manager: Instance of ConfigManager for loading/saving settings.
            shortcut_manager: Instance of ShortcutManager for global hotkey bindings.
        """
        super().__init__()
        self.config_manager = config_manager
        self.shortcut_manager = shortcut_manager
        self._exiting_flag = False

        self._drag_offset = QPoint()
        self._is_dragging = False
        self._is_resizing = False
        self._current_resize_edge = None
        self._resize_start_geometry = QRect()
        self._resize_start_mouse_pos = QPoint()

        self.min_width = int(self.config_manager.get("window.min_width", 100))
        self.min_height = int(self.config_manager.get("window.min_height", 50))
        
        self._peek_timer = QTimer(self)
        self._peek_timer.setSingleShot(True)
        self._peek_timer.timeout.connect(self._hide_after_peek_action)

        self.tasks_data = [] # This will be a list of main task dictionaries, each containing steps

        self._setup_ui()
        self._apply_initial_window_settings()
        self._connect_shortcuts()

        self.setMouseTracking(True)
        if self.main_content_widget: self.main_content_widget.setMouseTracking(True)
        if self.main_label: self.main_label.setMouseTracking(True)
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


    def _setup_ui(self):
        """
        Sets up the main UI elements, window flags, and basic appearance of the overlay.
        """
        flags = Qt.FramelessWindowHint
        if self.config_manager.get("window.always_on_top"):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        opacity = float(self.config_manager.get("appearance.transparency", 0.85))
        self.setWindowOpacity(opacity)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.main_content_widget = QWidget(self)
        content_bg_color = self.config_manager.get("appearance.content_background_color", "#3C3C3C")
        text_color = self.config_manager.get("appearance.text_color", "#FFFFFF")
        font_family = self.config_manager.get("appearance.font_family", "Arial")
        font_size = int(self.config_manager.get("appearance.font_size", 10))
        
        self.main_content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {content_bg_color};
                color: {text_color};
                border: none;
            }}
        """)
        
        content_layout = QVBoxLayout(self.main_content_widget)
        content_layout.setContentsMargins(5,5,5,5)

        exit_shortcut_str = self.config_manager.get("shortcuts.exit_application", "Ctrl+Shift+Q")
        self.main_label = QLabel(
            f"Overlay Initialized. Focus and Ctrl+V to paste tasks.\n({exit_shortcut_str} to Exit)", 
            self.main_content_widget
        )
        self.main_label.setFont(QFont(font_family, font_size))
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setWordWrap(True)
        self.main_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content_layout.addWidget(self.main_label)
        self.main_layout.addWidget(self.main_content_widget)
        self.setLayout(self.main_layout)


    def _apply_initial_window_settings(self):
        """
        Applies initial geometry (position and size) to the window based on
        configuration settings (remembered values or defaults).
        """
        primary_screen = QApplication.primaryScreen()
        screen_width, screen_height = 1920, 1080 
        if primary_screen:
            screen_geometry = primary_screen.availableGeometry()
            screen_width, screen_height = screen_geometry.width(), screen_geometry.height()
        else:
            print("Warning: Could not get primary screen for initial geometry calculation.")

        width = self.min_width
        if self.config_manager.get("window.remember_size") and \
           self.config_manager.get("window.last_width") is not None:
            width = max(int(self.config_manager.get("window.last_width")), self.min_width)
        else:
            width = max(int(self.config_manager.get("window.initial_width")), self.min_width)

        height = self.min_height
        if self.config_manager.get("window.remember_size") and \
           self.config_manager.get("window.last_height") is not None:
            height = max(int(self.config_manager.get("window.last_height")), self.min_height)
        else:
            height = max(int(self.config_manager.get("window.initial_height", 200)), self.min_height)
        
        x, y = 0,0
        if self.config_manager.get("window.remember_position") and \
           self.config_manager.get("window.last_x") is not None and \
           self.config_manager.get("window.last_y") is not None:
            x = int(self.config_manager.get("window.last_x"))
            y = int(self.config_manager.get("window.last_y"))
        else:
            x_offset = int(self.config_manager.get("window.initial_x_offset_from_right", 10))
            y_offset = int(self.config_manager.get("window.initial_y_offset_from_top", 10))
            x = screen_width - width - x_offset
            y = y_offset
            if self.config_manager.get("window.remember_position"):
                self.config_manager.set("window.last_x", x)
                self.config_manager.set("window.last_y", y)
        
        if self.config_manager.get("window.remember_size"):
             if self.config_manager.get("window.last_width") is None: self.config_manager.set("window.last_width", width)
             if self.config_manager.get("window.last_height") is None: self.config_manager.set("window.last_height", height)

        self.setGeometry(x, y, width, height)

    def _connect_shortcuts(self):
        """
        Connects signals from the ShortcutManager to the corresponding
        methods (slots) in this window.
        """
        self.shortcut_manager.toggle_visibility_requested.connect(self.toggle_visibility)
        self.shortcut_manager.peek_visibility_requested.connect(self.peek_visibility)
        self.shortcut_manager.exit_application_requested.connect(self.exit_application)

    def keyPressEvent(self, event: QKeyEvent):
        """
        Handles key press events for the window, specifically for Ctrl+V paste.
        """
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V:
            clipboard = QApplication.clipboard()
            pasted_text = clipboard.text(QClipboard.Mode.Clipboard)
            if pasted_text:
                self._parse_and_load_tasks(pasted_text)
                event.accept()
                return 
        super().keyPressEvent(event)

    def _parse_and_load_tasks(self, text_block: str):
        """
        Parses a block of text into main tasks and their steps.
        Each line from the pasted text becomes a main task.
        Sentences within each line become individual steps for that task.
        The self.tasks_data attribute will store a list of main task dictionaries.
        """
        print("Parsing tasks...")
        self.tasks_data = [] # List of main task dictionaries
        lines = text_block.strip().splitlines()
        current_time = datetime.now()
        total_steps_count = 0

        for line_content in lines:
            if not line_content.strip(): 
                continue
            
            task_id_str = str(uuid.uuid4()) # Unique ID for the main task
            task_title_str = line_content.strip() # The original pasted line is the task title
            
            current_main_task = {
                "task_id": task_id_str,
                "task_title": task_title_str,
                "created_timestamp": current_time, 
                "steps": [] # List of step dictionaries for this main task
            }
            
            try:
                # Tokenize the task_title (which is the full line) into sentences (steps)
                sentences = nltk.sent_tokenize(task_title_str) 
            except LookupError as e:
                print(f"NLTK LookupError tokenizing task: '{task_title_str}'. Error: {e}")
                print("This might indicate a missing NLTK sub-resource.")
                print("Ensure NLTK 'punkt' data and its components are downloaded.")
                sentences = [task_title_str] # Fallback: treat the whole line as a single step
            except Exception as e: 
                print(f"General error tokenizing task: '{task_title_str}'. Error: {e}")
                sentences = [task_title_str]

            if not sentences: 
                sentences = [task_title_str] 

            for i, sentence_text in enumerate(sentences):
                if not sentence_text.strip(): 
                    continue
                
                step = {
                    "step_id": str(uuid.uuid4()), # Unique ID for the step
                    "step_index": i, # Order of the step within the task
                    "text": sentence_text.strip(),
                    "completed": False,
                    "completed_timestamp": None,
                }
                current_main_task["steps"].append(step)
                total_steps_count += 1
            
            if current_main_task["steps"]: # Only add the main task if it has steps
                self.tasks_data.append(current_main_task)
        
        print(f"Loaded {len(self.tasks_data)} main tasks with a total of {total_steps_count} steps.")
        for task_item in self.tasks_data: 
            print(f"  Task: '{task_item['task_title'][:50]}...' ({len(task_item['steps'])} steps)")
        
        if self.tasks_data:
            self.main_label.setText(f"{len(self.tasks_data)} tasks loaded. Display coming soon!\n(Ctrl+V to paste new tasks)")
        else:
            self.main_label.setText("Pasted text resulted in no tasks.\n(Ctrl+V to paste tasks)")


    def mousePressEvent(self, event: QMouseEvent):
        """
        Handles mouse button press events.
        Initiates dragging or resizing based on the mouse position.
        Also explicitly sets focus to the window on click, aiding paste functionality.
        """
        if not self.hasFocus():
            self.setFocus(Qt.FocusReason.MouseFocusReason)

        if event.button() == Qt.LeftButton:
            self._current_resize_edge = self._get_resize_edge(event.position().toPoint())
            if self._current_resize_edge:
                self._is_resizing = True
                self._is_dragging = False
                self._resize_start_geometry = self.geometry()
                self._resize_start_mouse_pos = event.globalPosition().toPoint()
                cursor_type = self._current_resize_edge_to_cursor_type(self._current_resize_edge)
                self.setCursor(CURSOR_MAP.get(cursor_type, Qt.ArrowCursor))
            else: 
                self._is_dragging = True
                self._is_resizing = False
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Handles mouse move events.
        Performs dragging or resizing if active. Otherwise, updates the cursor shape
        if hovering over a resize edge.
        """
        if self._is_resizing and (event.buttons() & Qt.LeftButton):
            delta = event.globalPosition().toPoint() - self._resize_start_mouse_pos
            new_geom = QRect(self._resize_start_geometry)

            if "left" in self._current_resize_edge:
                new_width = max(self.min_width, new_geom.width() - delta.x())
                new_geom.setLeft(new_geom.right() - new_width)
            elif "right" in self._current_resize_edge:
                new_geom.setWidth(max(self.min_width, new_geom.width() + delta.x()))
            
            if "top" in self._current_resize_edge:
                new_height = max(self.min_height, new_geom.height() - delta.y())
                new_geom.setTop(new_geom.bottom() - new_height)
            elif "bottom" in self._current_resize_edge:
                new_geom.setHeight(max(self.min_height, new_geom.height() + delta.y()))
            
            self.setGeometry(new_geom)
            event.accept()
        elif self._is_dragging and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else: 
            current_hover_edge = self._get_resize_edge(event.position().toPoint())
            cursor_type = self._current_resize_edge_to_cursor_type(current_hover_edge)
            self.setCursor(CURSOR_MAP.get(cursor_type, Qt.ArrowCursor))
            event.accept() 

    def mouseReleaseEvent(self, event: QMouseEvent):
        """
        Handles mouse button release events.
        Finalizes dragging or resizing operations and saves new geometry if configured.
        """
        if event.button() == Qt.LeftButton:
            action_taken = False
            if self._is_resizing:
                self._is_resizing = False
                action_taken = True
                if self.config_manager.get("window.remember_size"):
                    self.config_manager.set("window.last_width", self.width())
                    self.config_manager.set("window.last_height", self.height())
                if self.config_manager.get("window.remember_position") and \
                   (self._current_resize_edge and ("left" in self._current_resize_edge or "top" in self._current_resize_edge)):
                    self.config_manager.set("window.last_x", self.x())
                    self.config_manager.set("window.last_y", self.y())

            elif self._is_dragging:
                self._is_dragging = False
                action_taken = True
                if self.config_manager.get("window.remember_position"):
                    self.config_manager.set("window.last_x", self.x())
                    self.config_manager.set("window.last_y", self.y())
            
            self._current_resize_edge = None
            if action_taken:
                current_hover_edge = self._get_resize_edge(event.position().toPoint())
                cursor_type = self._current_resize_edge_to_cursor_type(current_hover_edge)
                self.setCursor(CURSOR_MAP.get(cursor_type, Qt.ArrowCursor))
            event.accept()

    def _get_resize_edge(self, pos: QPoint) -> str | None:
        """
        Determines which resize edge, if any, the given mouse position (relative to widget)
        is currently over.
        """
        on_left = pos.x() >= 0 and pos.x() < RESIZE_MARGIN
        on_right = pos.x() <= self.width() and pos.x() > self.width() - RESIZE_MARGIN
        on_top = pos.y() >=0 and pos.y() < RESIZE_MARGIN
        on_bottom = pos.y() <= self.height() and pos.y() > self.height() - RESIZE_MARGIN

        if on_left and on_top: return "top_left"
        if on_right and on_top: return "top_right"
        if on_left and on_bottom: return "bottom_left"
        if on_right and on_bottom: return "bottom_right"
        
        if on_left: return "left"
        if on_right: return "right"
        if on_top: return "top"
        if on_bottom: return "bottom"
        
        return None

    def _current_resize_edge_to_cursor_type(self, edge_str: str | None) -> str:
        """
        Maps a resize edge string identifier to a cursor type string identifier
        used in CURSOR_MAP.
        """
        if not edge_str: return "arrow"
        if edge_str in ["left", "right"]: return "size_h"
        if edge_str in ["top", "bottom"]: return "size_v"
        if edge_str in ["top_left", "bottom_right"]: return "size_tl_br"
        if edge_str in ["top_right", "bottom_left"]: return "size_tr_bl"
        return "arrow"
        
    def paintEvent(self, event: 'QPaintEvent'):
        """
        Handles paint events for the window.
        """
        super().paintEvent(event)

    def toggle_visibility(self):
        """
        Toggles the visibility of the overlay window.
        """
        if self._exiting_flag: return
        if self.isVisible():
            self.hide()
            print("Overlay hidden.")
            if self._peek_timer.isActive():
                self._peek_timer.stop()
        else:
            self.show()
            if self.config_manager.get("window.always_on_top"):
                self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
                self.show() 
            self.activateWindow() 
            self.raise_() 
            print("Overlay shown.")

    def peek_visibility(self):
        """
        Shows the overlay window temporarily for a configured duration ("peek").
        """
        if self._exiting_flag: return
        duration_ms = int(self.config_manager.get("shortcuts.peek_duration_seconds", 3) * 1000)
        
        if not self.isVisible():
            self.show()
            if self.config_manager.get("window.always_on_top"):
                self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
                self.show() 
            self.activateWindow()
            self.raise_()
            print("Overlay peek: shown.")
        else: 
            print("Overlay peek: already visible, restarting timer.")
            
        self._peek_timer.start(duration_ms)

    def _hide_after_peek_action(self):
        """
        Slot connected to the _peek_timer's timeout signal.
        """
        if self.isVisible() and not self._exiting_flag:
            self.hide()
            print("Overlay peek: auto-hidden.")

    def exit_application(self):
        """
        Initiates the application shutdown sequence.
        """
        if self._exiting_flag: return
        self._exiting_flag = True
        print("Exit application initiated by shortcut/signal.")
        self.close() 

    def closeEvent(self, event: 'QCloseEvent'):
        """
        Handles the window's close event.
        """
        print("OverlayWindow.closeEvent() called.")
        if not self._exiting_flag: 
            self._exiting_flag = True 

        print("App Info: Stopping shortcut listener...")
        if self.shortcut_manager:
            self.shortcut_manager.stop_listening()
        
        print("App Info: Cancelling timers...")
        if self._peek_timer and self._peek_timer.isActive():
            self._peek_timer.stop()
        
        print("App Info: Accepting close event. Application will quit.")
        event.accept()
        QApplication.instance().quit()

if __name__ == "__main__":
    nltk_data_verified = True
    nltk_punkt_downloaded = False

    try:
        nltk.data.find('tokenizers/punkt')
        print("NLTK 'punkt' tokenizer found.")
        nltk_punkt_downloaded = True
    except LookupError:
        print("NLTK 'punkt' tokenizer not found. Attempting to download...")
        try:
            nltk.download('punkt', quiet=True)
            nltk.data.find('tokenizers/punkt') 
            print("'punkt' tokenizer downloaded and verified.")
            nltk_punkt_downloaded = True
        except Exception as e:
            print(f"Error downloading or verifying 'punkt' tokenizer: {e}.")
            nltk_data_verified = False 
    except ImportError:
        print("NLTK library not found. Please install it: pip install nltk")
        nltk_data_verified = False 
    
    if not nltk_data_verified: 
        print("Critical NLTK setup failed. Please ensure NLTK is installed and 'punkt' data can be downloaded.")
        sys.exit(1)

    app = QApplication(sys.argv)

    config_mgr = ConfigManager()
    shortcut_mgr = ShortcutManager(config_mgr)
    overlay_window = OverlayWindow(config_mgr, shortcut_mgr)
    
    overlay_window.show() 
    
    shortcut_mgr.start_listening()

    exit_code = app.exec()
    print(f"Application event loop finished. Exiting with code: {exit_code}")
    
    if shortcut_mgr: 
        shortcut_mgr.stop_listening() 
    
    sys.exit(exit_code)