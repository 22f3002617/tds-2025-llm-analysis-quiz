import logging

from app import config
from pathlib import Path

def setup(filename: Path | None = None, level: int = logging.INFO) -> None:
    if filename is None:
        filename = config.LOGS_DIR / "app.log"

    # file logger
    logs_dir = config.LOGS_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(filename=str(filename), encoding="utf-8")
    file_handler.setLevel(level)

    # stream logger
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)

    logging.basicConfig(level=level,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=[file_handler, stream_handler], force=True)
