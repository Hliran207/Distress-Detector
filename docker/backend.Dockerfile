# --- Stage 1: builder ---
    FROM python:3.12-slim AS builder

    WORKDIR /build
    
    RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ && \
        rm -rf /var/lib/apt/lists/*
    
    COPY requirements-api.txt .
    RUN pip install --user --no-cache-dir --no-warn-script-location \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r requirements-api.txt
    
    # --- Stage 2: runtime ---
    FROM python:3.12-slim AS runtime
    
    WORKDIR /app
    
    RUN groupadd --system app && \
        useradd --system --gid app --create-home --home-dir /home/app app
    
    COPY --from=builder /root/.local /home/app/.local
    
    ENV PATH=/home/app/.local/bin:$PATH
    ENV PYTHONDONTWRITEBYTECODE=1
    ENV PYTHONUNBUFFERED=1
    # Point HuggingFace cache to a directory the app user owns
    ENV HF_HOME=/home/app/.cache/huggingface
    
    # Create the cache directory and give ownership to app user
    # Must be done BEFORE switching to USER app
    RUN mkdir -p /home/app/.cache/huggingface && \
        chown -R app:app /home/app/.cache
    
    COPY --chown=app:app api_main.py .
    COPY --chown=app:app app ./app
    
    USER app
    
    EXPOSE 8000
    
    CMD ["uvicorn", "api_main:app", "--host", "0.0.0.0", "--port", "8000"]