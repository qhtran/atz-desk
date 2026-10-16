"""Log có nhãn [DBG-INGEST-<LABEL>] trên mọi dòng."""
import logging
import sys

LOGGER = logging.getLogger("ingestion")


def setup(level: str = "INFO") -> None:
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(level)


def log(label: str, message: str, level: int = logging.INFO) -> None:
    LOGGER.log(level, "[DBG-INGEST-%s] %s", label, message)
