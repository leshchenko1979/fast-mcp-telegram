import sys
import asyncio
import pytest
import os
import subprocess
import time
import requests

# Добавляем project root в sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000

@pytest.fixture(scope="session", autouse=True)
def mcp_server():
    print(f"[conftest] Starting MCP server process: python -m src.server --test-mode")
    proc = subprocess.Popen([sys.executable, "-m", "src.server", "--test-mode"])
    # Ждём, пока сервер поднимется
    for i in range(30):
        try:
            print(f"[conftest] Waiting for server... attempt {i+1}")
            requests.get(f"http://{SERVER_HOST}:{SERVER_PORT}")
            print("[conftest] Server is up!")
            break
        except Exception as e:
            print(f"[conftest] Server not up yet: {e}")
            time.sleep(1)
    else:
        proc.terminate()
        raise RuntimeError("MCP сервер не поднялся за 30 секунд")
    yield
    print("[conftest] Stopping MCP server process...")
    proc.terminate()
    proc.wait()
    print("[conftest] MCP server process stopped.")
