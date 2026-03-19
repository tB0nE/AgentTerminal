import os
import re

SCRIPTS_DIR = "project/scripts"
label_pattern = re.compile(r"^\s*([\w.]+)(?:\s+[^:]*)?:", re.MULTILINE)

labels = set()
for root, _, files in os.walk(SCRIPTS_DIR):
    for file in files:
        if file.endswith(".narrat"):
            with open(os.path.join(root, file), 'r') as f:
                content = f.read()
                found = label_pattern.findall(content)
                print(f"File: {file} - Found {len(found)} labels: {found[:5]}")
                labels.update(found)

print(f"\nTotal unique labels found: {len(labels)}")
print(f"Check for 'initVariables': {'initVariables' in labels}")
print(f"Check for 'pre_intro': {'pre_intro' in labels}")
