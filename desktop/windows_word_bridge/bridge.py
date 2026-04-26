import base64
import html as std_html
import mimetypes
import os
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from urllib.parse import unquote

from flask import Flask, jsonify, make_response, request
from lxml import html as lxml_html


HOST = "127.0.0.1"
PORT = int(os.environ.get("QUIZ_WORD_BRIDGE_PORT", "8765"))
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


def _status_page_html():
    documents, errors = _collect_open_office_documents()
    list_items = []
    for document in documents:
        suffix = f" - {document['path']}" if document.get("path") else ""
        list_items.append(
            f"<li><strong>[{std_html.escape(document['app_name'])}]</strong> "
            f"{std_html.escape(document['name'])}{std_html.escape(suffix)}</li>"
        )
    if not list_items:
        list_items.append("<li>Hozircha ochiq Office oynasi topilmadi.</li>")

    error_html = ""
    if errors:
        error_html = "<p style='color:#9a3412;'>Ba'zi oynalarni o'qishda xatolik bo'ldi.</p>"

    return f"""
    <html>
      <head><title>Quiz Office Helper</title></head>
      <body style="font-family: Segoe UI, sans-serif; padding: 24px;">
        <h2>Quiz Office Helper ishlayapti</h2>
        <p>Manzil: <code>http://{HOST}:{PORT}</code></p>
        <p>Qo'llab-quvvatlanadigan oynalar: Word, Excel, PowerPoint</p>
        {error_html}
        <h3>Ochiq Office oynalari</h3>
        <ul>{''.join(list_items)}</ul>
      </body>
    </html>
    """


@app.route("/", methods=["GET"])
def index():
    return _status_page_html()


@app.route("/health", methods=["GET"])
def health():
    documents, errors = _collect_open_office_documents()
    return jsonify(
        {
            "ok": True,
            "mode": "quiz-office-helper",
            "host": HOST,
            "port": PORT,
            "supported_apps": [OFFICE_APPS[key]["label"] for key in OFFICE_APPS],
            "open_documents_count": len(documents),
            "errors": errors,
        }
    )


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
    return "Quiz Office Helper.exe" if getattr(sys, "frozen", False) else "bridge.py"


def main():
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
            pystray.MenuItem("Office oynalari ro'yxatini ochish", open_status_page),
            pystray.MenuItem("Chiqish", quit_helper),
        ),
    )
    icon.run()


if __name__ == "__main__":
    main()
