from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DJANGO_DEBUG=(bool, True), CFTC_API_TIMEOUT_SECONDS=(int, 30), CFTC_API_PAGE_SIZE=(int, 5000))
env.read_env(BASE_DIR / ".env")
SECRET_KEY = env("DJANGO_SECRET_KEY", default="local-only-insecure-key")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])
INSTALLED_APPS = ["django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles", "cot"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": env.db("DATABASE_URL", default=f"postgresql://{env('POSTGRES_USER', default='postgres')}:{env('POSTGRES_PASSWORD', default='5525')}@{env('POSTGRES_HOST', default='127.0.0.1')}:{env('POSTGRES_PORT', default='5432')}/{env('POSTGRES_DB', default='global_futures_oi')}")}
if env.bool("USE_SQLITE", default=False):
    DATABASES["default"] = {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CFTC_API_TIMEOUT_SECONDS = env("CFTC_API_TIMEOUT_SECONDS")
CFTC_API_PAGE_SIZE = env("CFTC_API_PAGE_SIZE")
CFTC_USER_AGENT = env("CFTC_USER_AGENT", default="GlobalFuturesOI/0.1")
LOGGING = {"version": 1, "disable_existing_loggers": False, "formatters": {"standard": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}}, "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard"}}, "loggers": {"global_futures_oi": {"handlers": ["console"], "level": "INFO"}}}

