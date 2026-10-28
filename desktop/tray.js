/**
 * System Tray Integration for Desktop Companion (Phase 13).
 *
 * Provides a persistent Windows notification area icon with quick access
 * controls, service status checks, and minimize-to-tray handling.
 */

const { Tray, Menu, nativeImage, app } = require("electron");
const path = require("path");

class CompanionTray {
  /**
   * @param {import("electron").BrowserWindow} mainWindow
   * @param {import("./process-manager")} processManager
   */
  constructor(mainWindow, processManager) {
    this.mainWindow = mainWindow;
    this.processManager = processManager;
    this.tray = null;
    this.isQuitting = false;
  }

  /**
   * Initialize system tray icon and context menu.
   */
  init() {
    // Generate an in-memory 16x16 icon if no file icon is provided
    const icon = this._createTrayIcon();
    this.tray = new Tray(icon);
    this.tray.setToolTip("AI Software Engineering Companion");

    this._updateContextMenu({ backend: false, aiService: false, frontend: false });

    // Click on tray toggles window visibility
    this.tray.on("click", () => {
      this.toggleWindow();
    });

    // Double-click restores window
    this.tray.on("double-click", () => {
      this.showWindow();
    });

    // Periodic health check to update tray tooltip and menu
    this.healthInterval = setInterval(async () => {
      const status = await this.processManager.checkAllServices();
      this._updateContextMenu(status);
    }, 10000);
  }

  toggleWindow() {
    if (this.mainWindow.isVisible()) {
      this.mainWindow.hide();
    } else {
      this.showWindow();
    }
  }

  showWindow() {
    this.mainWindow.show();
    this.mainWindow.focus();
  }

  _updateContextMenu(status) {
    const backendLabel = status.backend ? "🟢 Backend: Online" : "🔴 Backend: Offline";
    const aiLabel = status.aiService ? "🟢 AI Service: Online" : "🔴 AI Service: Offline";

    const contextMenu = Menu.buildFromTemplate([
      {
        label: "AI Engineering Companion",
        enabled: false,
      },
      { type: "separator" },
      {
        label: "Open Companion",
        click: () => this.showWindow(),
      },
      { type: "separator" },
      {
        label: backendLabel,
        enabled: false,
      },
      {
        label: aiLabel,
        enabled: false,
      },
      { type: "separator" },
      {
        label: "Toggle DevTools",
        click: () => {
          this.mainWindow.webContents.toggleDevTools();
        },
      },
      {
        label: "Quit Companion",
        click: () => {
          this.isQuitting = true;
          app.quit();
        },
      },
    ]);

    this.tray.setContextMenu(contextMenu);
  }

  _createTrayIcon() {
    // 16x16 simple data URI icon for system tray
    // Simple cyan circle representing AI Companion
    const svgIcon = `
      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">
        <circle cx="8" cy="8" r="7" fill="#0891b2" stroke="#06b6d4" stroke-width="1.5"/>
        <text x="8" y="11" font-size="8" font-family="sans-serif" font-weight="bold" fill="#ffffff" text-anchor="middle">AI</text>
      </svg>
    `;
    return nativeImage.createFromBuffer(Buffer.from(svgIcon));
  }

  destroy() {
    if (this.healthInterval) {
      clearInterval(this.healthInterval);
    }
    if (this.tray) {
      this.tray.destroy();
    }
  }
}

module.exports = CompanionTray;
