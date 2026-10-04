import sys
import os

# Ensure the backend module can be found
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.main import app
