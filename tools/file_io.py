import os

# Define read-only directories to prevent agents from modifying source material
PROTECTED_PREFIXES = [
    os.path.abspath("project/reference/"),
]

def read_file(path: str) -> str:
    """Read local .json, .txt, and .gd files."""
    if not os.path.exists(path):
        return f"Error: File {path} not found."
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(path: str, content: str) -> str:
    """Overwrite or create new files. Blocks access to protected directories."""
    try:
        abs_target = os.path.abspath(path)
        
        # Security: Prevent overwriting reference/lore files
        for protected in PROTECTED_PREFIXES:
            if abs_target.startswith(protected):
                return f"Error: Access Denied. {path} is in a read-only directory."

        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}."
    except Exception as e:
        return f"Error writing file: {str(e)}"

def list_dir(directory: str = ".") -> str:
    """List items in a directory."""
    try:
        if not os.path.exists(directory):
            return f"Error: Directory {directory} not found."
        items = os.listdir(directory)
        folders = [f"{item}/" for item in items if os.path.isdir(os.path.join(directory, item))]
        files = [item for item in items if os.path.isfile(os.path.join(directory, item))]
        return f"Items in {os.path.abspath(directory)}:\n" + "\n".join(folders + files)
    except Exception as e:
        return f"Error listing directory: {str(e)}"

# Export tools for dynamic discovery by the UI and Agent
TOOL_DISPATCH = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir
}
