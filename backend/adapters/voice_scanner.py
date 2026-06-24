"""Descoberta de modelos RVC no sistema de arquivos.

Adapter leve (apenas stdlib + domínio): escaneia subpastas de *voices_dir*
e devolve `VoiceModel`s. Sem ML, para permitir testes com tmpdir.
"""

import logging
from pathlib import Path

from domain.voice import VoiceModel

logger = logging.getLogger(__name__)


def scan_voices(voices_dir: str) -> list[VoiceModel]:
    """Escaneia *voices_dir* em busca de subpastas contendo arquivos .pth.

    Cada subpasta com ao menos um `.pth` vira uma voz; um `.index` (FAISS)
    é associado quando presente. A lista sai ordenada alfabeticamente.
    """
    voices: list[VoiceModel] = []
    base = Path(voices_dir)
    if not base.is_dir():
        logger.warning("Diretorio de vozes nao encontrado: %s", voices_dir)
        return voices

    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue

        pth_files = list(entry.glob("*.pth"))
        if not pth_files:
            continue

        index_files = list(entry.glob("*.index"))
        voices.append(VoiceModel(
            name=entry.name,
            pth_path=str(pth_files[0]),
            index_path=str(index_files[0]) if index_files else None,
        ))

    logger.info("Vozes RVC encontradas: %s", [v.name for v in voices])
    return voices
