// Única fonte de verdade para os endpoints do backend e a taxa de amostragem.
// A CSP em index.html precisa autorizar estes mesmos hosts em connect-src.

export const BACKEND_HTTP = "http://localhost:8000";
export const BACKEND_WS = "ws://localhost:8000/ws/voice";
export const SAMPLE_RATE = 16000;

// Tamanho fixo do chunk de áudio enviado ao backend. Pequeno (250ms) para que a
// detecção de fim de fala (hangover) tenha baixa latência; a transcrição
// parcial é desacoplada disso no backend (~1x/s). Antes era selecionável na UI
// ("buffer"), substituído pela escolha do tempo de pausa (hangover).
export const CHUNK_MS = 250;
export const CHUNK_SAMPLES = Math.floor((CHUNK_MS / 1000) * SAMPLE_RATE);
