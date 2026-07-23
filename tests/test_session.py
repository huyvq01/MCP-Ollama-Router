import uuid


def test_new_session(session):
    session_id = session.new_session()

    assert isinstance(session_id, str)

    # Kiểm tra UUID hợp lệ
    uuid.UUID(session_id)


def test_new_session_unique(session):
    session1 = session.new_session()
    session2 = session.new_session()

    assert session1 != session2


def test_new_session_not_empty(session):
    session_id = session.new_session()

    assert session_id != ""
    assert len(session_id) > 0
