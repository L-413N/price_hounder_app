# Используем образ с Python 3.11
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Устанавливаем зависимости
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Устанавливаем браузеры
RUN playwright install chromium

# Копируем код
COPY . .

# Запускаем тест
CMD ["python", "test_proxy.py"]