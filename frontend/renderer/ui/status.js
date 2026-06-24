// Indicador de status (bolinha + texto) no topo da interface.

export class StatusIndicator {
  constructor(dotEl, textEl) {
    this.dot = dotEl;
    this.text = textEl;
  }

  set(state, text) {
    this.dot.className = `dot dot--${state}`;
    this.text.textContent = text;
  }
}
