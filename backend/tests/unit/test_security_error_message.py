from app.security import client_error_message, STAGE_LABELS


def test_message_is_human_readable_and_leak_free():
    msg = client_error_message(3)
    assert "Target identification" in msg
    assert "stage 3" in msg
    # No technical leakage
    for bad in ["Traceback", "Error", "Exception", "/", "\\", ".py", "line "]:
        assert bad not in msg


def test_all_eight_stages_have_labels():
    assert set(STAGE_LABELS.keys()) == set(range(1, 9))


def test_unknown_stage_is_still_safe():
    msg = client_error_message(99)
    assert "stage 99" in msg
    assert "Traceback" not in msg
