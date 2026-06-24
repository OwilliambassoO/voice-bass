// Captura de áudio do microfone via AudioWorklet (audio thread dedicada).
// O acúmulo de amostras e a conversão para Int16 acontecem no worklet
// (frontend/renderer/audio/worklet-processor.js), liberando a main thread.
//
// A API pública (start/stop/getAnalyser) é a mesma da versão anterior, de
// modo que app.js não muda; apenas o onChunk passa a receber Int16Array.

import { SAMPLE_RATE } from "../services/config.js";

const WORKLET_MODULE = "audio/worklet-processor.js";
const WORKLET_NAME = "capture-processor";

export class AudioCapture {
  constructor() {
    this.mediaStream = null;
    this.audioContext = null;
    this.sourceNode = null;
    this.workletNode = null;
    this.analyser = null;
    this._running = false;
    this._lastBufferSamples = null;
  }

  async start({ deviceId, getBufferSamples, onChunk, noiseSuppression = true }) {
    // A supressão de ruído do navegador (WebRTC) é opcional: quando ativa, pode
    // cortar fala baixa/curta. O controle vem da UI; aplica-se a cada start().
    const constraints = {
      audio: {
        deviceId: deviceId ? { exact: deviceId } : undefined,
        sampleRate: SAMPLE_RATE,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: noiseSuppression,
      },
    };

    this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
    this.audioContext = new AudioContext({ sampleRate: SAMPLE_RATE });
    this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);

    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 2048;
    this.sourceNode.connect(this.analyser);

    await this.audioContext.audioWorklet.addModule(WORKLET_MODULE);
    this.workletNode = new AudioWorkletNode(this.audioContext, WORKLET_NAME);

    this._running = true;
    this._lastBufferSamples = getBufferSamples();
    this.workletNode.port.postMessage({ bufferSamples: this._lastBufferSamples });

    this.workletNode.port.onmessage = (e) => {
      if (!this._running) return;
      onChunk(new Int16Array(e.data));

      // Adapta o tamanho do chunk em tempo real se o usuário trocar o buffer.
      const n = getBufferSamples();
      if (n !== this._lastBufferSamples) {
        this._lastBufferSamples = n;
        this.workletNode.port.postMessage({ bufferSamples: n });
      }
    };

    this.sourceNode.connect(this.workletNode);
    // Conecta ao destino para que process() seja invocado; a saída do worklet
    // é silenciosa (não escreve em outputs), logo não há retorno de áudio.
    this.workletNode.connect(this.audioContext.destination);
  }

  stop() {
    this._running = false;

    if (this.workletNode) {
      this.workletNode.port.onmessage = null;
      this.workletNode.disconnect();
      this.workletNode = null;
    }
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((t) => t.stop());
      this.mediaStream = null;
    }

    this.analyser = null;
    this._lastBufferSamples = null;
  }

  getAnalyser() {
    return this.analyser;
  }
}
