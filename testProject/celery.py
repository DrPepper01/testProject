import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'testProject.settings')

app = Celery('testProject')

# Читаем конфигурацию Celery из настроек Django (можно также .env)
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
