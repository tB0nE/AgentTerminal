import os
import sys
import uuid
from pathlib import Path

# Try modular import
try:
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from am_voice.engine import get_engine
    HAS_TTS_MODULE = True
except ImportError:
    HAS_TTS_MODULE = False

def generate_voice(text: str, character: str = "Anya", voice_preset: str = None) -> str:
    """
    Synthesizes speech for the given text and saves it to the character's folder.
    Uses MD5 hashing for simple file-based caching.
    """
    if not HAS_TTS_MODULE:
        return "Error: am_voice module not found."

    import hashlib
    # Clean text for hashing (same as engine does internally)
    clean_text = text.strip()
    text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    filename = f"voice_{text_hash[:12]}.wav"

    try:
        from am_character_api.engine import manager as char_manager
        char_path = char_manager.get_character_path(character)
        audio_dir = char_path / "images"
        audio_dir.mkdir(exist_ok=True)
        
        file_path = audio_dir / filename
        audio_url = f"/character-images/{character}/images/{filename}"

        # --- CACHE CHECK ---
        if file_path.exists():
            print(f"DEBUG: [TTS Tool] Cache HIT for {filename}")
            return f"Success! Voice retrieved from cache. Audio URL: {audio_url}"

        # --- GENERATION ---
        print(f"DEBUG: [TTS Tool] Cache MISS. Generating new audio...")
        engine = get_engine()
        wav_data = engine.synthesize_wav(text, voice_preset)
        
        if not wav_data:
            return "Error: No audio data generated."

        with open(file_path, "wb") as f:
            f.write(wav_data)
            
        return f"Success! Voice generated. Audio URL: {audio_url}"
        
    except Exception as e:
        return f"Error during TTS synthesis: {str(e)}"

# Export
TOOL_DISPATCH = {
    "generate_voice": generate_voice
}
