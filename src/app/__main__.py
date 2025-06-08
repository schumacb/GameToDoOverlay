import sys
import nltk

from PySide6.QtWidgets import QApplication

from .config_manager import ConfigManager, APP_NAME, APP_AUTHOR
from .shortcut_manager import ShortcutManager
from .task_manager import TaskManager
from .task_parser import NltkTaskParser # Import the concrete parser
from .overlay_window import OverlayWindow

def ensure_nltk_data():
    """Checks for NLTK 'punkt' tokenizer and attempts to download if missing."""
    nltk_data_verified = True
    try:
        nltk.data.find('tokenizers/punkt')
        print("NLTK 'punkt' tokenizer found.")
    except LookupError:
        print("NLTK 'punkt' tokenizer not found. Attempting to download...")
        try:
            nltk.download('punkt', quiet=True)
            nltk.data.find('tokenizers/punkt') 
            print("'punkt' tokenizer downloaded and verified.")
        except Exception as e:
            print(f"Error downloading or verifying 'punkt' tokenizer: {e}.")
            nltk_data_verified = False
    except ImportError: 
        print("NLTK library not found. Please install it: pip install nltk")
        nltk_data_verified = False 
    
    if not nltk_data_verified: 
        print("Critical NLTK setup failed. Please ensure NLTK is installed and 'punkt' data can be downloaded.")
        sys.exit(1)

if __name__ == "__main__":
    try:
        ensure_nltk_data()
    except ImportError: 
         print("NLTK library not found. Please install it: pip install nltk")
         sys.exit(1)

    app = QApplication(sys.argv)

    config_mgr = ConfigManager()
    shortcut_mgr = ShortcutManager(config_mgr)
    task_mgr = TaskManager(APP_NAME, APP_AUTHOR) 
    task_psr = NltkTaskParser() # Instantiate the parser
    
    main_overlay_window = OverlayWindow(config_mgr, shortcut_mgr, task_mgr, task_psr) # Pass parser
    main_overlay_window.show() 
    
    shortcut_mgr.start_listening()
    
    exit_code = app.exec()
    print(f"Application event loop finished. Exiting with code: {exit_code}")
    
    if shortcut_mgr: 
        shortcut_mgr.stop_listening() 
    
    sys.exit(exit_code)