# question/admin.py
from django.contrib import admin
from .models import Category, Test, Question, Answer, UserTestResult

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
    list_display = ('text', 'question', 'is_correct')
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
