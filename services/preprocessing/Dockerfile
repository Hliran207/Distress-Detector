FROM python:3.11-slim

WORKDIR /app

COPY services/preprocessing/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/distress_ml /opt/distress_ml
RUN pip install --no-cache-dir /opt/distress_ml && rm -rf /opt/distress_ml

COPY services/preprocessing/main.py .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
