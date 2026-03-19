import os
import re
import yaml
import shutil

# Path to the Narrat engine config directory
CONFIG_DIR = "project/engine/src/config"
SCRIPTS_DIR = "project/scripts"
ASSETS_DIR = "project/engine/public"

# COMPREHENSIVE NARRAT KEYWORDS
NARRAT_KEYWORDS = {
    "main", "choice", "run", "jump", "set", "if", "else", "elseif", "talk", 
    "add_item", "remove_item", "has_item?", "start_quest", "complete_quest", 
    "quest_status", "var", "data", "true", "false", "undefined", "null", 
    "save", "load", "clear_dialog", "text", "log", "return", "through", "with",
    "play", "stop", "animate", "wait", "add_level", "set_stat", "add_stat",
    "set_screen", "transition_instant", "transition", "transition_black",
    "empty_layer", "create_sprite", "delete_sprite", "add", "set_button",
    "start_objective", "complete_objective", "quest_status", "show_button"
}

def sync_narrat_config() -> str:
    """
    ULTRA-STRICT Narrat config sync tool. 
    Guarantees schema validity and creates placeholder assets for missing images.
    """
    if not os.path.exists(CONFIG_DIR) or not os.path.exists(SCRIPTS_DIR):
        return "Error: Narrat engine directories not found."

    results = []
    found_ids = {"characters": set(), "screens": set(), "items": set(), "quests": set(), "buttons": set(), "skills": set()}
    all_labels = set()
    
    patterns = {
        "characters": re.compile(r"^\s*talk\s+([a-zA-Z_]\w*)\s+", re.MULTILINE),
        "screens": re.compile(r"(?:set_screen|transition_instant|set_background|transition|transition_black)\s+(\w+)"),
        "items": re.compile(r"(?:add_item|remove_item|has_item\?)\s+(\w+)"),
        "quests": re.compile(r"(?:start_quest|complete_quest|quest_status|start_objective|complete_objective|quest_completed\?|objective_started\?|objective_completed\?)\s+(\w+)"),
        "objectives": re.compile(r"(?:start_objective|complete_objective|objective_started\?|objective_completed\?)\s+(\w+)\s+(\w+)"),
        "buttons": re.compile(r"(?:set_button|show_button)\s+(\w+)"),
        "skills": re.compile(r"(?:roll|add_stat|set_stat)\s+[\$\w.]+\s+([a-zA-Z_]\w*)"),
        "audio": re.compile(r"(?:play\s+music|play\s+sound|play\s+ambient|stop\s+music|stop\s+sound)\s+(\w+)")
    }

    try:
        # 1. SCAN ALL SCRIPTS
        found_objectives = {} # quest_id -> set(objective_ids)
        found_audio = set()

        for root, _, files in os.walk(SCRIPTS_DIR):
            for file in files:
                if file.endswith(".narrat"):
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        content = f.read()
                        found_ids["characters"].update(patterns["characters"].findall(content))
                        found_ids["screens"].update(patterns["screens"].findall(content))
                        found_ids["items"].update(patterns["items"].findall(content))
                        found_ids["quests"].update(patterns["quests"].findall(content))
                        found_ids["buttons"].update(patterns["buttons"].findall(content))
                        found_ids["skills"].update(patterns["skills"].findall(content))
                        found_audio.update(patterns["audio"].findall(content))
                        
                        # Find objectives
                        for quest_id, obj_id in patterns["objectives"].findall(content):
                            if quest_id not in found_objectives:
                                found_objectives[quest_id] = set()
                            found_objectives[quest_id].add(obj_id)
        
        # Add basic characters
        found_ids["characters"].update({"player", "narrator"})
        found_ids["characters"] = found_ids["characters"] - NARRAT_KEYWORDS - {"internal", "talk"}

        # 2. SYNC YAML FILES
        sync_map = [
            ("characters", "characters.yaml", {"name": "NAME", "color": "white"}),
            ("screens", "screens.yaml", {"background": "img/backgrounds/curtain.webp"}),
            ("quests", "quests.yaml", {"title": "TITLE", "description": "DESC", "category": "default", "objectives": {"start": {"description": "Begin."}}}),
            ("items", "items.yaml", {"name": "NAME", "description": "DESC", "icon": "img/ui/default_item.png", "category": "default"}),
            ("buttons", "buttons.yaml", {"enabled": True, "text": "Button", "position": {"left": 0, "top": 0}, "action": "main"}),
            ("skills", "skills.yaml", {"name": "Skill", "description": "DESC", "startingLevel": 0, "maxLevel": 10, "icon": "img/ui/default_item.png"}),
            ("files", "audio.yaml", {"src": "audio/placeholder.mp3"})
        ]

        for key, path_suffix, defaults in sync_map:
            full_path = os.path.join(CONFIG_DIR, path_suffix)
            if not os.path.exists(full_path): continue
            
            with open(full_path, 'r') as f:
                content = f.read()
                if content.startswith("---"): content = content[3:]
                config = yaml.safe_load(content) or {}
            
            if key not in config: config[key] = {}
            modified = False
            
            items_to_sync = found_ids.get(key, found_audio if key in ["audio", "files"] else [])

            # REPAIR AND ADD
            for entry_id in list(config[key].keys()) + list(items_to_sync):
                if entry_id not in config[key]:
                    # Add new
                    if entry_id in ["main", "choice", "true", "false", "hidden", "greyed"]: continue
                    entry = defaults.copy()
                    if "name" in entry: entry["name"] = entry_id.capitalize()
                    if "title" in entry: entry["title"] = entry_id.replace("_", " ").capitalize()
                    config[key][entry_id] = entry
                    modified = True
                
                # Force repair required fields
                data = config[key][entry_id]
                if not isinstance(data, dict): continue
                for req_k, req_v in defaults.items():
                    if req_k not in data:
                        data[req_k] = req_v
                        modified = True
                
                # SPECIAL HANDLING FOR QUEST OBJECTIVES
                if key == "quests" and entry_id in found_objectives:
                    if "objectives" not in data: data["objectives"] = {}; modified = True
                    for obj_id in found_objectives[entry_id]:
                        if obj_id not in data["objectives"]:
                            data["objectives"][obj_id] = {"description": f"Objective {obj_id}"}
                            modified = True

                # BUTTON SCHEMAS
                if key == "buttons" and "position" in data:
                    if "x" in data["position"]: data["position"]["left"] = data["position"].pop("x"); modified = True
                    if "y" in data["position"]: data["position"]["top"] = data["position"].pop("y"); modified = True

            if modified:
                with open(full_path, 'w') as f:
                    f.write("---\n")
                    yaml.dump(config, f, default_flow_style=False)
                results.append(f"Hardened {key}.")

        # 3. REPAIR COMMON.YAML
        common_path = os.path.join(CONFIG_DIR, "common.yaml")
        if os.path.exists(common_path):
            with open(common_path, 'r') as f:
                content = f.read()
                if content.startswith("---"): content = content[3:]
                common = yaml.safe_load(content) or {}
            required = {"gameTitle": "AgentTerminal Game", "saveFileName": "narrat_save", "hudStats": {}, "layout": {"backgrounds": {"width": 1280, "height": 720}}}
            upd = False
            for k, v in required.items():
                if k not in common: common[k] = v; upd = True
            if upd:
                with open(common_path, 'w') as f: f.write("---\n"); yaml.dump(common, f, default_flow_style=False)
                results.append("Repaired common.yaml.")

        # 4. --- AUTO-GENERATE ASSET PLACEHOLDERS ---
        # This fixes the 'Failed to load image' errors that block engine start
        placeholders_created = 0
        curtain_src = os.path.join(ASSETS_DIR, "img/backgrounds/curtain.webp")
        if os.path.exists(curtain_src):
            with open(os.path.join(CONFIG_DIR, "screens.yaml"), 'r') as f:
                content = f.read()
                if content.startswith("---"): content = content[3:]
                screens_cfg = yaml.safe_load(content).get("screens", {})
            
            for sid, sdata in screens_cfg.items():
                bg_path = sdata.get("background")
                if bg_path:
                    abs_bg_path = os.path.join(ASSETS_DIR, bg_path)
                    if not os.path.exists(abs_bg_path):
                        os.makedirs(os.path.dirname(abs_bg_path), exist_ok=True)
                        shutil.copy2(curtain_src, abs_bg_path)
                        placeholders_created += 1
        
        if placeholders_created > 0:
            results.append(f"Generated {placeholders_created} placeholder images.")

        return "Sync Complete:\n" + "\n".join(results) if results else "Sync Check: Project is healthy."
    except Exception as e: return f"Error during sync: {str(e)}"

def validate_narrat_scripts() -> str:
    """Syntax check logic."""
    if not os.path.exists(SCRIPTS_DIR): return "Error: Scripts directory not found."
    issues = []
    global_labels = set()
    for root, _, files in os.walk(SCRIPTS_DIR):
        for file in files:
            if file.endswith(".narrat"):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        content = f.read()
                        file_labels = re.findall(r"^([\w.]+)(?:\s+[^:]*)?:", content, re.MULTILINE)
                        global_labels.update(file_labels)
                except: continue
    for root, _, files in os.walk(SCRIPTS_DIR):
        for file in files:
            if file.endswith(".narrat"):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                except: continue
                for line_num, line in enumerate(lines, 1):
                    if not line.strip() or line.strip().startswith("//"): continue
                    line_issues = []
                    stripped = line.strip()
                    leading_spaces = len(line) - len(line.lstrip())
                    if leading_spaces > 0 and leading_spaces % 4 != 0:
                        line_issues.append(f"Invalid indentation ({leading_spaces} spaces).")
                    first_word = stripped.split()[0].rstrip(":").strip('"').strip("'")
                    is_choice = stripped.startswith('"') and (stripped.endswith(":") or " if " in stripped)
                    is_dialogue = stripped.startswith('"') and stripped.endswith('"') and not is_choice
                    is_command = first_word in NARRAT_KEYWORDS or first_word in global_labels or first_word.startswith("$")
                    if not is_choice and not is_dialogue and not is_command and not stripped.endswith(":"):
                        if len(stripped.split()) > 1: line_issues.append("Unquoted dialogue.")
                    if stripped.startswith('"') and not is_choice and not stripped.endswith('"'): line_issues.append("Unclosed quotes.")
                    match = re.search(r"(?:jump|run)\s+([\w.]+)", stripped)
                    if match:
                        target = match.group(1)
                        if target not in global_labels and target not in ["main", "choice"] and target not in NARRAT_KEYWORDS:
                            line_issues.append(f"Broken label: '{target}' not found.")
                    for issue in line_issues:
                        issues.append(f"[{file}:{line_num}] {issue} -> TEXT: {stripped}")
    return "PASS: All scripts pass syntax check." if not issues else "FAIL:\n" + "\n".join(issues[:15])

# Export
TOOL_DISPATCH = {
    "sync_narrat_config": sync_narrat_config,
    "validate_narrat_scripts": validate_narrat_scripts
}
