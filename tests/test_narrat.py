import os
import pytest
import yaml
from tools.narrat import sync_narrat_config, validate_narrat_scripts

@pytest.fixture
def mock_narrat_env(tmp_path, mocker):
    """Sets up a mock Narrat project structure."""
    config_dir = tmp_path / "src/config"
    scripts_dir = tmp_path / "src/scripts"
    config_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    
    mocker.patch("tools.narrat.CONFIG_DIR", str(config_dir))
    mocker.patch("tools.narrat.SCRIPTS_DIR", str(scripts_dir))
    
    return config_dir, scripts_dir

def test_cross_file_label_validation(mock_narrat_env):
    """Test that labels defined in one file are recognized by jumps in another."""
    config_dir, scripts_dir = mock_narrat_env
    
    # 1. Define a function in one file
    file_a = scripts_dir / "functions.narrat"
    file_a.write_text("my_utility_func arg1:\n    log \"Doing something\"\n")
    
    # 2. Call that function from another file
    file_b = scripts_dir / "main.narrat"
    file_b.write_text("main:\n    run my_utility_func some_val\n")
    
    # 3. Run validation - Should PASS
    result = validate_narrat_scripts()
    assert "PASS" in result

def test_sync_logic(mock_narrat_env):
    config_dir, scripts_dir = mock_narrat_env
    script_file = scripts_dir / "test.narrat"
    script_file.write_text("hacker: \"Hello\"\n  start_quest intro_quest\n")
    (config_dir / "characters.yaml").write_text("characters: {}\n")
    (config_dir / "quests.yaml").write_text("quests: {}\n")
    
    sync_narrat_config()
    
    with open(config_dir / "characters.yaml", 'r') as f:
        chars = yaml.safe_load(f)
        assert "hacker" in chars["characters"]

def test_syntax_errors(mock_narrat_env):
    config_dir, scripts_dir = mock_narrat_env
    script_file = scripts_dir / "bad.narrat"
    # Indent error (3 spaces instead of 4) and unquoted dialogue
    script_file.write_text("main:\n   hacker: Hello world without quotes\n")
    
    result = validate_narrat_scripts()
    assert "FAIL" in result
    assert "Invalid indentation" in result
    assert "Unquoted dialogue" in result
