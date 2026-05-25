from .base import *

DEBUG = False

# Allow Render's auto-generated domain by default; override via ALLOWED_HOSTS env var
_default_hosts = 'breathe-esg-backend-g2h9.onrender.com,localhost,127.0.0.1'
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default=_default_hosts).split(',')

# Allow frontend Vercel/Render origins; override via CORS_ALLOWED_ORIGINS env var
_default_cors = 'https://breathe-esg-backend-g2h9.onrender.com'
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default=_default_cors).split(',')

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Render handles SSL termination at the load balancer — enabling this causes redirect loops
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
