from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django import forms
from .models import Category, Test, Question, Answer, StudentTestAssignment, StudentTest, StudentTestQuestion, SystemSetting
from django_ckeditor_5.widgets import CKEditor5Widget

# Category uchun maxsus forma
class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'
        widgets = {
            'description': CKEditor5Widget(),
        }

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    list_display = ('name', 'description_preview', 'image_preview', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'description')
    date_hierarchy = 'created_at'
    ordering = ('name',)

    def description_preview(self, obj):
        return format_html(
            '{}...',
            obj.description[:50] if obj.description else ''
        )
    description_preview.short_description = 'Tavsif'

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px;" />',
                obj.image.url
            )
        return '-'
    image_preview.short_description = 'Rasm'

# Answer uchun inline
class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 2
    fields = ('text', 'is_correct')
    ordering = ('text',)

# Question uchun maxsus forma
class QuestionAdminForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = '__all__'
        widgets = {
            'text': CKEditor5Widget(),
        }

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    form = QuestionAdminForm
    inlines = [AnswerInline]
    list_display = ('text_preview', 'test', 'image_preview', 'created_at', 'updated_at')
    list_filter = ('test__category', 'created_at', 'updated_at')
    search_fields = ('text', 'test__name')
    list_select_related = ('test',)
    autocomplete_fields = ['test']
    ordering = ('test', 'created_at')

    def text_preview(self, obj):
        return format_html(
            '{}...',
            obj.text[:50]
        )
    text_preview.short_description = 'Savol matni'

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px;" />',
                obj.image.url
            )
        return '-'
    image_preview.short_description = 'Rasm'

# Test uchun inline Question
class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ('text', 'image')
    show_change_link = True

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    inlines = [QuestionInline]
    list_display = (
        'name', 'category', 'created_by', 'question_count',
        'student_count', 'created_at', 'updated_at'
    )
    list_filter = ('category', 'created_by', 'created_at', 'updated_at')
    search_fields = ('name', 'description', 'created_by__username')
    list_select_related = ('category', 'created_by')
    autocomplete_fields = ['category', 'created_by']
    filter_horizontal = ('students',)
    ordering = ('name',)
    actions = ['duplicate_test']

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Savollar'

    def student_count(self, obj):
        return obj.students.count()
    student_count.short_description = 'Talabalar'

    def duplicate_test(self, request, queryset):
        for test in queryset:
            original_id = test.id
            test.id = None
            test.name = f"{test.name} (Nusxa)"
            test.save()
            for question in Question.objects.filter(test_id=original_id):
                original_question_id = question.id
                question.id = None
                question.test = test
                question.save()
                for answer in Answer.objects.filter(question_id=original_question_id):
                    answer.id = None
                    answer.question = question
                    answer.save()
            messages.success(request, f"Test '{test.name}' muvaffaqiyatli nusxalandi.")
    duplicate_test.short_description = "Tanlangan testlarni nusxalash"

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct')
    list_filter = ('is_correct', 'question__test')
    search_fields = ('text', 'question__text')
    list_select_related = ('question', 'question__test')
    autocomplete_fields = ['question']
    ordering = ('question', 'text')

@admin.register(StudentTestAssignment)
class StudentTestAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'test', 'category', 'teacher', 'total_questions', 'start_time',
        'end_time', 'duration', 'is_active', 'status', 'attempts'
    )
    list_filter = ('category', 'teacher', 'start_time', 'end_time', 'is_active', 'status')
    search_fields = ('test__name', 'teacher__username', 'category__name')
    list_select_related = ('test', 'category', 'teacher')
    autocomplete_fields = ['test', 'category', 'teacher']
    date_hierarchy = 'start_time'
    ordering = ('-start_time',)
    actions = ['make_active', 'make_inactive']

    def make_active(self, request, queryset):
        queryset.update(is_active=True)
        messages.success(request, "Tanlangan topshiriqlar faollashtirildi.")
    make_active.short_description = "Tanlangan topshiriqlarni faollashtirish"

    def make_inactive(self, request, queryset):
        queryset.update(is_active=False)
        messages.success(request, "Tanlangan topshiriqlar faolsizlashtirildi.")
    make_inactive.short_description = "Tanlangan topshiriqlarni faolsizlashtirish"

@admin.register(StudentTest)
class StudentTestAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'assignment', 'score', 'duration_display',
        'completed', 'start_time', 'end_time'
    )
    list_filter = ('assignment__test', 'student', 'completed', 'start_time')
    search_fields = (
        'student__username', 'student__first_name',
        'assignment__test__name', 'assignment__category__name'
    )
    list_select_related = ('student', 'assignment__test', 'assignment__category')
    autocomplete_fields = ['student', 'assignment']
    date_hierarchy = 'start_time'
    ordering = ('-start_time',)

    def duration_display(self, obj):
        return obj.get_duration_display()
    duration_display.short_description = 'Davomiylik'

@admin.register(StudentTestQuestion)
class StudentTestQuestionAdmin(admin.ModelAdmin):
    list_display = ('student_test', 'question_preview', 'selected_answer', 'is_correct', 'order')
    list_filter = ('student_test__assignment__test', 'is_correct')
    search_fields = ('student_test__student__username', 'question__text')
    list_select_related = ('student_test__student', 'student_test__assignment', 'question', 'selected_answer')
    autocomplete_fields = ['student_test', 'question', 'selected_answer']
    ordering = ('student_test', 'order')

    def question_preview(self, obj):
        return format_html(
            '{}...',
            obj.question.text[:50]
        )
    question_preview.short_description = 'Savol'

# SystemSetting uchun maxsus forma
class SystemSettingAdminForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = '__all__'
        widgets = {
            'description': CKEditor5Widget(),
            'status_message': CKEditor5Widget(),
        }

@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    form = SystemSettingAdminForm
    list_display = (
        'name', 'is_active', 'status', 'status_message_preview',
        'contact_email', 'contact_phone', 'updated_at'
    )
    list_filter = ('is_active', 'status', 'updated_at')
    search_fields = ('name', 'description', 'contact_email', 'contact_phone')
    fieldsets = (
        ('Umumiy sozlamalar', {
            'fields': ('name', 'description', 'logo', 'favicon', 'is_active')
        }),
        ('Aloqa ma\'lumotlari', {
            'fields': ('contact_email', 'contact_phone', 'address', 'footer_text')
        }),
        ('HEMIS integratsiyasi', {
            'fields': ('hemis_url', 'hemis_api_key')
        }),
        ('Tizim holati', {
            'fields': ('status', 'status_message')
        }),
    )

    def status_message_preview(self, obj):
        return format_html(
            '{}...',
            obj.status_message[:50] if obj.status_message else ''
        )
    status_message_preview.short_description = 'Holat xabari'

# Autocomplete uchun qidiruv maydonlari
admin.site.search_fields = {
    'Test': ['name', 'description'],
    'Category': ['name'],
    'Question': ['text'],
    'Answer': ['text'],
    'StudentTestAssignment': ['test__name', 'category__name', 'teacher__username'],
    'StudentTest': ['student__username', 'assignment__test__name'],
}