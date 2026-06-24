// Desenho da forma de onda em um canvas a partir de um AnalyserNode.

export class Visualizer {
  constructor(canvas, color) {
    this.canvas = canvas;
    this.color = color;
    this.animFrame = null;
  }

  start(analyser) {
    this.stop();
    const ctx = this.canvas.getContext("2d");
    const data = new Uint8Array(analyser.frequencyBinCount);

    const draw = () => {
      this.animFrame = requestAnimationFrame(draw);
      analyser.getByteTimeDomainData(data);
      this._render(ctx, data);
    };
    draw();
  }

  stop() {
    if (this.animFrame) cancelAnimationFrame(this.animFrame);
    this.animFrame = null;
  }

  _render(ctx, data) {
    const w = this.canvas.width;
    const h = this.canvas.height;
    ctx.fillStyle = "#0f0f13";
    ctx.fillRect(0, 0, w, h);

    ctx.lineWidth = 2;
    ctx.strokeStyle = this.color;
    ctx.beginPath();

    const sliceWidth = w / data.length;
    let x = 0;
    for (let i = 0; i < data.length; i++) {
      const v = data[i] / 128.0;
      const y = (v * h) / 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      x += sliceWidth;
    }
    ctx.lineTo(w, h / 2);
    ctx.stroke();
  }
}
