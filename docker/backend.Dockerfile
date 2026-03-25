# --- Stage 1: builder ---
# Base image with Python 3.12 on Debian slim; used only to compile wheels / install deps.
FROM python:3.12-slim AS builder

WORKDIR /build

# Install API-only dependencies into /root/.local so we can copy them into the final stage.
COPY requirements-api.txt .
RUN pip install --user --no-cache-dir --no-warn-script-location -r requirements-api.txt

# --- Stage 2: runtime ---
# Fresh slim image keeps the final image small (no build tools, no pip cache from builder layers).
FROM python:3.12-slim AS runtime

WORKDIR /app

# Dedicated non-root account: processes should not run as root inside the container.
RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

# Copy installed packages from builder into the non-root user's home.
COPY --from=builder /root/.local /home/app/.local

# Ensure scripts like uvicorn are on PATH when we exec as `app`.
ENV PATH=/home/app/.local/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Application code owned by the runtime user.
COPY --chown=app:app api_main.py .
COPY --chown=app:app app ./app

USER app

EXPOSE 8000

# Bind to 0.0.0.0 so the server accepts traffic from outside the container (e.g. host port mapping).
CMD ["uvicorn", "api_main:app", "--host", "0.0.0.0", "--port", "8000"]
