import numpy as np
import pytest

from estudio_voz import dataset


def test_parse_links_with_range():
    src = dataset.parse_links("https://youtu.be/abc 1:30-12:45\n\n# comentário\nhttps://vimeo.com/1")
    assert [s.value for s in src] == ["https://youtu.be/abc", "https://vimeo.com/1"]
    assert src[0].start == 90 and src[0].end == 765 and src[1].start is None


def test_parse_links_rejects_text():
    with pytest.raises(ValueError):
        dataset.parse_links("isto não é um link")


def test_main_speaker_filter_drops_guest():
    rng = np.random.default_rng(0)
    me, guest = rng.normal(size=64), rng.normal(size=64)

    def emb(base, n):
        e = base + 0.3 * rng.normal(size=(n, 64))
        return e / np.linalg.norm(e, axis=1, keepdims=True)

    embeds = np.vstack([emb(me, 20), emb(guest, 6)])
    keep, sims = dataset.main_speaker_filter(embeds, threshold=0.75)
    assert keep[:20].all() and not keep[20:].any()


def test_quality_filter():
    assert dataset._quality_ok(0.3 * np.sin(np.linspace(0, 500, 44100)).astype(np.float32))
    assert not dataset._quality_ok(np.zeros(44100, dtype=np.float32))
    assert not dataset._quality_ok(np.ones(44100, dtype=np.float32))
