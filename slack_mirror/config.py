import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# Workspace directory: can be set externally (packaged app) or derived locally
WORKSPACE_ID = os.getenv("WORKSPACE_ID", "default")

if os.getenv("WORKSPACE_DIR"):
    WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR"))
else:
    WORKSPACE_DIR = BASE_DIR / "workspaces" / WORKSPACE_ID

# Ensure workspace directory exists
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

AUTH_STATE_PATH = WORKSPACE_DIR / "auth.json"
SYNC_STATE_PATH = WORKSPACE_DIR / "sync_state.json"

SLACK_WORKSPACE_URL = os.getenv("SLACK_WORKSPACE_URL", "https://app.slack.com")
OBSIDIAN_VAULT = os.getenv("OBSIDIAN_VAULT", "my-vault")

# Channels can be comma-separated via env var
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "general").split(",") if c.strip()]
