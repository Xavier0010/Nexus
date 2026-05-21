import json
import logging
import signal
import sys
import threading
import time
from datetime import datetime, timedelta

from config import ANOMALY_LOG_PATH, FETCH_INTERVAL_SECONDS

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("nexus")

_shutdown = threading.Event()

def _clear_anomaly_log() -> None:
    try:
        with open(str(ANOMALY_LOG_PATH), "w") as f:
            json.dump([], f)
        log.info("[log-clear] Anomaly log cleared after summary generation.")
    except Exception as e:
        log.error(f"[log-clear] Failed to clear anomaly log: {e}")


def _detector_thread() -> None:
    log.info("[detector] Thread started.")
    from anomaly_detector.detector import AnomalyDetector
    from anomaly_detector.batch_detector import detect_database

    try:
        detector = AnomalyDetector()
        detect_database(detector)
    except Exception as e:
        log.error(f"[detector] Fatal error: {e}")
    finally:
        log.info("[detector] Thread exiting.")
        _shutdown.set()


def _retrain_thread() -> None:
    log.info("[retrain] Thread started. First retrain in 1 hour.")
    while not _shutdown.is_set():
        _interruptible_sleep(3600)
        if _shutdown.is_set():
            break

        log.info("[retrain] Starting scheduled retrain...")
        try:
            from anomaly_detector.retrain_scheduler import retrain_model
            retrain_model()
        except Exception as e:
            log.error(f"[retrain] Error during retrain: {e}")

    log.info("[retrain] Thread exiting.")


def _summary_thread() -> None:
    log.info("[summary] Thread started.")

    while not _shutdown.is_set():
        now = datetime.now()

        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        sleep_secs = (next_midnight - now).total_seconds()
        log.info(
            f"[summary] Next daily summary at "
            f"{next_midnight.strftime('%Y-%m-%d %H:%M:%S')} "
            f"({sleep_secs / 3600:.1f}h away)"
        )

        _interruptible_sleep(sleep_secs)
        if _shutdown.is_set():
            break

        log.info("[summary] Generating daily summary...")
        try:
            from report.daily_summary import daily_summary
            result = daily_summary()
            if result is not None:
                _clear_anomaly_log()
        except Exception as e:
            log.error(f"[summary] Daily summary error: {e}")

        if datetime.now().weekday() == 6:
            log.info("[summary] Sunday detected — generating weekly summary...")
            try:
                from report.weekly_summary import weekly_summary
                weekly_summary()
            except Exception as e:
                log.error(f"[summary] Weekly summary error: {e}")

    log.info("[summary] Thread exiting.")


def _interruptible_sleep(seconds: float) -> None:
    end = time.monotonic() + seconds
    while not _shutdown.is_set():
        remaining = end - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(remaining, 1.0))


def _handle_signal(signum, frame):
    log.info(f"\n[nexus] Signal {signum} received — shutting down gracefully...")
    _shutdown.set()


def main() -> None:
    log.info("=" * 50)
    log.info("  Welcome to Nexus!")
    log.info("  Loops: DB detection | hourly retrain | daily/weekly summary")
    log.info("=" * 50)

    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    threads = [
        threading.Thread(target=_detector_thread, name="NEXUS-Detector", daemon=True),
        threading.Thread(target=_retrain_thread,  name="NEXUS-Retrain",  daemon=True),
        threading.Thread(target=_summary_thread,  name="NEXUS-Summary",  daemon=True),
    ]

    for t in threads:
        t.start()

    while not _shutdown.is_set():
        time.sleep(1)

    log.info("[nexus] Goodbye.")
    sys.exit(0)


if __name__ == "__main__":
    main()
