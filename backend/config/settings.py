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
DATABASE_URL = os.getenv('DATABASE_URL', '')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': '',
        'OPTIONS': {},
    }
}

# Parse DATABASE_URL if present
if DATABASE_URL:
    import re
    # Parse: postgresql://user:password@host:port/dbname?sslmode=require
    pattern = r'postgresql://([^:]+):([^@]+)@([^:\/]+):?(\d+)?/([^?]+)(?:\?(.*))?'
    match = re.match(pattern, DATABASE_URL)
    if match:
        DATABASES['default'] = {
            'ENGINE': 'django.db.backends.postgresql',
            'USER': match.group(1),
            'PASSWORD': match.group(2),
            'HOST': match.group(3),
            'PORT': match.group(4) or '5432',
            'NAME': match.group(5),
            'OPTIONS': {
                'sslmode': 'require',
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
