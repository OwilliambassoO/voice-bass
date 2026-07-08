# Voice Bass

Sistema de alteração de voz em tempo real via IA. Captura áudio do microfone, transcreve com Whisper (STT), sintetiza com Edge-TTS, aplica conversão vocal (RVC) e injeta marca d'água com AudioSeal.

## Arquitetura

```plain text
Microfone → [Electron Frontend] → WebSocket → [Python Backend] → Alto-falante
                                                   │
                                             Whisper (STT)
                                                   ↓
                                            Edge-TTS (TTS)
                                                   ↓
                                           RVC (rvc-python)
                                                   ↓
                                          AudioSeal (watermark)
```

## Estrutura do Projeto

O backend segue uma organização em camadas (Clean Architecture); o frontend separa
captura, rede e interface em módulos.

```plain text
voice-bass/
├── backend/
│   ├── main.py               # FastAPI startup (lifespan), injeção de dependências, rotas
│   ├── domain/               # Regras puras: audio (PCM/WAV/RMS), voice, thresholds
│   ├── adapters/             # Wrappers: whisper, edge_tts, rvc, audioseal, voice_scanner
│   ├── services/             # voice_pipeline (orquestração) + streaming_session (VAD)
│   ├── api/                  # config_routes, voice_websocket, dependencies
│   ├── voices/               # Diretório de modelos RVC (.pth + .index)
│   └── requirements.txt      # Dependências Python
└── frontend/
    ├── main.js               # Processo principal Electron
    ├── backend-manager.js    # Orquestra o backend embutido (app empacotado)
    ├── preload.js            # Bridge seguro para IPC
    ├── package.json          # Dependências Node.js
    └── renderer/
        ├── index.html        # Interface do usuário
        ├── styles.css        # Estilos
        ├── app.js            # Composição dos módulos do renderer
        ├── audio/            # capture, worklet-processor, playback-queue
        ├── services/         # websocket-client, config-client
        └── ui/               # controls, status, visualizer
```

## Download e Instalação (usuários)

Para quem só quer **usar** o Voice Bass, baixe a versão pronta — não é preciso
instalar Python, FFmpeg nem ferramentas de compilação.

### Variante CPU (recomendada)

1. Acesse a página de **[Releases](../../releases)** do projeto.
2. Baixe o instalador **`VoiceBass-<versão>-cpu.exe`** — funciona em qualquer PC Windows.
3. Execute o instalador e abra o **Voice Bass** pelo atalho criado.

### Variante GPU (exige NVIDIA com CUDA)

A variante GPU excede o limite de 2 GB por arquivo do GitHub Release (e do formato
NSIS), então é distribuída como **pacote portátil** `VoiceBass-<versão>-gpu.7z` por
link externo (Google Drive), indicado nas notas da Release.

1. Baixe o `.7z` pelo link nas notas da **[Release](../../releases)**.
2. Extraia com o [7-Zip](https://www.7-zip.org/) (o Windows 11 recente também abre `.7z` nativamente).
3. Abra a pasta extraída e execute **`Voice Bass.exe`** (não há instalador nem atalho).

Na primeira execução, o app prepara os modelos localmente (alguns segundos) e abre a
interface. Selecione microfone, alto-falante e voz e clique em **Iniciar**.

> O pacote é grande (2 GB ou mais) porque já inclui todo o backend de IA, o FFmpeg e
> os modelos — tudo offline. **Exceção:** o Edge-TTS precisa de **internet** em tempo
> de execução (usa os servidores de voz da Microsoft).

A seção abaixo (**Pré-requisitos / Instalação**) destina-se a **desenvolvedores** que
querem rodar a partir do código-fonte ou gerar os instaladores.

## Pré-requisitos

- **Python 3.10.x** (não use Python 3.14 para o backend)
- **Node.js 18+**
- **FFmpeg** disponível no PATH
- **Microsoft C++ Build Tools** com workload C++ para compilar `fairseq`
- **GPU com CUDA** recomendada (para Whisper e AudioSeal)

## Instalação

### Backend

```powershell
# Instala o FFmpeg
winget install Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# Instala as ferramentas C++ necessárias para compilar fairseq
winget install Microsoft.VisualStudio.2022.BuildTools --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
```

Depois de instalar o Build Tools, feche e abra o terminal para atualizar o ambiente.

```powershell
cd backend
py -3.10 -m venv venv
venv\Scripts\activate.ps1    # Windows
# source venv/bin/activate  # Linux/macOS

python -m pip install "pip<24.1" "setuptools<81" wheel
python -m pip install --no-build-isolation openai-whisper
python -m pip install -r requirements.txt
```

Não atualize o `pip` para 24.1 ou superior nesse backend. O `rvc-python` depende de pacotes antigos, como `omegaconf==2.0.6`, que são rejeitados por versões mais novas do `pip`.

### Frontend

```bash
cd frontend
npm install
```

## Execução

### 1. Iniciar o Backend

```powershell
cd backend
venv\Scripts\activate.ps1
python main.py
```

O servidor iniciará em `http://127.0.0.1:8000`. Na primeira execução, o Whisper baixará o modelo `base` e o AudioSeal carregará o watermarker — isso pode levar alguns minutos.

### 2. Iniciar o Frontend

Em outro terminal:

```bash
cd frontend
npm start
```

A janela do Electron abrirá automaticamente. Selecione o microfone, o alto-falante de saída, escolha a voz, ajuste a pausa (sensibilidade ao silêncio) e clique em **Iniciar**.

### Modo desenvolvimento

```bash
cd frontend
npm run dev
```

Abre o Electron com DevTools habilitado.

## Gerando os instaladores (build)

Para produzir os instaladores autocontidos distribuídos aos usuários. Requer as
**VS C++ Build Tools** (para compilar `fairseq`) e conexão de internet.

```powershell
# 1) Monta o runtime do backend (Python portátil + stack + FFmpeg + modelos) em dist/
#    Use -Variant gpu para a build CUDA.
.\build\build-backend-runtime.ps1 -Variant cpu -Clean

# 2) Empacota o app Electron + recursos (dist/installer/)
cd frontend
npm install
npm run dist:cpu   # instalador NSIS  -> VoiceBass-<versão>-cpu.exe
npm run dist:gpu   # pacote portátil  -> VoiceBass-<versão>-gpu.7z
```

O CI em `.github/workflows/release.yml` automatiza apenas o build **CPU** e publica
o `.exe` no Release ao empurrar uma tag `v*`. A variante **GPU** não passa pelo CI:
o payload com torch CUDA excede o limite do instalador NSIS (~2 GiB) e o limite de
2 GiB por asset do GitHub Release — gere o `.7z` localmente com os comandos acima,
hospede no Google Drive e cole o link nas notas do Release.

> A versão do Python portátil baixada fica numa variável no topo de
> `build/build-backend-runtime.ps1` — revise-a periodicamente
> ([releases do python-build-standalone](https://github.com/astral-sh/python-build-standalone/releases)).

## Configuração de Pausa (VAD)

A fala é segmentada por **detecção de atividade de voz (VAD)**: o backend acumula o
enunciado em curso e o envia ao Whisper quando detecta uma pausa (silêncio contínuo).
Não há mais escolha de buffer; o único controle de tempo exposto ao usuário é a duração
dessa pausa, chamada de *hangover*.

| Pausa    | Descrição                                                             |
|----------|-----------------------------------------------------------------------|
| `300 ms` | Mais sensível: fecha a frase rápido, mas pode cortar em pausas curtas |
| `400 ms` | Intermediário                                                         |
| `500 ms` | Padrão: evita cortar a fala em pausas naturais entre palavras         |

A captura usa blocos fixos de ~250 ms, apenas para detectar a pausa com baixa latência;
eles não delimitam a transcrição. Enquanto o usuário fala, a transcrição parcial é
atualizada ao vivo (~1×/s); ao detectar a pausa, a voz convertida é sintetizada uma única
vez para a frase inteira.

## Adicionando uma Voz RVC (Passo a Passo)

O RVC (Retrieval-based Voice Conversion) converte o áudio gerado pelo Edge-TTS para soar como uma voz-alvo. Para adicionar uma nova voz, siga os passos abaixo.

> **Atalho (recomendado):** na interface, clique no botão **+** ao lado do seletor **Modelo de Voz (RVC)** para abrir a pasta de vozes (ela é criada se ainda não existir). Coloque o modelo lá conforme os passos abaixo e reinicie o app. Funciona tanto no modo dev quanto no app instalado — neste, a pasta fica num caminho interno e o botão evita ter que procurá-la manualmente.

### 1. Obter os arquivos do modelo

Cada modelo RVC é composto por:

| Arquivo   | Obrigatório       | Descrição                                                 |
|-----------|-------------------|-----------------------------------------------------------|
| `*.pth`   | Sim               | Pesos da rede neural treinada                             |
| `*.index` | Não (recomendado) | Índice FAISS para retrieval — melhora a fidelidade da voz |

Você pode treinar seu próprio modelo com ferramentas como [Applio](https://github.com/IAHispano/Applio) ou [RVC-WebUI](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI), ou baixar modelos prontos de repositórios da comunidade (ex.: [voice-models.com](https://voice-models.com), [weights.gg](https://weights.gg)).

### 2. Criar a pasta do modelo

Dentro de `backend/voices/`, crie uma subpasta com o nome que deseja exibir na interface:

```powershell
mkdir backend\voices\NomeDaVoz
```

### 3. Copiar os arquivos

Coloque o `.pth` e o `.index` (se tiver) dentro da pasta criada:

```plain text
backend/voices/
├── MeuModelo/
│   ├── MeuModelo.pth          ← obrigatório
│   └── added_IVF512_Flat.index  ← opcional, melhora qualidade
└── OutroModelo/
    └── OutroModelo.pth
```

> **Importante:** cada pasta deve conter exatamente **um** arquivo `.pth`. Se houver mais de um, apenas o primeiro (em ordem alfabética) será usado. O mesmo vale para o `.index`.

### 4. Reiniciar o backend

O escaneamento de vozes ocorre na inicialização do servidor. Após adicionar ou remover modelos, reinicie:

```powershell
# No terminal do backend
Ctrl+C
python main.py
```

No log, você verá:

```plain text
Vozes RVC encontradas: ['MeuModelo', 'OutroModelo']
```

### 5. Selecionar no frontend

Na interface do Electron, o dropdown **Modelo de Voz (RVC)** listará todas as pastas detectadas. Selecione o modelo desejado e clique em **Iniciar**.

### Sem modelo RVC

Se a pasta `backend/voices/` estiver vazia ou não existir, o pipeline ignora o passo de conversão RVC automaticamente (bypass). O áudio do Edge-TTS segue direto para o AudioSeal.

## Vozes Disponíveis

- **António** (pt-BR-AntonioNeural) — Masculino
- **Francisca** (pt-BR-FranciscaNeural) — Feminino
- **Thalita** (pt-BR-ThalitaNeural) — Feminino

## Solução de Problemas

| Erro | Solução |
| ---- | ------- |
| `FFmpeg não encontrado no PATH` | Instale com `winget install Gyan.FFmpeg` e reabra o terminal |
| `Microsoft Visual C++ 14.0 or greater is required` | Instale o Visual Studio Build Tools com workload C++ e rode `pip install -r requirements.txt` novamente |
| `Failed to build 'openai-whisper'` / `No module named 'pkg_resources'` | Mantenha `pip<24.1`, `setuptools<81` e instale `openai-whisper` com `--no-build-isolation` antes do `requirements.txt` |
| `OmegaConf has no attribute resolve` ou falha do AudioSeal com `AudioSealWMConfig.nbits` | A incompatibilidade com o `omegaconf==2.0.6` (fixado pelo `rvc-python`) já é tratada por um shim em `adapters/audioseal_adapter.py`, e o AudioSeal carrega normalmente. Se ainda assim falhar por outro motivo, o backend segue sem watermark (degradação graciosa) |
| `TorchCodec ... Could not load this library` | O backend de áudio já usa `soundfile` — esse warning pode ser ignorado |
| O Electron abre mas mostra "Desconectado" | Verifique se o backend está rodando na porta 8000 |

## API REST

- `GET /` — Status do servidor
- `GET /config` — Configurações disponíveis (vozes, opções de pausa e modelos RVC)
- `WebSocket /ws/voice` — Conexão de voz em tempo real
- `GET /metrics` — Latência média/p95 por etapa (STT, TTS, RVC, AudioSeal). Exposto apenas para depuração local: defina a variável de ambiente `ENABLE_METRICS=1` antes de iniciar o backend; sem ela, a rota não é registrada.
