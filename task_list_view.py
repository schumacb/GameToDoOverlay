from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QCheckBox, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from config_manager import ConfigManager


class TaskListView(QWidget):
    """
    A widget responsible for displaying the list of tasks and their steps.
    This view shows task titles, step checkboxes, and step text,
    and handles scrolling. It emits a signal when a step's completion
    status is changed by the user.
    """
    step_completion_changed = Signal(str, str, bool)

    def __init__(self, config_manager: 'ConfigManager', parent: QWidget = None):
        """
        Initializes the TaskListView.

        Args:
            config_manager: The application's configuration manager for styling.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self._init_ui()

    def _init_ui(self):
        """Initializes the UI components for the task list view."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)
        self.main_layout.setSpacing(0) 

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        bg_color = self.config_manager.get("appearance.content_background_color")
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{ 
                background-color: {bg_color}; 
                border: none; 
            }}
            QScrollArea > QWidget > QWidget {{ 
                background-color: {bg_color}; 
            }}
        """)
        self.scroll_area.viewport().setStyleSheet(f"background-color: {bg_color};")


        self.tasks_container_widget = QWidget()
        self.tasks_container_widget.setStyleSheet(f"background-color: {bg_color};")
        self.tasks_layout = QVBoxLayout(self.tasks_container_widget)
        self.tasks_layout.setContentsMargins(2,2,2,2) 
        self.tasks_layout.setSpacing(8) 
        self.tasks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.tasks_container_widget)
        self.main_layout.addWidget(self.scroll_area)

        self.update_display([]) 

    def _clear_task_widgets(self):
        """Removes all existing task and step widgets from the layout."""
        while self.tasks_layout.count():
            child = self.tasks_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def update_display(self, tasks_data: list):
        """
        Updates the view to display the provided list of tasks and their steps.
        Clears previous content and rebuilds the UI elements for each task and step.

        Args:
            tasks_data: A list of task dictionaries, as parsed by TaskParser.
        """
        self._clear_task_widgets()

        font_family = self.config_manager.get("appearance.font_family")
        font_size = int(self.config_manager.get("appearance.font_size"))
        text_color = self.config_manager.get("appearance.text_color")
        
        checkbox_border_color_unchecked = "#707070" 
        checkbox_border_color_checked = "#5090D0"   
        checkbox_bg_color_checked = "#4070A0"       

        if not tasks_data:
            no_tasks_label = QLabel("No tasks. Focus and Ctrl+V to paste.", self.tasks_container_widget)
            no_tasks_label.setFont(QFont(font_family, font_size))
            no_tasks_label.setStyleSheet(f"color: {text_color}; padding: 10px;")
            no_tasks_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_tasks_label.setWordWrap(True)
            self.tasks_layout.addWidget(no_tasks_label)
            return

        for task_item in tasks_data:
            task_group_frame = QFrame(self.tasks_container_widget)
            task_group_frame_layout = QVBoxLayout(task_group_frame)
            task_group_frame_layout.setContentsMargins(0, 0, 0, 5) 
            task_group_frame_layout.setSpacing(3) 

            task_title_label = QLabel(task_item.get("task_title", "Untitled Task"), task_group_frame)
            title_font = QFont(font_family, font_size) 
            title_font.setBold(True)
            task_title_label.setFont(title_font)
            task_title_label.setStyleSheet(f"color: {text_color}; padding-bottom: 4px;")
            task_title_label.setWordWrap(True)
            task_group_frame_layout.addWidget(task_title_label)

            steps_container = QWidget(task_group_frame) 
            steps_layout_for_group = QVBoxLayout(steps_container)
            steps_layout_for_group.setContentsMargins(10, 0, 0, 0) 
            steps_layout_for_group.setSpacing(2)

            for step_item in task_item.get("steps", []):
                step_widget = QWidget(steps_container) 
                step_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)

                step_row_layout = QHBoxLayout(step_widget) 
                step_row_layout.setContentsMargins(0,0,0,0) 
                step_row_layout.setSpacing(5)

                checkbox = QCheckBox(step_widget)
                checkbox.setChecked(step_item.get("completed", False))
                checkbox.setStyleSheet(f"""
                    QCheckBox::indicator {{ 
                        width: 13px; height: 13px; 
                        border: 1px solid {checkbox_border_color_unchecked}; 
                        border-radius: 3px;
                        background-color: transparent; 
                    }}
                    QCheckBox::indicator:checked {{
                        background-color: {checkbox_bg_color_checked}; 
                        border: 1px solid {checkbox_border_color_checked};
                    }}
                    QCheckBox::indicator:unchecked {{
                        background-color: transparent;
                    }}
                    QCheckBox {{ color: {text_color}; }} 
                """)
                
                checkbox.setProperty("task_id", task_item.get("task_id"))
                checkbox.setProperty("step_id", step_item.get("step_id"))
                checkbox.stateChanged.connect(self._on_step_checkbox_changed)

                step_text_label = QLabel(step_item.get("text", ""), step_widget)
                step_text_label.setFont(QFont(font_family, font_size)) 
                step_text_label.setStyleSheet(f"color: {text_color};")
                step_text_label.setWordWrap(True)
                step_text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

                step_row_layout.addWidget(checkbox)
                step_row_layout.addWidget(step_text_label, 1) 
                steps_layout_for_group.addWidget(step_widget)
            
            task_group_frame_layout.addWidget(steps_container)
            self.tasks_layout.addWidget(task_group_frame)

    @Slot(int) 
    def _on_step_checkbox_changed(self, state: int):
        """
        Handles the stateChanged signal from a step's QCheckBox.
        Retrieves task_id and step_id stored as properties on the checkbox
        and emits the step_completion_changed signal.

        Args:
            state: The new state of the checkbox (an int representing Qt.CheckState).
        """
        checkbox = self.sender() 
        if checkbox:
            task_id = checkbox.property("task_id")
            step_id = checkbox.property("step_id")
            is_completed = (state == Qt.CheckState.Checked.value) 
            
            if task_id is not None and step_id is not None:
                self.step_completion_changed.emit(task_id, step_id, is_completed)
            else:
                print("Warning: Checkbox missing task_id or step_id property.")