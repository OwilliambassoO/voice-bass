"""Constantes de domínio do pipeline de voz.

Limiares empíricos de filtragem de áudio e padrões de configuração.
Não dependem de bibliotecas externas (puro domínio).
"""

# Energia mínima (RMS, 0..1) abaixo da qual o chunk é tratado como silêncio.
# 0.02 era agressivo demais: com supressão de ruído ligada e sem ganho
# automático, fala normal mede ~0.01–0.03 e parte das janelas caía abaixo do
# limiar, sendo descartada antes do Whisper. Mantido baixo para só barrar
# silêncio real; o no_speech_prob do Whisper filtra o resto. Calibre pelos
# valores de RMS logados em voice_pipeline.process_chunk.
SILENCE_RMS_THRESHOLD = 0.005

# Probabilidade de não-fala (Whisper) acima da qual o chunk é descartado.
NO_SPEECH_PROB_THRESHOLD = 0.6

# Log-probabilidade média (Whisper) abaixo da qual a transcrição é descartada.
AVG_LOGPROB_THRESHOLD = -1.0

# Padrões de configuração do pipeline.
DEFAULT_TTS_VOICE = "pt-BR-AntonioNeural"
DEFAULT_WHISPER_MODEL = "base"
