# question/models.py
import random
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils import timezone
from django_ckeditor_5.fields import CKEditor5Field
from django.db import models
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    image = models.ImageField(upload_to='category_images/', null=True, blank=True)  # Rasm maydoni
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Test(models.Model):
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='tests')
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Talabalarni biriktirish uchun ManyToManyField
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='assigned_tests',
        blank=True,
        limit_choices_to={'is_student': True},  # Faqat talabalarni ko‘rsatish
    )

    def __str__(self):
        return self.name


class Question(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()  # Matn uchun TextField ishlatilmoqda
    image = models.ImageField(upload_to='questions/images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.text[:50]  # Matnning birinchi 50 belgisi qaytariladi


class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    # Allow rich HTML (images as base64) for Word/Excel imports.
    text = models.TextField()
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Incorrect'})"


class StudentTestAssignment(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name='test_assignments')
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='assignments')
    category = models.ForeignKey(Category, on_delete=models.CASCADE,
                                 related_name='test_assignments')

    total_questions = models.PositiveIntegerField(default=10)
    start_time = models.DateTimeField()
    end_time   = models.DateTimeField()
    duration   = models.PositiveIntegerField(default=30)

    is_active  = models.BooleanField(default=True)
    status     = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('completed', 'Completed')],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    attempts   = models.PositiveIntegerField(default=0)

    # 🔎 Faqat ikkita tekshiruv qoldi
    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("Boshlanish vaqti tugash vaqtidan oldin bo‘lishi kerak.")
        if self.total_questions > self.test.questions.count():
            raise ValidationError(
                f"Savollar soni testdagi savollar sonidan ({self.test.questions.count()}) oshmasligi kerak."
            )

    def save(self, *args, **kwargs):
        self.full_clean()            # clean() ni majburiy chaqiramiz
        super().save(*args, **kwargs)

    def increment_attempts(self):
        """Urinishlar sonini birga oshiradi."""
        self.attempts += 1
        self.save()

    def __str__(self):
        return f"{self.teacher} - {self.test.name} ({self.start_time} – {self.end_time})"


class StudentTest(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_tests')
    assignment = models.ForeignKey(StudentTestAssignment, on_delete=models.CASCADE, related_name='student_tests')
    questions = models.ManyToManyField('Question', through='StudentTestQuestion')
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    duration = models.PositiveIntegerField(default=0)  # Soniyalarda davomiylik
    score = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.student.username} - {self.assignment.test.name}"

    def get_duration_display(self):
        """Soniyalarni MM:SS formatida qaytaradi."""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes:02d}:{seconds:02d}"


def student_test_answer_snapshot_upload_to(instance, filename):
    extension = Path(filename or "").suffix.lower() or ".jpg"
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return (
        f"student_tests/{instance.student_test_id}/answers/"
        f"question_{instance.question_id}_{timestamp}{extension}"
    )


class StudentTestQuestion(models.Model):
    student_test = models.ForeignKey(StudentTest, on_delete=models.CASCADE, related_name='student_questions')
    question = models.ForeignKey('Question', on_delete=models.CASCADE, related_name='student_test_questions')
    selected_answer = models.ForeignKey('Answer', on_delete=models.SET_NULL, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(null=True, blank=True)
    answer_snapshot = models.ImageField(
        upload_to=student_test_answer_snapshot_upload_to,
        null=True,
        blank=True,
    )
    order = models.PositiveIntegerField()  # Savollar tartibini saqlash

    def __str__(self):
        return f"{self.student_test.student.username} - {self.question.text[:50]}"


class HelpResultPlan(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Kutilmoqda"),
        (STATUS_COMPLETED, "Bajarildi"),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="help_result_plans",
    )
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="help_result_plans")
    assignment = models.ForeignKey(
        StudentTestAssignment,
        on_delete=models.CASCADE,
        related_name="help_result_plans",
    )
    total_questions = models.PositiveIntegerField()
    target_correct_answers = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_help_result_plans",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["student", "assignment", "status"]),
            models.Index(fields=["created_at"]),
        ]

    @property
    def target_percent(self):
        if not self.total_questions:
            return 0
        return self.target_correct_answers / self.total_questions * 100

    def clean(self):
        if self.assignment_id and self.test_id and self.assignment.test_id != self.test_id:
            raise ValidationError("Topshiriq va test bir-biriga mos bo'lishi kerak.")

        if self.assignment_id:
            self.total_questions = self.assignment.total_questions

        if self.target_correct_answers > self.total_questions:
            raise ValidationError(
                {
                    "target_correct_answers": (
                        "Kiritilgan savollar soni topshiriqdagi random savollar sonidan oshmasligi kerak."
                    )
                }
            )

    def save(self, *args, **kwargs):
        if self.assignment_id:
            self.test_id = self.assignment.test_id
            self.total_questions = self.assignment.total_questions
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.student} - {self.assignment.test.name}: "
            f"{self.target_correct_answers}/{self.total_questions}"
        )


class SystemSetting(models.Model):
    name = models.CharField(max_length=255, verbose_name="Tizim nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Tizim haqida tavsif")
    logo = models.ImageField(upload_to='system/logo/', blank=True, null=True, verbose_name="Logo")
    favicon = models.ImageField(upload_to='system/favicon/', blank=True, null=True, verbose_name="Favicon")
    contact_email = models.EmailField(blank=True, null=True, verbose_name="Aloqa email")
    contact_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Aloqa telefoni")
    address = models.TextField(blank=True, null=True, verbose_name="Manzil")
    footer_text = models.CharField(max_length=255, blank=True, null=True, verbose_name="Footer matni")
    is_active = models.BooleanField(default=True, verbose_name="Faollashtirilganmi")
    updated_at = models.DateTimeField(auto_now=True)

    # HEMIS
    hemis_url = models.URLField(blank=True, null=True, verbose_name="HEMIS URL")
    hemis_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="HEMIS API Key")

    # Holat
    status = models.CharField(max_length=50, choices=[
        ('active', 'Sayt ishlamoqda'),
        ('maintenance', 'Sayt tamirlanmoqda'),
        ('offline', 'Sayt offline'),
    ], default='active', verbose_name="Sayt holati")

    # ✅ YANGI MAYDON:
    status_message = models.TextField(blank=True, null=True, verbose_name="Holat matni")

    def __str__(self):
        return self.name
