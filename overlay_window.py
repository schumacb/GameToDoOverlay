import math
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QPoint, QTimer, QRect, Slot
from PySide6.QtGui import (
    QFont, QScreen, QCursor, QKeyEvent, QClipboard, QMouseEvent,
    QPainter, QColor, QImage
)

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from config_manager import ConfigManager
    from shortcut_manager import ShortcutManager
    from task_manager import TaskManager
    from task_parser import BaseTaskParser
    from task_list_view import TaskListView

from task_list_view import TaskListView

try:
    from noise import pnoise2
except ImportError:
    print("Warning: 'noise' library not found. Faded border will not have noise effect. Consider installing it: pip install noise")
    pnoise2 = None

RESIZE_MARGIN = 8
CURSOR_MAP = {
    "arrow": Qt.ArrowCursor, "size_h": Qt.SizeHorCursor, "size_v": Qt.SizeVerCursor,
    "size_tl_br": Qt.SizeFDiagCursor, "size_tr_bl": Qt.SizeBDiagCursor,
}

# Configuration for the faded border effect
FADE_BORDER_WIDTH = 20
NOISE_SCALE = 0.06
NOISE_OCTAVES = 4
NOISE_PERSISTENCE = 0.6
NOISE_LACUNARITY = 2.0
NOISE_BASE_SEED = 42
NOISE_MODULATION_STRENGTH = 1.0


class OverlayWindow(QWidget):
    """
    Main application window, acts as a controller for the overlay.
    Manages window properties (frameless, on-top, transparency, size, position),
    user interactions (drag, resize, paste via Ctrl+V), and coordinates with
    shortcut management, task parsing, task data persistence (TaskManager),
    and the task display component (TaskListView).
    Handles completion for both tasks with steps and directly checkable tasks.
    Features a custom-painted faded border with optional noise effect and selectable fade types.
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

        self.content_bg_color_str = "" # Will be set in _setup_ui
        self.fade_type = self.config_manager.get("appearance.fade_type", "quadratic")


        self.min_width = int(self.config_manager.get("window.min_width", 100))
        self.min_height = int(self.config_manager.get("window.min_height", 50))

        self._peek_timer = QTimer(self)
        self._peek_timer.setSingleShot(True)
        self._peek_timer.timeout.connect(self._hide_after_peek_action)

        self.tasks_data = self.task_manager.get_all_tasks()

        self.task_list_view: 'TaskListView' = None

        self._setup_ui()
        self._apply_initial_window_settings()
        self._connect_signals_and_shortcuts()

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
        # Add margins for the faded border effect
        self.main_layout.setContentsMargins(FADE_BORDER_WIDTH, FADE_BORDER_WIDTH, FADE_BORDER_WIDTH, FADE_BORDER_WIDTH)

        self.main_content_widget = QWidget(self)
        self.content_bg_color_str = self.config_manager.get("appearance.content_background_color", "#1F1F1F")

        self.main_content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {self.content_bg_color_str};
                border: none;
            }}
        """)

        content_area_layout = QVBoxLayout(self.main_content_widget)
        content_area_layout.setContentsMargins(0,0,0,0)

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

        # When calculating initial width/height, consider the border width
        effective_min_width = self.min_width + 2 * FADE_BORDER_WIDTH
        effective_min_height = self.min_height + 2 * FADE_BORDER_WIDTH


        width = effective_min_width
        if self.config_manager.get("window.remember_size") and \
           self.config_manager.get("window.last_width") is not None:
            width = max(int(self.config_manager.get("window.last_width")), effective_min_width)
        else:
            # Add border width to initial size config if it's for content size
            initial_content_width = int(self.config_manager.get("window.initial_width"))
            width = max(initial_content_width + 2 * FADE_BORDER_WIDTH, effective_min_width)


        height = effective_min_height
        if self.config_manager.get("window.remember_size") and \
           self.config_manager.get("window.last_height") is not None:
            height = max(int(self.config_manager.get("window.last_height")), effective_min_height)
        else:
            initial_content_height = int(self.config_manager.get("window.initial_height", 200))
            height = max(initial_content_height + 2 * FADE_BORDER_WIDTH, effective_min_height)

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
            self.task_list_view.task_completion_changed.connect(self._handle_task_completion_change)


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
        """
        print(f"Controller: Step completion change for task '{task_id}', step '{step_id}', completed: {is_completed}")
        success = self.task_manager.update_step_completion(task_id, step_id, is_completed)
        if success:
            self.tasks_data = self.task_manager.get_all_tasks()
            if self.task_list_view:
                self.task_list_view.update_display(self.tasks_data)
        else:
            print(f"Controller: Failed to update step '{step_id}' completion in TaskManager.")

    @Slot(str, bool)
    def _handle_task_completion_change(self, task_id: str, is_completed: bool):
        """
        Slot to handle changes in a task's completion status (for tasks without steps).
        Updates the TaskManager and then refreshes the TaskListView.
        """
        print(f"Controller: Task completion change for task '{task_id}', completed: {is_completed}")
        success = self.task_manager.update_task_completion(task_id, is_completed)
        if success:
            self.tasks_data = self.task_manager.get_all_tasks()
            if self.task_list_view:
                self.task_list_view.update_display(self.tasks_data)
        else:
            print(f"Controller: Failed to update task '{task_id}' completion in TaskManager.")


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
        effective_min_width = self.min_width + 2 * FADE_BORDER_WIDTH
        effective_min_height = self.min_height + 2 * FADE_BORDER_WIDTH

        if self._is_resizing and (event.buttons() & Qt.LeftButton):
            delta = event.globalPosition().toPoint() - self._resize_start_mouse_pos
            new_geom = QRect(self._resize_start_geometry)
            if "left" in self._current_resize_edge:
                new_w = max(effective_min_width, new_geom.width() - delta.x()); new_geom.setLeft(new_geom.right() - new_w)
            elif "right" in self._current_resize_edge: new_geom.setWidth(max(effective_min_width, new_geom.width() + delta.x()))
            if "top" in self._current_resize_edge:
                new_h = max(effective_min_height, new_geom.height() - delta.y()); new_geom.setTop(new_geom.bottom() - new_h)
            elif "bottom" in self._current_resize_edge: new_geom.setHeight(max(effective_min_height, new_geom.height() + delta.y()))
            self.setGeometry(new_geom)
            self.update() # Trigger repaint for border
            event.accept()
        elif self._is_dragging and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self.update() # Trigger repaint for border if noise is world-fixed (not an issue here)
            event.accept()
        else:
            current_hover_edge = self._get_resize_edge(event.position().toPoint())
            cursor_type = self._current_resize_edge_to_cursor_type(current_hover_edge)
            self.setCursor(CURSOR_MAP.get(cursor_type, Qt.ArrowCursor))
            # event.accept() # Not accepting here allows child widgets to get mouse move

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
            if action_taken: # Only reset cursor if we were dragging or resizing
                current_hover_edge = self._get_resize_edge(event.position().toPoint())
                cursor_type = self._current_resize_edge_to_cursor_type(current_hover_edge)
                self.setCursor(CURSOR_MAP.get(cursor_type, Qt.ArrowCursor))
            event.accept()


    def _get_resize_edge(self, pos: QPoint) -> str | None:
        """Determines which window edge the mouse is over for resizing."""
        # Check against the outer edges of the window, as FADE_BORDER_WIDTH is part of the window
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
        """Handles paint events for the window, drawing a custom faded border."""
        super().paintEvent(event)
        clear_painter = QPainter(self)
        clear_painter.setCompositionMode(QPainter.CompositionMode_Source)
        clear_painter.fillRect(self.rect(), Qt.transparent)
        clear_painter.end()
        if FADE_BORDER_WIDTH <= 0:
            return

        image_to_draw = QImage(self.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image_to_draw.fill(Qt.GlobalColor.transparent)
        image_painter = QPainter(image_to_draw)

        win_width = self.width()
        win_height = self.height()

        try:
            base_border_color = QColor(self.content_bg_color_str)
            if not base_border_color.isValid():
                base_border_color = QColor(self.config_manager.get("appearance.content_background_color", "#1F1F1F"))
        except Exception:
            base_border_color = QColor(Qt.GlobalColor.darkGray)

        content_r, content_g, content_b = base_border_color.red(), base_border_color.green(), base_border_color.blue()

        content_area_left = FADE_BORDER_WIDTH
        content_area_top = FADE_BORDER_WIDTH
        content_area_right = win_width - FADE_BORDER_WIDTH - 1
        content_area_bottom = win_height - FADE_BORDER_WIDTH - 1


        for py in range(win_height):
            for px in range(win_width):
                is_in_content_area = (content_area_left <= px <= content_area_right and
                                      content_area_top <= py <= content_area_bottom)

                if is_in_content_area:
                    continue

                dx_to_content_edge = 0
                if px < content_area_left:
                    dx_to_content_edge = content_area_left - px - 1
                elif px > content_area_right:
                    dx_to_content_edge = px - content_area_right - 1

                dy_to_content_edge = 0
                if py < content_area_top:
                    dy_to_content_edge = content_area_top - py - 1
                elif py > content_area_bottom:
                    dy_to_content_edge = py - content_area_bottom - 1

                margin_depth = math.hypot(dx_to_content_edge, dy_to_content_edge)

                if margin_depth < 0 or margin_depth >= FADE_BORDER_WIDTH:
                    continue

                intensity_factor = 0.0
                if FADE_BORDER_WIDTH <= 1:
                    normalized_progress = 1.0 if margin_depth == 0 else 0.0 # 0 near content, 1 at edge
                else:
                    # normalized_progress (x): 0 (pixel adjacent to content) to 1 (pixel at window edge)
                    normalized_progress = float(margin_depth) / (FADE_BORDER_WIDTH - 1.0)

                if self.fade_type == "linear":
                    intensity_factor = 1.0 - normalized_progress
                elif self.fade_type == "quadratic":
                    # (1-x)^2, opacity fades faster near content then levels off
                    intensity_factor = (1.0 - normalized_progress)**2
                elif self.fade_type == "logarithmic":
                    # y_param goes from 1 (near content) to 0 (at window edge)
                    y_param = 1.0 - normalized_progress
                    if y_param < 1e-9: # Avoid log issues with y_param = 0
                        intensity_factor = 0.0
                    else:
                        # Using natural log: log(y * (e-1) + 1). This gives a curve that is 1 at y=1 and 0 at y=0.
                        # The (e-1) term scales y such that when y=1, expression inside log is e, when y=0, expression is 1.
                        intensity_factor = math.log(y_param * (math.e - 1.0) + 1.0)
                else: # Fallback to linear
                    intensity_factor = 1.0 - normalized_progress
                
                # Ensure intensity_factor is clamped between 0 and 1
                intensity_factor = max(0.0, min(1.0, intensity_factor))
                current_alpha = int(intensity_factor * 255)


                if pnoise2 and NOISE_MODULATION_STRENGTH > 0:
                    noise_value = pnoise2(
                        px * NOISE_SCALE,
                        py * NOISE_SCALE,
                        octaves=NOISE_OCTAVES,
                        persistence=NOISE_PERSISTENCE,
                        lacunarity=NOISE_LACUNARITY,
                        base=NOISE_BASE_SEED
                    )
                    modulation = 1.0 + (noise_value * NOISE_MODULATION_STRENGTH)
                    current_alpha = int(current_alpha * modulation)

                current_alpha = max(0, min(255, current_alpha))

                image_to_draw.setPixelColor(px, py, QColor(content_r, content_g, content_b, current_alpha))

        image_painter.end()

        main_window_painter = QPainter(self)
        main_window_painter.drawImage(0, 0, image_to_draw)
        main_window_painter.end()


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

    def resizeEvent(self, event: 'QResizeEvent'):
        """Handles window resize events."""
        super().resizeEvent(event)
        self.update()