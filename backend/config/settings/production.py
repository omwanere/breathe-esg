from .base import *
from decouple import config

DEBUG = config('DEBUG', default=False, cast=bool)

# Render domain is the default; override via ALLOWED_HOSTS env var on Render Dashboard
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='breathe-esg-backend-g2h9.onrender.com,localhost,127.0.0.1'
).split(',')

# Frontend Vercel URL must be here for CORS preflight to pass
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='https://breathe-esg-kappa.vercel.app,http://localhost:5173,http://localhost:3000'
).split(',')

# Required in Django 4.x for HTTPS POST/PUT requests from trusted frontends
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://breathe-esg-backend-g2h9.onrender.com,https://breathe-esg-kappa.vercel.app'
).split(',')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Render terminates SSL at the load balancer — True causes infinite redirect loops
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

