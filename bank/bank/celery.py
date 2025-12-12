import os 
from celery import Celery

# set the default django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bank.settings')

# create the celery model
app = Celery('bank')

app.config_from_object('django.conf:settings', namespace='CELERY')

# load task module from all registered django app configs
app.autodiscover_tasks()


# for celery beat
app.conf.beat_scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'

