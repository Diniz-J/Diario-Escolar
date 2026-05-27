"""Configurações do projeto Diário Escolar."""
import sys
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# True quando rodando a suíte (`manage.py test`). Usado para desligar o
# rate limit de login nos testes — senão os vários logins da suíte
# estourariam o limite e quebrariam testes não relacionados. O throttle
# em si é testado isoladamente reativando o rate via override_settings.
TESTING = "test" in sys.argv

# Segurança
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="", cast=Csv())

# Origens confiáveis pro CSRF — obrigatório com o admin atrás de proxy
# (nginx/HTTPS). Sem isso, POSTs do admin/forms falham com erro de CSRF
# em produção. Lista separada por vírgula, COM esquema. Ex.:
#   CSRF_TRUSTED_ORIGINS=https://diario.onrender.com,https://diario.com.br
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

# O app roda atrás de um proxy (nginx/Render) que termina o TLS. Este
# header faz o Django confiar no X-Forwarded-Proto enviado pelo proxy ao
# decidir se a requisição é https — sem isso, redirects e URLs absolutas
# saem como http em produção.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Hardening só em produção (DEBUG=False). Em dev atrapalharia (redirect
# https no localhost, cookies que o navegador recusa em http).
if not DEBUG:
    # HSTS e nosniff são inofensivos mesmo sem TLS (o navegador só aplica
    # HSTS sob https), então ficam sempre ligados em produção.
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=2592000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Redirect pra https + cookies "secure" dependem de TLS estar ativo na
    # frente. Ligados por env (`SECURE_SSL=True`) pra não quebrar cenários
    # sem TLS — ex.: testar o docker-compose.prod localmente em http puro,
    # onde SECURE_SSL_REDIRECT viraria loop e os cookies seriam recusados.
    # No Render/produção com HTTPS: defina SECURE_SSL=True.
    _usar_ssl = config("SECURE_SSL", default=False, cast=bool)
    SECURE_SSL_REDIRECT = _usar_ssl
    SESSION_COOKIE_SECURE = _usar_ssl
    CSRF_COOKIE_SECURE = _usar_ssl

# Apps
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    # Permite invalidar refresh tokens (logout efetivo + rotação segura).
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
]

# Apps locais — adicionadas conforme cada domínio é implementado
LOCAL_APPS: list[str] = [
    "apps.common",
    "apps.accounts",
    "apps.escola",
    "apps.ocorrencias",
    "apps.presenca",
    "apps.tarefas",
    "apps.boletins",
    "apps.planos_ensino",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serve os estáticos do Django em produção. Em DEBUG o
    # runserver continua servindo via finders — este middleware fica
    # inerte no dev, então não atrapalha o fluxo local.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Banco de dados
# Em produção/PaaS (Render, Fly, AWS...) a config vem de uma única
# DATABASE_URL. No dev/Docker local continuamos com DB_NAME/DB_USER/...
# separados. `conn_max_age` reaproveita conexões (pool) em produção.
DATABASE_URL = config("DATABASE_URL", default="")
if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
        }
    }

# Validação de senha
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internacionalização
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# Arquivos estáticos
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Storage dos estáticos: WhiteNoise comprime os arquivos no collectstatic.
# Versão sem manifest (não exige hash nos nomes) — mais tolerante a um
# primeiro deploy do que CompressedManifestStaticFilesStorage.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Modelo de usuário customizado
AUTH_USER_MODEL = "accounts.Usuario"

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    # ScopedRateThrottle só limita views que definem `throttle_scope`
    # (ex.: o login). Não afeta os endpoints normais da API.
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # Anti-brute-force no login: 5 tentativas por minuto por IP.
        # Desligado sob testes (rate None) — ver TESTING acima.
        "login": None if TESTING else "5/min",
    },
}

# SimpleJWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    # A cada refresh, emite um novo refresh e invalida o anterior
    # (blacklist). Reduz a janela de um refresh roubado e habilita logout
    # efetivo via /auth/logout/.
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# CORS
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="", cast=Csv())

# Email — usado pra notificar o responsável quando uma ocorrência é criada.
# Default = console backend (imprime o email no log; não envia de verdade),
# pra dev funcionar sem SMTP. Em produção, defina EMAIL_BACKEND como SMTP e
# preencha as credenciais (ex.: Resend — ver DEPLOY.md).
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="Diário Escolar <onboarding@resend.dev>"
)

# Em testes, usa o backend em memória pra inspecionar `mail.outbox` sem
# enviar nada de verdade.
if TESTING:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
