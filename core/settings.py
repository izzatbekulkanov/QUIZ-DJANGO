from pathlib import Path
# Simple JWT settings
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-1((^1n9a13z-6yge#o$-g$p9^p5r6$iohu(a!=l5i3h@*n5gb2'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

LOCAL_APPS = [
    'account',
    'question',
    'dashboard',
    'logs',
    'bot',  # Telegram bot app
]

ASGI_APPLICATION = 'core.asgi.application'

DYNAMIC_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
INSTALLED_APPS = LOCAL_APPS + DYNAMIC_APPS

INSTALLED_APPS += [
    'django_ckeditor_5',
    'common',
]

# CKEditor sozlamalari
customColorPalette = [
    {'color': 'hsl(4, 90%, 58%)', 'label': 'Red'},
    {'color': 'hsl(340, 82%, 52%)', 'label': 'Pink'},
    {'color': 'hsl(291, 64%, 42%)', 'label': 'Purple'},
    {'color': 'hsl(231, 48%, 48%)', 'label': 'Indigo'},
    {'color': 'hsl(207, 90%, 54%)', 'label': 'Blue'},
]

CKEDITOR_5_CUSTOM_CSS = None
CKEDITOR_5_CONFIGS = {
    'default': {
        'toolbar': [
            'bold', 'italic', 'link', 'bulletedList', 'numberedList', 'blockQuote', '|',
            'undo', 'redo', 'imageUpload', 'insertTable'
        ],
        'image': {
            'toolbar': [
                'imageTextAlternative', '|',
                'imageStyle:full', 'imageStyle:alignLeft', 'imageStyle:alignCenter', 'imageStyle:alignRight'
            ],
            'styles': [
                'full', 'alignLeft', 'alignCenter', 'alignRight'
            ],
        },
        'table': {
            'contentToolbar': ['tableColumn', 'tableRow', 'mergeTableCells', 'tableProperties'],
            'tableProperties': {
                'borderColors': [
                    {'color': 'hsl(4, 90%, 58%)', 'label': 'Red'},
                    {'color': 'hsl(340, 82%, 52%)', 'label': 'Pink'},
                    {'color': 'hsl(291, 64%, 42%)', 'label': 'Purple'}
                ],
                'backgroundColors': [
                    {'color': 'hsl(207, 90%, 54%)', 'label': 'Blue'},
                    {'color': 'hsl(231, 48%, 48%)', 'label': 'Indigo'},
                    {'color': 'hsl(262, 52%, 47%)', 'label': 'Deep Purple'}
                ],
            }
        },
        'mediaEmbed': {
            'previewsInData': True,
        },
    },
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'logs.middleware.LogMiddleware',
]

# settings.py
AUTH_USER_MODEL = 'account.CustomUser'

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.media',
                'django.contrib.messages.context_processors.messages',
                'common.context_processors.system_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Tashkent'  # Tashkent vaqti
USE_TZ = True  # Timezone-aware vaqtni ishlatish

USE_I18N = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Logging configuration
# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'handlers': {
#         'file': {
#             'level': 'DEBUG',
#             'class': 'logging.FileHandler',
#             'filename': BASE_DIR / 'logs/debug.log',
#         },
#     },
#     'loggers': {
#         'django': {
#             'handlers': ['file'],
#             'level': 'DEBUG',
#             'propagate': True,
#         },
#     },
# }

# Default email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your_email@gmail.com'
EMAIL_HOST_PASSWORD = 'your_email_password'

# REST framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# Login and Logout URLs
LOGIN_URL = '/account/login/'
LOGOUT_URL = '/account/logout/'
LOGIN_REDIRECT_URL = '/'  # Redirect after successful login
LOGOUT_REDIRECT_URL = '/account/login/'  # Redirect after logout
