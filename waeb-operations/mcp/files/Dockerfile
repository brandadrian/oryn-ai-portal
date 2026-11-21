# Nur lesender Datei-MCP (SFTP) mit Streamable HTTP auf Port 8000 (/mcp) für Open WebUI.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
USER nobody
EXPOSE 8000
CMD ["python", "-u", "server.py"]
