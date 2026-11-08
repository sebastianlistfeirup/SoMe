from types import SimpleNamespace

import pytest

from app.pipeline.approvals import set_pause
from app.pipeline.production import produce


def test_render_stops_at_ninety_percent_disk(db, monkeypatch):
    monkeypatch.setattr("app.pipeline.production.require_tools", lambda: None)
    monkeypatch.setattr("app.pipeline.production.shutil.disk_usage", lambda _path: SimpleNamespace(total=100, used=90, free=10))
    with pytest.raises(RuntimeError, match="disk_at_or_above_90"):
        produce(db, 1, True)


def test_emergency_stop_blocks_before_production(db):
    set_pause(db, True, "owner")
    with pytest.raises(RuntimeError, match="emergency_stop_active"):
        produce(db, 1, True)
