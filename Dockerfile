FROM python:3.11-slim

WORKDIR /app

# k6 (static binary) for performance_baseline_mcp and the security k6 script
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://github.com/grafana/k6/releases/latest/download/k6-linux-amd64.tar.gz -o /tmp/k6.tar.gz \
    && tar -xzf /tmp/k6.tar.gz -C /tmp \
    && mv /tmp/k6-*/k6 /usr/local/bin/k6 \
    && rm -rf /tmp/k6* \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY qaforge_mcp ./qaforge_mcp

RUN pip install --no-cache-dir . \
    && playwright install --with-deps chromium

ENV MCP_TRANSPORT=http
EXPOSE 8000

CMD ["python", "-m", "qaforge_mcp"]
