# Используем лёгкий официальный образ Python
FROM python:3.11-slim

# Рабочая директория в контейнере
WORKDIR /app

# Не кешируем pyc и делаем вывод сразу
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Установим зависимости
RUN pip install --no-cache-dir --upgrade pip

# Скопируем файлы зависимостей (pyproject.toml, poetry.lock или requirements.txt)
COPY pyproject.toml ./

# Устанавливаем зависимости проекта
RUN pip install --no-cache-dir -e .

# Копируем всё приложение внутрь контейнера
COPY . .

# Порт, на котором работает uvicorn внутри контейнера
EXPOSE 8000

# Команда запуска
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
