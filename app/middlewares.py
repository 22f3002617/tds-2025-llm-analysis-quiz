import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        logger.info(f"Request ID: {request_id} - Start processing request: {request.url}")
        response = await call_next(request)
        logger.info(f"Request ID: {request_id} - Finished processing request")
        return response