import sys
import os

# Add the current directory to sys.path to find 'tools'
sys.path.append(os.getcwd())

from tools.narrat import sync_narrat_config

result = sync_narrat_config()
print(result)
