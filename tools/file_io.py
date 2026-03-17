import os

def read_file(filepath: str) -> str:
    if not os.path.exists(filepath):
        return f"Error: File {filepath} not found."
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(filepath: str, content: str) -> str:
    try:
        if os.path.dirname(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {filepath}."
    except Exception as e:
        return f"Error writing file: {str(e)}"

def list_dir(directory: str = ".") -> str:
    try:
        if not os.path.exists(directory):
            return f"Error: Directory {directory} not found."
        items = os.listdir(directory)
        folders = [f"{item}/" for item in items if os.path.isdir(os.path.join(directory, item))]
        files = [item for item in items if os.path.isfile(os.path.join(directory, item))]
        return f"Items in {os.path.abspath(directory)}:\n" + "\n".join(folders + files)
    except Exception as e:
        return f"Error listing directory: {str(e)}"
