import os, sys, django
from pathlib import Path

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verticebook.settings')
django.setup()

from django.conf import settings
from django.template import loader

print(f"PYTHONPATH: {sys.path}")
print(f"BASE_DIR: {settings.BASE_DIR}")
print(f"TEMPLATES DIRS: {settings.TEMPLATES[0].get('DIRS')}")

try:
    template = loader.get_template('base.html')
    print(f"base.html path: {template.origin.name}")
except Exception as e:
    print(f"Error loading base.html: {e}")
