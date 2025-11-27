import logging

import config

def setup():
    # file logger
    logs_dir = config.LOGS_DIR
    logs_dir.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(filename=logs_dir / "app.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    # stream logger
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=[file_handler, stream_handler], force=True)
