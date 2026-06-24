"""Adapter do Edge-TTS (síntese intermediária de voz).

`edge_tts` é importado dentro do método (Regra 5).
"""


class EdgeTTSAdapter:
    """Sintetiza texto em fala usando as vozes neurais do Edge-TTS."""

    async def synthesize(self, text: str, voice: str, out_path: str) -> None:
        """Gera o áudio de *text* com *voice* e salva em *out_path* (mp3)."""
        import edge_tts

        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(out_path)
