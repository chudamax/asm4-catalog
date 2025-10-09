FROM python:3.11-slim
WORKDIR /app
COPY adapter.py /app/adapter.py
RUN python -m pip install --no-cache-dir requests
ENTRYPOINT ["python", "/app/adapter.py"]
