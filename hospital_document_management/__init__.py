from __future__ import absolute_import, unicode_literals

# Esto asegurará que la app siempre se importe cuando Django se inicie
# de forma que las tareas compartidas (@shared_task) usarán esta app.
from .celery import app as celery_app

__all__ = ('celery_app',)
