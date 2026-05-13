"""Tests for embed_utils module."""

from utils.embed_utils import validate_embed_data


def test_validate_embed_data_valid():
    """Valid embed data passes validation."""
    data = {"title": "Test", "description": "Desc"}
    is_valid, error = validate_embed_data(data)
    assert is_valid is True
    assert error is None
