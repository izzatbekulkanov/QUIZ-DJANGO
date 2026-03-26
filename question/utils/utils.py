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


def _word_doc_to_docx(doc_path):
    import shutil
    import subprocess
    from pathlib import Path
    soffice = shutil.which("soffice")
    if not soffice:
        raise RuntimeError("Tizimda LibreOffice (soffice) o'rnatilmagan, faqat .docx format ishlaydi. .doc faylni konvert qilib bo'lmadi.")

    doc_path = Path(doc_path).resolve()
    out_dir = doc_path.parent
    proc = subprocess.run(
        [soffice, "--headless", "--convert-to", "docx", "--outdir", str(out_dir), str(doc_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    out_path = doc_path.with_suffix(".docx")
    if proc.returncode != 0 or not out_path.exists():
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f".doc faylni .docx ga konvert qilishda xato: {stderr or proc.returncode}")
    return out_path


def parse_word(file) -> list[dict]:
    """
    Word (.doc, .docx) fayllarini o'qish (Linux va Windows).
    Eski format (Variant va Jadval) hamda yangi format (===== #) qo'llab-quvvatlanadi.
    """
    from docx import Document
    from pathlib import Path
    import tempfile
    import re

    name = getattr(file, "name", "") or ""
    suffix = Path(name).suffix.lower()
    if suffix not in [".docx", ".doc"]:
        raise ValueError("Faqat .docx yoki .doc fayllar qabul qilinadi")

    with tempfile.TemporaryDirectory(prefix="quiz_word_") as td:
        img_path = Path(td)
        in_path = img_path / f"input{suffix}"
        
        # Faylni temp direktoriyaga yozish
        with open(in_path, "wb") as f:
            if hasattr(file, "chunks"):
                for chunk in file.chunks():
                    f.write(chunk)
            else:
                f.write(file.read())

        docx_path = in_path
        if suffix == ".doc":
            docx_path = _word_doc_to_docx(in_path)

        doc = Document(docx_path)
        questions = []
        
        q_re = re.compile(r"^Savol\s*(\d+)\s*[:.)]?\s*", re.IGNORECASE)
        v_re = re.compile(r"^Variant\s*(\d+)\b", re.IGNORECASE)
        sep_re = re.compile(r"^[=\-]{10,}$")
        
        current_q_text = []
        current_answers = []
        
        # 1. Matnli (Paragraph) tahlil
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
                
            # Separator
            if text == "+++++" or sep_re.match(text):
                if current_q_text and current_answers:
                    questions.append({
                        "text": "<br>".join(current_q_text),
                        "image_base64": None,
                        "answers": current_answers
                    })
                current_q_text = []
                current_answers = []
                continue
                
            # Match Savol
            if q_re.match(text):
                if current_q_text and current_answers:
                    questions.append({
                        "text": "<br>".join(current_q_text),
                        "image_base64": None,
                        "answers": current_answers
                    })
                current_q_text = [text]
                current_answers = []
                continue
                
            # Yangi yondashuv (===== #Javob)
            if text.startswith("====="):
                ans_text = text[5:].strip()
                is_correct = False
                if ans_text.startswith("#"):
                    is_correct = True
                    ans_text = ans_text[1:].strip()
                current_answers.append((ans_text, is_correct))
                continue
                
            # Eski yondashuv (Variant N)
            vm = v_re.match(text)
            if vm:
                vnum = int(vm.group(1))
                t_low = text.lower()
                is_correct = (vnum == 1) or ("to'g'ri" in t_low) or ("togri" in t_low)
                current_answers.append((text, is_correct))
                continue
                
            current_q_text.append(text)
            
        if current_q_text and current_answers:
            questions.append({
                "text": "<br>".join(current_q_text),
                "image_base64": None,
                "answers": current_answers
            })
            
        # Agar matn orqali topilsa, o'shani qaytarish
        if questions:
            return questions
            
        # 2. Jadval orqali (Fallback)
        for table in doc.tables:
            for row in table.rows:
                cells = row.cells
                if len(cells) < 3:
                    continue
                    
                stem = cells[0].text.strip()
                if not stem:
                    continue
                    
                answers = []
                options = cells[1:5]
                # Bitta cell matni faqat 1 marta append bo'lishi uchun kichik filter (mergedlar uchun shart emas, lekin word cellarni takrorlaydi)
                last_txt = None
                for cell in options:
                    c_text = cell.text.strip()
                    if c_text and c_text != last_txt:
                        answers.append((c_text, False))
                        last_txt = c_text
                        
                if len(answers) < 2:
                    continue
                    
                answers[0] = (answers[0][0], True)
                questions.append({
                    "text": stem,
                    "image_base64": None,
                    "answers": answers
                })
                
        return questions

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
