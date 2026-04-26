import base64
import html as std_html
import json
import mimetypes
import os
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

from flask import Flask, jsonify, make_response, request
from lxml import html as lxml_html


HOST = "127.0.0.1"
PORT = int(os.environ.get("QUIZ_WORD_BRIDGE_PORT", "8765"))
APP_NAME = "Quiz Office Helper"
APP_VERSION = "1.3.0"
SESSION_EXPIRY_GRACE_SECONDS = 5
STARTED_AT = datetime.now().astimezone()
STARTED_MONOTONIC = time.monotonic()
STATE_DIR = Path(
    os.environ.get(
        "QUIZ_OFFICE_HELPER_STATE_DIR",
        Path(os.environ.get("APPDATA") or Path.home()) / "QuizOfficeHelper",
    )
)
STATE_FILE = STATE_DIR / "state.json"
STARTUP_RUN_KEY = "QuizOfficeHelper"
STARTUP_REGISTRY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("QUIZ_WORD_BRIDGE_ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

OFFICE_APPS = {
    "word": {
        "prog_id": "Word.Application",
        "label": "Word",
        "empty_message": "Hozir ochiq Word oynasi topilmadi.",
    },
    "excel": {
        "prog_id": "Excel.Application",
        "label": "Excel",
        "empty_message": "Hozir ochiq Excel oynasi topilmadi.",
    },
    "powerpoint": {
        "prog_id": "PowerPoint.Application",
        "label": "PowerPoint",
        "empty_message": "Hozir ochiq PowerPoint oynasi topilmadi.",
    },
}

app = Flask(__name__)
STATE_LOCK = threading.RLock()
APP_STATE = {
    "session": {},
}


def _allowed_origin(origin):
    if not origin:
        return "*"
    if "*" in ALLOWED_ORIGINS:
        return origin
    normalized_origin = origin.rstrip("/")
    for allowed in ALLOWED_ORIGINS:
        if normalized_origin == allowed.rstrip("/"):
            return origin
    return None


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    allowed_origin = _allowed_origin(origin)
    if allowed_origin:
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Requested-With"
    return response


@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        return make_response("", 204)
    return None


def _safe_str(value):
    return str(value or "").strip()


def _iso_now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_iso_datetime(value):
    try:
        parsed = datetime.fromisoformat(_safe_str(value))
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed
    except Exception:
        return None


def _coerce_ttl_seconds(value, default=1800):
    try:
        ttl = int(float(value))
    except Exception:
        ttl = default
    return max(30, min(ttl, 86400))


def _session_expires_at(payload):
    return datetime.now().astimezone() + timedelta(
        seconds=_coerce_ttl_seconds(payload.get("expires_in_seconds"))
    )


def _read_json_file(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_state():
    stored_state = _read_json_file(STATE_FILE)
    if not isinstance(stored_state, dict):
        return
    with STATE_LOCK:
        stored_session = stored_state.get("session")
        if isinstance(stored_session, dict):
            if stored_session.get("is_bound"):
                stored_session = _build_unbound_session(stored_session, "helper-restarted")
                stored_session["restored_waiting_for_login"] = True
            else:
                stored_session = _build_unbound_session(
                    stored_session,
                    stored_session.get("unbound_reason") or "logout",
                )
            APP_STATE["session"] = stored_session


def _save_state():
    with STATE_LOCK:
        session = dict(APP_STATE.get("session") or {})
        # Session key is intentionally kept in memory only and shown masked in UI.
        had_active_session_key = bool(session.pop("session_key", None))
        if had_active_session_key:
            session["is_bound"] = False
            session["restored_waiting_for_login"] = True
        payload = {
            "session": session,
            "updated_at": _iso_now(),
        }

    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _mask_value(value, left=6, right=4):
    text = _safe_str(value)
    if not text:
        return ""
    if len(text) <= left + right + 3:
        return "*" * len(text)
    return f"{text[:left]}...{text[-right:]}"


def _build_unbound_session(previous=None, reason="logout"):
    previous = dict(previous or {})
    return {
        "is_bound": False,
        "username": "",
        "full_name": "",
        "email": "",
        "user_id": "",
        "django_host": previous.get("django_host", ""),
        "system_origin": previous.get("system_origin", ""),
        "system_label": previous.get("system_label", ""),
        "session_key_masked": "",
        "last_seen_at": previous.get("last_seen_at", ""),
        "expires_at": "",
        "last_unbound_at": previous.get("last_unbound_at") or _iso_now(),
        "unbound_reason": _safe_str(reason) or "logout",
        "restored_waiting_for_login": False,
    }


def _set_unbound_session(reason="logout"):
    with STATE_LOCK:
        previous = dict(APP_STATE.get("session") or {})
        APP_STATE["session"] = _build_unbound_session(previous, reason)
    _save_state()


def _expire_session_if_needed():
    with STATE_LOCK:
        session = dict(APP_STATE.get("session") or {})
    if not session.get("is_bound"):
        return

    expires_at = _parse_iso_datetime(session.get("expires_at"))
    if not expires_at:
        return

    if datetime.now().astimezone() > expires_at + timedelta(seconds=SESSION_EXPIRY_GRACE_SECONDS):
        _set_unbound_session("session-timeout")


def _public_session():
    _expire_session_if_needed()
    with STATE_LOCK:
        session = dict(APP_STATE.get("session") or {})
    session_key = session.pop("session_key", "")
    if session_key:
        session["session_key_masked"] = _mask_value(session_key)
        session["is_bound"] = True
    else:
        session["session_key_masked"] = session.get("session_key_masked", "")
        session["is_bound"] = bool(session.get("is_bound"))
    return session


def _bind_session(payload):
    session_key = _safe_str(payload.get("session_key"))
    if not session_key:
        raise ValueError("Session key topilmadi.")

    django_host = _safe_str(payload.get("django_host"))
    page_url = _safe_str(payload.get("page_url"))
    expires_at = _session_expires_at(payload)
    session = {
        "session_key": session_key,
        "session_key_masked": _mask_value(session_key),
        "user_id": _safe_str(payload.get("user_id")),
        "username": _safe_str(payload.get("username")),
        "full_name": _safe_str(payload.get("full_name")),
        "email": _safe_str(payload.get("email")),
        "django_host": django_host,
        "page_url": page_url,
        "system_origin": _safe_str(payload.get("system_origin")),
        "system_label": _safe_str(payload.get("system_label")) or django_host,
        "expires_in_seconds": payload.get("expires_in_seconds"),
        "bound_at": _iso_now(),
        "last_seen_at": _iso_now(),
        "expires_at": expires_at.isoformat(timespec="seconds"),
        "is_bound": True,
        "restored_waiting_for_login": False,
    }

    with STATE_LOCK:
        APP_STATE["session"] = session
    _save_state()
    return _public_session()


def _heartbeat_session(payload):
    session_key = _safe_str(payload.get("session_key"))
    if not session_key:
        raise ValueError("Session key topilmadi.")

    with STATE_LOCK:
        current = dict(APP_STATE.get("session") or {})

    if not current.get("is_bound") or current.get("session_key") != session_key:
        return _bind_session(payload)

    expires_at = _session_expires_at(payload)
    updates = {
        "last_seen_at": _iso_now(),
        "expires_at": expires_at.isoformat(timespec="seconds"),
        "expires_in_seconds": payload.get("expires_in_seconds"),
        "page_url": _safe_str(payload.get("page_url")) or current.get("page_url", ""),
        "system_origin": _safe_str(payload.get("system_origin")) or current.get("system_origin", ""),
        "django_host": _safe_str(payload.get("django_host")) or current.get("django_host", ""),
        "system_label": _safe_str(payload.get("system_label")) or current.get("system_label", ""),
        "restored_waiting_for_login": False,
    }

    with STATE_LOCK:
        APP_STATE["session"].update(updates)
    _save_state()
    return _public_session()


def _clear_session(reason="logout"):
    _set_unbound_session(reason)
    return _public_session()


def _format_mac_address(value):
    try:
        raw = f"{int(value):012x}"
    except Exception:
        return ""
    return ":".join(raw[index:index + 2] for index in range(0, 12, 2)).upper()


def _get_primary_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(0.25)
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return ""
    finally:
        sock.close()


def _get_local_ip_addresses():
    addresses = []
    primary_ip = _get_primary_ip()
    if primary_ip:
        addresses.append(primary_ip)

    try:
        host_name = socket.gethostname()
        _, _, host_ips = socket.gethostbyname_ex(host_name)
        addresses.extend(host_ips)
    except Exception:
        pass

    cleaned = []
    for address in addresses:
        address = _safe_str(address)
        if not address or address.startswith("127."):
            continue
        if address not in cleaned:
            cleaned.append(address)
    return cleaned


def _run_quick_command(command):
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=2,
            check=False,
        )
        return (completed.stdout or "").strip()
    except Exception:
        return ""


def _get_device_info():
    username = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    if not username:
        try:
            username = os.getlogin()
        except Exception:
            username = ""

    computer_name = os.environ.get("COMPUTERNAME") or socket.gethostname()
    mac_address = _format_mac_address(uuid.getnode())
    uptime_seconds = max(0, round(time.monotonic() - STARTED_MONOTONIC))

    return {
        "computer_name": computer_name,
        "windows_username": username,
        "os": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "host": HOST,
        "port": PORT,
        "dashboard_url": f"http://{HOST}:{PORT}/",
        "ip_addresses": _get_local_ip_addresses(),
        "mac_address": mac_address,
        "helper_path": sys.executable if getattr(sys, "frozen", False) else str(Path(__file__).resolve()),
        "is_packaged_exe": bool(getattr(sys, "frozen", False)),
        "started_at": STARTED_AT.isoformat(timespec="seconds"),
        "uptime_seconds": uptime_seconds,
        "timezone": STARTED_AT.tzname(),
    }


def _startup_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" "{Path(__file__).resolve()}"'


def _startup_status():
    if sys.platform != "win32":
        return {
            "supported": False,
            "enabled": False,
            "message": "Avtomatik ishga tushirish faqat Windows uchun mavjud.",
            "command": "",
        }

    try:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_PATH, 0, winreg.KEY_READ) as key:
                try:
                    current_command, _ = winreg.QueryValueEx(key, STARTUP_RUN_KEY)
                except FileNotFoundError:
                    current_command = ""
        except FileNotFoundError:
            current_command = ""

        desired_command = _startup_command()
        return {
            "supported": True,
            "enabled": bool(current_command),
            "command": _safe_str(current_command),
            "desired_command": desired_command,
            "matches_current_helper": _safe_str(current_command).lower() == desired_command.lower(),
            "message": "Kompyuter yoqilganda helper avtomatik ishga tushadi." if current_command else "Avtomatik ishga tushirish hali yoqilmagan.",
        }
    except Exception as exc:
        return {
            "supported": False,
            "enabled": False,
            "message": str(exc),
            "command": "",
        }


def _set_startup_enabled(enabled):
    if sys.platform != "win32":
        raise RuntimeError("Avtomatik ishga tushirish faqat Windows kompyuterda ishlaydi.")

    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_PATH) as key:
        if enabled:
            winreg.SetValueEx(key, STARTUP_RUN_KEY, 0, winreg.REG_SZ, _startup_command())
        else:
            try:
                winreg.DeleteValue(key, STARTUP_RUN_KEY)
            except FileNotFoundError:
                pass
    return _startup_status()


def _ensure_startup_on_launch():
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    if os.environ.get("QUIZ_OFFICE_HELPER_DISABLE_AUTO_STARTUP") == "1":
        return
    try:
        status = _startup_status()
        if not status.get("enabled") or not status.get("matches_current_helper"):
            _set_startup_enabled(True)
    except Exception:
        pass


_load_state()


def _office_modules():
    import pythoncom
    import win32com.client

    return pythoncom, win32com.client


def _get_application(app_key):
    if app_key not in OFFICE_APPS:
        raise ValueError(f"Noma'lum Office turi: {app_key}")

    pythoncom_module, win32_client = _office_modules()
    pythoncom_module.CoInitialize()
    try:
        return pythoncom_module, win32_client.GetActiveObject(OFFICE_APPS[app_key]["prog_id"])
    except Exception as exc:
        pythoncom_module.CoUninitialize()
        raise RuntimeError(OFFICE_APPS[app_key]["empty_message"]) from exc


def _release_application(pythoncom_module):
    try:
        pythoncom_module.CoUninitialize()
    except Exception:
        pass


def _build_document_key(app_key, index, identifier):
    return f"{app_key}:{index}:{identifier or index}"


def _normalize_saved_flag(value):
    try:
        return bool(value)
    except Exception:
        return True


def _list_open_word_documents():
    pythoncom_module, word = _get_application("word")
    try:
        documents = []
        active_full_name = ""
        try:
            active_document = getattr(word, "ActiveDocument", None)
            if active_document is not None:
                active_full_name = _safe_str(getattr(active_document, "FullName", ""))
        except Exception:
            active_full_name = ""

        for index in range(1, int(word.Documents.Count) + 1):
            document = word.Documents(index)
            name = _safe_str(getattr(document, "Name", "")) or f"Word hujjati {index}"
            full_name = _safe_str(getattr(document, "FullName", ""))
            documents.append(
                {
                    "key": _build_document_key("word", index, full_name or name),
                    "app_key": "word",
                    "app_name": "Word",
                    "name": name,
                    "path": full_name,
                    "is_active": bool(full_name and full_name == active_full_name),
                    "is_saved": _normalize_saved_flag(getattr(document, "Saved", True)),
                }
            )

        return documents
    finally:
        _release_application(pythoncom_module)


def _list_open_excel_documents():
    pythoncom_module, excel = _get_application("excel")
    try:
        documents = []
        active_full_name = ""
        try:
            active_workbook = getattr(excel, "ActiveWorkbook", None)
            if active_workbook is not None:
                active_full_name = _safe_str(getattr(active_workbook, "FullName", ""))
        except Exception:
            active_full_name = ""

        for index in range(1, int(excel.Workbooks.Count) + 1):
            workbook = excel.Workbooks(index)
            name = _safe_str(getattr(workbook, "Name", "")) or f"Excel fayli {index}"
            full_name = _safe_str(getattr(workbook, "FullName", ""))
            active_sheet_name = ""
            try:
                active_sheet = getattr(workbook, "ActiveSheet", None)
                active_sheet_name = _safe_str(getattr(active_sheet, "Name", ""))
            except Exception:
                active_sheet_name = ""

            documents.append(
                {
                    "key": _build_document_key("excel", index, full_name or name),
                    "app_key": "excel",
                    "app_name": "Excel",
                    "name": name,
                    "path": full_name,
                    "sheet_name": active_sheet_name,
                    "is_active": bool(full_name and full_name == active_full_name),
                    "is_saved": _normalize_saved_flag(getattr(workbook, "Saved", True)),
                }
            )

        return documents
    finally:
        _release_application(pythoncom_module)


def _list_open_powerpoint_documents():
    pythoncom_module, powerpoint = _get_application("powerpoint")
    try:
        documents = []
        active_full_name = ""
        try:
            active_presentation = getattr(powerpoint, "ActivePresentation", None)
            if active_presentation is not None:
                active_full_name = _safe_str(getattr(active_presentation, "FullName", ""))
        except Exception:
            active_full_name = ""

        for index in range(1, int(powerpoint.Presentations.Count) + 1):
            presentation = powerpoint.Presentations(index)
            name = _safe_str(getattr(presentation, "Name", "")) or f"PowerPoint fayli {index}"
            full_name = _safe_str(getattr(presentation, "FullName", ""))
            documents.append(
                {
                    "key": _build_document_key("powerpoint", index, full_name or name),
                    "app_key": "powerpoint",
                    "app_name": "PowerPoint",
                    "name": name,
                    "path": full_name,
                    "is_active": bool(full_name and full_name == active_full_name),
                    "is_saved": _normalize_saved_flag(getattr(presentation, "Saved", True)),
                }
            )

        return documents
    finally:
        _release_application(pythoncom_module)


def _collect_open_office_documents():
    documents = []
    errors = []
    loaders = (
        _list_open_word_documents,
        _list_open_excel_documents,
        _list_open_powerpoint_documents,
    )

    for loader in loaders:
        try:
            documents.extend(loader())
        except RuntimeError:
            continue
        except Exception as exc:
            errors.append(str(exc))

    documents.sort(
        key=lambda item: (
            0 if item.get("is_active") else 1,
            item.get("app_name") or "",
            item.get("name") or "",
        )
    )
    return documents, errors


def _split_document_key(document_key):
    parts = str(document_key or "").split(":", 2)
    if len(parts) != 3:
        raise ValueError("Tanlangan Office oynasi formati noto'g'ri.")
    return parts[0], parts[1], parts[2]


def _find_word_document(word, document_key):
    for index in range(1, int(word.Documents.Count) + 1):
        document = word.Documents(index)
        identifier = _safe_str(getattr(document, "FullName", "")) or _safe_str(getattr(document, "Name", ""))
        if _build_document_key("word", index, identifier) == document_key:
            return document
    raise ValueError("Tanlangan Word hujjati topilmadi yoki yopilgan.")


def _find_excel_workbook(excel, document_key):
    for index in range(1, int(excel.Workbooks.Count) + 1):
        workbook = excel.Workbooks(index)
        identifier = _safe_str(getattr(workbook, "FullName", "")) or _safe_str(getattr(workbook, "Name", ""))
        if _build_document_key("excel", index, identifier) == document_key:
            return workbook
    raise ValueError("Tanlangan Excel fayli topilmadi yoki yopilgan.")


def _find_powerpoint_presentation(powerpoint, document_key):
    for index in range(1, int(powerpoint.Presentations.Count) + 1):
        presentation = powerpoint.Presentations(index)
        identifier = _safe_str(getattr(presentation, "FullName", "")) or _safe_str(getattr(presentation, "Name", ""))
        if _build_document_key("powerpoint", index, identifier) == document_key:
            return presentation
    raise ValueError("Tanlangan PowerPoint fayli topilmadi yoki yopilgan.")


def _detect_charset(raw_bytes):
    import re

    head = raw_bytes[:5000].decode("ascii", errors="ignore")
    match = re.search(r"charset=([\w-]+)", head, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip().strip("\"'")
    return "utf-8"


def _embed_word_html_images(root, html_dir, images_dir):
    def resolve_src(source):
        source = (source or "").strip()
        if not source or source.lower().startswith("data:"):
            return None

        source = unquote(source)
        if source.lower().startswith("file:///"):
            return Path(source[8:])
        if source.lower().startswith("file:"):
            return Path(source[5:])

        normalized_source = source.replace("\\", "/")
        candidates = [
            html_dir / normalized_source,
            images_dir / normalized_source,
            images_dir / Path(normalized_source).name,
            html_dir / Path(normalized_source).name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def embed_attribute(element, attr_name):
        file_path = resolve_src(element.get(attr_name) or "")
        if not file_path or not file_path.exists():
            return
        mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
        element.set(attr_name, f"data:{mime_type};base64,{encoded}")

    for image in root.xpath("//*[local-name()='img']"):
        embed_attribute(image, "src")
    for vml_image in root.xpath("//*[local-name()='imagedata']"):
        if vml_image.get("src"):
            embed_attribute(vml_image, "src")


def _extract_word_document_content(document_key):
    pythoncom_module, word = _get_application("word")
    temp_clone = None
    exported_document = None
    try:
        document = _find_word_document(word, document_key)
        with tempfile.TemporaryDirectory(prefix="quiz_office_helper_word_") as temp_dir:
            temp_dir_path = Path(temp_dir)
            temp_docx_path = temp_dir_path / "office_copy.docx"
            temp_html_path = temp_dir_path / "office_copy.html"

            temp_clone = word.Documents.Add()
            temp_clone.Range().FormattedText = document.Range().FormattedText
            temp_clone.SaveAs2(str(temp_docx_path), FileFormat=16)
            temp_clone.Close(False)
            temp_clone = None

            exported_document = word.Documents.Open(str(temp_docx_path), ReadOnly=True)
            exported_document.SaveAs(str(temp_html_path), FileFormat=10)
            plain_text = _safe_str(getattr(exported_document.Range(), "Text", ""))
            exported_document.Close(False)
            exported_document = None

            raw_html = temp_html_path.read_bytes()
            html_text = raw_html.decode(_detect_charset(raw_html), errors="replace")
            root = lxml_html.fromstring(html_text)
            images_dir = temp_html_path.parent / f"{temp_html_path.stem}.files"
            _embed_word_html_images(root, temp_html_path.parent, images_dir)

            body_nodes = root.xpath("//body")
            if body_nodes:
                body_html = "".join(
                    lxml_html.tostring(child, encoding="unicode", method="html")
                    for child in body_nodes[0]
                )
            else:
                body_html = lxml_html.tostring(root, encoding="unicode", method="html")

            return {
                "app_key": "word",
                "app_name": "Word",
                "document_name": _safe_str(getattr(document, "Name", "")) or "Word hujjati",
                "html": body_html,
                "text": plain_text,
            }
    finally:
        try:
            if temp_clone is not None:
                temp_clone.Close(False)
        except Exception:
            pass
        try:
            if exported_document is not None:
                exported_document.Close(False)
        except Exception:
            pass
        _release_application(pythoncom_module)


def _excel_value_to_text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _excel_rows_from_range(values):
    if values is None:
        return []
    if isinstance(values, tuple):
        rows = []
        for row in values:
            if isinstance(row, tuple):
                rows.append([_excel_value_to_text(cell) for cell in row])
            else:
                rows.append([_excel_value_to_text(row)])
        return rows
    return [[_excel_value_to_text(values)]]


def _rows_to_html_table(rows):
    if not rows:
        return "<p></p>"

    row_html = []
    for row in rows:
        cells_html = "".join(f"<td>{std_html.escape(cell)}</td>" for cell in row)
        row_html.append(f"<tr>{cells_html}</tr>")
    return "<table><tbody>" + "".join(row_html) + "</tbody></table>"


def _extract_excel_document_content(document_key):
    pythoncom_module, excel = _get_application("excel")
    try:
        workbook = _find_excel_workbook(excel, document_key)
        sheet = getattr(workbook, "ActiveSheet", None) or workbook.Worksheets(1)
        used_range = getattr(sheet, "UsedRange", None)
        values = getattr(used_range, "Value", None) if used_range is not None else None
        rows = _excel_rows_from_range(values)
        meaningful_rows = [row for row in rows if any((cell or "").strip() for cell in row)]

        single_column_like = all(sum(1 for cell in row if (cell or "").strip()) <= 1 for row in meaningful_rows) if meaningful_rows else True
        if single_column_like:
            text = "\n".join(next((cell for cell in row if (cell or "").strip()), "") for row in meaningful_rows).strip()
        else:
            text = "\n".join("\t".join(row).rstrip() for row in meaningful_rows).strip()

        return {
            "app_key": "excel",
            "app_name": "Excel",
            "document_name": f"{_safe_str(getattr(workbook, 'Name', 'Excel fayli'))} / {_safe_str(getattr(sheet, 'Name', 'Sheet'))}",
            "html": _rows_to_html_table(meaningful_rows),
            "text": text,
        }
    finally:
        _release_application(pythoncom_module)


def _powerpoint_table_to_text_and_html(table):
    rows = []
    for row_index in range(1, int(table.Rows.Count) + 1):
        row_values = []
        for column_index in range(1, int(table.Columns.Count) + 1):
            try:
                cell_text = _safe_str(table.Cell(row_index, column_index).Shape.TextFrame.TextRange.Text)
            except Exception:
                cell_text = ""
            row_values.append(cell_text)
        rows.append(row_values)

    text = "\n".join("\t".join(row).rstrip() for row in rows if any(cell.strip() for cell in row))
    html = _rows_to_html_table(rows)
    return text, html


def _extract_powerpoint_document_content(document_key):
    pythoncom_module, powerpoint = _get_application("powerpoint")
    try:
        presentation = _find_powerpoint_presentation(powerpoint, document_key)
        text_chunks = []
        html_sections = []

        for slide_index in range(1, int(presentation.Slides.Count) + 1):
            slide = presentation.Slides(slide_index)
            slide_parts = []
            slide_html_parts = []

            for shape in slide.Shapes:
                try:
                    if getattr(shape, "HasTextFrame", 0) and shape.TextFrame.HasText:
                        shape_text = _safe_str(shape.TextFrame.TextRange.Text)
                        if shape_text:
                            slide_parts.append(shape_text)
                            slide_html_parts.append(f"<p>{std_html.escape(shape_text)}</p>")
                    elif getattr(shape, "HasTable", 0):
                        table_text, table_html = _powerpoint_table_to_text_and_html(shape.Table)
                        if table_text:
                            slide_parts.append(table_text)
                            slide_html_parts.append(table_html)
                except Exception:
                    continue

            if slide_parts:
                text_chunks.append("\n".join(slide_parts))
            if slide_html_parts:
                html_sections.append("".join(slide_html_parts))

        return {
            "app_key": "powerpoint",
            "app_name": "PowerPoint",
            "document_name": _safe_str(getattr(presentation, "Name", "")) or "PowerPoint fayli",
            "html": "".join(html_sections) or "<p></p>",
            "text": "\n\n".join(text_chunks).strip(),
        }
    finally:
        _release_application(pythoncom_module)


def _extract_office_document_content(document_key):
    app_key, _, _ = _split_document_key(document_key)
    if app_key == "word":
        return _extract_word_document_content(document_key)
    if app_key == "excel":
        return _extract_excel_document_content(document_key)
    if app_key == "powerpoint":
        return _extract_powerpoint_document_content(document_key)
    raise ValueError("Tanlangan Office turi qo'llab-quvvatlanmaydi.")


def _build_status_payload(include_documents=True):
    documents = []
    errors = []
    if include_documents:
        documents, errors = _collect_open_office_documents()

    return {
        "ok": True,
        "mode": "quiz-office-helper",
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "host": HOST,
        "port": PORT,
        "supported_apps": [OFFICE_APPS[key]["label"] for key in OFFICE_APPS],
        "open_documents_count": len(documents),
        "documents": documents,
        "errors": errors,
        "device": _get_device_info(),
        "startup": _startup_status(),
        "session": _public_session(),
    }


def _status_page_html():
    return """
<!doctype html>
<html lang="uz">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Quiz Office Helper</title>
    <style>
      :root {
        --ink: #102033;
        --muted: #66758a;
        --line: rgba(16, 32, 51, 0.12);
        --card: rgba(255, 255, 255, 0.86);
        --glass: rgba(255, 255, 255, 0.72);
        --soft-blue: #e8f1ff;
        --deep-blue: #155eef;
        --green: #16a34a;
        --red: #dc2626;
        --blue: #2563eb;
        --amber: #d97706;
      }

      * { box-sizing: border-box; }

      body {
        margin: 0;
        min-height: 100vh;
        color: var(--ink);
        font-family: "Segoe UI", Tahoma, sans-serif;
        background:
          linear-gradient(rgba(255, 255, 255, 0.22) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255, 255, 255, 0.22) 1px, transparent 1px),
          radial-gradient(circle at top left, rgba(37, 99, 235, 0.20), transparent 34rem),
          radial-gradient(circle at 85% 15%, rgba(22, 163, 74, 0.18), transparent 28rem),
          linear-gradient(135deg, #eef5ff 0%, #f7fafc 46%, #f8fbf3 100%);
        background-size: 32px 32px, 32px 32px, auto, auto, auto;
      }

      .page {
        width: min(1180px, calc(100% - 32px));
        margin: 0 auto;
        padding: 32px 0;
      }

      .hero {
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.58);
        border-radius: 32px;
        background:
          linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 64, 175, 0.88)),
          linear-gradient(135deg, rgba(255,255,255,0.08), transparent);
        color: #fff;
        box-shadow: 0 28px 70px rgba(15, 23, 42, 0.18);
        padding: 30px;
      }

      .hero:after {
        content: "";
        position: absolute;
        width: 340px;
        height: 340px;
        right: -120px;
        top: -120px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.12);
      }

      .hero-inner {
        position: relative;
        z-index: 1;
        display: grid;
        gap: 22px;
        grid-template-columns: 1fr auto;
        align-items: center;
      }

      h1 {
        margin: 0 0 8px;
        font-size: clamp(28px, 4vw, 46px);
        letter-spacing: -0.04em;
      }

      .lead {
        margin: 0;
        color: rgba(255, 255, 255, 0.78);
        max-width: 700px;
        line-height: 1.65;
      }

      .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        border: 1px solid rgba(22, 163, 74, 0.18);
        border-radius: 999px;
        padding: 6px 10px;
        background: rgba(22, 163, 74, 0.10);
        backdrop-filter: blur(18px);
        font-weight: 700;
        font-size: 12px;
        white-space: nowrap;
      }

      .dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: var(--green);
        box-shadow: 0 0 0 5px rgba(22, 163, 74, 0.14);
      }

      .dot.offline {
        background: var(--red);
        box-shadow: 0 0 0 7px rgba(220, 38, 38, 0.16);
      }

      .grid {
        display: grid;
        grid-template-columns: repeat(12, 1fr);
        gap: 18px;
        margin-top: 18px;
      }

      .card {
        grid-column: span 6;
        border: 1px solid rgba(255, 255, 255, 0.72);
        border-radius: 24px;
        background: var(--card);
        box-shadow: 0 18px 48px rgba(15, 23, 42, 0.08);
        backdrop-filter: blur(18px);
        padding: 22px;
      }

      .card.full { grid-column: 1 / -1; }
      .card.third { grid-column: span 4; }

      .card-title {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 16px;
      }

      h2 {
        margin: 0;
        font-size: 13px;
        letter-spacing: -0.02em;
      }

      .badge {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 4px 8px;
        background: rgba(37, 99, 235, 0.10);
        color: var(--blue);
        font-size: 10px;
        font-weight: 800;
      }

      .badge.green {
        background: rgba(22, 163, 74, 0.12);
        color: var(--green);
      }

      .badge.amber {
        background: rgba(217, 119, 6, 0.12);
        color: var(--amber);
      }

      .kv {
        display: grid;
        grid-template-columns: 150px 1fr;
        gap: 10px 14px;
        align-items: start;
      }

      .key {
        color: var(--muted);
        font-size: 11px;
      }

      .value {
        min-width: 0;
        overflow-wrap: anywhere;
        font-weight: 700;
        font-size: 11px;
      }

      .doc-list {
        display: grid;
        gap: 6px;
      }

      .doc {
        display: grid;
        grid-template-columns: auto 1fr auto;
        gap: 8px;
        align-items: center;
        border: 1px solid var(--line);
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.72);
        padding: 8px;
      }

      .doc-icon {
        width: 30px;
        height: 30px;
        display: grid;
        place-items: center;
        border-radius: 10px;
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.12), rgba(22, 163, 74, 0.12));
        color: var(--blue);
        font-weight: 900;
      }

      .doc-name {
        font-weight: 800;
        margin-bottom: 2px;
        font-size: 12px;
      }

      .doc-path {
        color: var(--muted);
        font-size: 11px;
        overflow-wrap: anywhere;
      }

      .empty {
        border: 1px dashed var(--line);
        border-radius: 12px;
        padding: 12px;
        color: var(--muted);
        font-size: 12px;
        background: rgba(255, 255, 255, 0.54);
      }

      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }

      button, .link-button {
        border: 0;
        border-radius: 999px;
        padding: 10px 14px;
        background: var(--blue);
        color: #fff;
        font-weight: 800;
        cursor: pointer;
        text-decoration: none;
      }

      button.secondary, .link-button.secondary {
        background: rgba(15, 23, 42, 0.08);
        color: var(--ink);
      }

      button.danger {
        background: rgba(220, 38, 38, 0.10);
        color: var(--red);
      }

      .footer-note {
        margin-top: 18px;
        color: var(--muted);
        font-size: 13px;
        text-align: center;
      }

      .explorer-window {
        position: relative;
        width: min(1480px, calc(100% - 18px));
        margin: 9px auto;
        padding: 0;
        overflow: hidden;
        min-height: calc(100vh - 18px);
        border: 1px solid rgba(255, 255, 255, 0.78);
        border-radius: 22px;
        background:
          linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(246, 250, 255, 0.92)),
          #f8fafc;
        box-shadow: 0 24px 74px rgba(15, 23, 42, 0.18);
        backdrop-filter: blur(22px);
      }

      .explorer-window:before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background:
          radial-gradient(circle at 14% 12%, rgba(37, 99, 235, 0.14), transparent 25rem),
          radial-gradient(circle at 94% 4%, rgba(14, 165, 233, 0.14), transparent 22rem);
      }

      .explorer-titlebar {
        position: relative;
        z-index: 1;
        height: 44px;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 12px;
        padding: 0 14px;
        background:
          linear-gradient(90deg, rgba(255, 255, 255, 0.86), rgba(232, 241, 255, 0.78)),
          #f3f6fb;
        border-bottom: 1px solid rgba(217, 225, 236, 0.82);
        user-select: none;
      }

      .explorer-title {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        font-size: 14px;
        font-weight: 900;
        letter-spacing: -0.02em;
      }

      .explorer-app-icon {
        width: 28px;
        height: 28px;
        display: grid;
        place-items: center;
        border-radius: 10px;
        color: #fff;
        background: linear-gradient(135deg, #2563eb, #0ea5e9);
        box-shadow: 0 10px 24px rgba(37, 99, 235, 0.32);
      }

      .explorer-commandbar {
        position: relative;
        z-index: 1;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 8px 12px;
        background: rgba(255, 255, 255, 0.72);
        border-bottom: 1px solid rgba(229, 235, 243, 0.92);
        backdrop-filter: blur(18px);
      }

      .command-group {
        display: inline-flex;
        flex-wrap: wrap;
        gap: 6px;
        align-items: center;
      }

      .command-button {
        border: 1px solid transparent;
        background: rgba(248, 250, 252, 0.76);
        color: #1f2937;
        border-radius: 10px;
        padding: 7px 10px;
        font-size: 12px;
        font-weight: 800;
        box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.14);
      }

      .command-button:hover {
        background: #eaf2ff;
        border-color: #c9dcf7;
        color: var(--deep-blue);
      }

      .explorer-address {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: min(460px, 100%);
        border: 1px solid #d7e0ec;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.86);
        padding: 7px 10px;
        color: #475569;
        font-size: 12px;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
      }

      .explorer-body {
        display: block;
        min-height: calc(100vh - 101px);
      }

      .explorer-main {
        position: relative;
        z-index: 1;
        min-width: 0;
        padding: 12px;
        background:
          linear-gradient(180deg, rgba(251, 253, 255, 0.90), rgba(248, 251, 255, 0.96)),
          #fbfdff;
      }

      .explorer-heading {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 10px;
        border: 1px solid rgba(225, 232, 242, 0.92);
        border-radius: 18px;
        padding: 12px;
        background:
          linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(232, 241, 255, 0.78)),
          #ffffff;
        box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
      }

      .explorer-heading h1 {
        margin: 0;
        font-size: 20px;
        letter-spacing: -0.02em;
      }

      .explorer-heading p {
        margin: 2px 0 0;
        color: #64748b;
        font-size: 12px;
      }

      .explorer-status-strip {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(142px, 1fr));
        gap: 8px;
        margin-bottom: 8px;
      }

      .status-tile,
      .file-tile,
      .details-pane,
      .documents-pane {
        border: 1px solid rgba(225, 232, 242, 0.92);
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.86);
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
        backdrop-filter: blur(18px);
      }

      .status-tile {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        transition: transform 0.16s ease, box-shadow 0.16s ease;
      }

      .status-tile:hover,
      .file-tile:hover,
      .details-pane:hover,
      .documents-pane:hover {
        transform: translateY(-2px);
        box-shadow: 0 15px 34px rgba(15, 23, 42, 0.09);
      }

      .status-icon {
        width: 30px;
        height: 30px;
        display: grid;
        place-items: center;
        border-radius: 11px;
        background: linear-gradient(135deg, #eaf2ff, #f8fbff);
        color: #2563eb;
        font-weight: 900;
        box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.08);
      }

      .status-title {
        font-size: 10px;
        color: #64748b;
      }

      .status-value {
        font-size: 12px;
        color: #0f172a;
        font-weight: 800;
      }

      .file-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 8px;
        margin-bottom: 8px;
      }

      .file-tile {
        padding: 10px;
      }

      .file-tile-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
        margin-bottom: 8px;
      }

      .file-icon {
        width: 30px;
        height: 30px;
        display: grid;
        place-items: center;
        border-radius: 10px;
        background: linear-gradient(135deg, #dbeafe, #f0f9ff);
        color: #2563eb;
        font-weight: 900;
      }

      .pane-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 8px;
        margin-bottom: 8px;
      }

      .details-pane,
      .documents-pane {
        padding: 10px;
      }

      .documents-pane {
        min-height: 116px;
        max-height: 172px;
        overflow: auto;
      }

      .pane-title {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
      }

      .kv {
        grid-template-columns: 112px 1fr;
        gap: 5px 8px;
      }

      @media (max-width: 860px) {
        .explorer-window { width: calc(100% - 18px); margin: 9px auto; }
        .explorer-titlebar { height: 38px; }
        .explorer-commandbar { gap: 6px; padding: 7px 10px; }
        .command-button { padding: 6px 8px; font-size: 11px; }
        .explorer-address { padding: 6px 8px; font-size: 11px; }
        .explorer-main { padding: 8px; }
        .explorer-heading { padding: 9px; margin-bottom: 7px; }
        .explorer-heading h1 { font-size: 18px; }
        .explorer-heading p { font-size: 11px; }
        .explorer-status-strip,
        .file-grid,
        .pane-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; margin-bottom: 6px; }
        .status-tile { min-width: 0; padding: 6px; gap: 6px; }
        .status-icon,
        .file-icon,
        .doc-icon { width: 26px; height: 26px; border-radius: 9px; font-size: 11px; }
        .status-title { font-size: 9px; }
        .status-value { font-size: 10px; overflow-wrap: anywhere; }
        .file-tile,
        .details-pane,
        .documents-pane { padding: 8px; border-radius: 14px; }
        .file-tile-header,
        .pane-title { margin-bottom: 6px; }
        h2 { font-size: 12px; }
        .key,
        .value,
        .doc-path { font-size: 10px; }
        .doc-name { font-size: 11px; }
        .documents-pane { max-height: 132px; }
        .hero-inner { grid-template-columns: 1fr; }
        .card, .card.third { grid-column: 1 / -1; }
        .kv { grid-template-columns: 1fr; }
        .doc { grid-template-columns: auto 1fr; }
        .doc .badge { grid-column: 1 / -1; justify-self: start; }
      }
    </style>
  </head>
  <body>
    <main class="page explorer-window">
      <div class="explorer-titlebar">
        <div class="explorer-title">
          <span class="explorer-app-icon">Q</span>
          <span>Quiz Office Helper</span>
        </div>
      </div>

      <div class="explorer-commandbar">
        <div class="command-group">
          <button type="button" class="command-button" onclick="refreshStatus()">⟳ Yangilash</button>
          <button type="button" class="command-button" id="enable-startup">Startup yoqish</button>
          <button type="button" class="command-button" id="disable-startup">Startup o'chirish</button>
        </div>
        <div class="explorer-address">
          <span>Kompyuter</span>
          <span>›</span>
          <strong>Quiz Office Helper</strong>
          <span>›</span>
          <span>http://__HOST__:__PORT__</span>
        </div>
      </div>

      <div class="explorer-body">
        <section class="explorer-main">
          <div class="explorer-heading">
            <div>
              <h1>Quiz Office Helper</h1>
              <p>Word, Excel va PowerPoint oynalarini test tizimiga bog'lab turuvchi lokal yordamchi.</p>
            </div>
            <div class="command-group">
              <span class="status-pill"><span class="dot" id="status-dot"></span><span id="status-label">Online</span></span>
              <span class="badge green" id="version-badge">v__VERSION__</span>
            </div>
          </div>

          <div class="explorer-status-strip">
            <div class="status-tile">
              <div class="status-icon">●</div>
              <div>
                <div class="status-title">Online holat</div>
                <div class="status-value" id="online-summary">Tekshirilmoqda</div>
              </div>
            </div>
            <div class="status-tile">
              <div class="status-icon">👤</div>
              <div>
                <div class="status-title">Session</div>
                <div class="status-value" id="session-summary">Kutilmoqda</div>
              </div>
            </div>
            <div class="status-tile">
              <div class="status-icon">⏱</div>
              <div>
                <div class="status-title">Qolgan vaqt</div>
                <div class="status-value" id="session-countdown">-</div>
              </div>
            </div>
            <div class="status-tile">
              <div class="status-icon">📄</div>
              <div>
                <div class="status-title">Office oynalari</div>
                <div class="status-value" id="document-count">0 ta</div>
              </div>
            </div>
            <div class="status-tile">
              <div class="status-icon">↻</div>
              <div>
                <div class="status-title">Startup</div>
                <div class="status-value" id="startup-summary">-</div>
              </div>
            </div>
            <div class="status-tile">
              <div class="status-icon">PC</div>
              <div>
                <div class="status-title">Kompyuter</div>
                <div class="status-value" id="device-summary">-</div>
              </div>
            </div>
            <div class="status-tile">
              <div class="status-icon">IP</div>
              <div>
                <div class="status-title">Asosiy IP</div>
                <div class="status-value" id="ip-summary">-</div>
              </div>
            </div>
            <div class="status-tile">
              <div class="status-icon">ID</div>
              <div>
                <div class="status-title">MAC</div>
                <div class="status-value" id="mac-summary">-</div>
              </div>
            </div>
          </div>

          <div class="file-grid">
            <article class="file-tile">
              <div class="file-tile-header">
                <div class="file-icon">⚙</div>
                <span class="badge green">App</span>
              </div>
              <div class="pane-title"><h2>Dastur holati</h2></div>
              <div class="kv" id="app-kv"></div>
            </article>

            <article class="file-tile">
              <div class="file-tile-header">
                <div class="file-icon">👤</div>
                <span class="badge" id="session-badge">Session</span>
              </div>
              <div class="pane-title"><h2>Foydalanuvchi</h2></div>
              <div class="kv" id="session-kv"></div>
            </article>

            <article class="file-tile">
              <div class="file-tile-header">
                <div class="file-icon">↻</div>
                <span class="badge amber" id="startup-badge">Startup</span>
              </div>
              <div class="pane-title"><h2>Avtomatik ishga tushish</h2></div>
              <div class="kv" id="startup-kv"></div>
            </article>
          </div>

          <div class="pane-grid">
            <article class="details-pane">
              <div class="pane-title">
                <h2>Kompyuter ma'lumotlari</h2>
                <span class="badge">Device</span>
              </div>
              <div class="kv" id="device-kv"></div>
            </article>

            <article class="details-pane">
              <div class="pane-title">
                <h2>Tarmoq</h2>
                <span class="badge">127.0.0.1:__PORT__</span>
              </div>
              <div class="kv" id="network-kv"></div>
            </article>
          </div>

          <article class="documents-pane">
            <div class="pane-title">
              <h2>Ochiq Office oynalari</h2>
              <span class="badge">Real vaqt</span>
            </div>
            <div class="doc-list" id="documents"></div>
          </article>
        </section>
      </div>
    </main>

    <script>
      const $ = (selector) => document.querySelector(selector);

      function escapeHtml(value) {
        return String(value ?? '')
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;');
      }

      function formatUptime(seconds) {
        const total = Number(seconds || 0);
        const hours = Math.floor(total / 3600);
        const minutes = Math.floor((total % 3600) / 60);
        const secs = total % 60;
        if (hours) return `${hours} soat ${minutes} daqiqa`;
        if (minutes) return `${minutes} daqiqa ${secs} soniya`;
        return `${secs} soniya`;
      }

      function formatRemaining(isoValue) {
        if (!isoValue) return '-';
        const expiresAt = new Date(isoValue).getTime();
        if (!expiresAt) return '-';
        const remaining = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000));
        if (!remaining) return 'Tugagan';
        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;
        if (minutes >= 60) {
          const hours = Math.floor(minutes / 60);
          return `${hours} soat ${minutes % 60} daqiqa`;
        }
        return `${minutes} daqiqa ${seconds} soniya`;
      }

      function renderKv(target, rows) {
        target.innerHTML = rows.map(([key, value]) => `
          <div class="key">${escapeHtml(key)}</div>
          <div class="value">${value ? escapeHtml(value) : '-'}</div>
        `).join('');
      }

      function renderDocuments(documents) {
        const box = $('#documents');
        $('#document-count').textContent = `${documents.length} ta`;
        if (!documents.length) {
          box.innerHTML = '<div class="empty">Hozircha ochiq Office oynasi topilmadi. Word, Excel yoki PowerPoint faylini oching va sahifani bir necha soniya kuting.</div>';
          return;
        }

        box.innerHTML = documents.map((doc) => `
          <div class="doc">
            <div class="doc-icon">${escapeHtml((doc.app_name || 'O').slice(0, 1))}</div>
            <div>
              <div class="doc-name">[${escapeHtml(doc.app_name || 'Office')}] ${escapeHtml(doc.name || 'Fayl')}</div>
              <div class="doc-path">${escapeHtml(doc.path || 'Saqlanmagan fayl')}</div>
            </div>
            <span class="badge ${doc.is_active ? 'green' : ''}">${doc.is_active ? 'Faol oyna' : (doc.is_saved ? 'Saqlangan' : 'Saqlanmagan')}</span>
          </div>
        `).join('');
      }

      async function fetchJson(path, options = {}) {
        const response = await fetch(path, {
          method: options.method || 'GET',
          headers: { 'Content-Type': 'application/json' },
          body: options.body ? JSON.stringify(options.body) : undefined,
        });
        const text = await response.text();
        const data = text ? JSON.parse(text) : {};
        if (!response.ok) throw new Error(data.message || 'Amal bajarilmadi');
        return data;
      }

      function renderStatus(data) {
        $('#status-dot').classList.remove('offline');
        $('#status-label').textContent = 'Online va tayyor';
        $('#online-summary').textContent = 'Ishlayapti';

        const device = data.device || {};
        const session = data.session || {};
        const startup = data.startup || {};
        const documents = data.documents || [];
        const ipAddresses = device.ip_addresses || [];

        renderKv($('#app-kv'), [
          ['Dastur', data.app_name || 'Quiz Office Helper'],
          ['Versiya', data.version || '-'],
          ['Ishlagan vaqt', formatUptime(device.uptime_seconds)],
          ["Qo'llab-quvvatlash", (data.supported_apps || []).join(', ')],
        ]);

        renderKv($('#session-kv'), [
          ['Holat', session.is_bound ? "Tizimga bog'langan" : "Test tizimiga login qilinishini kutmoqda"],
          ['Username', session.username || '-'],
          ['F.I.Sh.', session.full_name || '-'],
          ['Tizim domeni', session.django_host || session.system_origin || '-'],
          ['Session', session.session_key_masked || '-'],
          ["Bog'langan vaqt", session.bound_at || '-'],
          ['Oxirgi chiqish', session.last_unbound_at || '-'],
        ]);
        $('#session-badge').className = `badge ${session.is_bound ? 'green' : 'amber'}`;
        $('#session-badge').textContent = session.is_bound ? "Bog'langan" : 'Kutilmoqda';
        $('#session-summary').textContent = session.is_bound ? (session.username || "Bog'langan") : 'Login kutilmoqda';
        $('#session-countdown').textContent = session.is_bound ? formatRemaining(session.expires_at) : '-';
        $('#startup-summary').textContent = startup.enabled ? 'Yoqilgan' : 'Yoqilmagan';
        $('#device-summary').textContent = device.computer_name || '-';
        $('#ip-summary').textContent = ipAddresses[0] || '-';
        $('#mac-summary').textContent = device.mac_address || '-';

        renderKv($('#startup-kv'), [
          ['Holat', startup.enabled ? 'Yoqilgan' : 'Yoqilmagan'],
          ['Izoh', startup.message || '-'],
          ['Buyruq', startup.command || startup.desired_command || '-'],
        ]);
        $('#startup-badge').className = `badge ${startup.enabled ? 'green' : 'amber'}`;
        $('#startup-badge').textContent = startup.enabled ? 'Yoqilgan' : 'Yoqilmagan';

        renderKv($('#device-kv'), [
          ['Kompyuter', device.computer_name],
          ['Windows user', device.windows_username],
          ['Operatsion tizim', device.os],
          ['Helper fayli', device.helper_path],
          ['Ishga tushgan vaqt', device.started_at],
        ]);

        renderKv($('#network-kv'), [
          ['Lokal manzil', device.dashboard_url],
          ['IP manzillar', ipAddresses.join(', ') || 'Topilmadi'],
          ['MAC manzil', device.mac_address],
          ['Port', String(device.port || '')],
        ]);

        renderDocuments(documents);
      }

      async function refreshStatus() {
        try {
          const data = await fetchJson('/api/status');
          renderStatus(data);
        } catch (error) {
          $('#status-dot').classList.add('offline');
          $('#status-label').textContent = "Ma'lumot yangilanmadi";
          $('#online-summary').textContent = "Ulanmadi";
        }
      }

      async function setStartup(enabled) {
        const path = enabled ? '/api/startup/enable' : '/api/startup/disable';
        await fetchJson(path, { method: 'POST', body: {} });
        await refreshStatus();
      }

      $('#enable-startup').addEventListener('click', () => setStartup(true).catch((error) => alert(error.message)));
      $('#disable-startup').addEventListener('click', () => setStartup(false).catch((error) => alert(error.message)));

      refreshStatus();
      window.setInterval(refreshStatus, 2000);
    </script>
  </body>
</html>
    """.replace("__HOST__", std_html.escape(HOST)).replace("__PORT__", str(PORT)).replace("__VERSION__", std_html.escape(APP_VERSION))


@app.route("/", methods=["GET"])
def index():
    return _status_page_html()


@app.route("/health", methods=["GET"])
def health():
    return jsonify(_build_status_payload(include_documents=False))


@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify(_build_status_payload(include_documents=True))


@app.route("/api/session", methods=["GET"])
def api_session():
    return jsonify({"ok": True, "session": _public_session()})


@app.route("/api/session/bind", methods=["POST"])
def api_session_bind():
    payload = request.get_json(silent=True) or request.form or {}
    try:
        session = _bind_session(payload)
        return jsonify({"ok": True, "session": session})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400


@app.route("/api/session/heartbeat", methods=["POST"])
def api_session_heartbeat():
    payload = request.get_json(silent=True) or request.form or {}
    try:
        session = _heartbeat_session(payload)
        return jsonify({"ok": True, "session": session})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400


@app.route("/api/session/unbind", methods=["POST"])
def api_session_unbind():
    payload = request.get_json(silent=True) or request.form or {}
    session = _clear_session(payload.get("reason") or "logout")
    return jsonify({"ok": True, "session": session})


@app.route("/api/startup/status", methods=["GET"])
def api_startup_status():
    return jsonify({"ok": True, "startup": _startup_status()})


@app.route("/api/startup/enable", methods=["POST"])
def api_startup_enable():
    try:
        return jsonify({"ok": True, "startup": _set_startup_enabled(True)})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500


@app.route("/api/startup/disable", methods=["POST"])
def api_startup_disable():
    try:
        return jsonify({"ok": True, "startup": _set_startup_enabled(False)})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500


@app.route("/api/office/windows", methods=["GET"])
def api_office_windows():
    documents, errors = _collect_open_office_documents()
    return jsonify({"success": True, "documents": documents, "errors": errors})


@app.route("/api/office/document-content", methods=["POST"])
def api_office_document_content():
    payload = request.get_json(silent=True) or request.form or {}
    document_key = _safe_str(payload.get("document_key"))
    if not document_key:
        return jsonify({"ok": False, "message": "document_key majburiy."}), 400

    try:
        content = _extract_office_document_content(document_key)
        return jsonify({"ok": True, **content})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500


@app.route("/api/word/documents", methods=["GET"])
def api_word_documents():
    try:
        return jsonify({"success": True, "documents": _list_open_word_documents()})
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/api/word/document-content", methods=["POST"])
def api_word_document_content():
    payload = request.get_json(silent=True) or request.form or {}
    document_key = _safe_str(payload.get("document_key"))
    if not document_key:
        return jsonify({"ok": False, "message": "document_key majburiy."}), 400

    try:
        content = _extract_word_document_content(document_key)
        return jsonify({"ok": True, **content})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500


def _create_tray_image():
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (64, 64), (24, 33, 52, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 56, 56), radius=14, fill=(52, 123, 247, 255))
    draw.rectangle((16, 16, 48, 48), fill=(255, 255, 255, 255))
    draw.rectangle((21, 22, 43, 26), fill=(52, 123, 247, 255))
    draw.rectangle((21, 31, 43, 35), fill=(16, 185, 129, 255))
    draw.rectangle((21, 40, 43, 44), fill=(249, 115, 22, 255))
    return image


def _run_server():
    app.run(host=HOST, port=PORT, threaded=True, use_reloader=False)


def _current_process_label():
    return f"{APP_NAME}.exe" if getattr(sys, "frozen", False) else "bridge.py"


def main():
    _ensure_startup_on_launch()
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    try:
        import pystray
    except Exception:
        server_thread.join()
        return

    def open_status_page(icon, item):
        webbrowser.open(f"http://{HOST}:{PORT}/")

    def quit_helper(icon, item):
        icon.stop()
        os._exit(0)

    icon = pystray.Icon(
        "quiz-office-helper",
        _create_tray_image(),
        _current_process_label(),
        menu=pystray.Menu(
            pystray.MenuItem("Dashboardni ochish", open_status_page),
            pystray.MenuItem("Chiqish", quit_helper),
        ),
    )
    icon.run()


if __name__ == "__main__":
    main()
