import csv
import json
import random
import tempfile
from pathlib import Path
from io import BytesIO
import base64
import shutil
import subprocess
import mimetypes
import html as std_html
from urllib.parse import unquote
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from docx.shared import Inches
from openpyxl import load_workbook, Workbook
import re
from docx import Document
from sympy import sympify, latex
import matplotlib.pyplot as plt
from lxml import html as lxml_html


def _word_doc_to_docx_via_com(doc_path: Path) -> Path:
    """
    Convert legacy .doc to .docx using Microsoft Word COM automation.
    Requires MS Word installed on Windows. Returns path to generated .docx.
    """
    try:
        import win32com.client  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("pywin32/Word COM topilmadi. .doc faylni .docx ga o'girib bo'lmadi.") from e

    doc_path = doc_path.resolve()
    out_path = doc_path.with_suffix(".docx")

    word = None
    doc = None
    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0  # wdAlertsNone
        doc = word.Documents.Open(str(doc_path))
        # 16 = wdFormatXMLDocument (.docx)
        doc.SaveAs(str(out_path), FileFormat=16)
        return out_path
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            if word is not None:
                word.Quit()
        except Exception:
            pass


def _word_doc_to_docx(doc_path: Path) -> Path:
    """
    Convert legacy .doc -> .docx.

    Primary path: Microsoft Word COM automation (best fidelity for old .doc).
    Fallback: LibreOffice (soffice) if installed.
    """
    try:
        return _word_doc_to_docx_via_com(doc_path)
    except Exception:
        soffice = shutil.which("soffice")
        if not soffice:
            raise

        doc_path = doc_path.resolve()
        out_dir = doc_path.parent
        # LibreOffice writes output into out_dir with same basename.
        proc = subprocess.run(
            [soffice, "--headless", "--convert-to", "docx", "--outdir", str(out_dir), str(doc_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        out_path = doc_path.with_suffix(".docx")
        if proc.returncode != 0 or not out_path.exists():
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(f".doc faylni .docx ga o'girishda xato (LibreOffice): {stderr or proc.returncode}")
        return out_path


def _docx_to_html_embedded(docx_path: Path) -> str:
    """
    Convert docx to HTML with embedded resources (images as base64).

    Preference order:
      1) Microsoft Word export (best fidelity for old Word + formulas/images; outputs PNG/JPG)
      2) pandoc fallback (may embed some equation images as WMF which browsers can't render)
    """
    try:
        return _docx_to_html_embedded_via_word(docx_path)
    except Exception:
        # Fallback to pandoc (still useful when MS Word is not installed/available).
        pass

    try:
        import pypandoc  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("pypandoc o'rnatilmagan. Word import ishlamaydi.") from e

    # Ensure pandoc exists (pypandoc-binary ships it)
    _ = pypandoc.get_pandoc_path()

    extra_args = [
        "--standalone",
        "--embed-resources",
        "--mathml",
    ]
    return pypandoc.convert_file(str(docx_path), "html", extra_args=extra_args)


def _detect_charset_from_meta(raw: bytes) -> str | None:
    head = raw[:5000].decode("ascii", errors="ignore")
    m = re.search(r"charset=([\w-]+)", head, flags=re.IGNORECASE)
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


def _embed_word_html_images(root, html_dir: Path, images_dir: Path) -> None:
    # Embed <img src="..."> and VML <imagedata src="..."> into data URIs.
    def resolve_src(src: str) -> Path | None:
        src = (src or "").strip()
        if not src or src.lower().startswith("data:"):
            return None

        src = unquote(src)
        if src.lower().startswith("file:///"):
            return Path(src[8:])
        if src.lower().startswith("file:"):
            return Path(src[5:])

        # Normalize slashes for joining.
        src_norm = src.replace("\\", "/")
        candidates = [
            (html_dir / src_norm),
            (images_dir / src_norm),
            (images_dir / Path(src_norm).name),
            (html_dir / Path(src_norm).name),
        ]
        for c in candidates:
            try:
                if c.exists():
                    return c
            except Exception:
                continue
        return None

    def embed_attr(el, attr: str) -> None:
        src = el.get(attr) or ""
        fp = resolve_src(src)
        if not fp or not fp.exists():
            return
        mime = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
        b64 = base64.b64encode(fp.read_bytes()).decode("ascii")
        el.set(attr, f"data:{mime};base64,{b64}")

    for img in root.xpath("//*[local-name()='img']"):
        embed_attr(img, "src")
    for vml in root.xpath("//*[local-name()='imagedata']"):
        if vml.get("src"):
            embed_attr(vml, "src")


def _docx_to_html_embedded_via_word(docx_path: Path) -> str:
    """
    Convert docx to HTML via Microsoft Word and embed exported images as base64.
    This is critical for math/formula images: Word exports them as PNG/JPG, which browsers can render.
    """
    try:
        import win32com.client  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("MS Word COM topilmadi. Word import ishlamaydi.") from e

    docx_path = docx_path.resolve()

    with tempfile.TemporaryDirectory(prefix="quiz_word_html_") as td:
        td_path = Path(td)
        out_html = td_path / "input.html"

        word = None
        doc = None
        try:
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0  # wdAlertsNone
            doc = word.Documents.Open(str(docx_path))
            # 10 = wdFormatFilteredHTML
            doc.SaveAs(str(out_html), FileFormat=10)
        finally:
            try:
                if doc is not None:
                    doc.Close(False)
            except Exception:
                pass
            try:
                if word is not None:
                    word.Quit()
            except Exception:
                pass

        if not out_html.exists():
            raise RuntimeError("Word faylni HTML ga o'girishda xato: HTML fayl yaratilmadi.")

        raw = out_html.read_bytes()
        enc = _detect_charset_from_meta(raw) or "utf-8"
        html_text = raw.decode(enc, errors="replace")

        root = lxml_html.fromstring(html_text)
        images_dir = out_html.parent / f"{out_html.stem}.files"
        _embed_word_html_images(root, out_html.parent, images_dir)
        return lxml_html.tostring(root, encoding="unicode", method="html")


def parse_word(file) -> list[dict]:
    """
    Parse Word (.docx/.doc) exported structure into questions.

    Expected (recommended) Word structure (matches ExportQuestionsView.export_docx):
      - Savol N: ...
      - Variant 1 (To'g'ri): ...
      - Variant 2: ...
      - Variant 3: ...
      - Variant 4: ...
      - ==================================================

    This parser converts Word to HTML (images base64 embedded) and then splits by markers.
    """
    name = getattr(file, "name", "") or ""
    suffix = Path(name).suffix.lower()
    if suffix not in (".docx", ".doc"):
        raise ValueError("Faqat .docx yoki .doc fayllar qabul qilinadi")

    with tempfile.TemporaryDirectory(prefix="quiz_word_import_") as td:
        td_path = Path(td)
        in_path = td_path / f"input{suffix}"
        with open(in_path, "wb") as f:
            # Django UploadedFile has .chunks(); fall back to .read() for other file-like objects.
            if hasattr(file, "chunks"):
                for chunk in file.chunks():
                    f.write(chunk)
            else:  # pragma: no cover
                f.write(file.read())

        docx_path = in_path
        if suffix == ".doc":
            docx_path = _word_doc_to_docx(in_path)

        html = _docx_to_html_embedded(docx_path)

        root = lxml_html.fromstring(html)
        body_list = root.xpath("//body")
        if not body_list:
            return []
        body = body_list[0]

        def _localname(tag) -> str:
            if not isinstance(tag, str):
                return ""
            if tag.startswith("{") and "}" in tag:
                tag = tag.split("}", 1)[1]
            return tag.lower()

        def iter_blocks(el):
            for child in el.iterchildren():
                tag = _localname(child.tag)
                if tag in ("p", "h1", "h2", "h3", "h4", "table"):
                    yield child
                elif tag in ("ul", "ol"):
                    for li in child.xpath(".//*[local-name()='li']"):
                        yield li
                else:
                    yield from iter_blocks(child)

        import re as _re

        # NOTE: raw strings must use single backslashes for regex escapes.
        q_re = _re.compile(r"^Savol\s*(\d+)\s*[:.)]?\s*", _re.IGNORECASE)
        v_re = _re.compile(r"^Variant\s*(\d+)\b", _re.IGNORECASE)
        sep_re = _re.compile(r"^[=\\-]{10,}$")

        questions: list[dict] = []
        current = None

        for block in iter_blocks(body):
            text = " ".join((block.text_content() or "").split())
            if not text:
                continue
            block_html = lxml_html.tostring(block, encoding="unicode", method="html")

            if sep_re.match(text):
                if current and current.get("answers"):
                    questions.append(current)
                current = None
                continue

            if q_re.match(text):
                if current and current.get("answers"):
                    questions.append(current)
                current = {"text_parts": [block_html], "answers": []}
                continue

            if current is None:
                continue

            vm = v_re.match(text)
            if vm:
                vnum = int(vm.group(1))
                t_low = text.lower()
                # Variant 1 is treated as correct (matches export format). Also honor explicit markers.
                is_correct = vnum == 1 or ("to'g'ri" in t_low) or ("togri" in t_low)
                current["answers"].append((block_html, is_correct))
            else:
                # Still part of the question statement
                current["text_parts"].append(block_html)

        if current and current.get("answers"):
            questions.append(current)

        # Normalize output to same shape as parse_excel()
        out: list[dict] = []
        for q in questions:
            q_html = "\n".join(q.get("text_parts") or [])
            out.append(
                {
                    "text": q_html,
                    "image_base64": None,
                    "answers": q.get("answers") or [],
                }
            )
        if out:
            return out

        # Fallback: many teachers keep tests as a single Word table:
        #   col0 = question stem, col1-4 = answer options (often images/formulas).
        tables = body.xpath(".//*[local-name()='table']")
        if not tables:
            return []

        def cell_to_html(cell) -> str:
            # Keep original structure from Word HTML; wrap into a safe container.
            parts: list[str] = []
            for child in cell:
                parts.append(lxml_html.tostring(child, encoding="unicode", method="html"))
            inner = "".join(parts).strip()
            if not inner:
                txt = " ".join((cell.text_content() or "").split())
                if txt:
                    inner = f"<p>{std_html.escape(txt)}</p>"
            if not inner:
                return ""
            return f"<div>{inner}</div>"

        out2: list[dict] = []
        for table in tables:
            for tr in table.xpath(".//tr"):
                cells = tr.xpath("./th|./td")
                if len(cells) < 3:
                    continue

                stem_cell = cells[0]
                option_cells = cells[1:5]  # up to 4 options

                q_html = cell_to_html(stem_cell)
                if not q_html:
                    continue

                answers: list[tuple[str, bool]] = []
                for cell in option_cells:
                    a_text = " ".join((cell.text_content() or "").split())
                    has_img = bool(cell.xpath(".//*[local-name()='img']")) or bool(cell.xpath(".//*[local-name()='imagedata']"))
                    if not a_text and not has_img:
                        continue
                    answers.append((cell_to_html(cell), False))

                # At least 2 options required.
                if len(answers) < 2:
                    continue

                # Keep existing import convention: first option is correct.
                answers[0] = (answers[0][0], True)
                out2.append({"text": q_html, "image_base64": None, "answers": answers})

        return out2

from question.models import Test, Question, Answer


def parse_excel(file, additional_files=None):
    wb = load_workbook(file)
    sheet = wb.active
    questions = []

    def convert_formula_to_base64(formula):
        """LaTeX yoki matematik formulani rasmga aylantirib, Base64 ga kodlaydi."""
        try:
            # Formulani LaTeX formatiga oвЂtkazish
            expr = sympify(formula)
            latex_expr = latex(expr)

            # Rasm yaratish
            plt.figure(figsize=(4, 1))
            plt.text(0.5, 0.5, f"${latex_expr}$", fontsize=12, ha='center', va='center')
            plt.axis('off')

            # Rasmni Base64 ga aylantirish
            buffer = BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
            plt.close()
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            return image_base64
        except Exception as e:
            print(f"Formula konvertatsiyasida xato: {str(e)}")
            return None

    for row in sheet.iter_rows(min_row=2, values_only=True):
        # Qator boвЂsh yoki yetarli ustunlarga ega emasligini tekshirish
        if not row or len(row) < 2:  # Kamida savol + 1 javob boвЂlishi kerak
            print(f"Qator oвЂtkazib yuborildi: yetarli ustunlar yoвЂq (ustunlar soni: {len(row) if row else 0})")
            continue

        question_text = row[0]
        if not question_text:
            print("Qator oвЂtkazib yuborildi: savol matni boвЂsh")
            continue

        # Formula aniqlash (masalan, LaTeX yoki oddiy matematik ifoda)
        formula_match = re.search(r'\[Formula:\s*([^\]]+)\]', question_text)
        image_base64 = None
        if formula_match:
            formula = formula_match.group(1).strip()
            image_base64 = convert_formula_to_base64(formula)
            # Formula belgisini matndan olib tashlash
            question_text = re.sub(r'\[Formula:\s*[^\]]+\]', '', question_text).strip()

        # [Rasm: nom.jpg] belgisini olib tashlash (agar mavjud boвЂlsa)
        question_text = re.sub(r'\[Rasm:\s*[^\]]+\]', '', question_text).strip()

        # Javoblarni olish (dinamik son)
        answers = [(row[i], i == 1) for i in range(1, len(row)) if row[i]]  # 1-variant toвЂgвЂri
        if len(answers) < 2:  # Kamida 1 toвЂgвЂri va 1 notoвЂgвЂri javob
            print(f"Qator oвЂtkazib yuborildi: yetarli javoblar yoвЂq (javoblar soni: {len(answers)})")
            continue

        # Javoblarni tasodifiy tartibda almashtirish
        random.shuffle(answers)

        questions.append({
            'text': question_text,
            'image_base64': image_base64,
            'answers': answers
        })

    print(f"Jami {len(questions)} ta savol topildi")
    return questions


@method_decorator(login_required, name='dispatch')
class ImportQuestionsView(View):
    def post(self, request, test_id):
        print(f"POST soвЂrovi keldi: test_id={test_id}, foydalanuvchi={request.user}")
        test = get_object_or_404(Test, id=test_id)
        print(f"Test topildi: {test.name} (ID: {test_id})")

        file = request.FILES.get('import_file')
        additional_files = request.FILES.getlist('additional_files', [])
        print(f"Fayl: {file.name if file else 'Fayl yuklanmadi'}")
        print(f"QoвЂshimcha fayllar: {[f.name for f in additional_files] if additional_files else 'YoвЂq'}")

        if not file:
            return JsonResponse({"success": False, "errors": "Fayl yuklanmadi"})

        name = (file.name or "").lower()
        is_excel = name.endswith(".xlsx")
        is_word = name.endswith(".docx") or name.endswith(".doc")
        if not (is_excel or is_word):
            return JsonResponse({"success": False, "errors": "Faqat .xlsx, .docx yoki .doc fayllar qabul qilinadi"})

        if file.size > 10 * 1024 * 1024:
            print(f"Xato: Fayl hajmi {file.size} bayt, 10MB dan katta")
            return JsonResponse({"success": False, "errors": "Fayl hajmi 10MB dan kichik boвЂlishi kerak"})

        try:
            if is_excel:
                print("Excel faylini parsing boshlandi...")
                questions = parse_excel(file, additional_files)
            else:
                print("Word faylini parsing boshlandi...")
                questions = parse_word(file)
            print(f"Parsing natijasi: {len(questions)} ta savol topildi")
            if not questions:
                print("Xato: Faylda savollar topilmadi")
                return JsonResponse({"success": False, "errors": "Faylda savollar topilmadi"})

            # Savollarni sessionвЂ™da saqlash
            request.session['imported_questions'] = questions
            request.session['test_id'] = test_id
            print(f"SessionвЂ™da saqlandi: {len(questions)} ta savol, test_id={test_id}")

            return JsonResponse({
                "success": True,
                "questions": questions,
                "message": "Savollar muvaffaqiyatli oвЂqildi, modalda koвЂrsatilmoqda!"
            })
        except Exception as e:
            print(f"Xato yuz berdi: {str(e)}")
            return JsonResponse({"success": False, "errors": f"Faylni oвЂqishda xato: {str(e)}"})


@method_decorator(login_required, name='dispatch')
class DownloadTemplateView(View):
    def get(self, request):
        wb = Workbook()
        ws = wb.active
        ws.title = "Questions Template"

        headers = ["Savol matni", "Variant 1", "Variant 2", "Variant 3", "Variant 4", "ToвЂgвЂri javob"]
        ws.append(headers)

        example_row = ["Misol savol", "ToвЂgвЂri javob", "NotoвЂgвЂri 1", "NotoвЂgвЂri 2", "NotoвЂgвЂri 3", "1 variant"]
        ws.append(example_row)

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            content=buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=questions_template.xlsx'
        return response


@method_decorator(login_required, name='dispatch')
class SaveImportedQuestionsView(View):
    def post(self, request):
        test_id = request.session.get('test_id')
        if not test_id:
            return JsonResponse({"success": False, "errors": "Test topilmadi"})

        questions = request.session.get('imported_questions', [])
        if not questions:
            return JsonResponse({"success": False, "errors": "Saqlash uchun savollar topilmadi"})

        test = get_object_or_404(Test, id=test_id)
        saved_count = 0

        try:
            for q in questions:
                question_text = q['text'].strip()
                correct_answer = next((text for text, is_correct in q['answers'] if is_correct), None)
                if not correct_answer:
                    print(f"Savol oвЂtkazib yuborildi: toвЂgвЂri javob yoвЂq: {question_text}")
                    continue

                # Bazada takrorlanishni tekshirish
                exists = Question.objects.filter(
                    test=test,
                    text__iexact=question_text
                ).filter(
                    answers__text__iexact=correct_answer,
                    answers__is_correct=True
                ).exists()

                if exists:
                    print(f"Savol oвЂtkazib yuborildi: takrorlangan savol: {question_text} (toвЂgвЂri javob: {correct_answer})")
                    continue

                # Yangi savolni saqlash
                question = Question.objects.create(test=test, text=question_text)
                if q.get('image_base64'):
                    image_data = base64.b64decode(q['image_base64'])
                    image_name = f"question_{question.id}.png"
                    question.image.save(image_name, ContentFile(image_data))

                for answer_text, is_correct in q['answers']:
                    Answer.objects.create(
                        question=question,
                        text=answer_text,
                        is_correct=is_correct
                    )

                saved_count += 1

            # SessionвЂ™ni tozalash
            del request.session['imported_questions']
            del request.session['test_id']
            return JsonResponse({
                "success": True,
                "message": f"{saved_count} ta savol muvaffaqiyatli saqlandi!"
            })
        except Exception as e:
            print(f"Saqlashda xato: {str(e)}")
            return JsonResponse({"success": False, "errors": f"Saqlashda xato: {str(e)}"})


@method_decorator(login_required, name='dispatch')
class DownloadTemplateView(View):
    def get(self, request):
        wb = Workbook()
        ws = wb.active
        ws.title = "Questions Template"

        headers = ["Savol matni", "Variant 1", "Variant 2", "Variant 3", "Variant 4"]  # ToвЂgвЂri javob ustuni olib tashlandi
        ws.append(headers)

        example_row = ["Misol savol", "ToвЂgвЂri javob", "NotoвЂgвЂri 1", "NotoвЂgвЂri 2", "NotoвЂgвЂri 3"]
        ws.append(example_row)

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            content=buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=questions_template.xlsx'
        return response


@method_decorator(login_required, name='dispatch')
class ExportQuestionsView(View):
    def get(self, request, test_id, format_type):
        test = get_object_or_404(Test, id=test_id)
        questions = Question.objects.filter(test=test).prefetch_related('answers')

        if format_type == 'json':
            return self.export_json(questions, test)
        elif format_type == 'xlsx':
            return self.export_excel(questions, test)
        elif format_type == 'csv':
            return self.export_csv(questions, test)
        elif format_type == 'docx':
            return self.export_docx(questions, test)
        else:
            return HttpResponse(status=400, content="NotoвЂgвЂri format turi")

    def export_json(self, questions, test):
        data = {
            'test_name': test.name,
            'questions': [
                {
                    'text': q.text,
                    'image': q.image.url if q.image else None,
                    'answers': [
                        {'text': a.text, 'is_correct': a.is_correct}
                        for a in q.answers.all()
                    ]
                }
                for q in questions
            ]
        }
        response = HttpResponse(
            content_type='application/json',
            content=json.dumps(data, ensure_ascii=False, indent=2)
        )
        response['Content-Disposition'] = f'attachment; filename="{test.name}_questions.json"'
        return response

    def export_excel(self, questions, test):
        wb = Workbook()
        ws = wb.active
        ws.title = "Questions"

        headers = ["Savol matni", "Variant 1", "Variant 2", "Variant 3", "Variant 4", "ToвЂgвЂri javob", "Rasm"]
        ws.append(headers)

        for q in questions:
            answers = list(q.answers.all())
            correct_answer = next((a.text for a in answers if a.is_correct), '')
            incorrect_answers = [a.text for a in answers if not a.is_correct][:3]
            row = [
                q.text,
                correct_answer,  # Variant 1 doim toвЂgвЂri
                incorrect_answers[0] if len(incorrect_answers) > 0 else '',
                incorrect_answers[1] if len(incorrect_answers) > 1 else '',
                incorrect_answers[2] if len(incorrect_answers) > 2 else '',
                "1 variant",
                q.image.name if q.image else ''
            ]
            ws.append(row)

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            content=buffer
        )
        response['Content-Disposition'] = f'attachment; filename="{test.name}_questions.xlsx"'
        return response

    def export_csv(self, questions, test):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{test.name}_questions.csv"'

        writer = csv.writer(response, lineterminator='\n')
        writer.writerow(["Savol matni", "Variant 1", "Variant 2", "Variant 3", "Variant 4", "ToвЂgвЂri javob", "Rasm"])

        for q in questions:
            answers = list(q.answers.all())
            correct_answer = next((a.text for a in answers if a.is_correct), '')
            incorrect_answers = [a.text for a in answers if not a.is_correct][:3]
            row = [
                q.text,
                correct_answer,
                incorrect_answers[0] if len(incorrect_answers) > 0 else '',
                incorrect_answers[1] if len(incorrect_answers) > 1 else '',
                incorrect_answers[2] if len(incorrect_answers) > 2 else '',
                "1 variant",
                q.image.name if q.image else ''
            ]
            writer.writerow(row)

        return response

    def export_docx(self, questions, test):
        doc = Document()
        doc.add_heading(f"{test.name} - Savollar", 0)

        for idx, q in enumerate(questions, 1):
            doc.add_paragraph(f"Savol {idx}: {q.text}")
            if q.image:
                try:
                    with q.image.open('rb') as img_file:
                        image_data = base64.b64encode(img_file.read()).decode('utf-8')
                    buffer = BytesIO(base64.b64decode(image_data))
                    doc.add_picture(buffer, width=Inches(4))
                except Exception:
                    doc.add_paragraph(f"[Rasm: {q.image.name}]")

            answers = list(q.answers.all())
            correct_answer = next((a.text for a in answers if a.is_correct), '')
            incorrect_answers = [a.text for a in answers if not a.is_correct][:3]

            doc.add_paragraph("Variant 1 (ToвЂgвЂri): " + correct_answer)
            for i, ans in enumerate(incorrect_answers, 2):
                doc.add_paragraph(f"Variant {i}: {ans}")
            doc.add_paragraph("=" * 50)

        buffer = BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            content=buffer
        )
        response['Content-Disposition'] = f'attachment; filename="{test.name}_questions.docx"'
        return response
