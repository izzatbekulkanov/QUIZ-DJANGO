from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .env import env, env_bool, env_int, env_list, load_env_file


BASE_DIR = Path(__file__).resolve().parent.parent
load_env_file(BASE_DIR / ".env")

DEFAULT_SECRET_KEY = "django-insecure-local-dev-only-change-me"

SECRET_KEY = env("DJANGO_SECRET_KEY", DEFAULT_SECRET_KEY) or DEFAULT_SECRET_KEY
DEBUG = env_bool("DJANGO_DEBUG", default=True)

if not DEBUG and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in .env before running with DJANGO_DEBUG=False.")

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=["*"] if DEBUG else ["localhost", "127.0.0.1"],
)

ASGI_APPLICATION = "core.asgi.application"

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_ckeditor_5",
    "rest_framework",
    "rest_framework_simplejwt",
]

LOCAL_APPS = [
    "apps.common",
    "apps.account",
    "apps.question",
    "apps.dashboard",
    "apps.logs",
    "apps.bot",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

customColorPalette = [
    {"color": "hsl(4, 90%, 58%)", "label": "Red"},
    {"color": "hsl(340, 82%, 52%)", "label": "Pink"},
    {"color": "hsl(291, 64%, 42%)", "label": "Purple"},
    {"color": "hsl(231, 48%, 48%)", "label": "Indigo"},
    {"color": "hsl(207, 90%, 54%)", "label": "Blue"},
]

CKEDITOR_5_CUSTOM_CSS = None
CKEDITOR_5_CONFIGS = {
    "default": {
        "toolbar": [
            "bold",
            "italic",
            "link",
            "bulletedList",
            "numberedList",
            "blockQuote",
            "|",
            "undo",
            "redo",
            "imageUpload",
            "insertTable",
        ],
        "image": {
            "toolbar": [
                "imageTextAlternative",
                "|",
                "imageStyle:full",
                "imageStyle:alignLeft",
                "imageStyle:alignCenter",
                "imageStyle:alignRight",
            ],
            "styles": [
                "full",
                "alignLeft",
                "alignCenter",
                "alignRight",
            ],
        },
        "table": {
            "contentToolbar": ["tableColumn", "tableRow", "mergeTableCells", "tableProperties"],
            "tableProperties": {
                "borderColors": [
                    {"color": "hsl(4, 90%, 58%)", "label": "Red"},
                    {"color": "hsl(340, 82%, 52%)", "label": "Pink"},
                    {"color": "hsl(291, 64%, 42%)", "label": "Purple"},
                ],
                "backgroundColors": [
                    {"color": "hsl(207, 90%, 54%)", "label": "Blue"},
                    {"color": "hsl(231, 48%, 48%)", "label": "Indigo"},
                    {"color": "hsl(262, 52%, 47%)", "label": "Deep Purple"},
                ],
            },
        },
        "mediaEmbed": {
            "previewsInData": True,
        },
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.administrator.middleware.AdministratorAccessMiddleware",
    "apps.logs.middleware.LogMiddleware",
]

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default=[
        "https://webtest.namspi.uz",
        "http://webtest.namspi.uz",
        "https://test.namspi.uz",
    ],
)

AUTH_USER_MODEL = "account.CustomUser"

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.media",
                "django.contrib.messages.context_processors.messages",
                "apps.common.context_processors.system_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

database_engine = env("DJANGO_DB_ENGINE", "django.db.backends.sqlite3") or "django.db.backends.sqlite3"
database_name = env("DJANGO_DB_NAME", "db.sqlite3") or "db.sqlite3"

if database_engine == "django.db.backends.sqlite3":
    database_path = Path(database_name)
    if not database_path.is_absolute():
        database_path = BASE_DIR / database_path

    DATABASES = {
        "default": {
            "ENGINE": database_engine,
            "NAME": database_path,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": database_engine,
            "NAME": database_name,
            "USER": env("DJANGO_DB_USER", "") or "",
            "PASSWORD": env("DJANGO_DB_PASSWORD", "") or "",
            "HOST": env("DJANGO_DB_HOST", "localhost") or "localhost",
            "PORT": env("DJANGO_DB_PORT", "5432") or "5432",
        }
    }

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

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Tashkent"
USE_TZ = True
USE_I18N = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend") or (
    "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = env("EMAIL_HOST", "smtp.gmail.com") or "smtp.gmail.com"
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "") or ""
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "") or ""

TELEGRAM_BOT_TOKEN = env("TELEGRAM_BOT_TOKEN", "your-telegram-bot-token") or "your-telegram-bot-token"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

LOGIN_URL = "landing:login"
LOGOUT_URL = "landing:logout"
LOGIN_REDIRECT_URL = "landing:dashboard"
LOGOUT_REDIRECT_URL = "landing:login"

SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 600)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", default=not DEBUG)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=False)
