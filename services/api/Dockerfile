FROM python:3.11-slim

WORKDIR /app

RUN mkdir -p /home/app/.cache/huggingface

COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/distress_ml /opt/distress_ml
RUN pip install --no-cache-dir "/opt/distress_ml[inference]" && rm -rf /opt/distress_ml

COPY services/api/ .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/home/app/.cache/huggingface

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
