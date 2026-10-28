/**
 * Unit tests for Screen Context Permissions & Capturer (Phase 14).
 */

const test = require("node:test");
const assert = require("node:assert/strict");
const { ScreenPermissionManager } = require("../screen-permissions");
const ScreenCapturer = require("../screen-capturer");

test("Screen Permissions & Capturer Suite (Phase 14)", async (t) => {
  await t.test("Permission is disabled by default", () => {
    const pm = new ScreenPermissionManager();
    assert.equal(pm.isPermissionGranted(), false, "Screen permission must be false by default");
    const status = pm.getPermissionStatus();
    assert.equal(status.granted, false);
    assert.equal(status.revocationCount, 0);
  });

  await t.test("Explicit grant sets permission to true", () => {
    const pm = new ScreenPermissionManager();
    const res = pm.grantPermission();
    assert.equal(res.granted, true);
    assert.equal(pm.isPermissionGranted(), true);
  });

  await t.test("Revoke immediately resets permission and increments count", () => {
    const pm = new ScreenPermissionManager();
    pm.grantPermission();
    assert.equal(pm.isPermissionGranted(), true);

    const revokeRes = pm.revokePermission();
    assert.equal(revokeRes.granted, false);
    assert.equal(pm.isPermissionGranted(), false);

    const status = pm.getPermissionStatus();
    assert.equal(status.granted, false);
    assert.equal(status.revocationCount, 1);
  });

  await t.test("ScreenCapturer rejects capture when permission not granted", async () => {
    const pm = new ScreenPermissionManager(); // default: false
    const capturer = new ScreenCapturer(pm);

    await assert.rejects(
      async () => {
        await capturer.getAvailableSources();
      },
      {
        message: /SCREEN_PERMISSION_DENIED/,
      }
    );

    await assert.rejects(
      async () => {
        await capturer.captureContext();
      },
      {
        message: /SCREEN_PERMISSION_DENIED/,
      }
    );
  });

  await t.test("ScreenCapturer returns structured context when permission granted (mocked)", async () => {
    const pm = new ScreenPermissionManager();
    pm.grantPermission();

    // Mock desktopCapturer behavior
    const mockSource = {
      id: "window:123:0",
      name: "VS Code — AI Companion",
      thumbnail: {
        toJPEG: (quality) => Buffer.from("fake-jpeg-binary-data"),
      },
    };

    // Inject the mock capturer API directly via the constructor
    const mockCapturerApi = {
      getSources: async () => [mockSource],
    };

    const capturer = new ScreenCapturer(pm, mockCapturerApi);

    const result = await capturer.captureContext(mockSource.id);
    assert.equal(result.user_granted_permission, true);
    assert.equal(result.window_title, "VS Code — AI Companion");
    assert.equal(result.mime_type, "image/jpeg");
    assert.equal(result.image_base64, Buffer.from("fake-jpeg-binary-data").toString("base64"));
    assert.ok(result.captured_at);
  });

  await t.test("Subsequent revocation blocks capture immediately", async () => {
    const pm = new ScreenPermissionManager();
    pm.grantPermission();
    const capturer = new ScreenCapturer(pm);

    // Revoke
    pm.revokePermission();

    await assert.rejects(
      async () => {
        await capturer.captureContext();
      },
      {
        message: /SCREEN_PERMISSION_DENIED/,
      }
    );
  });

  await t.test("ScreenCapturer throws DESKTOP_CAPTURER_UNAVAILABLE when no capturerApi and not in Electron", async () => {
    const pm = new ScreenPermissionManager();
    pm.grantPermission();

    // Construct with permission granted but no capturer API (non-Electron environment)
    const capturer = new ScreenCapturer(pm, null);
    // Force capturerApi to null to simulate non-Electron
    capturer.capturerApi = null;

    await assert.rejects(
      async () => {
        await capturer.getAvailableSources();
      },
      {
        message: /DESKTOP_CAPTURER_UNAVAILABLE/,
      }
    );

    await assert.rejects(
      async () => {
        await capturer.captureContext();
      },
      {
        message: /DESKTOP_CAPTURER_UNAVAILABLE/,
      }
    );
  });

  await t.test("getAvailableSources returns structured source list (mocked)", async () => {
    const pm = new ScreenPermissionManager();
    pm.grantPermission();

    const mockCapturerApi = {
      getSources: async () => [
        { id: "screen:0:0", name: "Main Display", thumbnail: null },
        { id: "window:456:0", name: "Terminal", thumbnail: null },
      ],
    };

    const capturer = new ScreenCapturer(pm, mockCapturerApi);
    const sources = await capturer.getAvailableSources();

    assert.equal(sources.length, 2);
    assert.equal(sources[0].id, "screen:0:0");
    assert.equal(sources[0].name, "Main Display");
    assert.equal(sources[0].isScreen, true);
    assert.equal(sources[1].id, "window:456:0");
    assert.equal(sources[1].isScreen, false);
  });

  await t.test("captureContext throws NO_SCREEN_SOURCES when source list is empty", async () => {
    const pm = new ScreenPermissionManager();
    pm.grantPermission();

    const mockCapturerApi = {
      getSources: async () => [],
    };

    const capturer = new ScreenCapturer(pm, mockCapturerApi);

    await assert.rejects(
      async () => {
        await capturer.captureContext();
      },
      {
        message: /NO_SCREEN_SOURCES/,
      }
    );
  });

  await t.test("Multiple grant/revoke cycles tracked correctly", () => {
    const pm = new ScreenPermissionManager();
    assert.equal(pm.getPermissionStatus().revocationCount, 0);

    pm.grantPermission();
    pm.revokePermission();
    assert.equal(pm.getPermissionStatus().revocationCount, 1);

    pm.grantPermission();
    pm.revokePermission();
    assert.equal(pm.getPermissionStatus().revocationCount, 2);

    // Revoking when already revoked should NOT increment
    pm.revokePermission();
    assert.equal(pm.getPermissionStatus().revocationCount, 2);
  });
});
