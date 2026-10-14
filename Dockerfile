FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY bot ./bot
COPY scripts ./scripts
COPY web ./web
COPY data/sources.json data/concepts.json data/quiz.json ./data/
COPY data/corpus ./data/corpus
COPY data/index ./data/index

# Модель эмбеддингов скачивается при сборке образа, чтобы старт был быстрым
RUN python -c "from app.rag.index import get_embedder; get_embedder()"

# Непривилегированный пользователь
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
