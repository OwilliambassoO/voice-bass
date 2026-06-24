// Cliente WebSocket: conexão, reconexão, envio de JSON/áudio e callbacks.
// Faz o parsing seguro do JSON e a conversão float32 -> PCM16 no envio.

import { BACKEND_WS } from "./config.js";

const RECONNECT_MS = 3000;

export class WebSocketClient {
  constructor() {
    this.ws = null;
    // Callbacks (definidos pelo bootstrap):
    this.onStatusChange = () => {};   // (state, text)
    this.onOpen = () => {};           // conexão pronta
    this.onClose = () => {};          // conexão caiu
    this.onTranscription = () => {};  // (text, partial)
    this.onError = () => {};          // (message)
    this.onAudio = () => {};          // (arrayBuffer)
  }

  connect() {
    return new Promise((resolve, reject) => {
      this.onStatusChange("connecting", "Conectando...");
      this.ws = new WebSocket(BACKEND_WS);
      this.ws.binaryType = "arraybuffer";

      this.ws.onopen = () => {
        this.onStatusChange("connected", "Conectado");
        this.onOpen();
        resolve();
      };

      this.ws.onmessage = (event) => {
        if (typeof event.data === "string") {
          const msg = JSON.parse(event.data);
          if (msg.type === "transcription" && msg.text) {
            this.onTranscription(msg.text, msg.partial === true);
          } else if (msg.type === "error") {
            this.onError(msg.message);
          }
        } else {
          this.onAudio(event.data);
        }
      };

      this.ws.onclose = () => {
        this.onStatusChange("disconnected", "Desconectado");
        this.onClose();
        setTimeout(() => this.connect(), RECONNECT_MS);
      };

      this.ws.onerror = (err) => {
        console.error("WebSocket error:", err);
        reject(err);
      };
    });
  }

  isOpen() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  sendJson(obj) {
    if (this.isOpen()) this.ws.send(JSON.stringify(obj));
  }

  sendAudio(pcm16) {
    if (!this.isOpen()) return;
    // pcm16 é um Int16Array já convertido no AudioWorklet (audio thread).
    this.ws.send(pcm16.buffer);
  }
}
