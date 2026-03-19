const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  // Workspaces
  getWorkspaces: () => ipcRenderer.invoke("get-workspaces"),
  saveWorkspace: (ws) => ipcRenderer.invoke("save-workspace", ws),
  deleteWorkspace: (id) => ipcRenderer.invoke("delete-workspace", id),

  // Sync
  startSync: (wsId) => ipcRenderer.invoke("start-sync", wsId),
  stopSync: (wsId) => ipcRenderer.invoke("stop-sync", wsId),
  runOnce: (wsId) => ipcRenderer.invoke("run-once", wsId),
  getStatus: (wsId) => ipcRenderer.invoke("get-status", wsId),
  getAllStatuses: () => ipcRenderer.invoke("get-all-statuses"),

  // Auth
  runAuth: (wsId) => ipcRenderer.invoke("run-auth", wsId),
  signalAuth: (wsId) => ipcRenderer.invoke("signal-auth", wsId),

  // Logs
  getLogs: (wsId) => ipcRenderer.invoke("get-logs", wsId),

  // Startup
  setLoginAtStartup: (enabled) => ipcRenderer.invoke("set-login-at-startup", enabled),
  getLoginAtStartup: () => ipcRenderer.invoke("get-login-at-startup"),

  // Events
  onLog: (callback) => ipcRenderer.on("log", (_, data) => callback(data)),
  onSyncStatus: (callback) => ipcRenderer.on("sync-status", (_, status) => callback(status)),
});
