import pytest
from src.engine.agent import ContextManager

def test_context_manager_basic():
    system_prompt = "You are a test agent."
    cm = ContextManager(system_prompt, max_turns=2)
    
    # Check initial prompt
    prompt = cm.get_full_prompt()
    assert len(prompt) == 1
    assert prompt[0]["role"] == "system"
    assert "No current goal set." in prompt[0]["content"]

    # Add message and check prompt
    prompt = cm.get_full_prompt("Hello!")
    assert len(prompt) == 2
    assert prompt[1]["role"] == "user"
    assert prompt[1]["content"] == "Hello!"

def test_context_manager_sliding_window():
    cm = ContextManager("System", max_turns=2)
    # Adding more than max_turns pairs (user/assistant)
    for i in range(5):
        cm.add_message("user", f"User {i}")
        cm.add_message("assistant", f"Assistant {i}")
    
    # get_full_prompt(user_goal) adds one more user message
    prompt = cm.get_full_prompt("Latest")
    # Should have: System Prompt + 2*2 history messages + 1 current message = 6
    assert len(prompt) == 6
    assert prompt[0]["role"] == "system"
    # The first history pair in the window should be "User 3" (3, 4 are the last 2 pairs)
    assert prompt[1]["content"] == "User 3"
    assert prompt[-1]["content"] == "Latest"

def test_context_manager_scratchpad():
    cm = ContextManager("System")
    cm.update_scratchpad("Test goal")
    prompt = cm.get_full_prompt()
    assert "Test goal" in prompt[0]["content"]

def test_agent_loading_mock(tmp_path, mocker):
    import json
    config = {
        "name": "test_agent",
        "role": "Testing",
        "tools": ["read_file"]
    }
    config_file = tmp_path / "test_agent.json"
    config_file.write_text(json.dumps(config))
    
    # Mock APIHandler and Orchestrator
    mocker.patch("src.engine.agent.APIHandler")
    mock_orch = mocker.Mock()
    
    from src.engine.agent import Agent
    agent = Agent(str(config_file), mock_orch)
    
    assert agent.name == "test_agent"
    assert agent.role == "Testing"
    assert "read_file" in agent.allowed_tools
