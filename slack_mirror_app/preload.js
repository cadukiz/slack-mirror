const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  // Projects
  getProjects: () => ipcRenderer.invoke("get-projects"),
  saveProject: (proj) => ipcRenderer.invoke("save-project", proj),
  deleteProject: (id) => ipcRenderer.invoke("delete-project", id),

  // Sources
  addSource: (projectId, source) => ipcRenderer.invoke("add-source", { projectId, source }),
  deleteSource: (projectId, sourceId) => ipcRenderer.invoke("delete-source", { projectId, sourceId }),
  saveSource: (projectId, source) => ipcRenderer.invoke("save-source", { projectId, source }),

  // Sync
  startSync: (projectId, sourceId) => ipcRenderer.invoke("start-sync", { projectId, sourceId }),
  stopSync: (projectId, sourceId) => ipcRenderer.invoke("stop-sync", { projectId, sourceId }),
  runOnce: (projectId, sourceId) => ipcRenderer.invoke("run-once", { projectId, sourceId }),
  getStatus: (projectId, sourceId) => ipcRenderer.invoke("get-status", { projectId, sourceId }),
  getAllStatuses: () => ipcRenderer.invoke("get-all-statuses"),

  // Auth
  runAuth: (projectId, sourceId) => ipcRenderer.invoke("run-auth", { projectId, sourceId }),
  signalAuth: (projectId, sourceId) => ipcRenderer.invoke("signal-auth", { projectId, sourceId }),

  // Logs
  getLogs: (projectId, sourceId) => ipcRenderer.invoke("get-logs", { projectId, sourceId }),

  // Startup
  setLoginAtStartup: (enabled) => ipcRenderer.invoke("set-login-at-startup", enabled),
  getLoginAtStartup: () => ipcRenderer.invoke("get-login-at-startup"),

  // Events
  onLog: (callback) => ipcRenderer.on("log", (_, data) => callback(data)),
  onSyncStatus: (callback) => ipcRenderer.on("sync-status", (_, status) => callback(status)),
});
