"""Uvicorn entry point. Importing this module does not open a database."""
from applyflow.api import create_app

app = create_app()
