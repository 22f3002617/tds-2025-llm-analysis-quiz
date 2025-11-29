import logging
import os

import config


# this logger intended to log each agent request into a separate folder
class AgentLogger:
    _default_instance: "AgentLogger | None" = None

    def __init__(self, request_id):
        self.agent_log_dir = config.AGENT_LOG_BASE_PATH / request_id
        os.makedirs(self.agent_log_dir, exist_ok=True)
        log_file = self.agent_log_dir / f"agent.log"

        # file handler for logger
        filehandler = logging.FileHandler(log_file)
        filehandler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        filehandler.setFormatter(formatter)

        # stream logger handler
        streamhandler = logging.StreamHandler()
        streamhandler.setLevel(logging.INFO)
        streamhandler.setFormatter(formatter)


        self.logger = logging.getLogger(f"[AgentLogger::{request_id}]")
        self.logger.setLevel(logging.INFO)
        # Remove other handlers to avoid duplicate logs
        for handler in self.logger.handlers:
            self.logger.removeHandler(handler)
        self.logger.addHandler(filehandler)
        self.logger.addHandler(streamhandler)

        self.log(f"AgentLogger initialized, logging to {log_file}")

    def log(self, message: str, level: int = logging.INFO):
        # logger.log(level, message)
        self.logger.log(level, message)

    @classmethod
    def get_default(cls):
        if cls._default_instance is None:
            cls._default_instance = AgentLogger("default")
        return cls._default_instance
