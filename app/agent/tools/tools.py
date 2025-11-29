import logging
import mimetypes
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
import assemblyai as aai
import config


logger = logging.getLogger(__name__)


def scrape_with_playwright(url: str, script: str | None = None,
                           screenshot_required: bool = False,
                           headless: bool = True):
    content, script_result, screenshot_bytes = None, None, None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            page.goto(url)
            content = page.content()

            if screenshot_required:
                screenshot_bytes = page.screenshot()

            if script:
                script_result = page.evaluate(script)
            status = {"status": "success"}
    except Exception as e:
        logger.exception(f"[ERROR] Error while scraping the URL {url}: {str(e)}")
        status = {"status": "error", "error": str(e)}
    return status, content, script_result, screenshot_bytes


def submit_answer(quiz_url: str, answer_endpoint: str, answer: str):
    import requests
    try:
        response = requests.post(answer_endpoint,
                                 json={"answer": answer, "email": config.STUDENT_EMAIL_ID, "secret": config.SECRET_KEY,
                                       "url": quiz_url})
        return response.status_code, response.text
    except Exception as e:
        logger.exception(f"[ERROR] Error while submitting answer to {answer_endpoint}: {str(e)}")
        return 500, str(e)


aai.settings.api_key = config.ASSEMBLYAI_API_KEY
transcription_config = aai.TranscriptionConfig(speech_models=["universal"])
transcriber = aai.Transcriber(config=transcription_config)


def transcribe_audio(file: str):
    try:
        logger.info(f"[DEBUG] Audio transcription from file started... {file}")
        transcript = transcriber.transcribe(file)

        logger.info("[DEBUG] Audio transcription completed.")
        if transcript.status == "error":
            logger.info(f"[DEBUG] Transcription error: {transcript.error}")
            return {"error": f"Transcription error: {transcript.error}"}
        logger.info(f"[DEBUG] Transcription completed successfully: {transcript.text}")
        return {"transcription_text": transcript.text}
    except Exception as e:
        logger.exception(f"[DEBUG] Error decoding Base64", e)
        return {"error": f"Error decoding Base64: {e}"}


MAX_SAFE_SIZE = 10 * 1024 * 1024  # 25 MB

def download_file(file_name: str, url: str):
    target_path, mime_type, file_extension, size, error = None, None, None, None, None
    try:
        import requests
        import mimetypes
        import os

        download_dir = DOWNLOAD_DIR
        target_path = _safe_resolve_path(os.path.join(download_dir, file_name))

        if not _is_in_allowed_dirs(target_path):
            return {"error": "Invalid file_name: path escapes allowed directories."}

        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
        except Exception as e:
            return {"error": f"Download failed: {e}"}

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "wb") as f:
            f.write(response.content)

        size = os.path.getsize(target_path)
        mime_type, _ = mimetypes.guess_type(target_path)
        file_extension = os.path.splitext(target_path)[1]

        status = "success"
    except Exception as e:
        logger.exception(f"[ERROR] Error while downloading file from {url}: {str(e)}")
        status = "error"
        error = str(e)

    return {
            "status": status,
            "error": error,
            "url": url,
            "file_path": target_path,
            "file_name": file_name,
            "mime_type": mime_type,
            "file_extension": file_extension,
            "file_size": size,
        }

# List of directories the LLM is allowed to access
DOWNLOAD_DIR = str(config.project_path / "data" / "downloads")
ALLOWED_DIRS = {
    DOWNLOAD_DIR,
}


def _safe_resolve_path(path: str) -> str:
    return os.path.abspath(os.path.realpath(path))

def _is_in_allowed_dirs(path: str, allowed_dirs: set[str] | None = None) -> bool:
    """True only if path is inside one of ALLOWED_DIRS."""
    safe = _safe_resolve_path(path)

    if allowed_dirs is None:
        allowed_dirs = ALLOWED_DIRS

    for allowed in allowed_dirs:
        if safe.startswith(allowed + os.sep):
            return True
    return False

import cv2
import base64
import os
from typing import Optional, Dict, Any


def get_video_frames(
        file_name: str,
        start_sec: int = 0,
        end_sec: Optional[int] = None,
        frame_rate: int = 2
) -> Dict[str, Any]:
    """
    Extracts video frames at a specified rate within a time slice (start_sec to end_sec)
    and returns them as a list of Base64-encoded JPG strings.

    The function enforces a maximum limit of 10 frames to ensure efficient LLM processing.

    Args:
        file_name: Path to the source video file.
        start_sec: The starting time (in seconds) for extraction. Defaults to 0.
        end_sec: The ending time (in seconds) for extraction. If None, uses video end.
        frame_rate: The target number of frames to extract per second (e.g., 2 FPS).

    Returns:
        A dictionary containing the status, a list of base64 strings, and any error message.
    """

    # --- Configuration and Initialization ---
    MAX_FRAMES_LIMIT = 10
    frames_base64 = []
    error = {}

    # --- Boundary Try-Catch Block ---
    try:
        # 1. File and Video Check
        if not os.path.exists(file_name):
            error = {"error": f"File not found: {file_name}"}
            status = "error"
            # Return immediately to avoid unnecessary OpenCV initialization
            logger.error(f"stub: File not found: {file_name}")
            return {"status": status, "frames_base64": frames_base64} | error

        cap = cv2.VideoCapture(file_name)
        if not cap.isOpened():
            error = {"error": "Could not open video file. Check file path and codecs."}
            status = "error"
            logger.error(f"stub: Could not open video file: {file_name}")
            return {"status": status, "frames_base64": frames_base64} | error

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_video_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 2. Time-to-Frame Index Conversion (Precalculation)

        # Calculate the starting frame index
        start_frame_idx = int(start_sec * fps)

        # Calculate the ending frame index
        if end_sec is None:
            end_frame_idx = total_video_frames
        else:
            end_frame_idx = min(int(end_sec * fps), total_video_frames)

        # Calculate the frame interval (step size) based on desired frame_rate
        # We round to the nearest integer and ensure it's at least 1
        frame_interval = max(1, int(round(fps / frame_rate)))

        # Ensure start index is within bounds
        if start_frame_idx >= total_video_frames:
            error = {"error": f"Start time ({start_sec}s) is beyond the video's total duration."}
            status = "error"
            cap.release()
            logger.error(f"Start time ({start_sec}s) is beyond the video's total duration.")
            return {"status": status, "frames_base64": frames_base64} | error

        # 3. Main Extraction Loop
        current_frame_idx = start_frame_idx

        while current_frame_idx < end_frame_idx:
            # Check and enforce the MAX_FRAMES_LIMIT before reading the frame
            if len(frames_base64) >= MAX_FRAMES_LIMIT:
                error = {
                    "error": f"Maximum frame limit ({MAX_FRAMES_LIMIT}) reached. Only the first {MAX_FRAMES_LIMIT} frames were extracted from the time slice."}
                break

            # Explicitly set the position to the precalculated index
            cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame_idx)
            ret, frame = cap.read()

            if not ret:
                # Break if the read fails (e.g., end of file, corrupted frame)
                break

            # Process the frame: Encode to JPG and then Base64
            _, buffer = cv2.imencode('.jpg', frame)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            frames_base64.append(frame_base64)

            # Advance the frame index by the calculated interval for the next iteration
            current_frame_idx += frame_interval

        cap.release()
        status = "success"

    except Exception as e:
        # Generic catch for unexpected errors (e.g., memory, codec issues)
        status = "error"
        error = {"error": str(e)}
        logger.exception(f"Error while extracting video frames: {str(e)}")

    # Use dictionary union (|) to combine the result and error dictionary
    return {"status": status, "frames_base64": frames_base64} | error

def get_local_file(file_path: str, allow_large: bool):
    try:
        safe = _safe_resolve_path(file_path)

        # Core safety: path containment
        if not _is_in_allowed_dirs(safe):
            logger.error(f"File path: {file_path} is not in the allowed directory.")
            return {
                "error": "Access denied. File is outside allowed directories.",
                "file_path": file_path,
                "allowed_dirs": list(ALLOWED_DIRS),
            }

        # Normal checks
        if not os.path.exists(safe):
            logger.error(f"File path: {file_path} is not in the allowed directory.")
            return {"error": f"File not found: {file_path}"}

        size = os.path.getsize(safe)
        mime, _ = mimetypes.guess_type(safe)

        if mime not in config.OPENAI_SUPPORTED_FILE_MIME_TYPES:
            logger.error(f"Unsupported file type: {mime} for file {file_path}.")
            return {
                "error": f"Unsupported file type: {mime}. Supported types: {config.OPENAI_SUPPORTED_FILE_MIME_TYPES}",
                "file_path": safe,
                "file_size": size,
                "mime_type": mime or "application/octet-stream",
            }

        if size > MAX_SAFE_SIZE and not allow_large:
            logger.error(f"File size: {size} > {MAX_SAFE_SIZE} bytes.")
            return {
                "error": "File too large. Set allow_large=true to override.",
                "file_path": safe,
                "file_size": size,
                "max_safe_size": MAX_SAFE_SIZE,
                "mime_type": mime or "application/octet-stream",
            }

        return {
            "file_path": safe,
            "file_size": size,
            "mime_type": mime or "application/octet-stream",
        }
    except Exception as e:
        logger.exception(f"Error accessing local file {file_path}: {str(e)}")
        return {"error": str(e)}

# Note the use of {download_dir_name} and {code} as placeholders for f-string formatting
# during the function call.
SAFE_WRAPPER_TEMPLATE = r'''
# IMPORTANT: Only essential modules are imported to prevent module leakage.
import builtins
import os
import importlib 

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------
# Value injected dynamically
DOWNLOAD_DIR = "{download_dir_name}" 
# Ensure DOWNLOAD_DIR ends with a separator for correct path checking
ALLOWED_PREFIX = os.path.join(DOWNLOAD_DIR, '') 

# ------------------------------------------------------------
# Safe open: Only allows relative paths in current dir OR paths 
# prefixed by the ALLOWED_PREFIX. No writing.
# ------------------------------------------------------------
_real_open = open
def safe_open(path, mode="r", *args, **kwargs):
    # Check for absolute paths
    if os.path.isabs(path):
        raise PermissionError("Absolute paths not allowed.")

    # Check for forbidden write operations
    if any(m in mode for m in ("w", "a", "+", "x")):
        raise PermissionError("Write operations not allowed.")

    # Convert the path to its canonical form for consistent checking
    normalized_path = os.path.normpath(path)

    # We allow the path if it starts with the download prefix or doesn't escape 
    # the current directory ('..'). This provides a good balance of safety and utility.
    is_allowed_path = (
        normalized_path.startswith(ALLOWED_PREFIX) or 
        not normalized_path.startswith(os.pardir) 
    )

    if not is_allowed_path:
        # Final restrictive check if the initial check fails
        if not (normalized_path.startswith('./') or normalized_path.startswith(ALLOWED_PREFIX)):
            raise PermissionError(f"Access restricted. Only paths relative to CWD or starting with '{DOWNLOAD_DIR}' are allowed.")

    return _real_open(path, mode, *args, **kwargs)

# ------------------------------------------------------------
# Block dangerous modules
# ------------------------------------------------------------
_blocked = {{"os", "sys", "subprocess", "shutil", "pathlib"}}

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name in _blocked:
        raise ImportError(f"Import of '{{name}}' is blocked.")
    return importlib.__import__(name, globals, locals, fromlist, level)

# ------------------------------------------------------------
# Apply restrictions
# ------------------------------------------------------------
builtins.open = safe_open
builtins.__import__ = safe_import

# ------------------------------------------------------------
# Execute user code inside wrapper with restricted globals
# ------------------------------------------------------------
USER_CODE = """
{code}
"""
# Execute user code with a custom, restricted namespace.
# By passing only {'__builtins__': builtins}, we prevent the user code
# from accessing 'os', 'sys', 'importlib', etc., which are in the wrapper's scope.
exec(USER_CODE, {'__builtins__': builtins})
'''


# --- MAIN EXECUTION FUNCTION ---

# NOTE: The provided function name is slightly different, adapting it here.
def execute_python_in_sandbox(file_name: str, code: str) -> Dict[str, Any]:
    """Executes Python code in a temp sandbox with the secure wrapper."""

    # Define the name of the allowed download directory within the sandbox
    DOWNLOAD_DIR_NAME = "download_cache"

    stdout, stderr, returncode, archive_path, sandbox_path, error = None, None, None, None, None, None
    try:
        # ----------------------------------------------------
        # 1. Archive permanent copy (Mocked safe path logic)
        # ----------------------------------------------------
        archive_dir = Path(config.project_path) / "data" / "executed_python_files"
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Mocking the original logic that ensures the path is safe
        raw_path = archive_dir / file_name
        archive_path = Path(_safe_resolve_path(str(raw_path)))

        if not _is_in_allowed_dirs(str(archive_path), {str(archive_dir), }):
            return {"error": "Invalid file_name: escapes archive directory."}

        archive_path.write_text(code)

        # ----------------------------------------------------
        # 2. Sandbox directory for execution
        # ----------------------------------------------------
        # Use a real tempfile creation, but MockPath for type consistency
        sandbox = Path(tempfile.mkdtemp(prefix="pyexec_"))
        exec_path = sandbox / file_name

        # Create the allowed download directory inside the sandbox
        # This is where the code will be allowed to read files from
        (sandbox / DOWNLOAD_DIR_NAME).mkdir()

        # Write wrapper+code in sandbox ONLY
        # Crucial step: Inject both the download directory name and the user code
        final_wrapped_code = SAFE_WRAPPER_TEMPLATE.format(
            download_dir_name=DOWNLOAD_DIR_NAME,
            code=code
        )
        exec_path.write_text(final_wrapped_code)

        # ----------------------------------------------------
        # 3. Execute inside sandbox only
        # ----------------------------------------------------
        result = subprocess.run(
            ["python3", str(exec_path)],
            cwd=str(sandbox),
            capture_output=True,
            text=True,
            timeout=15,
        )

        stdout = result.stdout
        stderr = result.stderr
        returncode = result.returncode
        archive_path = str(archive_path)
        sandbox_path = str(exec_path)

        status = "success"
    except Exception as e:
        status = "error"
        error = {"error": str(e)}
        logger.exception(f"Error executing Python in sandbox: {str(e)}")

    return {
        "status": status,
        "error": error,
        "stdout": stdout,
        "stderr": stderr,
        "returncode": returncode,
        "archive_path": archive_path,
        "sandbox_path": sandbox_path
    }