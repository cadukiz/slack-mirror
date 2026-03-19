const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

// Paths adapt to dev vs packaged mode
const IS_PACKAGED = app.isPackaged;

const SCRAPER_DIR = IS_PACKAGED
  ? path.join(process.resourcesPath, "scraper")
  : path.join(__dirname, "..", "slack_mirror");

// User data dir for configs/workspaces (survives updates)
const USER_DATA_DIR = path.join(app.getPath("userData"), "data");
if (!fs.existsSync(USER_DATA_DIR)) fs.mkdirSync(USER_DATA_DIR, { recursive: true });

const WORKSPACES_CONFIG_PATH = path.join(USER_DATA_DIR, "workspaces.json");
const WORKSPACES_DIR = path.join(USER_DATA_DIR, "workspaces");
if (!fs.existsSync(WORKSPACES_DIR)) fs.mkdirSync(WORKSPACES_DIR, { recursive: true });

// Python: use bundled venv in dev, system python3 + auto-setup in packaged
const PYTHON_PATH = IS_PACKAGED
  ? "python3"
  : path.join(SCRAPER_DIR, "venv", "bin", "python");

let mainWindow;
let tray = null;

// Per-workspace state: { [id]: { interval, process, logs } }
const workspaceState = {};

// Global logs
let logs = [];

// --- Window ---

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 700,
    resizable: true,
    titleBarStyle: "hiddenInset",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile("index.html");

  mainWindow.on("close", (e) => {
    // Hide instead of quit (keep running in tray)
    e.preventDefault();
    mainWindow.hide();
  });
}

function createTray() {
  // Simple tray icon
  const icon = nativeImage.createFromDataURL(
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3NjYXBlLm9yZ5vuPBoAAADjSURBVDiNpZMxDoJAEEX/LAkFhYWVHdfwCHoCj+NRvIGx0MQCG+9gZWFBAmFn/RYssCzq62Yyf/68zCQDfBlJ5z0ASafnlPQWwIr0FsCW9Kau60Hf92VJN8AijuNz3/cPcRwfq6p6T5Kkm82mBkA7qiTPQRAkAK6dc/tF36qq6pxlmV5x0g1J5xERETMfmfluxzYDcBiGYZFlmQLwnKbpPgzD26LjIh+NRvsoimoAbwBeq8cNyd00TV/SNK2XNj8AWJI+Bda6SzOAveu6PYD7OI53fy2wxv7Llsjsz/gAfAA+L1YT2bYJJwAAAABJRU5ErkJggg=="
  );
  tray = new Tray(icon);
  tray.setToolTip("Slack Mirror");

  const contextMenu = Menu.buildFromTemplate([
    { label: "Show", click: () => mainWindow.show() },
    { type: "separator" },
    { label: "Quit", click: () => { app.exit(0); } },
  ]);
  tray.setContextMenu(contextMenu);
  tray.on("click", () => mainWindow.show());
}

app.whenReady().then(async () => {
  createWindow();
  createTray();

  // First-run: set up Python venv in packaged mode
  if (IS_PACKAGED) {
    await ensurePythonSetup();
  }

  // Auto-start all enabled workspaces
  const workspaces = loadWorkspaces();
  for (const ws of workspaces) {
    if (ws.autoSync) {
      startWorkspaceSync(ws.id);
    }
  }
});

async function ensurePythonSetup() {
  const venvDir = path.join(USER_DATA_DIR, "venv");
  const venvPython = path.join(venvDir, "bin", "python");

  if (fs.existsSync(venvPython)) return; // Already set up

  addLog("system", "First run: setting up Python environment...");

  return new Promise((resolve) => {
    // Create venv
    const setup = spawn("python3", ["-m", "venv", venvDir]);
    setup.on("close", () => {
      // Install deps
      const install = spawn(venvPython, ["-m", "pip", "install", "playwright", "python-dotenv"]);
      install.on("close", () => {
        // Install browser
        const pw = spawn(venvPython, ["-m", "playwright", "install", "chromium"]);
        pw.on("close", () => {
          addLog("system", "Python environment ready!");
          resolve();
        });
      });
    });
  });
}

function getPythonPath() {
  if (!IS_PACKAGED) {
    return path.join(SCRAPER_DIR, "venv", "bin", "python");
  }
  const venvPython = path.join(USER_DATA_DIR, "venv", "bin", "python");
  return fs.existsSync(venvPython) ? venvPython : "python3";
}

app.on("before-quit", () => {
  // Stop all syncs
  for (const id of Object.keys(workspaceState)) {
    stopWorkspaceSync(id);
  }
});

// --- Workspaces Config ---

function loadWorkspaces() {
  try {
    return JSON.parse(fs.readFileSync(WORKSPACES_CONFIG_PATH, "utf-8"));
  } catch {
    // First run: empty workspace list
    saveWorkspaces([]);
    return [];
  }
}

function saveWorkspaces(workspaces) {
  fs.writeFileSync(WORKSPACES_CONFIG_PATH, JSON.stringify(workspaces, null, 2));
}

function getWorkspace(id) {
  return loadWorkspaces().find((ws) => ws.id === id);
}

ipcMain.handle("get-workspaces", () => loadWorkspaces());

ipcMain.handle("save-workspace", (_, ws) => {
  const workspaces = loadWorkspaces();
  const idx = workspaces.findIndex((w) => w.id === ws.id);
  if (idx >= 0) {
    workspaces[idx] = ws;
  } else {
    workspaces.push(ws);
  }
  saveWorkspaces(workspaces);

  // Ensure workspace directory exists
  const wsDir = path.join(WORKSPACES_DIR, ws.id);
  if (!fs.existsSync(wsDir)) fs.mkdirSync(wsDir, { recursive: true });

  return { ok: true };
});

ipcMain.handle("delete-workspace", (_, id) => {
  stopWorkspaceSync(id);
  const workspaces = loadWorkspaces().filter((w) => w.id !== id);
  saveWorkspaces(workspaces);
  return { ok: true };
});

// --- Logging ---

function addLog(workspaceId, message) {
  const ts = new Date().toLocaleTimeString();
  const entry = `[${ts}] [${workspaceId}] ${message}`;
  logs.push(entry);
  if (logs.length > 500) logs.shift();

  // Per-workspace logs
  if (!workspaceState[workspaceId]) {
    workspaceState[workspaceId] = { interval: null, process: null, logs: [] };
  }
  workspaceState[workspaceId].logs.push(entry);
  if (workspaceState[workspaceId].logs.length > 200) {
    workspaceState[workspaceId].logs.shift();
  }

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("log", { workspaceId, message: entry });
  }
}

ipcMain.handle("get-logs", (_, workspaceId) => {
  if (workspaceId && workspaceState[workspaceId]) {
    return workspaceState[workspaceId].logs;
  }
  return logs;
});

// --- Sync ---

function runWorkspaceSync(workspaceId) {
  const ws = getWorkspace(workspaceId);
  if (!ws) {
    addLog(workspaceId, "Workspace not found!");
    return;
  }

  if (workspaceState[workspaceId]?.process) {
    addLog(workspaceId, "Sync already running, skipping...");
    return;
  }

  addLog(workspaceId, "Starting sync...");

  const env = {
    ...process.env,
    WORKSPACE_ID: ws.id,
    SLACK_WORKSPACE_URL: ws.slackUrl,
    OBSIDIAN_VAULT: ws.vault,
    CHANNELS: ws.channels || "",
  };

  if (!workspaceState[workspaceId]) {
    workspaceState[workspaceId] = { interval: null, process: null, logs: [] };
  }

  env.WORKSPACE_DIR = path.join(WORKSPACES_DIR, ws.id);
  const proc = spawn(getPythonPath(), ["main.py"], { cwd: SCRAPER_DIR, env });
  workspaceState[workspaceId].process = proc;

  proc.stdout.on("data", (data) => {
    data.toString().trim().split("\n").forEach((line) => addLog(workspaceId, line));
  });

  proc.stderr.on("data", (data) => {
    data.toString().trim().split("\n").forEach((line) => addLog(workspaceId, `ERROR: ${line}`));
  });

  proc.on("close", (code) => {
    addLog(workspaceId, `Sync finished (exit code: ${code})`);
    if (workspaceState[workspaceId]) {
      workspaceState[workspaceId].process = null;
    }
    sendStatus(workspaceId);
  });
}

function startWorkspaceSync(workspaceId) {
  const ws = getWorkspace(workspaceId);
  if (!ws) return;

  if (!workspaceState[workspaceId]) {
    workspaceState[workspaceId] = { interval: null, process: null, logs: [] };
  }

  // Stop existing interval if any
  if (workspaceState[workspaceId].interval) {
    clearInterval(workspaceState[workspaceId].interval);
  }

  const intervalMin = ws.intervalMinutes || 30;

  // Run immediately
  runWorkspaceSync(workspaceId);

  // Then on interval
  workspaceState[workspaceId].interval = setInterval(
    () => runWorkspaceSync(workspaceId),
    intervalMin * 60 * 1000
  );

  addLog(workspaceId, `Auto-sync started: every ${intervalMin} minutes`);
  sendStatus(workspaceId);
}

function stopWorkspaceSync(workspaceId) {
  const state = workspaceState[workspaceId];
  if (!state) return;

  if (state.interval) {
    clearInterval(state.interval);
    state.interval = null;
  }
  if (state.process) {
    state.process.kill();
    state.process = null;
  }
  addLog(workspaceId, "Sync stopped");
  sendStatus(workspaceId);
}

function sendStatus(workspaceId) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    const state = workspaceState[workspaceId];
    mainWindow.webContents.send("sync-status", {
      workspaceId,
      running: !!state?.interval,
      syncing: !!state?.process,
    });
  }
}

ipcMain.handle("start-sync", (_, workspaceId) => {
  startWorkspaceSync(workspaceId);
  return { ok: true };
});

ipcMain.handle("stop-sync", (_, workspaceId) => {
  stopWorkspaceSync(workspaceId);
  return { ok: true };
});

ipcMain.handle("run-once", (_, workspaceId) => {
  runWorkspaceSync(workspaceId);
  return { ok: true };
});

ipcMain.handle("get-status", (_, workspaceId) => {
  const state = workspaceState[workspaceId];
  return {
    running: !!state?.interval,
    syncing: !!state?.process,
  };
});

ipcMain.handle("get-all-statuses", () => {
  const statuses = {};
  const workspaces = loadWorkspaces();
  for (const ws of workspaces) {
    const state = workspaceState[ws.id];
    statuses[ws.id] = {
      running: !!state?.interval,
      syncing: !!state?.process,
    };
  }
  return statuses;
});

// --- Auth ---

ipcMain.handle("run-auth", (_, workspaceId) => {
  const ws = getWorkspace(workspaceId);
  if (!ws) return { ok: false, error: "Workspace not found" };

  addLog(workspaceId, "Opening browser for Slack login...");

  const env = {
    ...process.env,
    WORKSPACE_ID: ws.id,
    SLACK_WORKSPACE_URL: ws.slackUrl,
    OBSIDIAN_VAULT: ws.vault,
    CHANNELS: ws.channels || "",
    DISPLAY: ":0",
  };

  env.WORKSPACE_DIR = path.join(WORKSPACES_DIR, ws.id);
  const authProcess = spawn(getPythonPath(), ["auth.py", "--signal"], {
    cwd: SCRAPER_DIR,
    env,
  });

  authProcess.stdout.on("data", (data) => addLog(workspaceId, data.toString().trim()));
  authProcess.stderr.on("data", (data) => addLog(workspaceId, `AUTH: ${data.toString().trim()}`));
  authProcess.on("close", (code) => addLog(workspaceId, `Auth finished (exit code: ${code})`));

  return { ok: true };
});

ipcMain.handle("signal-auth", (_, workspaceId) => {
  const wsDir = path.join(WORKSPACES_DIR, workspaceId);
  if (!fs.existsSync(wsDir)) fs.mkdirSync(wsDir, { recursive: true });
  fs.writeFileSync(path.join(wsDir, ".auth_done"), "done");
  // Also write to scraper root for backward compat
  fs.writeFileSync(path.join(SCRAPER_DIR, ".auth_done"), "done");
  addLog(workspaceId, "Auth signal sent — saving session...");
  return { ok: true };
});

// --- Login at startup ---

ipcMain.handle("set-login-at-startup", (_, enabled) => {
  app.setLoginItemSettings({ openAtLogin: enabled, openAsHidden: true });
  return { ok: true };
});

ipcMain.handle("get-login-at-startup", () => {
  return app.getLoginItemSettings().openAtLogin;
});
