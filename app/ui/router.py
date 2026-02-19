from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# Router for all web UI HTML pages
router = APIRouter(prefix="/ui", tags=["web-ui"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard — lists all landing pages. Expanded in Plan 03."""
    return templates.TemplateResponse(request=request, name="index.html", context={"lps": []})
