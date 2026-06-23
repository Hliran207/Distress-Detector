FROM python:3.11-slim

WORKDIR /app

RUN mkdir -p /home/app/.cache/huggingface

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/home/app/.cache/huggingface

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
