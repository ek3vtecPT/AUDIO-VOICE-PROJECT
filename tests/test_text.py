from estudio_voz import text as T


def test_split_sentences_and_paragraphs():
    segs = T.split_text("Olá a todos. Hoje há novidades!\n\nSegundo parágrafo aqui.")
    assert [s.text for s in segs] == ["Olá a todos.", "Hoje há novidades!", "Segundo parágrafo aqui."]
    assert segs[0].pause_after == 0.25
    assert segs[1].pause_after == 0.6
    assert segs[-1].pause_after == 0.0


def test_pause_tag():
    segs = T.split_text("Primeiro. [pausa 1,5] Depois.")
    assert [s.text for s in segs] == ["Primeiro.", "Depois."]
    assert segs[0].pause_after == 0.25 + 1.5


def test_long_sentence_is_broken():
    long = ("palavra " * 80).strip() + "."
    segs = T.split_text(long, max_chars=100)
    assert all(len(s.text) <= 100 for s in segs)
    assert " ".join(s.text for s in segs) == long


def test_social_cleanup():
    segs = T.split_text("Vejam o #lançamento com a @marca em https://exemplo.pt/x hoje.")
    assert segs[0].text == "Vejam o lançamento com a marca em hoje."


def test_pronunciations_whole_words_longest_first():
    m = {"XPTO": "xis pê tê ó", "Banco XPTO": "banco xispêtó"}
    assert T.apply_pronunciations("O Banco XPTO e a XPTO.", m) == "O banco xispêtó e a xis pê tê ó."
    assert T.apply_pronunciations("XPTOS", m) == "XPTOS"


def test_numbers_pt_pt():
    assert T.expand_numbers("16 anos") == "dezasseis anos"
    assert T.expand_numbers("25%") == "vinte e cinco por cento"
    assert T.expand_numbers("1.000 €") == "mil euros"
    assert T.expand_numbers("às 10h30") == "às dez e trinta"
    assert T.expand_numbers("3,5") == "três vírgula cinco"
