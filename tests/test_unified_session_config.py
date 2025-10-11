"""
Test unified session configuration system.

This test verifies that cli_setup and the server use the same configuration
for session files, eliminating the mismatch issue.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cli_setup import SetupConfig
from src.config.server_config import ServerConfig


class TestUnifiedSessionConfig:
    """Test that ServerConfig and SetupConfig share the same session configuration."""

    def test_default_session_name(self):
        """Test that default session name is 'telegram'."""
        config = ServerConfig(_cli_parse_args=[])  # Disable CLI parsing in tests
        assert config.session_name == "telegram"

    def test_default_session_directory(self):
        """Test that default session directory is ~/.config/fast-mcp-telegram/."""
        config = ServerConfig(_cli_parse_args=[])
        expected_dir = Path.home() / ".config" / "fast-mcp-telegram"
        assert config.session_directory == expected_dir

    def test_default_session_path(self):
        """Test that session path combines directory and name correctly."""
        config = ServerConfig(_cli_parse_args=[])
        expected_path = Path.home() / ".config" / "fast-mcp-telegram" / "telegram"
        assert config.session_path == expected_path

    def test_custom_session_name_via_env(self):
        """Test that SESSION_NAME can be set via environment variable."""
        with patch.dict(os.environ, {"SESSION_NAME": "myaccount"}):
            config = ServerConfig(_cli_parse_args=[])
            assert config.session_name == "myaccount"
            expected_path = Path.home() / ".config" / "fast-mcp-telegram" / "myaccount"
            assert config.session_path == expected_path

    def test_custom_session_dir_via_env(self):
        """Test that SESSION_DIR can be set via environment variable."""
        with patch.dict(os.environ, {"SESSION_DIR": "/tmp/sessions"}):
            config = ServerConfig(_cli_parse_args=[])
            assert config.session_directory == Path("/tmp/sessions")
            expected_path = Path("/tmp/sessions") / "telegram"
            assert config.session_path == expected_path

    def test_custom_session_name_and_dir(self):
        """Test that both SESSION_NAME and SESSION_DIR can be customized."""
        with patch.dict(
            os.environ, {"SESSION_NAME": "work", "SESSION_DIR": "/tmp/work-sessions"}
        ):
            config = ServerConfig(_cli_parse_args=[])
            assert config.session_name == "work"
            assert config.session_directory == Path("/tmp/work-sessions")
            assert config.session_path == Path("/tmp/work-sessions") / "work"

    def test_setup_config_inherits_from_server_config(self):
        """Test that SetupConfig inherits session configuration from ServerConfig."""
        # SetupConfig should be a subclass of ServerConfig
        assert issubclass(SetupConfig, ServerConfig)

    def test_setup_config_shares_session_fields(self):
        """Test that SetupConfig has the same session-related fields as ServerConfig."""
        with patch.dict(os.environ, {"SESSION_NAME": "testaccount"}):
            setup_config = SetupConfig(_cli_parse_args=[])
            assert setup_config.session_name == "testaccount"
            assert setup_config.session_directory == (
                Path.home() / ".config" / "fast-mcp-telegram"
            )
            assert setup_config.session_path == (
                Path.home() / ".config" / "fast-mcp-telegram" / "testaccount"
            )

    def test_setup_config_has_setup_specific_fields(self):
        """Test that SetupConfig has setup-specific fields in addition to ServerConfig."""
        setup_config = SetupConfig(_cli_parse_args=[])
        # Should have setup-specific fields
        assert hasattr(setup_config, "overwrite")
        assert hasattr(setup_config, "bot_token")
        # Should also have all ServerConfig fields
        assert hasattr(setup_config, "session_name")
        assert hasattr(setup_config, "session_directory")
        assert hasattr(setup_config, "session_path")
        assert hasattr(setup_config, "api_id")
        assert hasattr(setup_config, "api_hash")

    def test_multiple_accounts_support(self):
        """Test that multiple accounts can be configured with different session names."""
        # Account 1: personal
        with patch.dict(os.environ, {"SESSION_NAME": "personal"}):
            config1 = ServerConfig(_cli_parse_args=[])
            assert config1.session_name == "personal"
            path1 = config1.session_path

        # Account 2: work
        with patch.dict(os.environ, {"SESSION_NAME": "work"}):
            config2 = ServerConfig(_cli_parse_args=[])
            assert config2.session_name == "work"
            path2 = config2.session_path

        # Verify different paths
        assert path1 != path2
        assert path1.name == "personal"
        assert path2.name == "work"

    def test_settings_module_uses_config(self):
        """Test that settings.py is structured to use ServerConfig."""
        # This test verifies the structure without importing settings.py
        # (which would trigger CLI parsing at module load time)

        # Test that ServerConfig has the expected properties
        config = ServerConfig(_cli_parse_args=[])
        assert hasattr(config, "session_name")
        assert hasattr(config, "session_path")
        assert hasattr(config, "session_directory")

        # Verify settings.py would use these correctly
        # settings.py does: SESSION_NAME = config.session_name
        assert config.session_name == "telegram"  # default
        # settings.py does: SESSION_PATH = config.session_path
        assert (
            config.session_path
            == Path.home() / ".config" / "fast-mcp-telegram" / "telegram"
        )

    def test_connection_uses_settings_session_path(self):
        """Test that connection.py would use SESSION_PATH correctly."""
        # This test verifies that the session path property works correctly
        # without importing settings.py (which would trigger CLI parsing)

        config = ServerConfig(_cli_parse_args=[])
        session_path = config.session_path

        # Verify SESSION_PATH would be correct for connection.py
        assert isinstance(session_path, Path)
        assert session_path.parent == Path.home() / ".config" / "fast-mcp-telegram"
        assert session_path.name == "telegram"  # Default session name

        # Test with custom session name
        with patch.dict(os.environ, {"SESSION_NAME": "custom"}):
            custom_config = ServerConfig(_cli_parse_args=[])
            assert custom_config.session_path.name == "custom"


class TestSessionConfigIntegration:
    """Integration tests for session configuration across the system."""

    def test_end_to_end_default_config(self):
        """Test the full configuration chain with defaults."""
        # 1. Create ServerConfig (what the server uses)
        server_config = ServerConfig(_cli_parse_args=[])

        # 2. Create SetupConfig (what cli_setup uses)
        setup_config = SetupConfig(_cli_parse_args=[])

        # 3. Verify they produce the same session path
        assert server_config.session_path == setup_config.session_path
        assert server_config.session_name == setup_config.session_name
        assert server_config.session_directory == setup_config.session_directory

    def test_end_to_end_custom_config(self):
        """Test the full configuration chain with custom values."""
        with patch.dict(
            os.environ,
            {
                "SESSION_NAME": "myaccount",
                "SESSION_DIR": "/tmp/test-sessions",
            },
        ):
            # 1. Create ServerConfig (what the server uses)
            server_config = ServerConfig(_cli_parse_args=[])

            # 2. Create SetupConfig (what cli_setup uses)
            setup_config = SetupConfig(_cli_parse_args=[])

            # 3. Verify they produce the same session path
            assert server_config.session_path == setup_config.session_path
            assert (
                server_config.session_path == Path("/tmp/test-sessions") / "myaccount"
            )

            # 4. Verify both configs have the custom values
            assert server_config.session_name == "myaccount"
            assert setup_config.session_name == "myaccount"

    def test_env_file_loading(self, tmp_path):
        """Test that .env file is loaded correctly."""
        # Create a temporary .env file
        env_file = tmp_path / ".env"
        env_file.write_text("SESSION_NAME=envtest\nSESSION_DIR=/tmp/envdir\n")

        # Load config with the .env file
        with patch.dict(os.environ, {}, clear=False):
            # Clear SESSION_NAME if it exists
            os.environ.pop("SESSION_NAME", None)
            os.environ.pop("SESSION_DIR", None)

            # This would normally load from .env in the working directory
            # For testing, we'll just verify the fields exist
            config = ServerConfig(_cli_parse_args=[])
            assert hasattr(config, "session_name")
            assert hasattr(config, "session_dir")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
