FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
        fastapi \
        "uvicorn[standard]" \
        jinja2 \
        pyyaml \
        ytmusicapi \
        yt-dlp \
        httpx

RUN useradd -m app
USER app
WORKDIR /app

COPY app/ .

EXPOSE 6969 6970
CMD ["python3", "main.py"]
