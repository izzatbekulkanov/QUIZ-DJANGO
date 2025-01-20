# question/admin.py
from django.contrib import admin
from .models import Category, Test, Question, Answer, UserTestResult, StudentTestAssignment, StudentQuestion


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

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'test', 'created_at', 'updated_at')
    search_fields = ('text',)
    list_filter = ('test',)
    ordering = ('test',)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('text', 'question', 'is_correct')  # 'text' maydoniga to‘g‘rilash kiritildi
    search_fields = ('text',)
    list_filter = ('is_correct', 'question')

@admin.register(UserTestResult)
class UserTestResultAdmin(admin.ModelAdmin):
    list_display = ('get_user_or_guest', 'test', 'score', 'completed_at')
    search_fields = ('user__username', 'test__name', 'guest_first_name', 'guest_last_name')
    list_filter = ('test', 'completed_at')
    ordering = ('-completed_at',)

    def get_user_or_guest(self, obj):
        if obj.user:
            return obj.user.username
        return f"{obj.guest_first_name} {obj.guest_last_name}"
    get_user_or_guest.short_description = 'User/Guest'


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


@admin.register(StudentQuestion)
class StudentQuestionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'question', 'is_correct', 'answered_at')
    list_filter = ('is_correct', 'assignment__test', 'answered_at')
    search_fields = ('student__username', 'question__text', 'assignment__test__name')
    ordering = ('-answered_at',)
    filter_horizontal = ('answers',)  # ManyToManyField uchun qo'shimcha UI
    fieldsets = (
        ('Question Details', {
            'fields': ('assignment', 'student', 'question', 'answers', 'is_correct', 'answered_at')
        }),
    )