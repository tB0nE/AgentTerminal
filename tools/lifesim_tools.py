import os
import sys

# Try modular import
try:
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from am_life_sim.engine import engine as lifesim_engine
    HAS_LIFESIM_MODULE = True
except ImportError:
    HAS_LIFESIM_MODULE = False

def read_lifesim(character_name: str, target_day: str = None) -> str:
    """Reads the character's schedule and physical stats (Energy, Hunger, Social, Mood)."""
    if not HAS_LIFESIM_MODULE:
        return "Error: am_life_sim module not found."
    return lifesim_engine.read_schedule(character_name, target_day)

def create_lifesim(character_name: str) -> str:
    """Generates a new 7-day schedule for the character using the API LLM."""
    if not HAS_LIFESIM_MODULE:
        return "Error: am_life_sim module not found."
    return lifesim_engine.create_schedule(character_name)

def change_lifesim(character_name: str, day: str, start_time: str, end_time: str, new_activity: str, details: str) -> str:
    """Modifies the character's schedule."""
    if not HAS_LIFESIM_MODULE:
        return "Error: am_life_sim module not found."
    return lifesim_engine.change_schedule(character_name, day, start_time, end_time, new_activity, details)

# Export for dynamic discovery
TOOL_DISPATCH = {
    "read_lifesim": read_lifesim,
    "create_lifesim": create_lifesim,
    "change_lifesim": change_lifesim
}
