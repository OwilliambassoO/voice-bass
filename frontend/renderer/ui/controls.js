// Controles da interface: seletores de dispositivos/voz/modelo, radio de
// buffer, botão iniciar/parar e log de transcrições. Isola o DOM do resto.

import { CHUNK_SAMPLES } from "../services/config.js";

export class Controls {
  constructor() {
    this.statusDot = document.getElementById("statusDot");
    this.statusText = document.getElementById("statusText");
    this.micSelect = document.getElementById("micSelect");
    this.speakerSelect = document.getElementById("speakerSelect");
    this.voiceSelect = document.getElementById("voiceSelect");
    this.rvcModelSelect = document.getElementById("rvcModelSelect");
    this.btnToggle = document.getElementById("btnToggle");
    this.logContainer = document.getElementById("logContainer");
    this.canvasInput = document.getElementById("canvasInput");
    this.canvasOutput = document.getElementById("canvasOutput");
    this.noiseSuppression = document.getElementById("noiseSuppression");

    // Linha de transcrição "ao vivo": atualizada a cada parcial e consolidada
    // no final do enunciado (quando uma nova começa).
    this._liveEntry = null;
    this._liveText = null;
  }

  // --- Captura ---

  get noiseSuppressionEnabled() {
    return this.noiseSuppression.checked;
  }

  // --- Chunk de áudio / pausa (hangover) ---

  getBufferSamples() {
    return CHUNK_SAMPLES;
  }

  // Tempo de silêncio (ms) que encerra o enunciado; escolhido na UI.
  get hangMsValue() {
    const checked = document.querySelector('input[name="hang"]:checked');
    return checked ? Number.parseInt(checked.value, 10) : 500;
  }

  // --- Valores selecionados ---

  get micValue() {
    return this.micSelect.value;
  }
  get speakerValue() {
    return this.speakerSelect.value;
  }
  get voiceValue() {
    return this.voiceSelect.value;
  }
  get rvcModelValue() {
    return this.rvcModelSelect.value;
  }

  // --- Botão iniciar/parar ---

  setToggleEnabled(enabled) {
    this.btnToggle.disabled = !enabled;
  }

  setRunning(running) {
    this.btnToggle.textContent = running ? "Parar" : "Iniciar";
    this.btnToggle.className = running ? "btn btn--stop" : "btn btn--start";
  }

  onToggle(cb) {
    this.btnToggle.addEventListener("click", cb);
  }

  onConfigChange(cb) {
    this.voiceSelect.addEventListener("change", cb);
    this.rvcModelSelect.addEventListener("change", cb);
    document
      .querySelectorAll('input[name="hang"]')
      .forEach((radio) => radio.addEventListener("change", cb));
  }

  // --- Log de transcrições ---

  addLog(text) {
    if (!text) return;
    const empty = this.logContainer.querySelector(".log-empty");
    if (empty) empty.remove();

    const entry = document.createElement("div");
    entry.className = "log-entry";

    const time = document.createElement("span");
    time.className = "log-time";
    time.textContent = new Date().toLocaleTimeString("pt-BR");

    entry.appendChild(time);
    entry.appendChild(document.createTextNode(text));
    this.logContainer.appendChild(entry);
    this.logContainer.scrollTop = this.logContainer.scrollHeight;
  }

  // Transcrição em tempo real: enquanto `partial` é true, atualiza a mesma
  // linha (o texto vai sendo refinado pelo Whisper); ao receber o final
  // (partial=false) consolida a linha e a próxima parcial começa uma nova.
  addTranscription(text, partial) {
    if (!text) return;
    const empty = this.logContainer.querySelector(".log-empty");
    if (empty) empty.remove();

    if (!this._liveEntry) {
      this._liveEntry = document.createElement("div");
      this._liveEntry.className = "log-entry";

      const time = document.createElement("span");
      time.className = "log-time";
      time.textContent = new Date().toLocaleTimeString("pt-BR");

      this._liveText = document.createTextNode("");
      this._liveEntry.appendChild(time);
      this._liveEntry.appendChild(this._liveText);
      this.logContainer.appendChild(this._liveEntry);
    }

    this._liveText.textContent = text;
    this.logContainer.scrollTop = this.logContainer.scrollHeight;

    if (!partial) {
      this._liveEntry = null;
      this._liveText = null;
    }
  }

  // --- Popular selects ---

  async loadAudioDevices() {
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true });
      const devices = await navigator.mediaDevices.enumerateDevices();

      const mics = devices.filter((d) => d.kind === "audioinput");
      this.micSelect.innerHTML = "";
      mics.forEach((mic) => {
        const opt = document.createElement("option");
        opt.value = mic.deviceId;
        opt.textContent = mic.label || `Microfone ${mic.deviceId.slice(0, 8)}`;
        this.micSelect.appendChild(opt);
      });

      const speakers = devices.filter((d) => d.kind === "audiooutput");
      this.speakerSelect.innerHTML = "";
      speakers.forEach((spk) => {
        const opt = document.createElement("option");
        opt.value = spk.deviceId;
        opt.textContent = spk.label || `Saída ${spk.deviceId.slice(0, 8)}`;
        this.speakerSelect.appendChild(opt);
      });
    } catch (err) {
      this.micSelect.innerHTML = '<option value="">Permissão negada</option>';
      this.speakerSelect.innerHTML = '<option value="">Indisponível</option>';
    }
  }

  populateRvcModels(models) {
    this.rvcModelSelect.innerHTML = '<option value="">Nenhum (bypass)</option>';
    models.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = m.label;
      this.rvcModelSelect.appendChild(opt);
    });
  }

  setRvcModel(value) {
    if (!value) return;
    const exists = [...this.rvcModelSelect.options].some((o) => o.value === value);
    if (exists) this.rvcModelSelect.value = value;
  }
}
