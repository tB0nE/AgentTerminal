import os
import pytest
from tools.file_io import read_file, write_file, list_dir

def test_file_io_operations(tmp_path):
    # Test writing a file
    test_file = tmp_path / "test.txt"
    content = "Hello, Agent!"
    result = write_file(str(test_file), content)
    assert "Successfully wrote" in result
    assert test_file.read_text() == content

    # Test reading the file
    read_content = read_file(str(test_file))
    assert read_content == content

    # Test list_dir
    dir_result = list_dir(str(tmp_path))
    assert "test.txt" in dir_result

def test_file_io_errors():
    # Test reading non-existent file
    result = read_file("non_existent_file_xyz.txt")
    assert "Error" in result

def test_web_search_mock(mocker):
    # Mock DDGS
    mock_ddgs = mocker.patch("tools.research.DDGS")
    mock_instance = mock_ddgs.return_value.__enter__.return_value
    mock_instance.text.return_value = [
        {"title": "Test Result", "href": "http://test.com", "body": "This is a test body"}
    ]

    from tools.research import web_search
    result = web_search("test query")
    assert "Test Result" in result
    assert "http://test.com" in result

def test_fetch_url_mock(mocker):
    # Mock requests.get
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.text = "<html><body><h1>Title</h1><p>Some content</p></body></html>"
    mock_get.return_value.status_code = 200

    from tools.research import fetch_url
    result = fetch_url("http://test.com")
    assert "Title" in result
    assert "Some content" in result
