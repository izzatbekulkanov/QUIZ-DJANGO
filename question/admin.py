# question/admin.py
from django.contrib import admin
from .models import Category, Test, Question, Answer, StudentTestAssignment, StudentTest, StudentTestQuestion


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    ordering = ('name',)

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'created_by', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    list_filter = ('category', 'created_by')
    ordering = ('name',)

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 1  # Qo‘shimcha bo‘sh javob formasi
    fields = ('text', 'is_correct')  # Ko‘rsatiladigan maydonlar
    readonly_fields = ()  # Faqat o'qiladigan maydonlar (agar kerak bo‘lsa)
    show_change_link = True  # Inline obyektga havola ko‘rsatish

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'test', 'get_answers', 'created_at', 'updated_at')
    search_fields = ('text',)
    list_filter = ('test',)
    ordering = ('test',)
    inlines = [AnswerInline]  # Answer modelini `Question` sahifasida ko‘rsatish

    def get_answers(self, obj):
        """
        Ushbu savolga tegishli javoblarni ko'rsatish.
        """
        answers = obj.answers.all()  # Related name: 'answers'
        return ", ".join([f"{answer.text} ({'Correct' if answer.is_correct else 'Incorrect'})" for answer in answers])

    get_answers.short_description = 'Answers'


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct')  # 'text' maydoniga to‘g‘rilash kiritildi
    search_fields = ('text',)
    list_filter = ('is_correct', 'question')

@admin.register(StudentTestAssignment)
class StudentTestAssignmentAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'test', 'category', 'total_questions', 'start_time', 'duration', 'end_time', 'is_active', 'status')
    list_filter = ('is_active', 'status', 'category', 'test', 'start_time', 'end_time')
    search_fields = ('teacher__username', 'test__name', 'category__name')
    ordering = ('-start_time',)
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Assignment Details', {
            'fields': ('teacher', 'test', 'category', 'total_questions', 'start_time', 'end_time', 'is_active', 'status')
        }),
        ('Additional Info', {
            'fields': ('created_at',),
        }),
    )

class StudentTestQuestionInline(admin.TabularInline):
    model = StudentTestQuestion
    extra = 0
    readonly_fields = ('question', 'selected_answer', 'is_correct')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StudentTest)
class StudentTestAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'start_time', 'end_time', 'duration', 'score', 'completed')
    list_filter = ('completed', 'assignment__test', 'assignment__category', 'start_time', 'end_time')
    search_fields = ('student__username', 'assignment__test__name', 'assignment__category__name')
    ordering = ('-start_time',)
    readonly_fields = ('start_time', 'end_time', 'duration', 'score', 'completed')
    actions = ['mark_as_completed', 'reset_scores']
    inlines = [StudentTestQuestionInline]

    @admin.action(description="Mark selected tests as completed")
    def mark_as_completed(self, request, queryset):
        queryset.update(completed=True)
        self.message_user(request, "Selected tests marked as completed.")

    @admin.action(description="Reset scores for selected tests")
    def reset_scores(self, request, queryset):
        queryset.update(score=0.0, completed=False)
        self.message_user(request, "Scores reset for selected tests.")