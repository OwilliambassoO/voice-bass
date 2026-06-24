const { app, BrowserWindow } = require("electron");
const path = require("path");
const { BackendManager } = require("./backend-manager");

const backend = new BackendManager();
let win = null;

function createWindow() {
  win = new BrowserWindow({
    width: 900,
    height: 650,
    minWidth: 700,
    minHeight: 500,
    title: "Voice Bass",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Abre na tela de carregamento; troca para a UI principal quando o backend
  // estiver pronto (ver startup()).
  win.loadFile(path.join(__dirname, "renderer", "loader.html"));

  if (process.argv.includes("--dev")) {
    win.webContents.openDevTools();
  }
}

// Sobe a janela, inicia o backend e, ao ficar pronto, carrega a UI principal.
async function startup() {
  createWindow();

  const send = (channel, payload) => {
    if (win && !win.isDestroyed()) win.webContents.send(channel, payload);
  };

  try {
    await backend.start({
      onStatus: (text) => send("backend:status", text),
    });
    await win.loadFile(path.join(__dirname, "renderer", "index.html"));
  } catch (err) {
    send("backend:error", String(err?.message ?? err));
  }
}

app.whenReady().then(startup);

app.on("window-all-closed", () => {
  app.quit();
});

app.on("before-quit", () => {
  backend.stop();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    startup();
  }
});
