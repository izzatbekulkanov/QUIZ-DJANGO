from django.urls import path

from apps.question.view.test import StartTestView, StartTestDetailView, SaveAnswerView, FinishTestView, TestResultView

from .views import DashboardView, CheckUnfinishedTestView, all_results, ViewResultView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('tests/<int:assignment_id>/instructions/', StartTestDetailView.as_view(), name='start-test-detail'),
    path('tests/<int:assignment_id>/start/', StartTestView.as_view(), name='start-test'),
    path('tests/answer/save/', SaveAnswerView.as_view(), name='save-answer'),
    path('tests/<int:test_id>/finish/', FinishTestView.as_view(), name='finish-test'),
    path('tests/<int:assignment_id>/unfinished-status/', CheckUnfinishedTestView.as_view(), name='check-unfinished-test'),
    path('tests/<int:test_id>/result/', TestResultView.as_view(), name='test-result'),
    path('results/', all_results, name='all_results'),
    path('results/<int:result_id>/', ViewResultView.as_view(), name='view_result'),
]
