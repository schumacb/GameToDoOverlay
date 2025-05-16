# main_app.py
import sys
import time # For the brief pause in exit, if still desired
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QPoint, QTimer, QRect, QMetaObject, Q_ARG
from PySide6.QtGui import QColor, QPainter, QScreen, QCursor, QFont

from config_manager import ConfigManager
from shortcut_manager import ShortcutManager

# --- Constants for Resizing and Cursors ---
RESIZE_MARGIN = 8 # In pixels
CURSOR_MAP = {
    "arrow": Qt.ArrowCursor,
    "size_h": Qt.SizeHorCursor,    # Horizontal resize
    "size_v": Qt.SizeVerCursor,    # Vertical resize
    "size_tl_br": Qt.SizeFDiagCursor, # Top-left to bottom-right
    "size_tr_bl": Qt.SizeBDiagCursor, # Top-right to bottom-left
}

class OverlayWindow(QWidget):
    def __init__(self, config_manager, shortcut_manager):
        super().__init__()
        self.config_manager = config_manager
        self.shortcut_manager = shortcut_manager
        self._exiting_flag = False

        # Dragging and Resizing State
        self._drag_offset = QPoint()
        self._is_dragging = False
        self._is_resizing = False
        self._current_resize_edge = None # "left", "right", "top", "bottom", "top_left", ...

        self._resize_start_geometry = QRect()
        self._resize_start_mouse_pos = QPoint()

        self.min_width = int(self.config_manager.get("window.min_width", 100))
        self.min_height = int(self.config_manager.get("window.min_height", 50))
        self._peek_timer = QTimer(self)
        self._peek_timer.setSingleShot(True)
        self._peek_timer.timeout.connect(self._hide_after_peek_action)

        self._setup_ui()
        self._apply_initial_window_settings()
        self._connect_shortcuts()

        # Enable mouse tracking to get move events even when no button is pressed (for cursor changes)
        self.setMouseTracking(True)
        self.main_content_widget.setMouseTracking(True) # Also for child absorbing events
        self.main_label.setMouseTracking(True)


    def _setup_ui(self):
        # Main window flags
        flags = Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus
        if self.config_manager.get("window.always_on_top"):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)

        # For custom painting of background for transparency
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Overall window opacity
        opacity = float(self.config_manager.get("appearance.transparency", 0.85))
        self.setWindowOpacity(opacity)

        # Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0) # No margins for the main layout itself

        # Content Widget (for background distinct from window transparency effects if needed)
        self.main_content_widget = QWidget(self)
        content_bg_color = self.config_manager.get("appearance.content_background_color", "#3C3C3C")
        text_color = self.config_manager.get("appearance.text_color", "#FFFFFF")
        font_family = self.config_manager.get("appearance.font_family", "Arial")
        font_size = int(self.config_manager.get("appearance.font_size", 10))
        
        self.main_content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {content_bg_color};
                color: {text_color};
                border: none; /* Ensure no default border interferes with custom drawing */
            }}
        """)
        
        content_layout = QVBoxLayout(self.main_content_widget)
        content_layout.setContentsMargins(5,5,5,5) # Padding inside the content

        # Main label
        exit_shortcut_str = self.config_manager.get("shortcuts.exit_application", "Ctrl+Shift+Q")
        self.main_label = QLabel(f"Overlay Initializing...\n({exit_shortcut_str} to Exit)", self.main_content_widget)
        self.main_label.setFont(QFont(font_family, font_size))
        self.main_label.setAlignment(Qt.AlignCenter)
        self.main_label.setWordWrap(True)
        self.main_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content_layout.addWidget(self.main_label)
        self.main_layout.addWidget(self.main_content_widget)
        self.setLayout(self.main_layout)


    def _apply_initial_window_settings(self):
        # Geometry
        primary_screen = QApplication.primaryScreen()
        if not primary_screen:
            print("Error: Could not get primary screen.")
            # Fallback defaults if screen info isn't available
            screen_width, screen_height = 1920, 1080 
        else:
            screen_geometry = primary_screen.availableGeometry() # Use available to avoid taskbars etc.
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()

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
                self.config_manager.set("window.last_x", x) # Save initial calculated if not remembered
                self.config_manager.set("window.last_y", y)
        
        if self.config_manager.get("window.remember_size"):
             if self.config_manager.get("window.last_width") is None: self.config_manager.set("window.last_width", width)
             if self.config_manager.get("window.last_height") is None: self.config_manager.set("window.last_height", height)

        self.setGeometry(x, y, width, height)

    def _connect_shortcuts(self):
        self.shortcut_manager.toggle_visibility_requested.connect(self.toggle_visibility)
        self.shortcut_manager.peek_visibility_requested.connect(self.peek_visibility)
        self.shortcut_manager.exit_application_requested.connect(self.exit_application)

    # --- Event Handlers for Dragging, Resizing, Cursor ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._current_resize_edge = self._get_resize_edge(event.position().toPoint())
            if self._current_resize_edge:
                self._is_resizing = True
                self._is_dragging = False
                self._resize_start_geometry = self.geometry()
                self._resize_start_mouse_pos = event.globalPosition().toPoint()
                self.setCursor(CURSOR_MAP.get(self._current_resize_edge_to_cursor_type(self._current_resize_edge), Qt.ArrowCursor))
            else:
                self._is_dragging = True
                self._is_resizing = False
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_resizing:
            if event.buttons() & Qt.LeftButton:
                delta = event.globalPosition().toPoint() - self._resize_start_mouse_pos
                new_geom = QRect(self._resize_start_geometry)

                if "left" in self._current_resize_edge:
                    new_w = max(self.min_width, new_geom.width() - delta.x())
                    new_geom.setLeft(new_geom.right() - new_w)
                elif "right" in self._current_resize_edge:
                    new_geom.setWidth(max(self.min_width, new_geom.width() + delta.x()))
                
                if "top" in self._current_resize_edge:
                    new_h = max(self.min_height, new_geom.height() - delta.y())
                    new_geom.setTop(new_geom.bottom() - new_h)
                elif "bottom" in self._current_resize_edge:
                    new_geom.setHeight(max(self.min_height, new_geom.height() + delta.y()))
                
                self.setGeometry(new_geom)
            event.accept()
        elif self._is_dragging:
            if event.buttons() & Qt.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else: # Not dragging or resizing, just hovering: update cursor
            edge = self._get_resize_edge(event.position().toPoint())
            cursor_type_str = self._current_resize_edge_to_cursor_type(edge)
            self.setCursor(CURSOR_MAP.get(cursor_type_str, Qt.ArrowCursor))
            event.accept()


    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            action_taken = False
            if self._is_resizing:
                self._is_resizing = False
                action_taken = True
                if self.config_manager.get("window.remember_size"):
                    self.config_manager.set("window.last_width", self.width())
                    self.config_manager.set("window.last_height", self.height())
                # If resizing from left/top edges, position also changes
                if self.config_manager.get("window.remember_position") and \
                   ("left" in self._current_resize_edge or "top" in self._current_resize_edge):
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
                 # Update cursor based on current position after action
                current_edge = self._get_resize_edge(event.position().toPoint())
                self.setCursor(CURSOR_MAP.get(self._current_resize_edge_to_cursor_type(current_edge), Qt.ArrowCursor))

            event.accept()


    def _get_resize_edge(self, pos: QPoint):
        r_margin, b_margin = RESIZE_MARGIN, RESIZE_MARGIN 
        on_left = pos.x() < r_margin
        on_right = pos.x() > self.width() - r_margin
        on_top = pos.y() < r_margin
        on_bottom = pos.y() > self.height() - b_margin

        if on_left and on_top: return "top_left"
        if on_right and on_top: return "top_right"
        if on_left and on_bottom: return "bottom_left"
        if on_right and on_bottom: return "bottom_right"
        if on_left: return "left"
        if on_right: return "right"
        if on_top: return "top"
        if on_bottom: return "bottom"
        return None

    def _current_resize_edge_to_cursor_type(self, edge_str):
        if not edge_str: return "arrow"
        if edge_str in ["left", "right"]: return "size_h"
        if edge_str in ["top", "bottom"]: return "size_v"
        if edge_str in ["top_left", "bottom_right"]: return "size_tl_br"
        if edge_str in ["top_right", "bottom_left"]: return "size_tr_bl"
        return "arrow"
        
    # Required for WA_TranslucentBackground if we want a specific background color
    # that isn't just full transparency.
    # If main_content_widget covers the whole area and has its own BG,
    # this paintEvent for the main window might only be needed for truly custom shapes
    # or if the content widget doesn't fill it / has margins showing window bg.
    # For now, we let main_content_widget handle its background.
    # If window opacity is < 1, this color will also be semi-transparent.
    def paintEvent(self, event):
        # If you want the window itself to have a base color before widgets are drawn on top,
        # or if content_widget doesn't fill the whole area.
        # painter = QPainter(self)
        # window_bg_color_str = self.config_manager.get("appearance.background_color", "#00000000") # default to transparent black
        # window_bg_color = QColor(window_bg_color_str)
        # painter.fillRect(self.rect(), window_bg_color) # This color will be affected by setWindowOpacity
        
        # If main_content_widget handles all visuals, this might not be needed
        # or could be used for custom borders if desired.
        super().paintEvent(event) # Important if there are child widgets that need painting.

    # --- Visibility Control Slots ---
    def toggle_visibility(self):
        if self._exiting_flag: return
        if self.isVisible():
            self.hide()
            print("Overlay hidden.")
            if self._peek_timer.isActive():
                self._peek_timer.stop()
        else:
            self.show()
            # Ensure it's on top again if it was hidden
            if self.config_manager.get("window.always_on_top"):
                self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.activateWindow() # Try to bring to front
            self.raise_()
            print("Overlay shown.")

    def peek_visibility(self):
        if self._exiting_flag: return
        duration_ms = int(self.config_manager.get("shortcuts.peek_duration_seconds", 3) * 1000)
        
        if not self.isVisible():
            self.show()
            if self.config_manager.get("window.always_on_top"):
                self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.activateWindow()
            self.raise_()
            print("Overlay peek: shown.")
        else:
            print("Overlay peek: already visible, restarting timer.")
            
        self._peek_timer.start(duration_ms)

    def _hide_after_peek_action(self):
        if self.isVisible():
            self.hide()
            print("Overlay peek: auto-hidden.")

    def exit_application(self):
        if self._exiting_flag:
            return
        self._exiting_flag = True
        print("Exit application initiated by shortcut/signal.")
        self.close() # This will trigger closeEvent

    def closeEvent(self, event):
        print("OverlayWindow.closeEvent() called.")
        if self._exiting_flag: # Already in shutdown
            event.accept()
            QApplication.instance().quit() # Ensure app quits
            return

        self._exiting_flag = True # Mark as exiting
        print("App Info: Stopping shortcut listener...")
        if self.shortcut_manager:
            self.shortcut_manager.stop_listening()
        
        print("App Info: Cancelling timers...")
        if self._peek_timer and self._peek_timer.isActive():
            self._peek_timer.stop()
        
        print("App Info: Closing PySide6 application window.")
        event.accept() # Accept the close event
        
        # Ensure the application instance quits
        # Sometimes QApplication.instance().quit() needs to be called explicitly after event loop processing
        QTimer.singleShot(50, QApplication.instance().quit) # Allow event queue to clear
        print("App Info: QApplication.instance().quit() scheduled.")


if __name__ == "__main__":
    # Ensure NLTK 'punkt' is available
    try:
        import nltk
        nltk.data.find('tokenizers/punkt')
        print("NLTK 'punkt' tokenizer found.")
    except LookupError:
        print("NLTK 'punkt' tokenizer not found. Attempting to download...")
        try:
            nltk.download('punkt', quiet=True)
            nltk.data.find('tokenizers/punkt') # Verify after download
            print("'punkt' tokenizer downloaded and verified.")
        except Exception as e:
            print(f"Error downloading or verifying 'punkt': {e}. Please install manually or check network.")
            sys.exit(1) # Critical for task parsing later
    except ImportError:
        print("NLTK library not found. Please install it: pip install nltk")
        sys.exit(1)

    # For HiDPI displays, if needed
    # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    # QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    config_mgr = ConfigManager()
    shortcut_mgr = ShortcutManager(config_mgr)
    
    overlay_window = OverlayWindow(config_mgr, shortcut_mgr)
    overlay_window.show() # Initially show the window, shortcuts will control visibility after
    
    # Start listening for shortcuts AFTER the window is created and shown (or ready)
    # to ensure all Qt setup is complete for signal/slot connections.
    shortcut_mgr.start_listening()

    exit_code = app.exec()
    print(f"Application exiting with code: {exit_code}")
    
    # Ensure final cleanup, pynput thread might keep script alive otherwise.
    if shortcut_mgr:
        shortcut_mgr.stop_listening() # Final attempt to stop
    
    # A small delay for any cleanup threads to finish, then force exit.
    # This is a bit aggressive but can help if pynput listener doesn't terminate cleanly.
    # Python's main thread might exit, but daemon threads from pynput could hang.
    # time.sleep(0.2) 
    # print("Forcing sys.exit after main loop.")
    sys.exit(exit_code)