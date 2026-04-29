FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/scripts/validate.sh
RUN chmod +x /app/scripts/start.sh

ENTRYPOINT ["/app/scripts/start.sh"]
