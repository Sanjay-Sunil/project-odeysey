"""
Django settings for Rare Disease Federated Detection MVP.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(PROJECT_ROOT / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-change-me-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = ['*']

# Application definition
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'corsheaders',
    'core',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

# CORS — wide open for hackathon speed
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_METHODS = ['GET', 'POST', 'OPTIONS']
CORS_ALLOW_HEADERS = ['*']

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database — Neon Postgres
# Prefer DATABASE_URL_UNPOOLED (direct connection) for pgvector compatibility
DATABASE_URL = os.getenv('DATABASE_URL_UNPOOLED', os.getenv('DATABASE_URL', ''))

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': '',
        'OPTIONS': {},
    }
}

# Parse DATABASE_URL using urllib.parse for robustness with Neon connection strings
if DATABASE_URL:
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(DATABASE_URL)
    if parsed.scheme in ('postgresql', 'postgres'):
        query_params = parse_qs(parsed.query)
        sslmode = query_params.get('sslmode', ['require'])[0]
        DATABASES['default'] = {
            'ENGINE': 'django.db.backends.postgresql',
            'USER': parsed.username or '',
            'PASSWORD': parsed.password or '',
            'HOST': parsed.hostname or 'localhost',
            'PORT': str(parsed.port or 5432),
            'NAME': parsed.path.lstrip('/'),
            'OPTIONS': {
                'sslmode': sslmode,
            },
        }

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = False
USE_TZ = True

# Static files
STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
# Project-specific settings
# ============================================================

# LLM Provider: "groq" or "gemini"
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'groq')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Embedding Provider: "local" (all-MiniLM-L6-v2) or "gemini"
EMBEDDING_PROVIDER = os.getenv('EMBEDDING_PROVIDER', 'local')

# Hospital ID to local table name mapping
HOSPITAL_TABLE_MAP = {
    'HOSP_TVM_01': 'hospital_tvm_cases',
    'HOSP_KCH_01': 'hospital_kochi_cases',
    'HOSP_KZK_01': 'hospital_kzk_cases',
}
