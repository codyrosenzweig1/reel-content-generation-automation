# pipeline_modules/logkit.py
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "ts": datetime.utcnow().isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        # record.extra will be merged if present
        extra = getattr(record, "extra", {})
        if isinstance(extra, dict):
            base.update(extra)
        return json.dumps(base, ensure_ascii=False)

def get_event_logger(log_dir: Path, run_id: str) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / f"{run_id}.jsonl", encoding="utf-8")
    fh.setFormatter(JsonFormatter())
    lg = logging.getLogger(f"pipeline.{run_id}")
    lg.setLevel(logging.INFO)
    lg.handlers.clear()
    lg.addHandler(fh)
    return lg

def stamp(extra: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    out = dict(extra or {})
    out.update(kwargs)
    return out

def timed(lg: logging.Logger, extra: Dict[str, Any], step: str):
    """Context manager to time steps and log start and finish events."""
    class _Timer:
        def __enter__(self):
            self.t0 = time.time()
            lg.info("start", extra=stamp(extra, step=step))
            return self
        def __exit__(self, exc_type, exc, tb):
            dt = int((time.time() - self.t0) * 1000)
            if exc:
                lg.error("error", extra=stamp(extra, step=step, error_type=str(exc_type), error_message=str(exc), duration_ms=dt))
            else:
                lg.info("finish", extra=stamp(extra, step=step, duration_ms=dt))
    return _Timer()

def append_run_summary(csv_path: Path, row: Dict[str, Any]) -> None:
    import csv
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)