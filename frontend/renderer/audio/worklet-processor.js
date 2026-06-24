// AudioWorkletProcessor: roda na audio thread (fora da main thread).
// Acumula amostras float32 e, ao atingir o tamanho de chunk alvo, converte
// para Int16 e posta o ArrayBuffer de volta ao renderer (transferido).
//
// O tamanho alvo (em amostras) chega via port.postMessage; hoje é fixo em
// ~250ms (definido pelo capture), pequeno para detectar a pausa com baixa
// latência no backend.

class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._targetSamples = 4000; // padrão 250 ms @ 16 kHz; definido pelo capture via port
    this.port.onmessage = (e) => {
      if (e.data && typeof e.data.bufferSamples === "number") {
        this._targetSamples = e.data.bufferSamples;
      }
    };
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channel = input[0];
    for (let i = 0; i < channel.length; i++) {
      this._buffer.push(channel[i]);
    }

    while (this._buffer.length >= this._targetSamples) {
      const chunk = this._buffer.splice(0, this._targetSamples);
      const pcm16 = new Int16Array(chunk.length);
      for (let i = 0; i < chunk.length; i++) {
        const s = Math.max(-1, Math.min(1, chunk[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    }

    return true;
  }
}

registerProcessor("capture-processor", CaptureProcessor);
