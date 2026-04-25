from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from QUIZ.hemis_formatter import (
    PROFILE_LABELS,
    find_sidecar_text_paths,
    format_word_file,
    format_uploaded_bytes,
    get_profile_order,
    make_output_stem,
    preview_text,
)


PROFILE_OPTIONS = ["auto", "sequential", "legacy", "jismoniy_uz", "jismoniy_ru"]
ENCODING_OPTIONS = ["auto", "cp1254", "cp1251", "utf-8", "cp1252", "latin1"]
BACKEND_LABELS = {
    "word": "MS Word",
    "libreoffice": "LibreOffice",
}
RUN_ID_RE = re.compile(r"^\d{8}_\d{6}_\d{6}$")


def _quiz_dir() -> Path:
    return Path(settings.BASE_DIR) / "QUIZ"


def _generated_dir() -> Path:
    path = _quiz_dir() / "generated"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_allowed_source(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() in {".doc", ".docx"}
        and not path.stem.lower().endswith("_hemis")
    )


def _source_files() -> list[Path]:
    return sorted((path for path in _quiz_dir().iterdir() if _is_allowed_source(path)), key=lambda item: item.name.lower())


def _resolve_source_path(source_name: str) -> Path:
    source_path = (_quiz_dir() / source_name).resolve()
    if source_path.parent != _quiz_dir().resolve() or not _is_allowed_source(source_path):
        raise Http404("Fayl topilmadi")
    return source_path


def _backend_label(value: str) -> str:
    if value.startswith("sidecar:"):
        return f"Yon fayl ({value.split(':', 1)[1]})"
    return BACKEND_LABELS.get(value, value)


@method_decorator(login_required, name="dispatch")
class GenerationView(View):
    template_name = "question/views/generation.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return HttpResponseForbidden("Bu sahifa faqat administrator uchun.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        source_files = []
        for path in _source_files():
            recommended_profile = get_profile_order(path.name, "auto")[0]
            sidecars = find_sidecar_text_paths(path)
            root_output = _quiz_dir() / f"{make_output_stem(path.name)}_hemis.docx"
            source_files.append(
                {
                    "name": path.name,
                    "extension": path.suffix.lower(),
                    "size_kb": round(path.stat().st_size / 1024, 1),
                    "recommended_profile": recommended_profile,
                    "recommended_profile_label": PROFILE_LABELS[recommended_profile],
                    "sidecars": [item.name for item in sidecars],
                    "has_ready_output": root_output.exists(),
                }
            )

        valid_run_dirs = [item for item in _generated_dir().iterdir() if item.is_dir() and RUN_ID_RE.fullmatch(item.name)]
        generated_docx = sorted(
            (path for run_dir in valid_run_dirs for path in run_dir.rglob("*_hemis.docx")),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        recent_outputs = []
        for file_path in generated_docx[:8]:
            recent_outputs.append(
                {
                    "name": file_path.name,
                    "run_id": file_path.parent.name,
                    "download_url": reverse("administrator:generation-download", args=[file_path.parent.name, file_path.name]),
                    "updated_at": datetime.fromtimestamp(file_path.stat().st_mtime),
                }
            )

        context = {
            "source_files": source_files,
            "profile_options": [(key, PROFILE_LABELS[key]) for key in PROFILE_OPTIONS],
            "encoding_options": ENCODING_OPTIONS,
            "recent_outputs": recent_outputs,
            "stats": {
                "source_count": len(source_files),
                "generated_count": len(generated_docx),
                "run_count": len(valid_run_dirs),
            },
        }
        return render(request, self.template_name, context)


@method_decorator(login_required, name="dispatch")
class GenerationRunView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return JsonResponse({"success": False, "errors": "Ruxsat yo'q"}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        mode = (request.POST.get("mode") or "single").strip()
        profile = (request.POST.get("profile") or "auto").strip()
        encoding = (request.POST.get("encoding") or "auto").strip()

        if profile not in PROFILE_OPTIONS:
            return JsonResponse({"success": False, "errors": "Noto'g'ri profil tanlandi"}, status=400)
        if encoding not in ENCODING_OPTIONS:
            return JsonResponse({"success": False, "errors": "Noto'g'ri encoding tanlandi"}, status=400)

        run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_dir = _generated_dir() / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        results = []
        errors = []

        def append_result(result):
            results.append(
                {
                    "source_name": result.source_name,
                    "profile": result.profile,
                    "profile_label": PROFILE_LABELS[result.profile],
                    "encoding": result.encoding,
                    "backend": result.backend,
                    "backend_label": _backend_label(result.backend),
                    "question_count": result.question_count,
                    "txt_name": result.txt_path.name,
                    "docx_name": result.docx_path.name,
                    "txt_download_url": reverse("administrator:generation-download", args=[run_id, result.txt_path.name]),
                    "docx_download_url": reverse("administrator:generation-download", args=[run_id, result.docx_path.name]),
                    "preview": preview_text(result.hemis_text, question_limit=6),
                    "output_dir": str(run_dir.resolve()),
                }
            )

        if mode == "upload":
            uploaded_file = request.FILES.get("upload_file")
            if not uploaded_file:
                return JsonResponse({"success": False, "errors": "Upload uchun fayl tanlanmadi"}, status=400)

            uploaded_name = Path(uploaded_file.name or "").name
            if Path(uploaded_name).suffix.lower() not in {".doc", ".docx"}:
                return JsonResponse({"success": False, "errors": "Faqat .docx yoki .doc yuklash mumkin"}, status=400)
            if uploaded_file.size > 20 * 1024 * 1024:
                return JsonResponse({"success": False, "errors": "Upload fayl hajmi 20MB dan kichik bo'lishi kerak"}, status=400)

            try:
                result = format_uploaded_bytes(
                    source_name=uploaded_name,
                    content=uploaded_file.read(),
                    output_dir=run_dir,
                    profile=profile,
                    encoding=encoding,
                )
                append_result(result)
            except Exception as exc:
                errors.append({"source_name": uploaded_name or "-", "error": str(exc)})
        else:
            try:
                if mode == "all":
                    sources = _source_files()
                else:
                    source_name = (request.POST.get("source_name") or "").strip()
                    if not source_name:
                        return JsonResponse({"success": False, "errors": "Fayl tanlanmadi"}, status=400)
                    sources = [_resolve_source_path(source_name)]
            except Http404:
                return JsonResponse({"success": False, "errors": "Fayl topilmadi"}, status=404)

            if not sources:
                return JsonResponse({"success": False, "errors": "Generatsiya uchun fayllar topilmadi"}, status=400)

            for source_path in sources:
                try:
                    result = format_word_file(source_path, output_dir=run_dir, profile=profile, encoding=encoding)
                    append_result(result)
                except Exception as exc:
                    errors.append({"source_name": source_path.name, "error": str(exc)})

        if not results:
            return JsonResponse(
                {
                    "success": False,
                    "errors": errors or [{"source_name": "-", "error": "Generatsiya bajarilmadi"}],
                },
                status=400,
            )

        return JsonResponse(
            {
                "success": True,
                "partial": bool(errors),
                "message": f"{len(results)} ta fayl generatsiya qilindi",
                "run_id": run_id,
                "results": results,
                "errors": errors,
            }
        )


@method_decorator(login_required, name="dispatch")
class GenerationDownloadView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, run_id, filename):
        run_dir = (_generated_dir() / run_id).resolve()
        if run_dir.parent != _generated_dir().resolve() or not run_dir.exists():
            raise Http404

        file_path = (run_dir / filename).resolve()
        if file_path.parent != run_dir or not file_path.exists() or file_path.suffix.lower() not in {".docx", ".txt"}:
            raise Http404

        return FileResponse(file_path.open("rb"), as_attachment=True, filename=file_path.name)
