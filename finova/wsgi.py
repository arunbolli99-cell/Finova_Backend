"""
WSGI config for finova project.
"""

import os
import logging
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'finova.settings')

# Initialize the WSGI application
application = get_wsgi_application()

# Automatically apply database migrations on boot (ensures Neon PostgreSQL tables exist)
try:
    from django.core.management import call_command
    call_command('migrate', interactive=False)
    logging.getLogger('stocks').info('Database migrations successfully applied on startup.')
except Exception as e:
    logging.getLogger('stocks').warning(f'Auto-migration on startup error: {e}')

