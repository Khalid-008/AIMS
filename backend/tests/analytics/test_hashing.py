"""Hash stability: changes when any input changes."""
import asyncio

import pytest

from app.services.analytics import hashing as hashing_mod
from app.services.analytics.hashing import InputHash, compute_input_hash


class _FakeRow:
    def __init__(self, value):
        self._v = value

    def scalar_one_or_none(self):
        return self._v

    def scalar_one(self):
        return self._v


class _FakeSession:
    def __init__(self, sid: int | None, max_id: int, count: int):
        self._returns = [_FakeRow(sid), _FakeRow(max_id), _FakeRow(count)]

    async def execute(self, *a, **kw):
        return self._returns.pop(0)


class _FakeSessionCM:
    def __init__(self, session):
        self._s = session

    async def __aenter__(self):
        return self._s

    async def __aexit__(self, *a):
        return False


def _patch_ro(monkeypatch, sid, max_id, count):
    def _factory():
        return _FakeSessionCM(_FakeSession(sid, max_id, count))

    monkeypatch.setattr(hashing_mod, "ro_session", _factory)


@pytest.mark.asyncio
async def test_hash_changes_when_max_answer_id_changes(monkeypatch):
    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    a = await compute_input_hash("S-1", "ar")

    _patch_ro(monkeypatch, sid=1, max_id=101, count=50)
    b = await compute_input_hash("S-1", "ar")

    assert a.sha256 != b.sha256


@pytest.mark.asyncio
async def test_hash_changes_when_language_changes(monkeypatch):
    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    a = await compute_input_hash("S-1", "ar")

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    b = await compute_input_hash("S-1", "en")

    assert a.sha256 != b.sha256


@pytest.mark.asyncio
async def test_hash_stable_when_inputs_match(monkeypatch):
    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    a = await compute_input_hash("S-1", "ar")

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    b = await compute_input_hash("S-1", "ar")

    assert a.sha256 == b.sha256
    assert a.max_answer_id == b.max_answer_id == 100
    assert a.answer_count == b.answer_count == 50


@pytest.mark.asyncio
async def test_hash_raises_on_missing_survey(monkeypatch):
    _patch_ro(monkeypatch, sid=None, max_id=0, count=0)
    with pytest.raises(ValueError):
        await compute_input_hash("missing", "ar")


@pytest.mark.asyncio
async def test_hash_changes_when_date_window_added(monkeypatch):
    from datetime import datetime

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    a = await compute_input_hash("S-1", "ar")

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    b = await compute_input_hash(
        "S-1", "ar",
        date_from=datetime(2026, 1, 1),
        date_to=datetime(2026, 1, 31, 23, 59, 59),
    )

    assert a.sha256 != b.sha256


@pytest.mark.asyncio
async def test_hash_stable_for_same_window(monkeypatch):
    from datetime import datetime

    df = datetime(2026, 1, 1)
    dt = datetime(2026, 1, 31, 23, 59, 59)

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    a = await compute_input_hash("S-1", "ar", date_from=df, date_to=dt)

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    b = await compute_input_hash("S-1", "ar", date_from=df, date_to=dt)

    assert a.sha256 == b.sha256


@pytest.mark.asyncio
async def test_hash_differs_between_windows(monkeypatch):
    from datetime import datetime

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    jan = await compute_input_hash(
        "S-1", "ar",
        date_from=datetime(2026, 1, 1),
        date_to=datetime(2026, 1, 31, 23, 59, 59),
    )

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    feb = await compute_input_hash(
        "S-1", "ar",
        date_from=datetime(2026, 2, 1),
        date_to=datetime(2026, 2, 28, 23, 59, 59),
    )

    assert jan.sha256 != feb.sha256


@pytest.mark.asyncio
async def test_hash_changes_when_submissions_limit_changes(monkeypatch):
    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    a = await compute_input_hash("S-1", "ar", submissions_limit=100, submission_ids=["s1", "s2"])

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    b = await compute_input_hash("S-1", "ar", submissions_limit=50, submission_ids=["s1", "s2"])

    assert a.sha256 != b.sha256


@pytest.mark.asyncio
async def test_hash_stable_for_same_limit(monkeypatch):
    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    a = await compute_input_hash("S-1", "ar", submissions_limit=100, submission_ids=["s1", "s2"])

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    b = await compute_input_hash("S-1", "ar", submissions_limit=100, submission_ids=["s1", "s2"])

    assert a.sha256 == b.sha256


@pytest.mark.asyncio
async def test_hash_unlimited_differs_from_limited(monkeypatch):
    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    unlimited = await compute_input_hash("S-1", "ar")

    _patch_ro(monkeypatch, sid=1, max_id=100, count=50)
    limited = await compute_input_hash("S-1", "ar", submissions_limit=100, submission_ids=["s1"])

    assert unlimited.sha256 != limited.sha256
