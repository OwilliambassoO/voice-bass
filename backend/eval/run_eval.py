"""Harness de medição offline para o Capítulo 7 (latência + artefatos de qualidade).

Roda o pipeline real (Whisper -> Edge-TTS -> RVC -> AudioSeal) sobre um áudio de
entrada, N vezes, cronometrando cada etapa com `perf_counter` (mesma técnica da
instrumentação da Seção 6.5) e salvando os WAVs intermediários (TTS e final) para
o cálculo posterior de PESQ/STOI/ECAPA por `analyze.py`.

A latência por etapa NÃO depende do hangover (Seção 7.4.1); basta rodar uma vez
por idioma de entrada (PT e EN). A primeira iteração é descartada (warm-up).

Execute a partir de `backend/` com o venv ativo:

    python eval/run_eval.py --input roteiro_pt.wav --lang pt \
        --voice pt-BR-AntonioNeural --rvc JustinBibier --repeat 10 --out eval_out/pt
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
import time
from statistics import mean

# Permite importar adapters/domain/services quando rodado de backend/eval/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import librosa
import numpy as np
import soundfile as sf

from adapters.audioseal_adapter import AudioSealAdapter
from adapters.edge_tts_adapter import EdgeTTSAdapter
from adapters.rvc_adapter import RVCAdapter
from adapters.voice_scanner import scan_voices
from adapters.whisper_adapter import WhisperAdapter
from domain.audio import pcm16_to_wav_bytes


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 1)


def _p95(xs: list[float]) -> float | None:
    if not xs:
        return None
    ordered = sorted(xs)
    idx = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
    return _ms(ordered[idx])


def _load_pcm16(path: str, sr: int = 16000) -> bytes:
    """Lê um áudio qualquer e devolve PCM 16-bit mono à taxa pedida."""
    y, _ = librosa.load(path, sr=sr, mono=True)
    return (np.clip(y, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def _save_wav16(src_path: str, dst_path: str) -> None:
    y, _ = librosa.load(src_path, sr=16000, mono=True)
    sf.write(dst_path, y, 16000, subtype="PCM_16")


async def _run(args) -> None:
    os.makedirs(args.out, exist_ok=True)

    whisper = WhisperAdapter()
    tts = EdgeTTSAdapter()
    rvc = RVCAdapter()
    audioseal = AudioSealAdapter.try_load()  # None se indisponível

    if args.rvc:
        match = next((v for v in scan_voices(args.voices_dir) if v.name == args.rvc), None)
        if match is None:
            sys.exit(f"Modelo RVC '{args.rvc}' não encontrado em {args.voices_dir}/")
        rvc.load_model(match.pth_path, match.index_path)

    wav_bytes = pcm16_to_wav_bytes(_load_pcm16(args.input), 16000)
    with open(os.path.join(args.out, "input_16k.wav"), "wb") as f:
        f.write(wav_bytes)

    timings: dict[str, list[float]] = {s: [] for s in ("stt", "tts", "rvc", "audioseal", "total")}
    transcripts: list[str] = []

    for iteration in range(args.repeat + 1):
        warm = iteration == 0
        tmp_in = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_in.write(wav_bytes)
        tmp_in.close()
        scratch = [tmp_in.name]
        try:
            t_total = time.perf_counter()

            t = time.perf_counter()
            result = await asyncio.to_thread(whisper.transcribe, tmp_in.name, args.stt_lang)
            d_stt = time.perf_counter() - t
            text = (result.get("text") or "").strip()

            tmp_tts = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
            scratch.append(tmp_tts)
            t = time.perf_counter()
            await tts.synthesize(text or "...", args.voice, tmp_tts)
            d_tts = time.perf_counter() - t

            if rvc.is_loaded:
                t = time.perf_counter()
                tmp_rvc = await asyncio.to_thread(rvc.infer, tmp_tts)
                d_rvc = time.perf_counter() - t
                scratch.append(tmp_rvc)
            else:
                tmp_rvc, d_rvc = tmp_tts, 0.0

            if audioseal is not None:
                t = time.perf_counter()
                tmp_final = await asyncio.to_thread(audioseal.apply, tmp_rvc)
                d_as = time.perf_counter() - t
                scratch.append(tmp_final)
            else:
                tmp_final, d_as = tmp_rvc, 0.0

            d_total = time.perf_counter() - t_total

            if not warm:
                timings["stt"].append(d_stt)
                timings["tts"].append(d_tts)
                timings["rvc"].append(d_rvc)
                timings["audioseal"].append(d_as)
                timings["total"].append(d_total)
                transcripts.append(text)
                # Persiste os artefatos da última iteração para PESQ/STOI/ECAPA.
                # rvc.wav (pré-watermark) vs final.wav isola o efeito do AudioSeal;
                # tts.wav é o áudio sintético limpo antes da conversão de timbre.
                if iteration == args.repeat:
                    _save_wav16(tmp_tts, os.path.join(args.out, "tts.wav"))
                    _save_wav16(tmp_rvc, os.path.join(args.out, "rvc.wav"))
                    _save_wav16(tmp_final, os.path.join(args.out, "final.wav"))

            stamp = "warm-up" if warm else f"{iteration}/{args.repeat}"
            print(f"[{stamp}] stt={_ms(d_stt)} tts={_ms(d_tts)} rvc={_ms(d_rvc)} "
                  f"as={_ms(d_as)} total={_ms(d_total)} :: {text[:60]!r}")
        finally:
            for p in scratch:
                try:
                    os.remove(p)
                except OSError:
                    pass

    stages = {
        s: {"avg_ms": _ms(mean(timings[s])) if timings[s] else None,
            "p95_ms": _p95(timings[s]), "n": len(timings[s])}
        for s in timings
    }
    report = {
        "config": {"input": args.input, "lang": args.lang, "stt_lang": args.stt_lang,
                   "voice": args.voice, "rvc": args.rvc, "audioseal": audioseal is not None,
                   "repeat": args.repeat},
        "stages": stages,
    }
    with open(os.path.join(args.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out, "transcripts.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(transcripts))

    print("\nResumo (avg / p95 ms):")
    for s, v in stages.items():
        print(f"  {s:10s} avg={v['avg_ms']}  p95={v['p95_ms']}  n={v['n']}")
    print(f"\nArtefatos em {args.out}/ (metrics.json, tts.wav, final.wav, transcripts.txt)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Harness de latência/qualidade do Cap. 7.")
    ap.add_argument("--input", required=True, help="WAV/áudio do roteiro lido (mono).")
    ap.add_argument("--lang", default="pt", help="Rótulo do idioma do roteiro (pt|en).")
    ap.add_argument("--stt-lang", default="pt", help="Idioma fixo do Whisper (Seção 6.3).")
    ap.add_argument("--voice", default="pt-BR-AntonioNeural", help="Voz Edge-TTS.")
    ap.add_argument("--rvc", default=None, help="Nome da pasta do modelo em voices/ (vazio = bypass).")
    ap.add_argument("--voices-dir", default="voices")
    ap.add_argument("--repeat", type=int, default=10, help="Iterações medidas (1a é warm-up extra).")
    ap.add_argument("--out", required=True, help="Diretório de saída dos artefatos.")
    asyncio.run(_run(ap.parse_args()))


if __name__ == "__main__":
    main()
