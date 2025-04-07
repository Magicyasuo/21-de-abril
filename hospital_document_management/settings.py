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
    "127.0.0.1",
    "localhost",
    "192.168.2.23",
    ".192.168.2.",
    ".192.168.",  # Permite todas las IPs que comienzan con 192.168.x.x cambiar en produccion quitar

]


# Configuración CORS
CORS_ALLOW_ALL_ORIGINS = False
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1",
    "http://localhost",
    "http://192.168.2.23",
    "https://192.168.2.23",  # Agregar esquema HTTPS
    "http://192.168.*",  # Permite todas las subredes HTTP cambiar en produccion
    "https://192.168.*",  # Permite todas las subredes HTTPS cambiar en produccion, quitar
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
    "django_extensions",
    "documentos",
    "adminlte3",
    "adminlte3_theme",
    "corsheaders",
    "admin_interface",
    "colorfield",
    'axes',
    "guardian",
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
        "ENGINE": "mssql",
        "NAME": os.getenv("DB_NAME", "NombreDeTuDB"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "1433"),
        "USER": os.getenv("DB_USER", "usuario"),
        "PASSWORD": os.getenv("DB_PASSWORD", "contraseña"),
        "OPTIONS": {
            "driver": "ODBC Driver 17 for SQL Server",
        },
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
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

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

# Si en algún momento usas Azure Storage, activa y configura aquí:
# DEFAULT_FILE_STORAGE = "storages.backends.azure_storage.AzureStorage"
# AZURE_ACCOUNT_NAME = os.getenv("AZURE_ACCOUNT_NAME")
# AZURE_ACCOUNT_KEY = os.getenv("AZURE_ACCOUNT_KEY")
# AZURE_CONTAINER = os.getenv("AZURE_CONTAINER")
