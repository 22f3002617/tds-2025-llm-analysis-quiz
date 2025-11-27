import os
from pathlib import Path

from dotenv import load_dotenv

project_path: Path = Path(__file__).resolve().parent.parent
load_dotenv(project_path / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
SCRAPER_TYPE = os.getenv("SCRAPER_TYPE", "playwright")
HEADLESS_SCRAPER = os.getenv("HEADLESS_SCRAPER", "false").lower == "true"
TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", 60 * 60 * 1000))  # 1 hour
LLM_AGENT_SYSTEM_PROMPT = (project_path / "prompts" / "agent_system_prompt.txt").read_text(encoding="utf-8")
STUDENT_EMAIL_ID = "22f3002671@ds.study.iitm.ac.in"
AGENT_LOG_BASE_PATH = project_path / "data" / "scraped"
LOGS_DIR = project_path / "data" / "logs"
