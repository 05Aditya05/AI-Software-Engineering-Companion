/**
 * Electron Forge Configuration for Windows Desktop Companion (Phase 13).
 */

module.exports = {
  packagerConfig: {
    name: "AI Software Engineering Companion",
    executableName: "ai-companion",
    asar: true,
  },
  rebuildConfig: {},
  makers: [
    {
      name: "@electron-forge/maker-squirrel",
      config: {
        name: "ai_companion",
        authors: "Aaditya Sharma",
        description: "AI Software Engineering Companion Windows Desktop App",
      },
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["win32"],
    },
  ],
};
