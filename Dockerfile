# Используем официальный образ Python
FROM python:3.9-slim

# Установим зависимости для работы с Git и другими инструментами
RUN apt-get update && apt-get install -y \
    git \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Установим необходимые библиотеки Python
RUN pip install --no-cache-dir aiogram requests beautifulsoup4 lxml cryptography

# Клонируем ваш репозиторий через HTTPS
RUN git clone https://github.com/bulatt57/KGEU_moodle.git /app

# Укажем рабочую директорию
WORKDIR /app

# Укажем команду для запуска бота
CMD ["python", "main.py"]
