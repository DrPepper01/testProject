FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Скопировать requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копировать код
COPY . /app

# Cобрать статику
RUN python manage.py collectstatic --noinput

# Запуск через gunicorn (на продакшн)
CMD ["gunicorn", "testProject.wsgi:application", "--bind", "0.0.0.0:8000", "--workers=4"]
