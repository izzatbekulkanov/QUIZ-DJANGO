import mimetypes
from pathlib import Path

from django.http import FileResponse, Http404, HttpResponseNotModified
from django.utils.http import http_date, parse_http_date_safe

from core import settings


MEDIA_CACHE_SECONDS = 86400


def _resolve_media_path(relative_path: str) -> Path:
    media_root = Path(settings.MEDIA_ROOT).resolve()
    target = (media_root / relative_path).resolve()

    if media_root != target and media_root not in target.parents:
        raise Http404("Media file not found.")

    return target


def serve_media_file(request, path: str):
    file_path = _resolve_media_path(path)

    if not file_path.exists() or not file_path.is_file():
        raise Http404("Media file not found.")

    stat = file_path.stat()
    modified_since = parse_http_date_safe(request.headers.get("If-Modified-Since", ""))
    if modified_since >= int(stat.st_mtime):
        return HttpResponseNotModified()

    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    response = FileResponse(file_path.open("rb"), content_type=content_type)
    response["Content-Length"] = str(stat.st_size)
    response["Last-Modified"] = http_date(stat.st_mtime)
    response["Cache-Control"] = f"public, max-age={MEDIA_CACHE_SECONDS}"
    response["X-Content-Type-Options"] = "nosniff"
    return response
