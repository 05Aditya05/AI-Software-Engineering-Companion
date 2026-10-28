/**
 * Main Process for Windows Desktop Companion (Phase 13).
 *
 * Coordinates:
 *  - Native Windows BrowserWindow with dark theme
 *  - System Tray integration and minimize-to-tray
 *  - Deep link protocol handling (`companion://open?project=...`)
 *  - Native Windows toast notifications
 *  - Companion service health checks
 */

const { app, BrowserWindow, ipcMain, Notification, shell } = require("electron");
const path = require("path");
const ProcessManager = require("./process-manager");
const CompanionTray = require("./tray");
const { screenPermissions } = require("./screen-permissions");
const ScreenCapturer = require("./screen-capturer");

// Handle squirrel startup events on Windows installer
if (require("electron-squirrel-startup")) {
  app.quit();
}

let mainWindow = null;
let companionTray = null;
const processManager = new ProcessManager();
const screenCapturer = new ScreenCapturer(screenPermissions);

// Enforce single instance lock
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", (_event, commandLine) => {
    // Someone tried to run a second instance, focus our window
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      if (!mainWindow.isVisible()) mainWindow.show();
      mainWindow.focus();

      // Check for deep link arguments
      const deepLink = commandLine.find((arg) => arg.startsWith("companion://"));
      if (deepLink) {
        mainWindow.webContents.send("desktop:deep-link", deepLink);
      }
    }
  });
}

// Register custom protocol client for deep linking
if (!app.isDefaultProtocolClient("companion")) {
  app.setAsDefaultProtocolClient("companion");
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 1024,
    minHeight: 700,
    backgroundColor: "#09090b",
    title: "AI Software Engineering Companion",
    autoHideMenuBar: true,
    show: false, // Show once ready-to-show
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  // Graceful show on ready
  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  // Intercept close to minimize to tray instead of quitting
  mainWindow.on("close", (event) => {
    if (!companionTray || !companionTray.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  // Initialize System Tray
  companionTray = new CompanionTray(mainWindow, processManager);
  companionTray.init();

  // Try loading Next.js frontend; if offline, load fallback page
  const frontendUrl = "http://localhost:3000";
  mainWindow.loadURL(frontendUrl).catch(() => {
    mainWindow.loadFile(path.join(__dirname, "fallback.html"));
  });

  // Safe external navigation
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });
}

// ---------------------------------------------------------------------------
// IPC Handlers
// ---------------------------------------------------------------------------

ipcMain.handle("desktop:notify", (_event, { title, body }) => {
  if (Notification.isSupported()) {
    new Notification({
      title: title || "AI Companion Notification",
      body: body || "",
      silent: false,
    }).show();
    return true;
  }
  return false;
});

ipcMain.handle("desktop:check-services", async () => {
  return await processManager.checkAllServices();
});

ipcMain.on("desktop:minimize-to-tray", () => {
  if (mainWindow) {
    mainWindow.hide();
  }
});

ipcMain.on("desktop:open-external", (_event, url) => {
  if (url && (url.startsWith("http://") || url.startsWith("https://"))) {
    shell.openExternal(url);
  }
});

// Phase 14: Screen Context IPC Handlers (Explicit, Visible, Revocable)
ipcMain.handle("desktop:screen-get-permission", () => {
  return screenPermissions.getPermissionStatus();
});

ipcMain.handle("desktop:screen-grant-permission", () => {
  return screenPermissions.grantPermission();
});

ipcMain.handle("desktop:screen-revoke-permission", () => {
  return screenPermissions.revokePermission();
});

ipcMain.handle("desktop:screen-get-sources", async () => {
  return await screenCapturer.getAvailableSources();
});

ipcMain.handle("desktop:screen-capture-context", async (_event, sourceId) => {
  return await screenCapturer.captureContext(sourceId);
});

// ---------------------------------------------------------------------------
// App Lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("before-quit", () => {
  if (companionTray) {
    companionTray.isQuitting = true;
    companionTray.destroy();
  }
  processManager.stopAll();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    // On Windows, background tray keeps running unless quit from tray
    if (!companionTray) {
      app.quit();
    }
  }
});
