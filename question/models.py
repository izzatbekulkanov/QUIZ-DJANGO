# question/models.py
import random
from datetime import timedelta

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
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='tests')
    name = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Question(models.Model):
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='questions')
    text = CKEditor5Field(config_name='default')  # CKEditor5 ni ishlatamiz
    image = models.ImageField(upload_to='questions/images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.text

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text = models.CharField(max_length=200)  # 'text' maydoni aniq ko'rsatilgan
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Incorrect'})"

class UserTestResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_results', null=True, blank=True)
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='results')
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    completed_at = models.DateTimeField(auto_now_add=True)
    guest_first_name = models.CharField(max_length=100, null=True, blank=True)
    guest_last_name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        if self.user:
            return f"{self.user.username} - {self.test.name}: {self.score}"
        return f"{self.guest_first_name} {self.guest_last_name} - {self.test.name}: {self.score}"

class StudentTestAssignment(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='test_assignments')
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='assignments')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='test_assignments')
    total_questions = models.PositiveIntegerField(default=10)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration = models.PositiveIntegerField(default=30)  # Davomiylik (daqiqa ko'rinishida)
    is_active = models.BooleanField(default=True)  # Active yoki Active emas
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('completed', 'Completed')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.teacher} - {self.test.name} ({self.start_time} - {self.end_time})"

    def generate_questions(self):
        """
        Test uchun random savollar generatsiya qilish.
        """
        all_questions = list(self.test.questions.all())
        if len(all_questions) < self.total_questions:
            raise ValueError("Testda yetarli savollar mavjud emas.")
        return random.sample(all_questions, self.total_questions)

    def calculate_end_time(self):
        """
        Testning avtomatik tugash vaqtini hisoblash.
        """
        return self.start_time + timedelta(minutes=self.duration)


class StudentQuestion(models.Model):
    assignment = models.ForeignKey(StudentTestAssignment, on_delete=models.CASCADE, related_name='student_questions')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answers = models.ManyToManyField(Answer, related_name='student_answers')  # O‘quvchi belgilagan javoblar
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student.username} - {self.question.text[:30]}"

    def check_correctness(self):
        """
        To‘g‘ri yoki noto‘g‘ri ekanligini tekshirish.
        """
        correct_answers = set(self.question.answers.filter(is_correct=True))
        selected_answers = set(self.answers.all())
        self.is_correct = correct_answers == selected_answers
        self.save()