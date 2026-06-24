// Fila de reprodução: enfileira WAVs recebidos e os toca em sequência,
// sem gaps, no dispositivo de saída selecionado (setSinkId defensivo).

export class PlaybackQueue {
  constructor({ getSinkId, onAnalyser, onIdle } = {}) {
    this.queue = [];
    this.isPlaying = false;
    this.ctx = null;
    this._getSinkId = getSinkId || (() => "");
    this._onAnalyser = onAnalyser || (() => {});
    this._onIdle = onIdle || (() => {});
  }

  enqueue(wavArrayBuffer) {
    this.queue.push(wavArrayBuffer);
    if (!this.isPlaying) this._playNext();
  }

  clear() {
    this.queue = [];
    this.isPlaying = false;
  }

  async _playNext() {
    if (this.queue.length === 0) {
      this.isPlaying = false;
      this._onIdle();
      return;
    }

    this.isPlaying = true;
    const buf = this.queue.shift();

    const selectedSinkId = this._getSinkId() || "";
    if (!this.ctx || this.ctx._sinkId !== selectedSinkId) {
      if (this.ctx) this.ctx.close();
      this.ctx = new AudioContext();
      if (selectedSinkId && typeof this.ctx.setSinkId === "function") {
        await this.ctx.setSinkId(selectedSinkId).catch(() => {});
      }
      this.ctx._sinkId = selectedSinkId;
    }

    try {
      const audioBuf = await this.ctx.decodeAudioData(buf);
      const source = this.ctx.createBufferSource();
      source.buffer = audioBuf;

      const analyser = this.ctx.createAnalyser();
      analyser.fftSize = 2048;
      source.connect(analyser);
      analyser.connect(this.ctx.destination);

      this._onAnalyser(analyser);

      source.onended = () => this._playNext();
      source.start(0);
    } catch (err) {
      console.error("Erro ao reproduzir áudio:", err);
      this._playNext();
    }
  }
}
