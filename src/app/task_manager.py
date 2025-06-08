import json
import os
import copy
from datetime import datetime
from appdirs import user_config_dir

class TaskManager:
    """
    Manages loading, saving, and handling of task data persisted in a JSON file.
    Handles conversion of datetime objects to/from ISO format strings for JSON serialization.
    Supports tasks with steps and tasks that are directly checkable.
    Updating a task's completion will also update all its steps if present.
    """
    def __init__(self, app_name: str, app_author: str):
        """
        Initializes the TaskManager.

        Args:
            app_name: The application name, used for determining the user data directory.
            app_author: The application author, used for determining the user data directory.
        """
        self.tasks_file_path = os.path.join(user_config_dir(app_name, app_author), "tasks.json")
        self._ensure_tasks_dir_exists()
        self.tasks_data = self._load_tasks_from_file() 

    def _ensure_tasks_dir_exists(self):
        """Ensures the directory for tasks.json exists."""
        tasks_dir = os.path.dirname(self.tasks_file_path)
        if not os.path.exists(tasks_dir):
            os.makedirs(tasks_dir, exist_ok=True)

    def _datetime_to_iso(self, dt_obj: datetime | None) -> str | None:
        """Converts a datetime object to an ISO format string. Returns None if input is None."""
        if dt_obj is None:
            return None
        return dt_obj.isoformat()

    def _iso_to_datetime(self, iso_str: str | None) -> datetime | None:
        """Converts an ISO format string to a datetime object. Returns None if input is None or invalid."""
        if iso_str is None:
            return None
        try:
            return datetime.fromisoformat(iso_str)
        except (TypeError, ValueError):
            print(f"Warning: Could not parse ISO datetime string: {iso_str}")
            return None

    def _load_tasks_from_file(self) -> list:
        """
        Loads tasks from the tasks.json file.
        Converts timestamp strings back to datetime objects for tasks and steps.
        Returns an empty list if the file doesn't exist, is empty, or is malformed.
        """
        if not os.path.exists(self.tasks_file_path) or os.path.getsize(self.tasks_file_path) == 0:
            return []

        try:
            with open(self.tasks_file_path, 'r') as f:
                loaded_data = json.load(f)
            
            for task in loaded_data:
                task['created_timestamp'] = self._iso_to_datetime(task.get('created_timestamp'))
                if 'completed' not in task: # Ensure older tasks get this field
                    task['completed'] = False
                if 'completed_timestamp' not in task: # Ensure older tasks get this field
                     task['completed_timestamp'] = None
                task['completed_timestamp'] = self._iso_to_datetime(task.get('completed_timestamp'))
                
                for step in task.get('steps', []):
                    step['completed_timestamp'] = self._iso_to_datetime(step.get('completed_timestamp'))
            return loaded_data
        except json.JSONDecodeError:
            print(f"Warning: Error decoding {self.tasks_file_path}. Returning empty task list.")
            return []
        except Exception as e:
            print(f"Error: Unexpected error loading tasks from {self.tasks_file_path}: {e}. Returning empty list.")
            return []

    def _save_tasks_to_file(self):
        """
        Saves the current in-memory self.tasks_data to tasks.json.
        Converts datetime objects to ISO format strings for serialization for tasks and steps.
        """
        self._ensure_tasks_dir_exists()
        
        data_to_save = copy.deepcopy(self.tasks_data) 
        for task in data_to_save:
            task['created_timestamp'] = self._datetime_to_iso(task.get('created_timestamp'))
            task['completed_timestamp'] = self._datetime_to_iso(task.get('completed_timestamp'))

            for step in task.get('steps', []):
                step['completed_timestamp'] = self._datetime_to_iso(step.get('completed_timestamp'))

        try:
            with open(self.tasks_file_path, 'w') as f:
                json.dump(data_to_save, f, indent=4)
        except IOError as e:
            print(f"Error: Could not save tasks to {self.tasks_file_path}: {e}")
        except TypeError as e:
            print(f"Error: Could not serialize task data for saving: {e}")

    def get_all_tasks(self) -> list:
        """
        Returns a deep copy of the current in-memory tasks data.
        """
        return copy.deepcopy(self.tasks_data)

    def replace_all_tasks(self, new_tasks_list: list):
        """
        Replaces the current in-memory tasks with a new list and saves to file.

        Args:
            new_tasks_list: The new list of task dictionaries to store.
        """
        self.tasks_data = copy.deepcopy(new_tasks_list) 
        self._save_tasks_to_file()
        print(f"Tasks replaced and saved. Current task count: {len(self.tasks_data)}")

    def update_step_completion(self, task_id: str, step_id: str, completed: bool) -> bool:
        """
        Updates the completion status of a specific step within a task.
        The parent task's own 'completed' status is not directly managed here but
        will be re-evaluated by TaskListView based on step states.
        """
        task_found = False
        step_updated = False
        for task in self.tasks_data:
            if task.get('task_id') == task_id:
                task_found = True
                for step in task.get('steps', []):
                    if step.get('step_id') == step_id:
                        step['completed'] = completed
                        step['completed_timestamp'] = datetime.now() if completed else None
                        step_updated = True
                        break 
                if step_updated:
                    # Optionally, update the parent task's 'completed' field based on aggregate step status
                    if task.get('steps'):
                        all_steps_done = all(s.get('completed', False) for s in task['steps'])
                        # Task 'completed' field reflects if ALL steps are done.
                        # A partially completed task is not 'completed': True at the task level.
                        if all_steps_done:
                            task['completed'] = True
                            if task.get('completed_timestamp') is None: # Set timestamp if newly completed
                                task['completed_timestamp'] = datetime.now()
                        else:
                            task['completed'] = False
                            task['completed_timestamp'] = None # Clear timestamp if not all steps are done
                    break
        
        if step_updated:
            self._save_tasks_to_file()
            print(f"Step '{step_id}' in task '{task_id}' updated to completed: {completed}")
            return True
        
        if not task_found:
            print(f"Warning: Task with ID '{task_id}' not found for updating step '{step_id}'.")
        elif not step_updated: 
            print(f"Warning: Step with ID '{step_id}' not found in task '{task_id}'.")
        return False

    def update_task_completion(self, task_id: str, completed: bool) -> bool:
        """
        Updates the completion status of a specific task.
        If the task has steps, all its steps are also updated to this status.
        """
        task_updated = False
        current_ts = datetime.now() if completed else None
        for task in self.tasks_data:
            if task.get('task_id') == task_id:
                task['completed'] = completed
                task['completed_timestamp'] = current_ts
                task_updated = True

                if task.get('steps'): # If task has steps, propagate change to all steps
                    for step in task['steps']:
                        step['completed'] = completed
                        step['completed_timestamp'] = current_ts
                break 
        
        if task_updated:
            self._save_tasks_to_file()
            print(f"Task '{task_id}' and its steps (if any) updated to completed: {completed}")
            return True
        
        print(f"Warning: Task with ID '{task_id}' not found for updating completion status.")
        return False