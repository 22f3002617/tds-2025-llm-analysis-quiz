import logging
from fastapi import FastAPI, BackgroundTasks, Request, Depends
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.responses import JSONResponse

from agent.simple_agent import SimpleAgent
import config
from middlewares import RequestIDMiddleware
from setup_logger import setup as setup_logging

setup_logging()
logger = logging.getLogger(__name__)

### STARTS App setup
app = FastAPI()
app.add_middleware(RequestIDMiddleware)


# Note: This is to conver "Respond with HTTP 400 for invalid JSON" case
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid JSON payload"},
    )


### END APP SETUP

### STARTS Dependency Injection
agent = SimpleAgent(config.SYSTEM_PROMPT_RESPONSE_ID)

### END Dependency Injection

### STARTS API Models
class QuizRequest(BaseModel):
    email: str
    secret: str
    url: str


### END API Models

### STARTS Background Tasks
def solve_quiz(quiz: QuizRequest):
    # Placeholder for quiz processing logic
    logger.info(f"Start processing quiz from URL: {quiz.url} - ")
    ## TODO: will add the llm agent logic here
    agent.run(quiz_url=quiz.url, message="solve the quiz from scraped content")
    # This is a synchronous placeholder function
    logger.info(f"Finished processing quiz from URL: {quiz.url}")


### END Background Tasks

### STARTS API Endpoints
@app.post("/submit-quiz")
async def submit_quiz(request: Request, quiz: QuizRequest, background_tasks: BackgroundTasks):
    logger.info(f"Got quiz: {quiz} - (id: {request.state.request_id})")
    if quiz.secret != config.SECRET_KEY:
        return JSONResponse(content={"detail": "Invalid secret"}, status_code=403)

    # quiz_details = QuizRequestDetails(url=quiz.url, request_id=request.state.request_id)
    background_tasks.add_task(solve_quiz, quiz)

    return JSONResponse(content={"message": "success"}, status_code=200)


### END API Endpoints

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000)
    # TODO: on ran this in huggingface use port 7860
