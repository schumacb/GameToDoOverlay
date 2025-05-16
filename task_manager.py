import json
import os
import copy
from datetime import datetime
from appdirs import user_config_dir

class TaskManager:
    """
    Manages loading, saving, and handling of task data persisted in a JSON file.
    Handles conversion of datetime objects to/from ISO format strings for JSON serialization.
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
        self.tasks_data = self._load_tasks_from_file() # Load tasks on initialization

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
            # Log error or handle as appropriate if malformed iso_str is critical
            print(f"Warning: Could not parse ISO datetime string: {iso_str}")
            return None

    def _load_tasks_from_file(self) -> list:
        """
        Loads tasks from the tasks.json file.
        Converts timestamp strings back to datetime objects.
        Returns an empty list if the file doesn't exist, is empty, or is malformed.
        """
        if not os.path.exists(self.tasks_file_path) or os.path.getsize(self.tasks_file_path) == 0:
            return []

        try:
            with open(self.tasks_file_path, 'r') as f:
                loaded_data = json.load(f)
            
            # Convert timestamps back to datetime objects
            for task in loaded_data:
                task['created_timestamp'] = self._iso_to_datetime(task.get('created_timestamp'))
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
        Converts datetime objects to ISO format strings for serialization.
        """
        self._ensure_tasks_dir_exists()
        
        # Create a temporary copy for serialization to avoid modifying in-memory datetime objects
        data_to_save = copy.deepcopy(self.tasks_data) 
        for task in data_to_save:
            task['created_timestamp'] = self._datetime_to_iso(task.get('created_timestamp'))
            for step in task.get('steps', []):
                step['completed_timestamp'] = self._datetime_to_iso(step.get('completed_timestamp'))
                # Note: step 'created_timestamp' is not explicitly stored per step, 
                # it's implicitly the task's created_timestamp.

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
        # It's good practice to store a deep copy if new_tasks_list might be modified elsewhere
        self.tasks_data = copy.deepcopy(new_tasks_list) 
        self._save_tasks_to_file()
        print(f"Tasks replaced and saved. Current task count: {len(self.tasks_data)}")

    def update_step_completion(self, task_id: str, step_id: str, completed: bool) -> bool:
        """
        Updates the completion status of a specific step within a task.

        Args:
            task_id: The ID of the main task containing the step.
            step_id: The ID of the step to update.
            completed: The new completion status (True or False).

        Returns:
            True if the step was found and updated, False otherwise.
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
                        break # Step found and updated
                if step_updated:
                    break # Task found and step updated
        
        if step_updated:
            self._save_tasks_to_file()
            print(f"Step '{step_id}' in task '{task_id}' updated to completed: {completed}")
            return True
        
        if not task_found:
            print(f"Warning: Task with ID '{task_id}' not found for updating step '{step_id}'.")
        elif not step_updated: # Task found but step not
            print(f"Warning: Step with ID '{step_id}' not found in task '{task_id}'.")
        return False