// Bootstrap: compõe os módulos de áudio, rede e UI e conecta seus eventos.

import { AudioCapture } from "./audio/capture.js";
import { PlaybackQueue } from "./audio/playback-queue.js";
import { WebSocketClient } from "./services/websocket-client.js";
import { fetchConfig } from "./services/config-client.js";
import { Controls } from "./ui/controls.js";
import { StatusIndicator } from "./ui/status.js";
import { Visualizer } from "./ui/visualizer.js";

const controls = new Controls();
const status = new StatusIndicator(controls.statusDot, controls.statusText);
const capture = new AudioCapture();
const wsClient = new WebSocketClient();
const inputViz = new Visualizer(controls.canvasInput, "#6c5ce7");
const outputViz = new Visualizer(controls.canvasOutput, "#2ecc71");

const playback = new PlaybackQueue({
  getSinkId: () => controls.speakerValue,
  onAnalyser: (analyser) => outputViz.start(analyser),
  onIdle: () => {
    if (running) status.set("connected", "Ouvindo...");
  },
});

let running = false;

function currentConfig() {
  return {
    action: "config",
    voice: controls.voiceValue,
    rvc_model: controls.rvcModelValue || null,
    hang_ms: controls.hangMsValue,
  };
}

function sendConfig() {
  wsClient.sendJson(currentConfig());
}

// ------------------------------------------------------------------
// Start / Stop
// ------------------------------------------------------------------

async function start() {
  running = true;
  controls.setRunning(true);

  sendConfig();

  await capture.start({
    deviceId: controls.micValue,
    getBufferSamples: () => controls.getBufferSamples(),
    noiseSuppression: controls.noiseSuppressionEnabled,
    onChunk: (chunk) => {
      wsClient.sendAudio(chunk);
      status.set("active", "Processando...");
    },
  });

  const analyser = capture.getAnalyser();
  if (analyser) inputViz.start(analyser);

  status.set("connected", "Ouvindo...");
}

function stop() {
  running = false;
  capture.stop();
  inputViz.stop();
  outputViz.stop();
  playback.clear();

  controls.setRunning(false);
  status.set("connected", "Conectado");
}

// ------------------------------------------------------------------
// WebSocket callbacks
// ------------------------------------------------------------------

wsClient.onStatusChange = (state, text) => status.set(state, text);
wsClient.onTranscription = (text, partial) => controls.addTranscription(text, partial);
wsClient.onError = (message) => controls.addLog(`[ERRO] ${message}`);
wsClient.onAudio = (buf) => playback.enqueue(buf);

async function loadRvcModels() {
  try {
    const data = await fetchConfig();
    const prev = controls.rvcModelValue;
    controls.populateRvcModels(data.rvc_models || []);
    controls.setRvcModel(prev);
  } catch (err) {
    console.error("Erro ao carregar modelos RVC:", err);
  }
}

wsClient.onOpen = () => {
  controls.setToggleEnabled(true);
  // O backend está comprovadamente no ar; (re)carrega a lista de modelos RVC.
  // Isso cobre o caso em que a página abriu durante o warm-up do servidor.
  loadRvcModels();
  sendConfig();
};

wsClient.onClose = () => {
  if (running) stop();
  controls.setToggleEnabled(false);
};

// ------------------------------------------------------------------
// UI events
// ------------------------------------------------------------------

controls.onToggle(() => {
  if (running) stop();
  else start();
});

controls.onConfigChange(sendConfig);

// ------------------------------------------------------------------
// Init
// ------------------------------------------------------------------

async function init() {
  await controls.loadAudioDevices();
  await loadRvcModels(); // tentativa inicial (best-effort); reforçada no onOpen
  wsClient.connect().catch(() => {});
}

init();
