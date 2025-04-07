# """
# WSGI config for hospital_document_management project.

# It exposes the WSGI callable as a module-level variable named ``application``.

# For more information on this file, see
# https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
# """

# import os

# from django.core.wsgi import get_wsgi_application

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hospital_document_management.settings")

# application = get_wsgi_application()


import os
from pathlib import Path
from dotenv import load_dotenv

# Define BASE_DIR de forma absoluta:
BASE_DIR = Path(__file__).resolve().parent.parent

# Construye la ruta completa al archivo .env
dotenv_path = os.path.join(BASE_DIR, ".env")

# Cargar el .env desde la ruta absoluta
load_dotenv(dotenv_path)

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hospital_document_management.settings")

application = get_wsgi_application()
