---
title: TDS 2025 llm analysis quiz
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
app_file: Dockerfile
pinned: false
---

# TDS 2025 LLM Analysis Quiz

An autonomous AI agent system designed to solve complex, multi-step quiz challenges using Large Language Models (LLMs), web scraping, and various data processing tools. This project was developed as part of the Tools in Data Science (TDS) course at IIT Madras.

## 📋 Project Overview

This project implements an intelligent quiz-solving agent that:
- Autonomously navigates through multi-step quiz challenges
- Scrapes web content using Playwright for dynamic content extraction
- Processes various data formats (CSV, images, audio, video)
- Executes Python code in a sandboxed environment for data analysis
- Transcribes audio using AssemblyAI
- Extracts frames from videos for visual analysis
- Submits answers and automatically progresses to the next quiz

The system uses OpenAI's Response API with custom function tools to create an autonomous agent capable of solving data science and analysis-based quizzes without human intervention.

## 🏗️ Project Architecture

### Core Components

1. **FastAPI Application** (`app/main.py`)
   - REST API endpoint `/submit-quiz` that accepts quiz requests
   - Processes requests asynchronously using background tasks
   - Includes request validation and error handling
   - Implements request ID middleware for tracking

2. **Simple Agent** (`app/agent/simple_agent.py`)
   - Autonomous agent using OpenAI's Response API
   - Manages conversation state and tool calls
   - Implements retry logic and timeout handling
   - Coordinates multiple quiz-solving strategies

3. **Custom Tools** (`app/agent/tools/`)
   - **Web Scraping**: Playwright-based scraping with screenshot support
   - **Audio Transcription**: AssemblyAI integration for audio processing
   - **File Downloads**: Secure file downloading and storage
   - **Python Execution**: Sandboxed Python code execution for data analysis
   - **Video Processing**: Frame extraction from video files
   - **Answer Submission**: Automated quiz answer submission

4. **Configuration Management** (`app/config.py`)
   - Environment-based configuration
   - Support for multiple LLM providers
   - Configurable timeouts and settings

### Agent Workflow

```
Quiz Request → Scrape Web Content → Analyze Question → 
Execute Tools (download, process, analyze) → Submit Answer → 
Check Response → Move to Next Quiz (or retry if incorrect)
```

## 🛠️ Technology Stack

- **Backend Framework**: FastAPI
- **LLM Provider**: OpenAI (GPT-4.5-mini or configurable)
- **Web Scraping**: Playwright
- **Audio Processing**: AssemblyAI
- **Data Processing**: Pandas, NumPy
- **Image/Video Processing**: OpenCV
- **Testing**: pytest
- **Containerization**: Docker
- **Package Management**: uv (modern Python package manager)

## 📦 Project Setup

### Prerequisites

- Python 3.13 or higher
- Docker (optional, for containerized deployment)
- uv package manager (recommended) or pip

### Installation

#### Option 1: Using uv (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd tds-2025-llm-analysis-quiz

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync dependencies
uv sync

# Install Playwright browsers
uv run playwright install chromium
```

#### Option 2: Using pip

```bash
# Clone the repository
git clone <repository-url>
cd tds-2025-llm-analysis-quiz

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### Environment Configuration

Create a `.env` file in the project root with the following variables:

```env
# Required
SECRET_KEY=your-secret-key-here
OPENAI_API_KEY=your-openai-api-key
ASSEMBLYAI_API_KEY=your-assemblyai-api-key
STUDENT_EMAIL_ID=your-email@example.com

# Optional (with defaults)
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4.5-mini
SYSTEM_PROMPT_RESPONSE_ID=  # Optional: pre-generated system prompt response ID
LLM_PROVIDER=openai
SCRAPER_TYPE=playwright
HEADLESS_SCRAPER=true
DEV=true
```

## 🚀 Running the Application

### Development Mode

#### Using uv:
```bash
# Run the FastAPI server
uv run -m app.main

# Or using uvicorn directly
uv run uvicorn app.main:app --host localhost --port 8000 --reload
```

#### Using pip:
```bash
# Activate virtual environment
source venv/bin/activate

# Run the server
python -m app.main

# Or using uvicorn
uvicorn app.main:app --host localhost --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### Production Mode (Docker)

```bash
# Build the Docker image
docker build -t tds-quiz-agent .

# Run the container
docker run -p 7860:7860 --env-file .env tds-quiz-agent
```

The API will be available at `http://localhost:7860`

### Running Tests

```bash
# Using uv
uv run pytest

# Using pip (with activated venv)
pytest

# Run specific test file
pytest test/test_sumbit_quiz.py

# Run with coverage
pytest --cov=app test/
```

## 📡 API Usage

### Submit Quiz Request

**Endpoint**: `POST /submit-quiz`

**Request Body**:
```json
{
  "email": "your-email@example.com",
  "secret": "your-secret-key",
  "url": "https://quiz-url.example.com/quiz"
}
```

**Success Response** (200):
```json
{
  "message": "success"
}
```

**Error Responses**:
- `400`: Invalid JSON payload
- `403`: Invalid secret key
- `422`: Validation error

### Example Usage

```bash
curl -X POST http://localhost:8000/submit-quiz \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "secret": "your-secret-key",
    "url": "https://tds-llm-analysis.s-anand.net/demo"
  }'
```

## 🧪 Testing

The project includes comprehensive tests in the `test/` directory:

- `test_sumbit_quiz.py`: Tests for the quiz submission endpoint
- `conftest.py`: Shared test fixtures and configuration

Run tests with:
```bash
uv run pytest -v
```

## 📁 Project Structure

```
tds-2025-llm-analysis-quiz/
├── app/                          # Main application code
│   ├── main.py                   # FastAPI application entry point
│   ├── config.py                 # Configuration management
│   ├── middlewares.py            # Request middleware
│   ├── setup_logger.py           # Logging configuration
│   └── agent/                    # Agent implementation
│       ├── simple_agent.py       # Main agent logic
│       ├── agent_logger.py       # Agent-specific logging
│       └── tools/                # Custom function tools
│           ├── schema.py         # Tool schemas for LLM
│           └── tools.py          # Tool implementations
├── data/                         # Data directory
│   ├── downloads/                # Downloaded files
│   ├── executed_python_files/    # Sandboxed Python execution
│   ├── logs/                     # Application logs
│   └── scraped/                  # Scraped content and agent logs
├── prompts/                      # System prompts
│   └── agent_system_prompt.txt   # Agent instructions
├── test/                         # Test suite
│   ├── conftest.py               # Test configuration
│   └── test_sumbit_quiz.py       # API tests
├── Dockerfile                    # Docker configuration
├── requirements.txt              # Python dependencies (pip)
├── pyproject.toml                # Project metadata (uv)
└── README.md                     # This file
```

## 🔧 Development Tools

### Helper Scripts

Located in `scripts/`:
- `run_server.sh`: Start the FastAPI server
- `test.sh`: Run the test suite
- `check_aipipe_usage.sh`: Check API usage statistics

### Logging

The application includes comprehensive logging:
- Request/response logging with unique request IDs
- Agent execution logs stored in `data/logs/`
- Per-quiz session logs in `data/scraped/`

View logs in real-time:
```bash
tail -f data/logs/app.log
```

## 🎯 Key Features

1. **Autonomous Operation**: The agent operates without human intervention, making decisions based on the quiz context
2. **Multi-modal Processing**: Handles text, images, audio, video, CSV, and other data formats
3. **Robust Error Handling**: Implements retry logic and fallback strategies
4. **Time Management**: Built-in timeout handling to ensure timely quiz completion
5. **Sandboxed Execution**: Safe execution of Python code for data analysis tasks
6. **Comprehensive Logging**: Detailed logs for debugging and analysis
7. **Scalable Architecture**: Background task processing for handling multiple requests

## 🔐 Security Considerations

- Secret key validation for all requests
- Sandboxed Python execution to prevent malicious code
- Path traversal protection for file operations
- File size limits to prevent resource exhaustion
- Input validation using Pydantic models

## 📊 Performance

- **Quiz Timeout**: 3 minutes per quiz question
- **Agent Timeout**: 1 hour maximum for entire session

## 🤝 Contributing

This is a college project repository. For evaluation purposes, please refer to the commit history and code quality.

## 📝 License

See LICENSE file for details.

## 👤 Author

**Student ID**: 22f3002671  
**Email**: 22f3002671@ds.study.iitm.ac.in  
**Course**: Tools in Data Science (TDS) 2025  
**Institution**: IIT Madras

## 🙏 Acknowledgments

- IIT Madras TDS Course Team
- OpenAI for LLM API
- AssemblyAI for audio transcription
- Playwright team for web automation tools

