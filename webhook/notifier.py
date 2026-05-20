import os
import time
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from config import (
    MAX_RETRIES,
    BASE_DELAY,
)
from webhook.priority_classifier import classify

load_dotenv(Path(__file__).parent.parent / ".env")

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

_pending_queue: dict[tuple, dict] = {}


def _escape_md(text: str) -> str:
    for ch in ("_", "*", "`", "["):
        text = str(text).replace(ch, f"\\{ch}")
    return text


def _format_batch_message(anomalies: list[dict], header_prefix: str = "🚨 *ANOMALIES DETECTED") -> str:
    count = len(anomalies)
    last_entry = anomalies[-1]
    ts_raw = last_entry.get("detected_at", "")

    try:
        ts = datetime.fromisoformat(ts_raw).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        ts = ts_raw or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"{header_prefix} ({count})*",
        "━━━━━━━━━━━━━━━━━"
    ]

    for entry in anomalies:
        name = entry.get("nama")
        if not name:
            url = str(entry.get("url", "?"))
            name = url.replace("https://", "").replace("http://", "").replace("www.", "").split(".")[0].capitalize()

        status_val = entry.get("status")
        http_code = entry.get("http_status_code", "?")
        rt_val = entry.get("response_time_ms", "?")

        if status_val == 1 and str(http_code) == "200":
            icon = "⚠️"
        else:
            icon = "❌"

        if isinstance(rt_val, (int, float)):
            rt_str = f"{rt_val}ms"
        else:
            rt_str = str(rt_val)

        line = f"{icon} {_escape_md(name)} | {_escape_md(http_code)} | {_escape_md(rt_str)}"
        lines.append(line)

    lines.append("━━━━━━━━━━━━━━━━━")
    lines.append(f"🕒 {_escape_md(ts)}")
    lines.append("🏷  Nexus Detector")

    return "\n".join(lines)


def _send_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[notifier] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload)
            if resp.status_code == 200 and resp.json().get("ok"):
                return True
            print(f"[notifier] Telegram error (attempt {attempt}): {resp.text[:200]}")
        except Exception as exc:
            print(f"[notifier] Request failed (attempt {attempt}): {exc}")

        if attempt < MAX_RETRIES:
            time.sleep(BASE_DELAY * (2 ** (attempt - 1)))

    print(f"[notifier] All {MAX_RETRIES} attempts failed.")
    return False


def send_critical(anomalies: list[dict]) -> int:
    """Send CRITICAL anomalies immediately with a 🔴 CRITICAL ALERT header."""
    if not anomalies:
        return 0
    text = _format_batch_message(anomalies, header_prefix="🔴 *CRITICAL ALERT")
    return 1 if _send_message(text) else 0


def queue_warning(entry: dict) -> None:
    """Add a WARNING anomaly to the pending queue. Same endpoint overwrites (no dupes)."""
    key = (entry.get("id_aplikasi"), entry.get("url"))
    _pending_queue[key] = entry


def flush_warnings() -> int:
    """Send all queued warnings as one digest, clear queue. Returns 1 if sent, 0 if empty."""
    if not _pending_queue:
        return 0

    entries = list(_pending_queue.values())
    _pending_queue.clear()

    text = _format_batch_message(entries)
    return 1 if _send_message(text) else 0


def notify_anomalies(anomalies: list[dict]) -> int:
    """Legacy entry point — routes via classifier. CRITICAL sent immediately, WARNING queued."""
    if not anomalies:
        return 0

    critical = [e for e in anomalies if classify(e) == "critical"]
    warnings = [e for e in anomalies if classify(e) == "warning"]

    sent = 0
    if critical:
        sent = send_critical(critical)

    for entry in warnings:
        queue_warning(entry)

    return sent
