import os

from app.online import create_app
from online.config import Settings


app = create_app(Settings.from_mapping(os.environ))
