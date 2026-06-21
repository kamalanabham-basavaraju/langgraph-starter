FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/home/agent

WORKDIR /app

RUN addgroup --system agent && adduser --system --ingroup agent agent
RUN mkdir -p /home/agent && chown agent:agent /home/agent

RUN apt-get update \
  && apt-get install -y --no-install-recommends git nodejs npm \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY package*.json ./
RUN npm ci --omit=dev

COPY --chown=agent:agent . .
RUN chmod +x /app/scripts/docker-entrypoint.sh
USER agent

EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=2)"

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
