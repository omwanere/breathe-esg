from .base import *
from decouple import config

DEBUG = config('DEBUG', default=False, cast=bool)

# Render domain is the default; override via ALLOWED_HOSTS env var on Render Dashboard
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='breathe-esg-backend-g2h9.onrender.com,localhost,127.0.0.1'
).split(',')

# Frontend Vercel URL; override via CORS_ALLOWED_ORIGINS env var
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173'
).split(',')

# CSRF trusted origins — required for Django 4.x when using HTTPS
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://breathe-esg-backend-g2h9.onrender.com'
).split(',')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Render terminates SSL at the load balancer — True causes infinite redirect loops
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
