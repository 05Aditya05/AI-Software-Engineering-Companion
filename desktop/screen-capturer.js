/**
 * Screen Context Capturer (Phase 14).
 *
 * Implements safe, on-demand screen and window capture using Electron's desktopCapturer API.
 *
 * Safety & Privacy Invariants:
 *  - Enforces explicit user permission via ScreenPermissionManager before any capture.
 *  - Disallows background continuous recording; all captures are single on-demand frames.
 *  - Downscales captures to low-resolution JPEG to minimize payload and memory footprint.
 *  - Data is ephemeral: in-memory buffers are released after return.
 */

const { desktopCapturer } = require("electron");
const { screenPermissions } = require("./screen-permissions");

class ScreenCapturer {
  constructor(permissionManager = screenPermissions, capturerApi = null) {
    this.permissions = permissionManager;
    // In Electron main process, require("electron").desktopCapturer is available.
    // In test or non-Electron environments, an injected capturerApi can be provided.
    let electronCapturer = null;
    try {
      const electron = require("electron");
      electronCapturer = electron && electron.desktopCapturer ? electron.desktopCapturer : null;
    } catch {
      electronCapturer = null;
    }
    this.capturerApi = capturerApi || electronCapturer;
  }

  /**
   * List available screen and window sources without capturing full content.
   * Throws if permission has not been granted.
   * @returns {Promise<Array<{ id: string, name: string, isScreen: boolean }>>}
   */
  async getAvailableSources() {
    if (!this.permissions.isPermissionGranted()) {
      throw new Error(
        "SCREEN_PERMISSION_DENIED: Screen capture permission has not been granted by user."
      );
    }

    if (!this.capturerApi || typeof this.capturerApi.getSources !== "function") {
      throw new Error("DESKTOP_CAPTURER_UNAVAILABLE: Desktop capturer is not available in this environment.");
    }

    const sources = await this.capturerApi.getSources({
      types: ["screen", "window"],
      thumbnailSize: { width: 160, height: 90 }, // Minimal thumbnail for source selection list
      fetchWindowIcons: false,
    });

    return sources.map((source) => ({
      id: source.id,
      name: source.name || "Untitled Window",
      isScreen: source.id.startsWith("screen:"),
    }));
  }

  /**
   * Capture a single on-demand screen frame for the selected source ID.
   * Throws if permission has not been granted.
   *
   * @param {string} [sourceId] - Target source identifier (defaults to primary screen if omitted)
   * @returns {Promise<{ image_base64: string, mime_type: string, window_title: string, user_granted_permission: boolean, captured_at: string }>}
   */
  async captureContext(sourceId) {
    if (!this.permissions.isPermissionGranted()) {
      throw new Error(
        "SCREEN_PERMISSION_DENIED: Cannot capture screen context without explicit user consent."
      );
    }

    if (!this.capturerApi || typeof this.capturerApi.getSources !== "function") {
      throw new Error("DESKTOP_CAPTURER_UNAVAILABLE: Desktop capturer is not available in this environment.");
    }

    const sources = await this.capturerApi.getSources({
      types: ["screen", "window"],
      thumbnailSize: { width: 1280, height: 720 }, // Standard 720p cap for prompt payload
      fetchWindowIcons: false,
    });

    if (sources.length === 0) {
      throw new Error("NO_SCREEN_SOURCES: No active screens or windows available for capture.");
    }

    let targetSource = sources[0];
    if (sourceId) {
      const match = sources.find((s) => s.id === sourceId);
      if (match) targetSource = match;
    }

    // Convert thumbnail to compressed JPEG buffer (quality 75)
    const jpegBuffer = targetSource.thumbnail.toJPEG(75);
    const imageBase64 = jpegBuffer.toString("base64");

    return {
      image_base64: imageBase64,
      mime_type: "image/jpeg",
      window_title: targetSource.name || "Active Workspace",
      display_name: targetSource.id,
      user_granted_permission: true,
      captured_at: new Date().toISOString(),
    };
  }
}

module.exports = ScreenCapturer;
