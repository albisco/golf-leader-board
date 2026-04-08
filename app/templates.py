from fastapi.templating import Jinja2Templates
from pathlib import Path

template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=template_dir)