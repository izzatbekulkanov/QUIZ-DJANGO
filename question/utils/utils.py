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


def parse_word(file) -> list[dict]:
    """
    Word (.docx) faylidan savollarni o'qish (Linux va Windows uchun mos).
    Faqat .docx fayllar qabul qilinadi.
    Format:
    Savol matni
    ===== #To'g'ri javob
    ===== Noto'g'ri javob 1
    ===== Noto'g'ri javob 2
    +++++
    """
    from docx import Document
    from pathlib import Path
    
    name = getattr(file, "name", "") or ""
    suffix = Path(name).suffix.lower()
    
    if suffix == ".doc":
        raise ValueError("Eski .doc fayllar qo'llab-quvvatlanmaydi, iltimos faylni .docx formatida saqlab yuklang.")
    elif suffix != ".docx":
        raise ValueError("Faqat .docx fayllar qabul qilinadi")

    doc = Document(file)
    questions = []
    
    current_question_text = []
    current_answers = []
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
            
        if text == "+++++":
            if current_question_text and current_answers:
                questions.append({
                    "text": "<br>".join(current_question_text),
                    "image_base64": None,
                    "answers": current_answers
                })
            current_question_text = []
            current_answers = []
            continue
            
        if text.startswith("====="):
            ans_text = text[5:].strip()
            is_correct = False
            if ans_text.startswith("#"):
                is_correct = True
                ans_text = ans_text[1:].strip()
                
            current_answers.append((ans_text, is_correct))
        else:
            current_question_text.append(text)
            
    if current_question_text and current_answers:
        questions.append({
            "text": "<br>".join(current_question_text),
            "image_base64": None,
            "answers": current_answers
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
