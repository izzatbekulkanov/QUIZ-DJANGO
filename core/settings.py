from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .env import env, env_bool, env_int, env_list, load_env_file


BASE_DIR = Path(__file__).resolve().parent.parent
load_env_file(BASE_DIR / ".env")

DEFAULT_SECRET_KEY = "django-insecure-local-dev-only-change-me"

SECRET_KEY = env("DJANGO_SECRET_KEY", DEFAULT_SECRET_KEY) or DEFAULT_SECRET_KEY
DEBUG = env_bool("DJANGO_DEBUG", default=True)
IS_PRODUCTION = not DEBUG

if not DEBUG and SECRET_KEY == DEFAULT_SECRET_KEY:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in .env before running with DJANGO_DEBUG=False.")

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=["*"] if DEBUG else ["localhost", "127.0.0.1"],
)


def _iter_trusted_origins_from_hosts(hosts: list[str]) -> list[str]:
    trusted: list[str] = []
    seen: set[str] = set()

    def add(origin: str) -> None:
        if origin and origin not in seen:
            trusted.append(origin)
            seen.add(origin)

    for raw_host in hosts:
        host = (raw_host or "").strip()
        if not host or host == "*":
            continue

        if "://" in host:
            parsed = urlsplit(host)
            if parsed.scheme and parsed.netloc:
                add(f"{parsed.scheme}://{parsed.netloc}")
            continue

        normalized_host = host[1:] if host.startswith(".") else host
        if normalized_host.startswith("*."):
            add(f"http://{normalized_host}")
            add(f"https://{normalized_host}")
            continue

        add(f"http://{normalized_host}")
        add(f"https://{normalized_host}")

    return trusted

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
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.administrator.middleware.AdministratorAccessMiddleware",
    "apps.logs.middleware.LogMiddleware",
]

DEFAULT_CSRF_TRUSTED_ORIGINS = _iter_trusted_origins_from_hosts(ALLOWED_HOSTS) + [
    "https://webtest.namspi.uz",
    "http://webtest.namspi.uz",
    "https://test.namspi.uz",
    "http://test.namspi.uz",
]

CSRF_TRUSTED_ORIGINS = []
for origin in env_list("DJANGO_CSRF_TRUSTED_ORIGINS", default=DEFAULT_CSRF_TRUSTED_ORIGINS):
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

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

if DEBUG:
    database_name = env("DJANGO_SQLITE_NAME", "db.sqlite3") or "db.sqlite3"
    database_path = Path(database_name)
    if not database_path.is_absolute():
        database_path = BASE_DIR / database_path

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": database_path,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DJANGO_DB_NAME", "question_db") or "question_db",
            "USER": env("DJANGO_DB_USER", "question_user") or "question_user",
            "PASSWORD": env("DJANGO_DB_PASSWORD", "question_1231") or "question_1231",
            "HOST": env("DJANGO_DB_HOST", "localhost") or "localhost",
            "PORT": env("DJANGO_DB_PORT", "5432") or "5432",
            "CONN_MAX_AGE": env_int("DJANGO_DB_CONN_MAX_AGE", 60),
            "OPTIONS": {
                "connect_timeout": env_int("DJANGO_DB_CONNECT_TIMEOUT", 5),
            },
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
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DJANGO_SERVE_MEDIA = env_bool("DJANGO_SERVE_MEDIA", default=DEBUG)

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
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 1800)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", default=IS_PRODUCTION)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_SAVE_EVERY_REQUEST = True

CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", default=IS_PRODUCTION)
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=False)
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if env_bool("SECURE_PROXY_SSL_HEADER", default=IS_PRODUCTION)
    else None
)
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", default=IS_PRODUCTION)
SECURE_HSTS_SECONDS = env_int("SECURE_HSTS_SECONDS", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", default=False)
