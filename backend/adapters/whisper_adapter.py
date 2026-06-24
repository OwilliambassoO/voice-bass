"""Adapter do OpenAI Whisper (STT).

O import de `whisper` é feito dentro do construtor (Regra 5): importar este
módulo é barato; o custo do stack de ML só é pago ao instanciar o adapter.
"""

import logging

from domain.thresholds import DEFAULT_WHISPER_MODEL, NO_SPEECH_PROB_THRESHOLD

logger = logging.getLogger(__name__)

_INITIAL_PROMPT = "Transcrição em português brasileiro:"


class WhisperAdapter:
    """Encapsula o modelo Whisper, carregado uma única vez."""

    def __init__(self, model_name: str = DEFAULT_WHISPER_MODEL):
        import whisper

        logger.info("Carregando modelo Whisper '%s'...", model_name)
        self._model = whisper.load_model(model_name)

    def transcribe(self, audio_path: str, language: str = "pt") -> dict:
        """Transcreve um arquivo de áudio, devolvendo o dict bruto do Whisper.

        Mantém os mesmos parâmetros da implementação original (prompt em
        pt-BR, sem condicionar no texto anterior, limiar de não-fala).
        """
        return self._model.transcribe(
            audio_path,
            language=language,
            initial_prompt=_INITIAL_PROMPT,
            condition_on_previous_text=False,
            no_speech_threshold=NO_SPEECH_PROB_THRESHOLD,
        )
