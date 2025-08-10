FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1         PYTHONUNBUFFERED=1

# Workdir
WORKDIR /app

# System deps (optional but good practice for manylinux wheels fallback)
RUN apt-get update && apt-get install -y --no-install-recommends         build-essential         && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY . /app

# Expose port for webhook
ENV PORT=8080
EXPOSE 8080

# Default to webhook mode (override with USE_WEBHOOK=0 for polling)
ENV USE_WEBHOOK=1

# Launch
CMD ["python", "bot.py"]
