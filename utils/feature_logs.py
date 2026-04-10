import logging
from datetime import datetime
from pathlib import Path
from typing import Dict


DEFAULT_FEATURES = [
    "auth",
    "chat",
    "sessions",
    "providers",
    "agents",
    "skills",
    "memory",
    "evolution",
    "hooks",
    "traces",
    "ws",
    "system",
]


class IssueDispatchHandler(logging.Handler):
    """Forward warning/error logs from feature loggers to root total log."""

    def __init__(self, total_log_file: Path):
        super().__init__()
        self.total_log_file = total_log_file

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.levelno < logging.WARNING:
                return
            feature = record.name.replace("feature.", "")
            dispatched_message = f"[ISSUE_DISPATCH][{feature}] {record.getMessage()}"

            timestamp = datetime.now().strftime("%H:%M:%S")
            level = logging.getLevelName(record.levelno)
            line = f"{timestamp} [{level}] issue_dispatch: {dispatched_message}\n"
            with self.total_log_file.open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            # Never let dispatch logging break business logic
            pass


def setup_feature_loggers(log_dir: Path, features=None) -> Dict[str, logging.Logger]:
    features = features or DEFAULT_FEATURES
    feature_dir = log_dir / "features"
    feature_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    total_log_file = log_dir / f"agens_{today}.log"
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    loggers: Dict[str, logging.Logger] = {}
    for feature in features:
        logger_name = f"feature.{feature}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        file_path = feature_dir / f"{feature}_{today}.log"
        handler = logging.FileHandler(file_path, encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        dispatch_handler = IssueDispatchHandler(total_log_file=total_log_file)
        dispatch_handler.setLevel(logging.WARNING)
        logger.addHandler(dispatch_handler)

        loggers[feature] = logger

    return loggers


def get_feature_logger(feature: str) -> logging.Logger:
    return logging.getLogger(f"feature.{feature}")
