# GameToDoOverlay

GameToDoOverlay is a Python application designed to display a checklist or task list as an overlay on top of games or other applications.

## Features

- (Please fill in specific features of the application)
- Task list display
- Overlay window
- Customizable appearance and shortcuts

## Requirements

- Python 3.10+
- [UV (Python Package Installer)](https://github.com/astral-sh/uv)

## Setup and Installation

1.  **Install UV:**
    If you don't have UV installed, you can install it by following the instructions on the [official UV installation guide](https://astral.sh/uv#installation). A common method is:
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
    After installation, ensure UV's installation directory (e.g., `~/.local/bin` or `~/.cargo/bin`) is in your system's PATH. You might need to restart your shell or source the appropriate environment file (e.g., `source ~/.local/bin/env` or `source ~/.cargo/env`).

2.  **Clone the repository:**
    ```bash
    git clone https://github.com/schumacb/GameToDoOverlay.git
    cd GameToDoOverlay
    ```

3.  **Install Python Development Headers (if not already present):**
    The project has dependencies that might require compilation. For example, on Debian/Ubuntu for Python 3.10:
    ```bash
    sudo apt-get update
    sudo apt-get install -y python3.10-dev
    ```
    Adjust this command based on your operating system and Python version if different.

4.  **Create a virtual environment and install dependencies:**
    ```bash
    # Create a virtual environment
    uv venv

    # Activate the virtual environment
    # On macOS/Linux:
    source .venv/bin/activate
    # On Windows (PowerShell):
    # .venv\Scripts\Activate.ps1
    # On Windows (CMD):
    # .venv\Scripts\activate.bat

    # Install the project and its dependencies
    uv pip install -e .
    ```

## Running the Application

Once the setup is complete and the virtual environment is activated, you can run the application using:

```bash
python -m task_list_overlay.__main__
```
