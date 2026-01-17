#!/usr/bin/env python3
"""Test script to verify stdlib logging configuration works correctly."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from config.logging import setup_logging, logger


def test_logging():
    """Test the logging configuration."""
    print("Setting up logging...")
    setup_logging()

    print("\nTesting different log levels:")
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    print("\nTesting with extra data:")
    logger.info("Operation completed", extra={"user_id": 123, "action": "test"})

    print("\nTesting exception logging:")
    try:
        raise ValueError("Test exception")
    except Exception as e:
        logger.exception("An exception occurred")

    print("\nLogging test completed.")


if __name__ == "__main__":
    test_logging()
