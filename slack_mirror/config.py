import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# Source configuration (passed by Electron or set manually)
SOURCE_TYPE = os.getenv("SOURCE_TYPE", "slack")  # "slack" or "teams"
SOURCE_ID = os.getenv("SOURCE_ID", "default")
PROJECT_ID = os.getenv("PROJECT_ID", "default")
PROJECT_NAME = os.getenv("PROJECT_NAME", "Default")
SOURCE_LABEL = os.getenv("SOURCE_LABEL", "default")
SOURCE_URL = os.getenv("SOURCE_URL", os.getenv("SLACK_WORKSPACE_URL", "https://app.slack.com"))
OBSIDIAN_VAULT = os.getenv("OBSIDIAN_VAULT", "my-vault")

# Sync toggles
SYNC_DMS = os.getenv("SYNC_DMS", "true").lower() == "true"
SYNC_GROUPS = os.getenv("SYNC_GROUPS", "true").lower() == "true"

# Channels (comma-separated)
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "general").split(",") if c.strip()]

# Source directory for state files (auth, sync_state)
if os.getenv("SOURCE_DIR"):
    SOURCE_DIR = Path(os.getenv("SOURCE_DIR"))
elif os.getenv("WORKSPACE_DIR"):
    # Backward compat for migration period
    SOURCE_DIR = Path(os.getenv("WORKSPACE_DIR"))
else:
    SOURCE_DIR = BASE_DIR / "workspaces" / SOURCE_ID

SOURCE_DIR.mkdir(parents=True, exist_ok=True)

AUTH_STATE_PATH = SOURCE_DIR / "auth.json"
SYNC_STATE_PATH = SOURCE_DIR / "sync_state.json"
