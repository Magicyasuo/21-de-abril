"""
Django settings for hospital_document_management project.
Generado por 'django-admin startproject' usando Django 5.1.3.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ====================================================================================
# SEGURIDAD
# ====================================================================================
SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-dummy-key")
DEBUG = True # En producción, cámbialo a False

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '.ngrok-free.app', # Permite cualquier subdominio de ngrok-free.app
    "192.168.2.23",
    ".192.168.2.",
]


# Configuración CORS
CORS_ALLOW_ALL_ORIGINS = False
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1",
    "http://localhost",
    "http://192.168.2.23",
    "https://192.168.2.23",  # Agregar esquema HTTPS
    "https://*.ngrok-free.app", # Añadido para permitir orígenes ngrok seguros
]

CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1",
    "http://localhost",
    "http://192.168.2.23",
    "https://192.168.2.23",  # Agregar esquema HTTPS
]


# Ajusta si no quieres que embeban el sitio (Clickjacking):
X_FRAME_OPTIONS = "DENY"

# ====================================================================================
# APLICACIONES Y MIDDLEWARE
# ====================================================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_extensions",
    "documentos",
    "widget_tweaks",
    "adminlte3",
    "adminlte3_theme",
    "corsheaders",
    "admin_interface",
    "colorfield",
    'axes',
    "guardian",
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'correspondencia',
    'crispy_forms',          # <-- Añadir esta línea
    'crispy_bootstrap5'     # <-- Añadir esta línea
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware", # Middleware de Allauth
]

ROOT_URLCONF = "hospital_document_management.urls"

WSGI_APPLICATION = "hospital_document_management.wsgi.application"

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
    "guardian.backends.ObjectPermissionBackend",
)
# bloqueo de usuario por exceder numeros de intentos
# Número de intentos permitidos
AXES_FAILURE_LIMIT = 6

# Bloquear cuando se alcance el límite
AXES_LOCK_OUT_AT_FAILURE = True

# Tiempo de bloqueo (ejemplo: 1 hora)
# Acepta un objeto timedelta, por ejemplo:
from datetime import timedelta
AXES_COOLOFF_TIME = timedelta(hours=0.2)  # Ajusta según tu preferencia

# Si solo quieres bloquear por nombre de usuario (no por IP):
AXES_ONLY_USER_FAILURES = True

# ====================================================================================
# BASE DE DATOS
# ====================================================================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}

# ====================================================================================
# VALIDACIÓN DE CONTRASEÑAS
# ====================================================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ====================================================================================
# INICIO DE SESIÓN
# ====================================================================================
LOGIN_URL = "/registros/login/"
LOGOUT_REDIRECT_URL = "/registros/login/"
LOGIN_REDIRECT_URL = "/registros/welcome/"

# ====================================================================================
# INTERNACIONALIZACIÓN
# ====================================================================================
LANGUAGE_CODE = "es"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

# ====================================================================================
# ARCHIVOS ESTÁTICOS Y MEDIA
# ====================================================================================
STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "documentos" / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ====================================================================================
# LOGGING
# ====================================================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django.db.backends": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}

# ====================================================================================
# TEMPLATES
# ====================================================================================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "documentos" / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ====================================================================================
# OTRAS CONFIGURACIONES
# ====================================================================================
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000  # Ajusta según tu caso

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"



# ====================================================================================
# CONFIGURACIÓN DE CELERY
# ====================================================================================
# Dirección del broker (Redis en este caso)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
# Dirección del backend de resultados (también Redis)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
# Formato de contenido aceptado para las tareas
CELERY_ACCEPT_CONTENT = ['json']
# Serializador para las tareas
CELERY_TASK_SERIALIZER = 'json'
# Serializador para los resultados de las tareas
CELERY_RESULT_SERIALIZER = 'json'
# Zona horaria para la programación de tareas
CELERY_TIMEZONE = TIME_ZONE # Usar la misma que Django

# Configuración de Celery Beat (para tareas periódicas)
CELERY_BEAT_SCHEDULE = {
    'procesar-emails-cada-5-minutos': {
        'task': 'correspondencia.tasks.procesar_emails_periodico', # Nombre completo de la tarea
        'schedule': 300.0,  # Ejecutar cada 300 segundos (5 minutos)
        # 'args': (16, 16), # Argumentos posicionales para la tarea (si los necesita)
        # 'kwargs': {'param': 'valor'}, # Argumentos de palabra clave (si los necesita)
    },
    # Puedes añadir más tareas periódicas aquí
    # 'otra-tarea-diaria': {
    #     'task': 'otra_app.tasks.tarea_diaria',
    #     'schedule': crontab(hour=7, minute=30), # Ejecutar todos los días a las 7:30 AM
    # },
}

# Opcional: Mejorar el manejo de resultados y estados
CELERY_RESULT_EXPIRES = timedelta(days=1) # Tiempo que se guardan los resultados
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_SEND_SENT_EVENT = True

# Opcional: Si usas Redis como backend, puedes ajustar la configuración de visibilidad
# CELERY_BROKER_TRANSPORT_OPTIONS = {'visibility_timeout': 3600} # 1 hora (en segundos)

# Asegúrate de importar timedelta si usas crontab o result_expires
from datetime import timedelta
from celery.schedules import crontab

# Si en algún momento usas Azure Storage, activa y configura aquí:
# DEFAULT_FILE_STORAGE = "storages.backends.azure_storage.AzureStorage"
# AZURE_ACCOUNT_NAME = os.getenv("AZURE_ACCOUNT_NAME")
# AZURE_ACCOUNT_KEY = os.getenv("AZURE_ACCOUNT_KEY")
# AZURE_CONTAINER = os.getenv("AZURE_CONTAINER")

# ====================================================================================
# CONFIGURACIÓN DE CORREO ELECTRÓNICO (SMTP - Gmail)
# ====================================================================================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'hospitalsararecolombia@gmail.com' # Tu dirección de correo
EMAIL_HOST_PASSWORD = 'nrqxthjfdfejjipz' # Tu contraseña de aplicación (NO la contraseña normal)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER # La dirección que aparecerá como remitente por defecto
