FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir prometheus-client==0.21.0
WORKDIR /app
COPY exporter.py .
EXPOSE 9400
CMD ["python", "-u", "exporter.py"]
