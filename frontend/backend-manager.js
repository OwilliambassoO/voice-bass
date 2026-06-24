// Orquestra o backend Python como processo filho do Electron.
//
// Resolve os caminhos em dois modos:
//   - dev: usa ../backend e o venv local (backend/venv); FFmpeg deve estar no PATH.
//   - empacotado: usa os recursos embutidos em process.resourcesPath (runtime
//     portátil, FFmpeg e modelos pré-baixados produzidos pela Fase 2 do build).
//
// Sobe o backend em 127.0.0.1:8000, faz polling de readiness em GET / até o
// warm-up do lifespan responder {status: "ok"} e encerra a árvore de processos
// ao sair. stdout/stderr do backend vão para um arquivo de log no userData.

const { spawn, execFile } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");
const { app } = require("electron");

const HOST = "127.0.0.1";
const PORT = 8000;
const READY_URL = `http://${HOST}:${PORT}/`;

// Tempo máximo de espera pelo warm-up (carga de Whisper/AudioSeal pode demorar).
const READY_TIMEOUT_MS = 180_000;
const POLL_INTERVAL_MS = 750;

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Copia uma árvore de diretórios (usado para popular o cache gravável no 1º uso).
function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const from = path.join(src, entry.name);
    const to = path.join(dest, entry.name);
    if (entry.isDirectory()) copyDirSync(from, to);
    else fs.copyFileSync(from, to);
  }
}

class BackendManager {
  constructor() {
    this.proc = null;
    this.logStream = null;
  }

  // Resolve todos os caminhos conforme o app esteja em dev ou empacotado.
  _paths() {
    if (app.isPackaged) {
      const runtime = path.join(process.resourcesPath, "backend-runtime");
      return {
        packaged: true,
        // Python portátil (relocável) com a stack instalada direto no site-packages
        // — sem venv, que quebraria ao ser movido para o diretório de instalação.
        pythonExe: path.join(runtime, "python", "python.exe"),
        cwd: path.join(runtime, "app"),
        ffmpegDir: path.join(process.resourcesPath, "ffmpeg", "bin"),
        modelsSrc: path.join(process.resourcesPath, "models"),
      };
    }
    const backendDir = path.join(__dirname, "..", "backend");
    return {
      packaged: false,
      pythonExe: path.join(backendDir, "venv", "Scripts", "python.exe"),
      cwd: backendDir,
      ffmpegDir: null, // em dev assume-se FFmpeg no PATH (como hoje)
      modelsSrc: null,
    };
  }

  get userDataDir() {
    return app.getPath("userData");
  }

  get cacheDir() {
    return path.join(this.userDataDir, "cache");
  }

  get logFile() {
    return path.join(this.userDataDir, "logs", "backend.log");
  }

  // 1º uso (apenas empacotado): copia os modelos embutidos para um diretório
  // gravável, evitando escrever em Program Files. É só cópia local, sem rede.
  _ensureModelCache(paths, onStatus) {
    if (!paths.packaged || !paths.modelsSrc) return;
    const marker = path.join(this.userDataDir, ".setup-done");
    if (fs.existsSync(marker)) return;
    onStatus?.("Preparando modelos (primeira execução)...");
    copyDirSync(paths.modelsSrc, this.cacheDir);
    fs.writeFileSync(marker, new Date().toISOString());
  }

  // Monta o ambiente do subprocesso: FFmpeg no PATH e caches apontando para o
  // diretório gravável onde os modelos pré-baixados foram copiados.
  _buildEnv(paths) {
    const env = { ...process.env };
    if (paths.ffmpegDir) {
      env.PATH = `${paths.ffmpegDir}${path.delimiter}${env.PATH || ""}`;
    }
    if (paths.packaged) {
      env.XDG_CACHE_HOME = this.cacheDir; // Whisper: <XDG_CACHE_HOME>/whisper/base.pt
      env.TORCH_HOME = path.join(this.cacheDir, "torch-hub"); // AudioSeal/torch hub
    }
    return env;
  }

  async start({ onStatus } = {}) {
    const paths = this._paths();

    if (!fs.existsSync(paths.pythonExe)) {
      throw new Error(
        `Python do backend não encontrado em: ${paths.pythonExe}. ` +
          (paths.packaged
            ? "Instalação corrompida."
            : "Crie o venv em backend/venv (veja o README).")
      );
    }

    this._ensureModelCache(paths, onStatus);

    fs.mkdirSync(path.dirname(this.logFile), { recursive: true });
    this.logStream = fs.createWriteStream(this.logFile, { flags: "a" });

    onStatus?.("Iniciando servidor de voz...");
    this.proc = spawn(paths.pythonExe, ["main.py"], {
      cwd: paths.cwd,
      env: this._buildEnv(paths),
      windowsHide: true,
    });

    this.proc.stdout?.pipe(this.logStream);
    this.proc.stderr?.pipe(this.logStream);
    this.proc.on("exit", (code) => {
      this.logStream?.write(`\n[backend-manager] processo encerrou (code=${code})\n`);
    });

    onStatus?.("Aquecendo modelos de IA...");
    await this._waitUntilReady();
    onStatus?.("Pronto!");
  }

  // Faz polling em GET / até o backend responder {status: "ok"} ou estourar o timeout.
  async _waitUntilReady() {
    const deadline = Date.now() + READY_TIMEOUT_MS;
    while (Date.now() < deadline) {
      if (this.proc && this.proc.exitCode !== null) {
        throw new Error(
          `O backend encerrou antes de ficar pronto. Veja o log: ${this.logFile}`
        );
      }
      if (await this._pingReady()) return;
      await delay(POLL_INTERVAL_MS);
    }
    throw new Error(
      `Tempo esgotado aguardando o backend iniciar. Veja o log: ${this.logFile}`
    );
  }

  _pingReady() {
    return new Promise((resolve) => {
      const req = http.get(READY_URL, (res) => {
        let body = "";
        res.on("data", (c) => (body += c));
        res.on("end", () => {
          try {
            resolve(JSON.parse(body).status === "ok");
          } catch {
            resolve(false);
          }
        });
      });
      req.on("error", () => resolve(false));
      req.setTimeout(2000, () => {
        req.destroy();
        resolve(false);
      });
    });
  }

  // Encerra a árvore de processos do backend (taskkill no Windows).
  stop() {
    if (!this.proc || this.proc.exitCode !== null) return;
    const pid = this.proc.pid;
    this.proc = null;
    if (process.platform === "win32" && pid) {
      execFile("taskkill", ["/pid", String(pid), "/T", "/F"]);
    } else if (pid) {
      try {
        process.kill(pid);
      } catch {
        /* já encerrado */
      }
    }
    this.logStream?.end();
    this.logStream = null;
  }
}

module.exports = { BackendManager };
