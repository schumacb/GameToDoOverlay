from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QCheckBox, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from config_manager import ConfigManager


class TaskListView(QWidget):
    """
    A widget responsible for displaying the list of tasks.
    Each task has a main checkbox. If the task has steps, this checkbox
    is tri-state (unchecked, partially, or fully checked) reflecting step completion,
    and clicking it toggles all steps. Steps also have individual checkboxes.
    If a task has no steps, its main checkbox is bi-state.
    Emits signals for completion changes.
    """
    step_completion_changed = Signal(str, str, bool) # task_id, step_id, is_completed
    task_completion_changed = Signal(str, bool)      # task_id, is_completed (for main task checkbox)

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
        Updates the view to display the provided list of tasks.
        """
        self._clear_task_widgets()

        font_family = self.config_manager.get("appearance.font_family")
        font_size = int(self.config_manager.get("appearance.font_size"))
        text_color = self.config_manager.get("appearance.text_color")
        
        checkbox_border_color_unchecked = self.config_manager.get("appearance.checkbox_border_color_unchecked", "#707070")
        checkbox_border_color_checked = self.config_manager.get("appearance.checkbox_border_color_checked", "#5090D0")
        checkbox_bg_color_checked = self.config_manager.get("appearance.checkbox_bg_color_checked", "#4070A0")
        checkbox_bg_color_partial = self.config_manager.get("appearance.checkbox_bg_color_partial", "#305070") 

        checkbox_style_sheet = f"""
            QCheckBox::indicator {{ 
                width: 13px; height: 13px; 
                border: 1px solid {checkbox_border_color_unchecked}; 
                border-radius: 3px;
                background-color: transparent; 
            }}
            QCheckBox::indicator:unchecked {{
                background-color: transparent;
            }}
            QCheckBox::indicator:checked {{
                background-color: {checkbox_bg_color_checked}; 
                border: 1px solid {checkbox_border_color_checked};
            }}
            QCheckBox::indicator:indeterminate {{
                background-color: {checkbox_bg_color_partial};
                border: 1px solid {checkbox_border_color_checked};
            }}
            QCheckBox {{ color: {text_color}; }} 
        """

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

            task_title_str = task_item.get("task_title", "Untitled Task")
            task_id = task_item.get("task_id")
            steps = task_item.get("steps", [])
            has_steps = bool(steps)

            task_header_widget = QWidget(task_group_frame)
            task_header_layout = QHBoxLayout(task_header_widget)
            task_header_layout.setContentsMargins(0, 0, 0, 0)
            task_header_layout.setSpacing(5)

            main_task_checkbox = QCheckBox(task_header_widget)
            main_task_checkbox.setStyleSheet(checkbox_style_sheet)
            main_task_checkbox.setProperty("task_id", task_id)
            main_task_checkbox.stateChanged.connect(self._on_task_checkbox_changed)

            title_font = QFont(font_family, font_size)
            title_font.setBold(True)
            task_title_label = QLabel(task_title_str, task_header_widget)
            task_title_label.setFont(title_font)
            task_title_label.setStyleSheet(f"color: {text_color};")
            task_title_label.setWordWrap(True)
            task_title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

            task_header_layout.addWidget(main_task_checkbox, 0, Qt.AlignmentFlag.AlignTop)
            task_header_layout.addWidget(task_title_label, 1)
            task_group_frame_layout.addWidget(task_header_widget)
            
            main_task_checkbox.blockSignals(True) # Block signals before programmatic state changes
            if has_steps:
                main_task_checkbox.setTristate(True)
                num_steps = len(steps)
                completed_steps = sum(1 for step in steps if step.get("completed"))

                if num_steps > 0:
                    if completed_steps == num_steps:
                        main_task_checkbox.setCheckState(Qt.CheckState.Checked)
                    elif completed_steps == 0:
                        main_task_checkbox.setCheckState(Qt.CheckState.Unchecked)
                    else: 
                        main_task_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
                else: 
                    main_task_checkbox.setTristate(False)
                    main_task_checkbox.setCheckState(Qt.CheckState.Checked if task_item.get("completed") else Qt.CheckState.Unchecked)
                
                steps_container = QWidget(task_group_frame) 
                steps_layout_for_group = QVBoxLayout(steps_container)
                steps_layout_for_group.setContentsMargins(20, 0, 0, 0) # Indent steps
                steps_layout_for_group.setSpacing(2)

                for step_item in steps:
                    step_widget = QWidget(steps_container) 
                    step_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
                    step_row_layout = QHBoxLayout(step_widget) 
                    step_row_layout.setContentsMargins(0,0,0,0) 
                    step_row_layout.setSpacing(5)

                    step_checkbox = QCheckBox(step_widget)
                    step_checkbox.setChecked(step_item.get("completed", False))
                    step_checkbox.setStyleSheet(checkbox_style_sheet)
                    step_checkbox.setProperty("task_id", task_id)
                    step_checkbox.setProperty("step_id", step_item.get("step_id"))
                    step_checkbox.stateChanged.connect(self._on_step_checkbox_changed)

                    step_text_label = QLabel(step_item.get("text", ""), step_widget)
                    step_text_label.setFont(QFont(font_family, font_size)) 
                    step_text_label.setStyleSheet(f"color: {text_color};")
                    step_text_label.setWordWrap(True)
                    step_text_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

                    step_row_layout.addWidget(step_checkbox, 0, Qt.AlignmentFlag.AlignTop)
                    step_row_layout.addWidget(step_text_label, 1) 
                    steps_layout_for_group.addWidget(step_widget)
                
                task_group_frame_layout.addWidget(steps_container)
            else: 
                main_task_checkbox.setTristate(False)
                main_task_checkbox.setCheckState(Qt.CheckState.Checked if task_item.get("completed") else Qt.CheckState.Unchecked)
            main_task_checkbox.blockSignals(False) # Unblock signals after state is set
            
            self.tasks_layout.addWidget(task_group_frame)

    @Slot(int) 
    def _on_step_checkbox_changed(self, state: int):
        """
        Handles the stateChanged signal from a step's QCheckBox.
        Emits the step_completion_changed signal.
        """
        checkbox = self.sender() 
        if checkbox:
            task_id = checkbox.property("task_id")
            step_id = checkbox.property("step_id")
            is_completed = (state == Qt.CheckState.Checked.value) 
            
            if task_id is not None and step_id is not None:
                self.step_completion_changed.emit(task_id, step_id, is_completed)
            else:
                print("Warning: Step checkbox missing task_id or step_id property.")
    
    @Slot(int)
    def _on_task_checkbox_changed(self, state: int):
        """
        Handles the stateChanged signal from a main task's QCheckBox.
        Emits the task_completion_changed signal. The new state determines
        if the task (and all its steps, if any) should be marked completed or uncompleted.
        This slot should only be triggered by direct user interaction due to signal blocking
        during programmatic updates.
        """
        checkbox = self.sender()
        if checkbox:
            task_id = checkbox.property("task_id")
            is_completed_intent = (state == Qt.CheckState.Checked.value or state == Qt.CheckState.PartiallyChecked.value)
            if checkbox.isTristate():
                 is_completed_intent = (state == Qt.CheckState.Checked.value) # If tristate, only fully checked means "intent to complete all"
                                                                              # Otherwise (partial or unchecked), intent to uncomplete all
            else: # Bi-state
                is_completed_intent = (state == Qt.CheckState.Checked.value)


            if task_id is not None:
                # When a main task checkbox is clicked:
                # If it becomes Checked, the intent is to mark all as complete.
                # If it becomes Unchecked (from Checked), the intent is to mark all as uncomplete.
                # If it was PartiallyChecked and becomes Checked, intent is to mark all as complete.
                # The `is_completed_intent` logic for tristate should be: if user interaction leads to checked, intent is True. Otherwise False.
                
                final_intent_to_complete = False
                if state == Qt.CheckState.Checked.value:
                    final_intent_to_complete = True
                elif state == Qt.CheckState.Unchecked.value:
                    final_intent_to_complete = False
                elif state == Qt.CheckState.PartiallyChecked.value:
                    # This state should not be achievable by a user click on a tristate checkbox.
                    # A click on PartiallyChecked makes it Checked.
                    # For safety, assume if it somehow ends up here, user wants to complete.
                    final_intent_to_complete = True 
                                
                self.task_completion_changed.emit(task_id, final_intent_to_complete)
            else:
                print("Warning: Task checkbox missing task_id property.")