import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import Setting
from app.db.session import SessionLocal

db = SessionLocal()
try:
    setting = db.get(Setting, "worker_heartbeat")
    if not setting:
        raise SystemExit(1)
    stamp = datetime.fromisoformat(setting.value_json["at_utc"])
    if (datetime.now(timezone.utc) - stamp).total_seconds() > 120:
        raise SystemExit(1)
finally:
    db.close()
