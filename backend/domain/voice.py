"""Tipos de domínio relacionados a modelos de voz RVC."""

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceModel:
    """Um modelo RVC descoberto no diretório de vozes.

    `index_path` é opcional (arquivo FAISS que melhora a fidelidade).
    """

    name: str
    pth_path: str
    index_path: str | None = None
