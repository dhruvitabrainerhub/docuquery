import os
from celery import Celery

#tell celery which django settings to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE","DocuQuery.settings")

#create celery application
app = Celery("DocuQuery")

#load configuration from django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

#automatically discover tasks.py from installed apps
app.autodiscover_tasks()