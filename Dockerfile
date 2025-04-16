# 1. Базовый образ — Python
FROM python:3.11-slim

# 2. Рабочая директория
WORKDIR /app

# 3. Копируем весь проект
COPY . .

# 4. Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# 5. Запуск бота
CMD ["python", "main.py"]
