import json
import os
from datetime import datetime

LOG_FILE_PATH = "static/run.jsonl"

def init_logger():
    os.makedirs("static", exist_ok=True)
    if not os.path.exists(LOG_FILE_PATH):
        open(LOG_FILE_PATH, "w", encoding="utf-8").close()

def log_event(data: dict):
    init_logger()
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **data
    }
    # Append line instantly and flush to disk
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        f.flush()