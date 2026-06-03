FROM python:3.11-slim

WORKDIR /app

RUN mkdir -p /home/app/.cache/huggingface app/ml && \
    touch app/__init__.py app/ml/__init__.py

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py ensemble.py escalation.py preprocess.py ./
RUN cp escalation.py app/ml/escalation.py && \
    cp preprocess.py app/ml/preprocess.py

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/home/app/.cache/huggingface

CMD ["python", "main.py"]
