/**
 * Screen Context Permission Manager (Phase 14).
 *
 * Enforces explicit, visible, and revocable user consent for screen context capture.
 *
 * Invariants:
 *  - Screen capture is strictly disabled by default (granted = false).
 *  - No background, continuous, or silent monitoring.
 *  - User can revoke permission at any time.
 *  - State changes are recorded with audit timestamps.
 */

class ScreenPermissionManager {
  constructor() {
    this.granted = false;
    this.lastUpdated = new Date().toISOString();
    this.revocationCount = 0;
  }

  /**
   * Check whether the user has explicitly granted screen capture permission.
   * @returns {boolean}
   */
  isPermissionGranted() {
    return this.granted === true;
  }

  /**
   * Return structured permission state.
   * @returns {{ granted: boolean, lastUpdated: string, revocationCount: number }}
   */
  getPermissionStatus() {
    return {
      granted: this.granted,
      lastUpdated: this.lastUpdated,
      revocationCount: this.revocationCount,
    };
  }

  /**
   * Explicitly grant screen capture permission.
   * Must be triggered by a direct user action in the UI.
   * @returns {{ granted: boolean, lastUpdated: string }}
   */
  grantPermission() {
    this.granted = true;
    this.lastUpdated = new Date().toISOString();
    return {
      granted: true,
      lastUpdated: this.lastUpdated,
    };
  }

  /**
   * Revoke screen capture permission immediately.
   * Subsequent capture attempts will be rejected.
   * @returns {{ granted: boolean, lastUpdated: string }}
   */
  revokePermission() {
    if (this.granted) {
      this.revocationCount += 1;
    }
    this.granted = false;
    this.lastUpdated = new Date().toISOString();
    return {
      granted: false,
      lastUpdated: this.lastUpdated,
    };
  }
}

// Export singleton instance
const screenPermissions = new ScreenPermissionManager();
module.exports = {
  ScreenPermissionManager,
  screenPermissions,
};
