import os
import shutil

# Define read-only directories
PROTECTED_PREFIXES = [
    os.path.abspath("project/reference/"),
]

def read_file(path: str) -> str:
    """Read local .json, .txt, .gd, and .narrat files."""
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

def copy_file(src: str, dst: str) -> str:
    """Copy a file from src to dst."""
    try:
        abs_dst = os.path.abspath(dst)
        for protected in PROTECTED_PREFIXES:
            if abs_dst.startswith(protected):
                return f"Error: Access Denied. Cannot copy to read-only directory {dst}."
        if os.path.dirname(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        return f"Successfully copied {src} to {dst}."
    except Exception as e:
        return f"Error copying file: {str(e)}"

def update_engine_registry() -> str:
    """
    Scans project/engine/src/scripts for .narrat files and 
    automatically updates index.ts to import and export them.
    """
    scripts_dir = "project/engine/src/scripts"
    index_path = os.path.join(scripts_dir, "index.ts")
    
    if not os.path.exists(scripts_dir):
        return f"Error: Scripts directory {scripts_dir} not found."
    
    try:
        files = [f for f in os.listdir(scripts_dir) if f.endswith(".narrat")]
        if not files:
            return "No .narrat files found to register."
        
        imports = []
        names = []
        
        for f in sorted(files):
            name = f.replace(".narrat", "").replace("-", "_").replace(".", "_")
            imports.append(f"import {name} from './{f}';")
            names.append(name)
            
        content = "\n".join(imports) + "\n\nexport default [\n  " + ",\n  ".join(names) + "\n];\n"
        
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return f"Successfully updated engine registry with {len(names)} scripts."
    except Exception as e:
        return f"Error updating engine registry: {str(e)}"

# Export tools
TOOL_DISPATCH = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "copy_file": copy_file,
    "update_engine_registry": update_engine_registry
}
