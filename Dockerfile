# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Устанавливаем curl для отладки
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Устанавливаем uv
RUN pip install uv

# Копируем зависимости
COPY pyproject.toml .

# Устанавливаем зависимости через uv
RUN uv pip install --system -r pyproject.toml

# Копируем исходный код
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]