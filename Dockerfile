FROM python:3.13-slim
LABEL authors="22f3002671@ds.study.iitm.ac.in"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
ENV PYTHON_PATH=/app

CMD ["/usr/local/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]