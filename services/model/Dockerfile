FROM python:3.11-slim

WORKDIR /app

RUN mkdir -p /home/app/.cache/huggingface

COPY services/model/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/distress_ml /opt/distress_ml
RUN pip install --no-cache-dir "/opt/distress_ml[inference]"

COPY services/model/main.py .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/home/app/.cache/huggingface

CMD ["python", "main.py"]
