// Tela de carregamento: reflete o status da inicialização do backend exposto
// pelo preload (window.voiceBass). Quando o backend fica pronto, o processo
// principal troca esta página pela UI principal (index.html).

const statusEl = document.getElementById("status");
const errorEl = document.getElementById("error");
const loaderEl = document.getElementById("loader");

window.voiceBass?.onBackendStatus?.((text) => {
  statusEl.textContent = text;
});

window.voiceBass?.onBackendError?.((message) => {
  loaderEl.classList.add("has-error");
  statusEl.textContent = "Não foi possível iniciar o Voice Bass.";
  errorEl.textContent = message;
  errorEl.classList.add("show");
});
