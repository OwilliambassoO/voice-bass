"""Adapter do rvc-python (conversão vocal).

Substitui o antigo `rvc_engine.py`. `torch` e `rvc_python` são importados
dentro do construtor (Regra 5); o monkeypatch de `torch.load` é aplicado uma
única vez, antes de qualquer carregamento de modelo.
"""

import os

os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

import logging
import tempfile

logger = logging.getLogger(__name__)

_torch_load_patched = False


def _patch_torch_load() -> None:
    """Restaura `weights_only=False` para checkpoints antigos do fairseq.

    A partir do PyTorch 2.6, `weights_only` passa a `True` por padrão e recusa
    os checkpoints `pickle` usados pelo HuBERT que o RVC empacota. O patch é
    idempotente. Modelos `.pth` devem vir de fontes confiáveis.
    """
    global _torch_load_patched
    if _torch_load_patched:
        return

    import torch

    original_load = torch.load

    def _torch_load_compat(*args, **kwargs):
        if "weights_only" not in kwargs:
            kwargs["weights_only"] = False
        return original_load(*args, **kwargs)

    torch.load = _torch_load_compat
    _torch_load_patched = True


class RVCAdapter:
    """Encapsula RVCInference, reutilizando a instância entre chamadas."""

    def __init__(self, device: str | None = None):
        _patch_torch_load()

        import torch
        from rvc_python.infer import RVCInference

        if device is None:
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        logger.info("Inicializando RVCAdapter no device '%s'", device)
        self._rvc = RVCInference(device=device)
        self.current_model: str | None = None

    def load_model(self, pth_path: str, index_path: str | None = None) -> None:
        logger.info("Carregando modelo RVC: %s", pth_path)
        self._rvc.load_model(pth_path, index_path=index_path or "")
        if index_path:
            logger.info("Index RVC: %s", index_path)
        self.current_model = pth_path

    @property
    def is_loaded(self) -> bool:
        return self.current_model is not None

    def infer(self, input_path: str) -> str:
        """Aplica a conversão vocal e devolve o caminho do WAV resultante."""
        if not self.is_loaded:
            raise RuntimeError("Nenhum modelo RVC carregado.")
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        self._rvc.infer_file(input_path, tmp.name)
        return tmp.name
