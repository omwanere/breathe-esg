import os
from django.core.wsgi import get_wsgi_application

# Default to development; Render overrides via DJANGO_SETTINGS_MODULE env var.
# Safety net: if DEBUG is explicitly False (as set on Render), force production.
if os.environ.get('DEBUG', 'True').lower() in ('false', '0', 'no'):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

application = get_wsgi_application()
