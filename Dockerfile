FROM python:3.11-slim

WORKDIR /app

# k6 for performance_baseline_mcp and the security k6 script (official apt repo).
# Best-effort: if this fails, the build still succeeds and only that one tool degrades
# (performance_baseline_mcp reports "k6 not installed" instead of crashing the server).
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && ( curl -fsSL https://dl.k6.io/key.gpg | gpg --dearmor -o /usr/share/keyrings/k6-archive-keyring.gpg \
         && echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" > /etc/apt/sources.list.d/k6.list \
         && apt-get update && apt-get install -y --no-install-recommends k6 \
         || echo "k6 install failed — continuing without it" ) \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY qaforge_mcp ./qaforge_mcp

RUN pip install --no-cache-dir . \
    && playwright install --with-deps chromium

ENV MCP_TRANSPORT=http
EXPOSE 8000

CMD ["python", "-m", "qaforge_mcp"]
