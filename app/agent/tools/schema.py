_send_answer_custom_func_tool = {
    "type": "function",
    "name": "submit_answer",
    "strict": True,
    "description": "To submit the answer to the mentioned endpoint in the quiz page."
                   "For the answer submission you are going to give the value for answer field only."
                   "I Have email, secret and quiz url from constants.",
    "parameters": {
        "type": "object",
        "properties": {
            "answer_endpoint": {
                "type": "string",
                "description": "The endpoint URL in the page to submit the answer.",
            },
            "answer": {
                "type": "string",
                "description": "The answer to submit.",
            },
        },
        "required": ["answer_endpoint", "answer"],
        "additionalProperties": False,
    },
}

_transcribe_audio_custom_func_tool = {
    "type": "function",
    "name": "transcribe_audio",
    "strict": True,
    "description": "To transcribe audio content from a given audio file URL. We are using AssemblyAI for transcription.",
    "parameters": {
        "type": "object",
        "properties": {
            "file": {
                "type": "string",
                "description": "An URL, a local file (as path)",
            },
        },
        "required": ["file"],
        "additionalProperties": False,
    },
}

_playwright_scraping_custom_func_tool = {
    "type": "function",
    "name": "scrape_with_playwright",
    "strict": True,
    "description": "To scrape web page content using Playwright. If you want to execute any JavaScript on the page (for some kind of click or move actions), provide the script.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the web page to scrape.",
            },
            "script": {
                "type": ["string", "null"],
                "description": "Optional JavaScript code to execute on the page.",
            },
            "screenshot_required": {
                "type": "boolean",
                "description": "Whether a screenshot of the page is required, in case of visual content analysis.",
            },
        },
        "required": ["url", "script", "screenshot_required"],
        "additionalProperties": False,
    },
}

_download_file_custom_func_tool = {
    "type": "function",
    "name": "download_file",
    "strict": True,
    "description": "To download a file from a given URL and save it locally.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_name": {
                "type": "string",
                "description": "The name to save the downloaded file as.",
            },
            "url": {
                "type": "string",
                "description": "The URL of the file to download.",
            },
        },
        "required": ["file_name", "url"],
        "additionalProperties": False,
    },
}

_python_execute_code_custom_func_tool = {
    "type": "function",
    "name": "python_execute_code",
    "strict": True,
    "description": (
        "Execute Python code inside an isolated, read-only sandbox with strict safety limits. "
        "The code runs in a temporary directory and can only access files relative to the "
        "current working directory or within the dedicated 'download_cache/' directory. "
        "All file write operations, absolute file paths, and dangerous modules such as os, sys, "
        "subprocess, shutil, and pathlib are explicitly blocked. No system commands or "
        "subprocesses are allowed. A read-only archived copy of the submitted code is stored for reference."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "file_name": {
                "type": "string",
                "description": "Name to assign to the Python script in the archive and sandbox."
            },
            "code": {
                "type": "string",
                "description": "The Python code to execute within the sandbox."
            }
        },
        "required": ["file_name", "code"],
        "additionalProperties": False
    }
}

_get_local_file_custom_func_tool = {
    "type": "function",
    "name": "get_local_file",
    "strict": True,
    "description": "To get a local file's path and size, ensuring it is within allowed directories.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The path of the local file to access.",
            },
            "allow_large": {
                "type": "boolean",
                "description": "Whether to allow files larger than the safe size limit.",
            },
        },
        "required": ["file_path", "allow_large"],
        "additionalProperties": False,
    },
}

_get_video_frames_custom_func_tool = {
    "type": "function",
    "name": "get_video_frames",
    "strict": True,
    "description": "To extract video frames at a specified rate within a time slice and return them as Base64-encoded JPG strings. Maximum limit of 10 frames is enforced.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_name": {
                "type": "string",
                "description": "Path to the source video file.",
            },
            "start_sec": {
                "type": "number",
                "description": "The starting time (in seconds) for extraction. Defaults to 0.",
            },
            "end_sec": {
                "type": ["number", "null"],
                "description": "The ending time (in seconds) for extraction. If None, uses video end.",
            },
            "frame_rate": {
                "type": "number",
                "description": "The target number of frames to extract per second (e.g., 2 FPS).",
            },
        },
        "required": ["file_name", "start_sec", "end_sec", "frame_rate"],
        "additionalProperties": False,
    },
}