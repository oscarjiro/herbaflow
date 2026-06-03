from app.security import sanitize_filename


def test_strips_crlf_and_quotes():
    out = sanitize_filename('na\r\nme"with/slash\\and:colon')
    for bad in ['\r', '\n', '"', '/', '\\', ':']:
        assert bad not in out


def test_keeps_dot_and_word_chars():
    assert sanitize_filename("aspirin_stage1.csv") == "aspirin_stage1.csv"


def test_empty_after_cleaning_falls_back_to_default():
    assert sanitize_filename('***') == "analysis"
    assert sanitize_filename('   ') == "analysis"


def test_length_is_capped():
    assert len(sanitize_filename("a" * 500)) <= 128


def test_non_ascii_dropped():
    # café_β -> ascii-drop -> "caf_" -> .strip(" ._") removes trailing "_" -> "caf"
    assert sanitize_filename("café_β") == "caf"
