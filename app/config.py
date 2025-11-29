import os
from pathlib import Path

from dotenv import load_dotenv

project_path: Path = Path(__file__).resolve().parent.parent
if os.environ.get("DEV", "true").lower() == "true":
    load_dotenv(project_path / ".env")

SECRET_KEY = os.getenv("SECRET_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
SYSTEM_PROMPT_RESPONSE_ID = os.getenv("SYSTEM_PROMPT_RESPONSE_ID", None)
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-5-mini")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
SCRAPER_TYPE = os.getenv("SCRAPER_TYPE", "playwright")
HEADLESS_SCRAPER = os.getenv("HEADLESS_SCRAPER", "true").lower == "true"
AGENT_TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", 60 * 60 * 1000))  # 1 hour
QUIZ_TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", 3 * 60 * 1000))  # 3 min
LLM_AGENT_SYSTEM_PROMPT = (project_path / "prompts" / "agent_system_prompt.txt").read_text(encoding="utf-8")
STUDENT_EMAIL_ID = "22f3002671@ds.study.iitm.ac.in"
AGENT_LOG_BASE_PATH = project_path / "data" / "scraped"
LOGS_DIR = project_path / "data" / "logs"

# This meant to be used for response api files working direc message itself, not for files API
OPENAI_SUPPORTED_FILE_MIME_TYPES  = {
    'application/pdf',
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/gif'
}
