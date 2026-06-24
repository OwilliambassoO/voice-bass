"""Calcula WER, PESQ, STOI e similaridade ECAPA a partir das saídas de run_eval.py
e monta as linhas dos Quadros 14 e 15 do Capítulo 7.

Referências (ver docs/testes/PROTOCOLO-CAP7.md, §7):
  WER   : roteiro de referência vs transcrição do Whisper (jiwer).
  PESQ  : tts.wav (síntese limpa) vs final.wav (após RVC + AudioSeal).
  STOI  : idem PESQ.
  ECAPA : cosseno entre embeddings de final.wav e --target-ref (voz-alvo real).

Cada dependência é opcional: o que não estiver instalado é apenas pulado.

    python eval/analyze.py --eval-dir eval_out/pt --reference "<roteiro>" --target-ref voz_alvo.wav
"""

import argparse
import json
import os

import numpy as np
import soundfile as sf


def _read_16k_mono(path):
    """Lê um WAV como float32 mono a 16 kHz, via soundfile (sem librosa).

    Evita-se librosa de propósito: o lazy_loader dele dispara, junto com o
    speechbrain, um import de k2 inexistente (ver _ecapa). Os artefatos do
    harness já são 16 kHz mono; resample só por garantia.
    """
    y, sr = sf.read(path, dtype="float32")
    if y.ndim > 1:
        y = y.mean(axis=1)
    if sr != 16000:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(int(sr), 16000)
        y = resample_poly(y, 16000 // g, int(sr) // g).astype("float32")
    return y


def _wer(reference: str, hypotheses_path: str):
    try:
        import jiwer
    except ImportError:
        return None
    if not os.path.exists(hypotheses_path):
        return None
    lines = [ln.strip() for ln in open(hypotheses_path, encoding="utf-8") if ln.strip()]
    if not lines:
        return None
    norm = jiwer.Compose([
        jiwer.ToLowerCase(), jiwer.RemovePunctuation(),
        jiwer.RemoveMultipleSpaces(), jiwer.Strip(),
    ])
    vals = [jiwer.wer(norm(reference), norm(h)) for h in lines]
    return round(float(np.mean(vals)), 3)


def _aligned_16k(ref_path: str, deg_path: str):
    ref = _read_16k_mono(ref_path)
    deg = _read_16k_mono(deg_path)
    n = min(len(ref), len(deg))
    return ref[:n], deg[:n]


def _pesq(ref_path: str, deg_path: str):
    try:
        from pesq import pesq
    except ImportError:
        return None
    ref, deg = _aligned_16k(ref_path, deg_path)
    try:
        return round(float(pesq(16000, ref, deg, "wb")), 3)
    except Exception as exc:  # noqa: BLE001
        print(f"  (PESQ falhou: {exc})")
        return None


def _stoi(ref_path: str, deg_path: str):
    try:
        from pystoi import stoi
    except ImportError:
        return None
    ref, deg = _aligned_16k(ref_path, deg_path)
    try:
        return round(float(stoi(ref, deg, 16000, extended=False)), 3)
    except Exception as exc:  # noqa: BLE001
        print(f"  (STOI falhou: {exc})")
        return None


def _ecapa(final_path: str, target_ref: str | None):
    if not target_ref or not os.path.exists(target_ref):
        return None
    try:
        import torch
        from speechbrain.inference.speaker import EncoderClassifier
        from speechbrain.utils.fetching import LocalStrategy
    except ImportError:
        return None
    try:
        # COPY (não SYMLINK) evita o WinError 1314 (symlink exige privilégio no
        # Windows); CPU evita mismatch de device com os tensores de entrada.
        savedir = os.path.join(os.path.dirname(os.path.dirname(final_path)) or ".", "_ecapa_model")
        enc = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=savedir,
            run_opts={"device": "cpu"},
            local_strategy=LocalStrategy.COPY,
        )

        def emb(path):
            y = _read_16k_mono(path)
            e = enc.encode_batch(torch.tensor(y).unsqueeze(0)).squeeze()
            return e / e.norm()

        a, b = emb(final_path), emb(target_ref)
        return round(float(torch.dot(a, b)), 3)
    except Exception as exc:  # noqa: BLE001
        print(f"  (ECAPA falhou: {exc})")
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Métricas de qualidade do Cap. 7.")
    ap.add_argument("--eval-dir", required=True, help="Saída de run_eval.py (contém metrics.json, tts.wav, final.wav).")
    ap.add_argument("--reference", required=True, help="Texto do roteiro de referência (para WER).")
    ap.add_argument("--target-ref", default=None, help="Amostra real da voz-alvo (para ECAPA).")
    args = ap.parse_args()

    d = args.eval_dir
    metrics = json.load(open(os.path.join(d, "metrics.json"), encoding="utf-8"))
    st = metrics["stages"]
    lang = metrics["config"]["lang"]

    def col(stage, key):
        v = st[stage][key]
        return "-" if v is None else v

    print(f"\n=== {d}  (idioma={lang}) ===")
    print("\nQuadro 14 (latência) — preencha as colunas de etapa (iguais p/ 300 e 500 ms):")
    print(f"  STT avg/p95   : {col('stt','avg_ms')} / {col('stt','p95_ms')} ms")
    print(f"  TTS avg/p95   : {col('tts','avg_ms')} / {col('tts','p95_ms')} ms")
    print(f"  RVC avg/p95   : {col('rvc','avg_ms')} / {col('rvc','p95_ms')} ms")
    print(f"  AudioSeal a/p : {col('audioseal','avg_ms')} / {col('audioseal','p95_ms')} ms")
    print(f"  TOTAL p95     : {col('total','p95_ms')} ms")
    tot = st["total"]["p95_ms"]
    if tot is not None:
        print(f"  Resposta após a fala p95 = hangover + {tot} ms  "
              f"(300ms -> {round(300+tot,1)} ; 500ms -> {round(500+tot,1)})")

    tts_wav = os.path.join(d, "tts.wav")
    rvc_wav = os.path.join(d, "rvc.wav")
    final_wav = os.path.join(d, "final.wav")
    has_final = os.path.exists(final_wav)
    has_rvc = os.path.exists(rvc_wav)

    wer = _wer(args.reference, os.path.join(d, "transcripts.txt"))
    ecapa = _ecapa(final_wav, args.target_ref) if has_final else None

    # Medida limpa de "qualidade percebida": impacto do watermark, isolando o
    # AudioSeal (mesmo timbre/conteúdo; só a marca difere). Valida a afirmação de
    # imperceptibilidade. Referência = RVC sem watermark.
    pesq_wm = _pesq(rvc_wav, final_wav) if has_rvc and has_final else None
    stoi_wm = _stoi(rvc_wav, final_wav) if has_rvc and has_final else None
    # Secundária (com ressalva): final vs TTS limpo mistura a mudança de timbre
    # intencional do RVC, então o PESQ sai pessimista — não é medida de qualidade.
    pesq_tts = _pesq(tts_wav, final_wav) if has_final else None
    stoi_tts = _stoi(tts_wav, final_wav) if has_final else None

    def fmt(v):
        return "(instalar dep / ver protocolo)" if v is None else v

    print("\nQuadro 15 (qualidade):")
    print(f"  WER (offline, harness)            : {fmt(wer)}   [WER por cenário live: usar os vídeos]")
    print(f"  PESQ watermark (rvc vs final)     : {fmt(pesq_wm)}   <- imperceptibilidade do AudioSeal")
    print(f"  STOI watermark (rvc vs final)     : {fmt(stoi_wm)}")
    print(f"  Similaridade ECAPA-TDNN           : {fmt(ecapa)}")
    print(f"  [ref] PESQ conversão (tts vs final): {fmt(pesq_tts)}   (timbre muda de propósito; não é qualidade)")
    print(f"  [ref] STOI conversão (tts vs final): {fmt(stoi_tts)}")


if __name__ == "__main__":
    main()
