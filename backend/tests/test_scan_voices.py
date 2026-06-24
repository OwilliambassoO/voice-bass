"""Testes do scanner de vozes RVC (sem ML, com tmpdir)."""

from adapters.voice_scanner import scan_voices


def test_scan_voices_lists_and_associates_index(tmp_path):
    # Modelo A: apenas .pth
    (tmp_path / "A").mkdir()
    (tmp_path / "A" / "A.pth").write_bytes(b"x")

    # Modelo B: .pth + .index
    (tmp_path / "B").mkdir()
    (tmp_path / "B" / "B.pth").write_bytes(b"x")
    (tmp_path / "B" / "B.index").write_bytes(b"x")

    # Pasta C: sem .pth -> ignorada
    (tmp_path / "C").mkdir()

    voices = scan_voices(str(tmp_path))

    assert [v.name for v in voices] == ["A", "B"]
    assert voices[0].index_path is None
    assert voices[1].index_path is not None


def test_scan_voices_missing_dir_returns_empty(tmp_path):
    assert scan_voices(str(tmp_path / "inexistente")) == []
