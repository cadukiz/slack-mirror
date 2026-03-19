const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } = require("electron");
const path = require("path");
const { spawn } = require("child_process");
const fs = require("fs");

// Paths adapt to dev vs packaged mode
const IS_PACKAGED = app.isPackaged;

const SCRAPER_DIR = IS_PACKAGED
  ? path.join(process.resourcesPath, "scraper")
  : path.join(__dirname, "..", "slack_mirror");

// User data dir for configs (survives updates)
const USER_DATA_DIR = path.join(app.getPath("userData"), "data");
if (!fs.existsSync(USER_DATA_DIR)) fs.mkdirSync(USER_DATA_DIR, { recursive: true });

const PROJECTS_CONFIG_PATH = path.join(USER_DATA_DIR, "projects.json");
const PROJECTS_DIR = path.join(USER_DATA_DIR, "projects");
if (!fs.existsSync(PROJECTS_DIR)) fs.mkdirSync(PROJECTS_DIR, { recursive: true });

// Legacy paths for migration
const LEGACY_WORKSPACES_CONFIG = path.join(USER_DATA_DIR, "workspaces.json");
const LEGACY_WORKSPACES_DIR = path.join(USER_DATA_DIR, "workspaces");

let mainWindow;
let tray = null;

// Per-source state: { "projectId::sourceId": { interval, process, logs } }
const sourceState = {};

// Global logs
let logs = [];

// --- Window ---

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 960,
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
    e.preventDefault();
    mainWindow.hide();
  });
}

function createTray() {
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
  // Run migration before anything else
  migrateWorkspacesToProjects();

  createWindow();
  createTray();

  if (IS_PACKAGED) {
    await ensurePythonSetup();
  }

  // Auto-start all enabled sources
  const projects = loadProjects();
  for (const proj of projects) {
    for (const src of proj.sources || []) {
      if (src.autoSync) {
        startSourceSync(proj.id, src.id);
      }
    }
  }
});

async function ensurePythonSetup() {
  const venvDir = path.join(USER_DATA_DIR, "venv");
  const venvPython = path.join(venvDir, "bin", "python");

  if (fs.existsSync(venvPython)) return;

  addLog("system", "system", "First run: setting up Python environment...");

  return new Promise((resolve) => {
    const setup = spawn("python3", ["-m", "venv", venvDir]);
    setup.on("close", () => {
      const install = spawn(venvPython, ["-m", "pip", "install", "playwright", "python-dotenv"]);
      install.on("close", () => {
        const pw = spawn(venvPython, ["-m", "playwright", "install", "chromium"]);
        pw.on("close", () => {
          addLog("system", "system", "Python environment ready!");
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
  for (const key of Object.keys(sourceState)) {
    const [projectId, sourceId] = key.split("::");
    stopSourceSync(projectId, sourceId);
  }
});

// --- Migration ---

function migrateWorkspacesToProjects() {
  if (!fs.existsSync(LEGACY_WORKSPACES_CONFIG)) return;
  if (fs.existsSync(PROJECTS_CONFIG_PATH)) return; // Already migrated

  try {
    const workspaces = JSON.parse(fs.readFileSync(LEGACY_WORKSPACES_CONFIG, "utf-8"));
    const projects = [];

    for (const ws of workspaces) {
      const sourceId = "src-" + Date.now() + "-" + Math.random().toString(36).slice(2, 6);
      const project = {
        id: ws.id,
        name: ws.name,
        sources: [{
          id: sourceId,
          type: "slack",
          label: extractDomain(ws.slackUrl || ws.url || ""),
          url: ws.slackUrl || ws.url || "",
          vault: ws.vault || "",
          channels: ws.channels || "",
          intervalMinutes: ws.intervalMinutes || 30,
          autoSync: ws.autoSync || false,
          syncDMs: ws.syncDMs !== false,
          syncGroups: ws.syncGroups !== false,
        }],
      };
      projects.push(project);

      // Copy workspace data to new project/source directory
      const oldDir = path.join(LEGACY_WORKSPACES_DIR, ws.id);
      const newDir = path.join(PROJECTS_DIR, ws.id, sourceId);
      if (fs.existsSync(oldDir)) {
        fs.mkdirSync(newDir, { recursive: true });
        for (const file of fs.readdirSync(oldDir)) {
          fs.copyFileSync(path.join(oldDir, file), path.join(newDir, file));
        }
      }
    }

    fs.writeFileSync(PROJECTS_CONFIG_PATH, JSON.stringify(projects, null, 2));
    fs.renameSync(LEGACY_WORKSPACES_CONFIG, LEGACY_WORKSPACES_CONFIG + ".backup");

    console.log(`Migrated ${workspaces.length} workspaces to projects`);
  } catch (err) {
    console.error("Migration failed:", err);
  }
}

function extractDomain(url) {
  try {
    const hostname = new URL(url).hostname;
    // "acme.slack.com" -> "acme", "teams.microsoft.com" -> "teams"
    return hostname.split(".")[0];
  } catch {
    return "default";
  }
}

// --- Projects Config ---

function loadProjects() {
  try {
    return JSON.parse(fs.readFileSync(PROJECTS_CONFIG_PATH, "utf-8"));
  } catch {
    saveProjects([]);
    return [];
  }
}

function saveProjects(projects) {
  fs.writeFileSync(PROJECTS_CONFIG_PATH, JSON.stringify(projects, null, 2));
}

function getProject(projectId) {
  return loadProjects().find((p) => p.id === projectId);
}

function getSource(projectId, sourceId) {
  const proj = getProject(projectId);
  return proj?.sources?.find((s) => s.id === sourceId);
}

ipcMain.handle("get-projects", () => loadProjects());

ipcMain.handle("save-project", (_, project) => {
  const projects = loadProjects();
  const idx = projects.findIndex((p) => p.id === project.id);
  if (idx >= 0) {
    projects[idx] = project;
  } else {
    projects.push(project);
  }
  saveProjects(projects);
  return { ok: true };
});

ipcMain.handle("delete-project", (_, projectId) => {
  // Stop all sources in this project
  const proj = getProject(projectId);
  if (proj) {
    for (const src of proj.sources || []) {
      stopSourceSync(projectId, src.id);
    }
  }
  const projects = loadProjects().filter((p) => p.id !== projectId);
  saveProjects(projects);
  return { ok: true };
});

ipcMain.handle("add-source", (_, { projectId, source }) => {
  const projects = loadProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (!proj) return { ok: false, error: "Project not found" };

  if (!proj.sources) proj.sources = [];

  // Enforce unique labels within a project
  const duplicate = proj.sources.find((s) => s.label === source.label);
  if (duplicate) return { ok: false, error: `Source label "${source.label}" already exists in this project` };

  proj.sources.push(source);
  saveProjects(projects);

  // Create source directory
  const srcDir = path.join(PROJECTS_DIR, projectId, source.id);
  if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });

  return { ok: true };
});

ipcMain.handle("delete-source", (_, { projectId, sourceId }) => {
  stopSourceSync(projectId, sourceId);
  const projects = loadProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (proj) {
    proj.sources = (proj.sources || []).filter((s) => s.id !== sourceId);
    saveProjects(projects);
  }
  return { ok: true };
});

ipcMain.handle("save-source", (_, { projectId, source }) => {
  const projects = loadProjects();
  const proj = projects.find((p) => p.id === projectId);
  if (!proj) return { ok: false, error: "Project not found" };

  // Enforce unique labels within a project (excluding self)
  const duplicate = (proj.sources || []).find((s) => s.label === source.label && s.id !== source.id);
  if (duplicate) return { ok: false, error: `Source label "${source.label}" already exists in this project` };

  const idx = (proj.sources || []).findIndex((s) => s.id === source.id);
  if (idx >= 0) {
    proj.sources[idx] = source;
  }
  saveProjects(projects);

  const srcDir = path.join(PROJECTS_DIR, projectId, source.id);
  if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });

  return { ok: true };
});

// --- Logging ---

function sourceKey(projectId, sourceId) {
  return `${projectId}::${sourceId}`;
}

function addLog(projectId, sourceId, message) {
  const key = sourceKey(projectId, sourceId);
  const ts = new Date().toLocaleTimeString();
  const entry = `[${ts}] [${key}] ${message}`;
  logs.push(entry);
  if (logs.length > 500) logs.shift();

  if (!sourceState[key]) {
    sourceState[key] = { interval: null, process: null, logs: [] };
  }
  sourceState[key].logs.push(entry);
  if (sourceState[key].logs.length > 200) {
    sourceState[key].logs.shift();
  }

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("log", { projectId, sourceId, message: entry });
  }
}

ipcMain.handle("get-logs", (_, { projectId, sourceId }) => {
  const key = sourceKey(projectId, sourceId);
  if (sourceState[key]) {
    return sourceState[key].logs;
  }
  return [];
});

// --- Sync ---

function runSourceSync(projectId, sourceId) {
  const src = getSource(projectId, sourceId);
  const proj = getProject(projectId);
  if (!src || !proj) {
    addLog(projectId, sourceId, "Source or project not found!");
    return;
  }

  const key = sourceKey(projectId, sourceId);
  if (sourceState[key]?.process) {
    addLog(projectId, sourceId, "Sync already running, skipping...");
    return;
  }

  addLog(projectId, sourceId, "Starting sync...");

  const srcDir = path.join(PROJECTS_DIR, projectId, sourceId);
  if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });

  const env = {
    ...process.env,
    SOURCE_TYPE: src.type || "slack",
    SOURCE_ID: sourceId,
    PROJECT_ID: projectId,
    PROJECT_NAME: proj.name,
    SOURCE_LABEL: src.label || "default",
    SOURCE_URL: src.url || "",
    OBSIDIAN_VAULT: src.vault || "",
    CHANNELS: src.channels || "",
    SYNC_DMS: String(src.syncDMs !== false),
    SYNC_GROUPS: String(src.syncGroups !== false),
    SOURCE_DIR: srcDir,
    SOURCES_JSON: JSON.stringify(proj.sources || []),
  };

  if (!sourceState[key]) {
    sourceState[key] = { interval: null, process: null, logs: [] };
  }

  const proc = spawn(getPythonPath(), ["main.py"], { cwd: SCRAPER_DIR, env });
  sourceState[key].process = proc;

  proc.stdout.on("data", (data) => {
    data.toString().trim().split("\n").forEach((line) => addLog(projectId, sourceId, line));
  });

  proc.stderr.on("data", (data) => {
    data.toString().trim().split("\n").forEach((line) => addLog(projectId, sourceId, `ERROR: ${line}`));
  });

  proc.on("close", (code) => {
    addLog(projectId, sourceId, `Sync finished (exit code: ${code})`);
    if (sourceState[key]) {
      sourceState[key].process = null;
    }
    sendStatus(projectId, sourceId);
  });
}

function startSourceSync(projectId, sourceId) {
  const src = getSource(projectId, sourceId);
  if (!src) return;

  const key = sourceKey(projectId, sourceId);
  if (!sourceState[key]) {
    sourceState[key] = { interval: null, process: null, logs: [] };
  }

  if (sourceState[key].interval) {
    clearInterval(sourceState[key].interval);
  }

  const intervalMin = src.intervalMinutes || 30;

  runSourceSync(projectId, sourceId);

  sourceState[key].interval = setInterval(
    () => runSourceSync(projectId, sourceId),
    intervalMin * 60 * 1000
  );

  addLog(projectId, sourceId, `Auto-sync started: every ${intervalMin} minutes`);
  sendStatus(projectId, sourceId);
}

function stopSourceSync(projectId, sourceId) {
  const key = sourceKey(projectId, sourceId);
  const state = sourceState[key];
  if (!state) return;

  if (state.interval) {
    clearInterval(state.interval);
    state.interval = null;
  }
  if (state.process) {
    state.process.kill();
    state.process = null;
  }
  addLog(projectId, sourceId, "Sync stopped");
  sendStatus(projectId, sourceId);
}

function sendStatus(projectId, sourceId) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    const key = sourceKey(projectId, sourceId);
    const state = sourceState[key];
    mainWindow.webContents.send("sync-status", {
      projectId,
      sourceId,
      running: !!state?.interval,
      syncing: !!state?.process,
    });
  }
}

ipcMain.handle("start-sync", (_, { projectId, sourceId }) => {
  startSourceSync(projectId, sourceId);
  return { ok: true };
});

ipcMain.handle("stop-sync", (_, { projectId, sourceId }) => {
  stopSourceSync(projectId, sourceId);
  return { ok: true };
});

ipcMain.handle("run-once", (_, { projectId, sourceId }) => {
  runSourceSync(projectId, sourceId);
  return { ok: true };
});

ipcMain.handle("get-status", (_, { projectId, sourceId }) => {
  const key = sourceKey(projectId, sourceId);
  const state = sourceState[key];
  return {
    running: !!state?.interval,
    syncing: !!state?.process,
  };
});

ipcMain.handle("get-all-statuses", () => {
  const statuses = {};
  const projects = loadProjects();
  for (const proj of projects) {
    for (const src of proj.sources || []) {
      const key = sourceKey(proj.id, src.id);
      const state = sourceState[key];
      statuses[key] = {
        projectId: proj.id,
        sourceId: src.id,
        running: !!state?.interval,
        syncing: !!state?.process,
      };
    }
  }
  return statuses;
});

// --- Auth ---

ipcMain.handle("run-auth", (_, { projectId, sourceId }) => {
  const src = getSource(projectId, sourceId);
  if (!src) return { ok: false, error: "Source not found" };

  addLog(projectId, sourceId, `Opening browser for ${src.type} login...`);

  const srcDir = path.join(PROJECTS_DIR, projectId, sourceId);
  if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });

  const env = {
    ...process.env,
    SOURCE_TYPE: src.type || "slack",
    SOURCE_ID: sourceId,
    PROJECT_ID: projectId,
    SOURCE_URL: src.url || "",
    OBSIDIAN_VAULT: src.vault || "",
    CHANNELS: src.channels || "",
    SOURCE_DIR: srcDir,
    DISPLAY: ":0",
  };

  const authProcess = spawn(getPythonPath(), ["auth.py", "--signal"], {
    cwd: SCRAPER_DIR,
    env,
  });

  authProcess.stdout.on("data", (data) => addLog(projectId, sourceId, data.toString().trim()));
  authProcess.stderr.on("data", (data) => addLog(projectId, sourceId, `AUTH: ${data.toString().trim()}`));
  authProcess.on("close", (code) => addLog(projectId, sourceId, `Auth finished (exit code: ${code})`));

  return { ok: true };
});

ipcMain.handle("signal-auth", (_, { projectId, sourceId }) => {
  const srcDir = path.join(PROJECTS_DIR, projectId, sourceId);
  if (!fs.existsSync(srcDir)) fs.mkdirSync(srcDir, { recursive: true });
  fs.writeFileSync(path.join(srcDir, ".auth_done"), "done");
  // Also write to scraper root for backward compat
  fs.writeFileSync(path.join(SCRAPER_DIR, ".auth_done"), "done");
  addLog(projectId, sourceId, "Auth signal sent — saving session...");
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
