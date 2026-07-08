const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("voiceBass", {
  platform: process.platform,

  // Eventos da inicialização, consumidos pela tela de carregamento (loader.html).
  onBackendStatus: (cb) =>
    ipcRenderer.on("backend:status", (_event, text) => cb(text)),
  onBackendError: (cb) =>
    ipcRenderer.on("backend:error", (_event, message) => cb(message)),

  // Abre (criando se necessário) a pasta onde o usuário coloca os modelos RVC.
  openVoicesFolder: () => ipcRenderer.invoke("voices:open"),
});
