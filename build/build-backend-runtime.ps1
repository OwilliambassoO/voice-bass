<#
.SYNOPSIS
  Monta o runtime autocontido do backend do Voice Bass para empacotamento.

.DESCRIPTION
  Produz, em <repo>/dist, tudo que o instalador embute via extraResources
  (ver frontend/package.json):

    dist/backend-runtime/python/   Python 3.10 portátil (relocável) + stack ML instalada
    dist/backend-runtime/app/      cópia do código do backend (sem venv/tests/cache)
    dist/ffmpeg/bin/               ffmpeg.exe + ffprobe.exe
    dist/models/whisper/           peso do Whisper "base"
    dist/models/torch-hub/         checkpoint do AudioSeal

  A stack é instalada DIRETO no Python portátil (sem venv), porque um venv grava
  caminhos absolutos da máquina de build e quebraria ao ser movido para o diretório
  de instalação. O backend chama uvicorn programaticamente (main.py), então não há
  console scripts a corrigir.

  PRÉ-REQUISITOS na máquina de build (não no cliente final):
    - Visual Studio Build Tools com workload C++ (para compilar fairseq).
    - Conexão de internet (baixa Python, FFmpeg, wheels e modelos).
    - tar e Expand-Archive disponíveis (Windows 10+).

.PARAMETER Variant
  cpu (padrão) ou gpu. Em gpu, instala torch/torchaudio do índice CUDA antes do resto.
  Também lido de $env:VB_VARIANT (definido por npm run dist:cpu / dist:gpu).

.PARAMETER Clean
  Remove dist/backend-runtime, dist/ffmpeg e dist/models antes de começar.

.EXAMPLE
  ./build/build-backend-runtime.ps1 -Variant cpu -Clean
#>

[CmdletBinding()]
param(
  [ValidateSet("cpu", "gpu")]
  [string]$Variant = $(if ($env:VB_VARIANT) { $env:VB_VARIANT } else { "cpu" }),
  [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # acelera Invoke-WebRequest

# --- URL do Python portátil (python-build-standalone) -----------------------
# Atualize aqui se necessário. Veja releases em:
#   https://github.com/astral-sh/python-build-standalone/releases
# Use a variante "install_only" cp310 x86_64 windows msvc (.tar.gz). O archive
# extrai uma pasta "python/" com python.exe na raiz.
$PythonUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/20250115/cpython-3.10.16+20250115-x86_64-pc-windows-msvc-install_only.tar.gz"

# --- FFmpeg estático --------------------------------------------------------
$FfmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

# --- Caminhos ---------------------------------------------------------------
$RepoRoot   = Split-Path $PSScriptRoot -Parent
$BackendDir = Join-Path $RepoRoot "backend"
$Dist       = Join-Path $RepoRoot "dist"
$RuntimeDir = Join-Path $Dist "backend-runtime"
$PyDir      = Join-Path $RuntimeDir "python"
$AppDir     = Join-Path $RuntimeDir "app"
$FfmpegDir  = Join-Path $Dist "ffmpeg"
$ModelsDir  = Join-Path $Dist "models"
$Work       = Join-Path $Dist ".work"
$PyExe      = Join-Path $PyDir "python.exe"

function Write-Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# ---------------------------------------------------------------------------
Write-Step "Variante: $Variant"

if ($Clean) {
  Write-Step "Limpando saídas anteriores"
  foreach ($d in @($RuntimeDir, $FfmpegDir, $ModelsDir, $Work)) {
    if (Test-Path $d) { Remove-Item $d -Recurse -Force }
  }
}
New-Item -ItemType Directory -Force -Path $Dist, $Work | Out-Null

# --- 1. Python portátil -----------------------------------------------------
Write-Step "1/6 Baixando Python portátil"
if (-not (Test-Path $PyExe)) {
  $pyArchive = Join-Path $Work "python.tar.gz"
  Invoke-WebRequest -Uri $PythonUrl -OutFile $pyArchive
  New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
  # O archive contém um diretório "python/" na raiz -> extrai direto em $RuntimeDir.
  tar -xf $pyArchive -C $RuntimeDir
  if (-not (Test-Path $PyExe)) {
    throw "python.exe não encontrado em $PyDir após extração. Confira a URL/layout do archive."
  }
} else {
  Write-Host "Python já presente em $PyDir (pulando)."
}

# --- 2. Stack Python --------------------------------------------------------
Write-Step "2/6 Instalando dependências (segue as restrições do README)"
& $PyExe -m pip install "pip<24.1" "setuptools<81" wheel
if ($LASTEXITCODE -ne 0) { throw "Falha ao fixar pip/setuptools/wheel." }

if ($Variant -eq "gpu") {
  Write-Host "Instalando torch CUDA antes do restante..."
  & $PyExe -m pip install -r (Join-Path $BackendDir "requirements-gpu.txt")
  if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar torch CUDA." }
}

# openai-whisper precisa de --no-build-isolation com setuptools<81 (ver README).
& $PyExe -m pip install --no-build-isolation openai-whisper
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar openai-whisper." }

& $PyExe -m pip install -r (Join-Path $BackendDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar requirements.txt (fairseq exige Build Tools C++)." }

# --- 3. Código do backend ---------------------------------------------------
Write-Step "3/6 Copiando código do backend"
if (Test-Path $AppDir) { Remove-Item $AppDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
foreach ($item in @("adapters", "api", "domain", "services", "main.py", "voices")) {
  $src = Join-Path $BackendDir $item
  if (Test-Path $src) { Copy-Item $src -Destination $AppDir -Recurse -Force }
}
# Remove caches Python que possam ter vindo na cópia.
Get-ChildItem $AppDir -Recurse -Directory -Filter "__pycache__" |
  ForEach-Object { Remove-Item $_.FullName -Recurse -Force }

# --- 4. FFmpeg --------------------------------------------------------------
Write-Step "4/6 Baixando FFmpeg"
$ffBin = Join-Path $FfmpegDir "bin"
if (-not (Test-Path (Join-Path $ffBin "ffmpeg.exe"))) {
  $ffZip = Join-Path $Work "ffmpeg.zip"
  $ffExtract = Join-Path $Work "ffmpeg"
  Invoke-WebRequest -Uri $FfmpegUrl -OutFile $ffZip
  if (Test-Path $ffExtract) { Remove-Item $ffExtract -Recurse -Force }
  Expand-Archive -Path $ffZip -DestinationPath $ffExtract -Force
  New-Item -ItemType Directory -Force -Path $ffBin | Out-Null
  foreach ($exe in @("ffmpeg.exe", "ffprobe.exe")) {
    $found = Get-ChildItem $ffExtract -Recurse -Filter $exe | Select-Object -First 1
    if (-not $found) { throw "$exe não encontrado no pacote do FFmpeg." }
    Copy-Item $found.FullName -Destination $ffBin -Force
  }
} else {
  Write-Host "FFmpeg já presente (pulando)."
}

# --- 5. Modelos pré-baixados ------------------------------------------------
Write-Step "5/6 Pré-baixando modelos (Whisper + AudioSeal)"
$whisperDir = Join-Path $ModelsDir "whisper"
New-Item -ItemType Directory -Force -Path $whisperDir | Out-Null
& $PyExe -c "import whisper; whisper.load_model('base', download_root=r'$whisperDir')"
if ($LASTEXITCODE -ne 0) { throw "Falha ao baixar o modelo Whisper 'base'." }

# AudioSeal é opcional no runtime; aqui apenas tentamos popular o cache. Se o
# load falhar (ex.: incompatibilidade com omegaconf antigo), o download do
# checkpoint normalmente já ocorreu — não derrubamos o build.
$torchHub = Join-Path $ModelsDir "torch-hub"
New-Item -ItemType Directory -Force -Path $torchHub | Out-Null
$env:TORCH_HOME = $torchHub
& $PyExe -c "from audioseal import AudioSeal; AudioSeal.load_generator('audioseal_wm_16bits'); print('audioseal ok')"
if ($LASTEXITCODE -ne 0) {
  Write-Warning "AudioSeal não carregou totalmente; verifique se o checkpoint foi baixado em $torchHub."
}
Remove-Item Env:TORCH_HOME -ErrorAction SilentlyContinue

# --- 6. Smoke test de imports ----------------------------------------------
Write-Step "6/6 Verificando imports da stack"
& $PyExe -c "import fastapi, uvicorn, numpy, whisper, torch, edge_tts, soundfile, audioseal; print('imports ok; torch', torch.__version__, 'cuda', torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw "Smoke test de imports falhou." }

# Limpeza do diretório temporário de download.
if (Test-Path $Work) { Remove-Item $Work -Recurse -Force }

Write-Host "`nRuntime pronto em: $RuntimeDir" -ForegroundColor Green
Write-Host "FFmpeg em:        $FfmpegDir"
Write-Host "Modelos em:       $ModelsDir"
Write-Host "`nProximo passo: cd frontend; npm run dist:$Variant" -ForegroundColor Green
