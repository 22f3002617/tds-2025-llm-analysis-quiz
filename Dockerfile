FROM python:3.13
LABEL authors="22f3002671@ds.study.iitm.ac.in"

WORKDIR /tds-2025-llm-analysis-quiz
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["/usr/local/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]