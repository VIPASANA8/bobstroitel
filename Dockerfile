FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY online ./online
COPY app ./app
COPY cash ./cash
COPY admin_bot ./admin_bot
COPY tools ./tools
COPY static ./static
COPY bots ./bots
COPY poker ./poker

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
