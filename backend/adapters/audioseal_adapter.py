"""Adapter do AudioSeal (marca d'água forense, opcional).

Reúne o shim de compatibilidade do OmegaConf e o fallback "sem watermark".
Imports pesados (audioseal, torch, soundfile, numpy) são feitos dentro dos
métodos (Regra 5).
"""

import os

os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

import logging
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


def _ensure_omegaconf_resolve() -> None:
    """Compatibiliza AudioSeal com o OmegaConf antigo exigido pelo rvc-python.

    O `rvc-python` fixa `omegaconf==2.0.6`, anterior ao método `resolve` em
    nível de módulo que o AudioSeal espera; aqui ele é recriado localmente.
    """
    from omegaconf import OmegaConf

    if hasattr(OmegaConf, "resolve"):
        return

    def _resolve(config):
        resolved = OmegaConf.to_container(config, resolve=True)
        config.clear()
        config.merge_with(resolved)

    OmegaConf.resolve = _resolve  # type: ignore[attr-defined]


def _ensure_audioseal_config_defaults() -> None:
    """Compatibiliza a montagem de config do AudioSeal com o OmegaConf antigo.

    O `rvc-python` fixa `omegaconf==2.0.6`, que não lida bem com schema
    estruturado a partir de dataclasses: `OmegaConf.structured(AudioSealWMConfig)`
    exige defaults explícitos (erro "Missing default value for ... nbits") e o
    `merge_with` de um dict aninhado falha ("Unexpected object type : dict").

    A correção substitui `AudioSeal.parse_config` por uma versão que monta a
    config como `DictConfig` simples (não estruturada). O `create_generator`
    funciona igual com ela (acesso por atributo + `OmegaConf.to_container`), de
    modo que o comportamento do watermark já descrito no projeto não muda;
    apenas destrava a carga sob o omegaconf antigo. Idempotente.
    """
    from dataclasses import fields as dataclass_fields

    from omegaconf import OmegaConf

    from audioseal.loader import AudioSeal

    if getattr(AudioSeal.parse_config, "_voicebass_patched", False):
        return

    def parse_config(config, config_type, nbits=None):
        assert "seanet" in config, f"missing seanet backbone config in {config}"
        config = OmegaConf.create(config)
        OmegaConf.resolve(config)
        config = OmegaConf.to_container(config)

        seanet_config = config["seanet"]
        for key_to_patch in ("encoder", "decoder", "detector"):
            if key_to_patch in seanet_config:
                config_to_patch = config.get(key_to_patch) or {}
                config[key_to_patch] = {
                    **config_to_patch,
                    **seanet_config.pop(key_to_patch),
                }
        seanet_config.pop("moshi", None)
        seanet_config["norm"] = "none"  # desabilita weight norm (igual ao original)
        config["seanet"] = seanet_config

        if nbits and "nbits" not in config:
            config["nbits"] = nbits

        result_config = {
            f.name: config[f.name]
            for f in dataclass_fields(config_type)
            if f.name in config
        }
        return OmegaConf.create(result_config)

    parse_config._voicebass_patched = True  # type: ignore[attr-defined]
    AudioSeal.parse_config = staticmethod(parse_config)


class AudioSealAdapter:
    """Aplica a marca d'água de 16 bits sobre um áudio."""

    def __init__(self, generator):
        self._generator = generator

    @classmethod
    def try_load(cls) -> "Optional[AudioSealAdapter]":
        """Tenta carregar o gerador; devolve None se indisponível.

        Mantém a degradação graciosa: se o AudioSeal não puder ser carregado
        (ex.: incompatibilidade com `omegaconf==2.0.6`), o pipeline segue sem
        watermark.
        """
        logger.info("Carregando AudioSeal watermarker...")
        _ensure_omegaconf_resolve()
        _ensure_audioseal_config_defaults()
        try:
            from audioseal import AudioSeal

            generator = AudioSeal.load_generator("audioseal_wm_16bits")
            return cls(generator)
        except Exception as exc:  # noqa: BLE001 - degradação graciosa intencional
            logger.warning(
                "AudioSeal indisponivel; o backend continuara sem watermark: %s",
                exc,
            )
            return None

    def apply(self, input_path: str) -> str:
        """Injeta a marca d'água e devolve o caminho do WAV protegido."""
        import numpy as np
        import soundfile as sf
        import torch

        audio_data, sr = sf.read(input_path, dtype="float32")
        if audio_data.ndim == 1:
            audio_data = audio_data[np.newaxis, :]  # (1, samples)
        else:
            audio_data = audio_data.T  # (channels, samples)

        waveform = torch.from_numpy(audio_data).unsqueeze(0)  # (1, channels, samples)
        with torch.no_grad():
            waveform_safe = self._generator(waveform, sample_rate=sr)
        waveform_safe = waveform_safe.squeeze(0)  # (channels, samples)

        tmp_output = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        out_np = waveform_safe.numpy().T  # (samples, channels)
        sf.write(tmp_output, out_np, sr)
        return tmp_output
