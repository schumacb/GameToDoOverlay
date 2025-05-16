from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QPoint, QTimer, QRect, Slot
from PySide6.QtGui import QFont, QScreen, QCursor, QKeyEvent, QClipboard, QMouseEvent

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from config_manager import ConfigManager
    from shortcut_manager import ShortcutManager
    from task_manager import TaskManager
    from task_parser import BaseTaskParser
    from task_list_view import TaskListView

from task_list_view import TaskListView 

RESIZE_MARGIN = 8 
CURSOR_MAP = { 
    "arrow": Qt.ArrowCursor, "size_h": Qt.SizeHorCursor, "size_v": Qt.SizeVerCursor,
    "size_tl_br": Qt.SizeFDiagCursor, "size_tr_bl": Qt.SizeBDiagCursor,
}

class OverlayWindow(QWidget):
    """
    Main application window, acts as a controller for the overlay.
    Manages window properties (frameless, on-top, transparency, size, position),
    user interactions (drag, resize, paste via Ctrl+V), and coordinates with
    shortcut management, task parsing, task data persistence (TaskManager),
    and the task display component (TaskListView).
    """
    def __init__(self, 
                 config_manager: 'ConfigManager', 
                 shortcut_manager: 'ShortcutManager', 
                 task_manager: 'TaskManager',
                 task_parser: 'BaseTaskParser'
                ):
        """
        Initializes the OverlayWindow.

        Args:
            config_manager: Manages application configuration.
            shortcut_manager: Manages global keyboard shortcuts.
            task_manager: Manages task data loading, saving, and updates.
            task_parser: Responsible for parsing raw text into structured tasks.
        """
        super().__init__()
        self.config_manager = config_manager
        self.shortcut_manager = shortcut_manager
        self.task_manager = task_manager
        self.task_parser = task_parser
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

        self.tasks_data = self.task_manager.get_all_tasks() 
        
        self.task_list_view: 'TaskListView' = None # Will be initialized in _setup_ui

        self._setup_ui() 
        self._apply_initial_window_settings()
        self._connect_signals_and_shortcuts() # Combined signal/shortcut connections
        
        if self.task_list_view:
            self.task_list_view.update_display(self.tasks_data)

        self.setMouseTracking(True)
        if hasattr(self, 'main_content_widget') and self.main_content_widget:
             self.main_content_widget.setMouseTracking(True)
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _setup_ui(self):
        """Initializes the main UI structure, window flags, and appearance."""
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
        
        self.main_content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {content_bg_color};
                border: none;
            }}
        """)
        
        content_area_layout = QVBoxLayout(self.main_content_widget)
        content_area_layout.setContentsMargins(0,0,0,0) # Let TaskListView handle its own padding
        
        self.task_list_view = TaskListView(self.config_manager, self.main_content_widget)
        content_area_layout.addWidget(self.task_list_view)
        
        self.main_layout.addWidget(self.main_content_widget)
        self.setLayout(self.main_layout)

    def _apply_initial_window_settings(self):
        """Applies initial window geometry based on configuration."""
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

    def _connect_signals_and_shortcuts(self):
        """Connects internal and external signals/shortcuts to their handlers."""
        self.shortcut_manager.toggle_visibility_requested.connect(self.toggle_visibility)
        self.shortcut_manager.peek_visibility_requested.connect(self.peek_visibility)
        self.shortcut_manager.exit_application_requested.connect(self.exit_application)

        if self.task_list_view:
            self.task_list_view.step_completion_changed.connect(self._handle_step_completion_change)

    def keyPressEvent(self, event: QKeyEvent):
        """Handles key press events, specifically Ctrl+V for pasting tasks."""
        if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_V:
            clipboard = QApplication.clipboard()
            pasted_text = clipboard.text(QClipboard.Mode.Clipboard)
            if pasted_text:
                self._process_pasted_text(pasted_text)
                event.accept()
                return 
        super().keyPressEvent(event)

    def _process_pasted_text(self, text_block: str):
        """
        Processes pasted text: uses the injected task_parser, updates 
        the TaskManager, refreshes local task data, and updates the UI.
        """
        print("Processing pasted text using injected parser...")
        parsed_tasks_list = self.task_parser.parse(text_block)
        
        self.task_manager.replace_all_tasks(parsed_tasks_list)
        self.tasks_data = self.task_manager.get_all_tasks() 
        
        if self.task_list_view:
            self.task_list_view.update_display(self.tasks_data)
        print(f"OverlayWindow: Tasks updated. Local count: {len(self.tasks_data)}")

    @Slot(str, str, bool)
    def _handle_step_completion_change(self, task_id: str, step_id: str, is_completed: bool):
        """
        Slot to handle changes in a step's completion status from TaskListView.
        Updates the TaskManager and then refreshes the TaskListView.

        Args:
            task_id: The ID of the task whose step changed.
            step_id: The ID of the step that changed.
            is_completed: The new completion status of the step.
        """
        print(f"Controller: Step completion change for task '{task_id}', step '{step_id}', completed: {is_completed}")
        success = self.task_manager.update_step_completion(task_id, step_id, is_completed)
        if success:
            self.tasks_data = self.task_manager.get_all_tasks() # Refresh local data
            if self.task_list_view:
                self.task_list_view.update_display(self.tasks_data) # Update view
        else:
            print(f"Controller: Failed to update step '{step_id}' completion in TaskManager.")


    def mousePressEvent(self, event: QMouseEvent):
        """Handles mouse press for dragging, resizing, and focus."""
        if not self.hasFocus():
            self.setFocus(Qt.FocusReason.MouseFocusReason)
        if event.button() == Qt.LeftButton:
            self._current_resize_edge = self._get_resize_edge(event.position().toPoint())
            if self._current_resize_edge:
                self._is_resizing = True; self._is_dragging = False
                self._resize_start_geometry = self.geometry()
                self._resize_start_mouse_pos = event.globalPosition().toPoint()
                cursor_type = self._current_resize_edge_to_cursor_type(self._current_resize_edge)
                self.setCursor(CURSOR_MAP.get(cursor_type, Qt.ArrowCursor))
            else: 
                self._is_dragging = True; self._is_resizing = False
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handles mouse move for dragging, resizing, and cursor updates."""
        if self._is_resizing and (event.buttons() & Qt.LeftButton):
            delta = event.globalPosition().toPoint() - self._resize_start_mouse_pos
            new_geom = QRect(self._resize_start_geometry)
            if "left" in self._current_resize_edge:
                new_w = max(self.min_width, new_geom.width() - delta.x()); new_geom.setLeft(new_geom.right() - new_w)
            elif "right" in self._current_resize_edge: new_geom.setWidth(max(self.min_width, new_geom.width() + delta.x()))
            if "top" in self._current_resize_edge:
                new_h = max(self.min_height, new_geom.height() - delta.y()); new_geom.setTop(new_geom.bottom() - new_h)
            elif "bottom" in self._current_resize_edge: new_geom.setHeight(max(self.min_height, new_geom.height() + delta.y()))
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
        """Handles mouse release to finalize drag/resize and save geometry."""
        if event.button() == Qt.LeftButton:
            action_taken = False
            if self._is_resizing:
                self._is_resizing = False; action_taken = True
                if self.config_manager.get("window.remember_size"):
                    self.config_manager.set("window.last_width", self.width())
                    self.config_manager.set("window.last_height", self.height())
                if self.config_manager.get("window.remember_position") and \
                   (self._current_resize_edge and ("left" in self._current_resize_edge or "top" in self._current_resize_edge)):
                    self.config_manager.set("window.last_x", self.x())
                    self.config_manager.set("window.last_y", self.y())
            elif self._is_dragging:
                self._is_dragging = False; action_taken = True
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
        """Determines which window edge the mouse is over for resizing."""
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
        """Maps resize edge string to a Qt cursor shape identifier."""
        if not edge_str: return "arrow"
        if edge_str in ["left", "right"]: return "size_h"
        if edge_str in ["top", "bottom"]: return "size_v"
        if edge_str in ["top_left", "bottom_right"]: return "size_tl_br"
        if edge_str in ["top_right", "bottom_left"]: return "size_tr_bl"
        return "arrow"
        
    def paintEvent(self, event: 'QPaintEvent'):
        """Handles paint events for the window."""
        super().paintEvent(event)

    def toggle_visibility(self):
        """Toggles the visibility of the overlay window."""
        if self._exiting_flag: return
        if self.isVisible():
            self.hide(); print("Overlay hidden.")
            if self._peek_timer.isActive(): self._peek_timer.stop()
        else:
            self.show()
            if self.config_manager.get("window.always_on_top"):
                self.setWindowFlag(Qt.WindowStaysOnTopHint, True); self.show() 
            self.activateWindow(); self.raise_()
            print("Overlay shown.")

    def peek_visibility(self):
        """Shows the overlay temporarily."""
        if self._exiting_flag: return
        duration_ms = int(self.config_manager.get("shortcuts.peek_duration_seconds", 3) * 1000)
        if not self.isVisible():
            self.show()
            if self.config_manager.get("window.always_on_top"):
                self.setWindowFlag(Qt.WindowStaysOnTopHint, True); self.show()
            self.activateWindow(); self.raise_()
            print("Overlay peek: shown.")
        else: 
            print("Overlay peek: already visible, restarting timer.")
        self._peek_timer.start(duration_ms)

    def _hide_after_peek_action(self):
        """Slot for QTimer to hide the window after peeking."""
        if self.isVisible() and not self._exiting_flag : self.hide(); print("Overlay peek: auto-hidden.")

    def exit_application(self):
        """Initiates application shutdown."""
        if self._exiting_flag: return
        self._exiting_flag = True
        print("Exit application initiated by shortcut/signal.")
        self.close() 

    def closeEvent(self, event: 'QCloseEvent'):
        """Handles window close event for cleanup before application quit."""
        print("OverlayWindow.closeEvent() called.")
        if not self._exiting_flag: self._exiting_flag = True 
        print("App Info: Stopping shortcut listener...")
        if self.shortcut_manager: self.shortcut_manager.stop_listening()
        print("App Info: Cancelling timers...")
        if self._peek_timer and self._peek_timer.isActive(): self._peek_timer.stop()
        print("App Info: Accepting close event. Application will quit.")
        event.accept()
        QApplication.instance().quit()