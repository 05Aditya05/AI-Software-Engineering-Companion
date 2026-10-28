/**
 * Preload script for Desktop Companion (Phase 13).
 *
 * Securely bridges native Windows desktop capabilities to the web application
 * via contextBridge without exposing node integration.
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("companionDesktop", {
  isDesktop: true,
  platform: process.platform,

  // Notifications
  notify: (title, options) => {
    return ipcRenderer.invoke("desktop:notify", { title, ...options });
  },

  // Service health checks
  checkServices: () => {
    return ipcRenderer.invoke("desktop:check-services");
  },

  // Window control
  minimizeToTray: () => {
    ipcRenderer.send("desktop:minimize-to-tray");
  },

  // External browser navigation
  openExternal: (url) => {
    ipcRenderer.send("desktop:open-external", url);
  },

  // Deep linking listener: companion://open?project=...
  onDeepLink: (callback) => {
    const handler = (_event, url) => callback(url);
    ipcRenderer.on("desktop:deep-link", handler);
    return () => ipcRenderer.removeListener("desktop:deep-link", handler);
  },

  // Screen Context (Phase 14) — Permission-based, explicit, revocable
  screenContext: {
    getPermission: () => ipcRenderer.invoke("desktop:screen-get-permission"),
    grantPermission: () => ipcRenderer.invoke("desktop:screen-grant-permission"),
    revokePermission: () => ipcRenderer.invoke("desktop:screen-revoke-permission"),
    getSources: () => ipcRenderer.invoke("desktop:screen-get-sources"),
    captureContext: (sourceId) => ipcRenderer.invoke("desktop:screen-capture-context", sourceId),
  },
});
