from django.urls import path

from question.view.test import StartTestView, StartTestDetailView, SaveAnswerView, FinishTestView, TestResultView
from .views import DashboardView, DashboardCategoriesView, CategoryAssignmentsView, CheckUnfinishedTestView, all_results

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('categories', DashboardCategoriesView.as_view(), name='dashboard-categories'),
    path('category/<int:category_id>/assignments/', CategoryAssignmentsView.as_view(), name='category-assignments'),
    path('start-test-detail/<int:assignment_id>/', StartTestDetailView.as_view(), name='start-test-detail'),
    path('start-test/<int:assignment_id>/', StartTestView.as_view(), name='start-test'),
    path('save-answer/', SaveAnswerView.as_view(), name='save-answer'),
    path('finish-test/<int:test_id>/', FinishTestView.as_view(), name='finish-test'),
    path('check-unfinished-test/<int:assignment_id>/', CheckUnfinishedTestView.as_view(), name='check-unfinished-test'),
    path('test/test_result/<int:test_id>/', TestResultView.as_view(), name='test-result'),
    path('all-results/', all_results, name='all_results'),
]
