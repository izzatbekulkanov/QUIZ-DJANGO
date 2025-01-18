from django.urls import path
from .views import MainView, UsersView, AnswerQuestionView, CategoriesView, LogsView, QuestionView, RolesView, \
    ResultsView

urlpatterns = [
    path('main/', MainView.as_view(), name='main'),
    path('users/', UsersView.as_view(), name='users'),
    path('answer-question/', AnswerQuestionView.as_view(), name='answer_question'),
    path('categories/', CategoriesView.as_view(), name='categories'),
    path('logs/', LogsView.as_view(), name='logs'),
    path('question/', QuestionView.as_view(), name='question'),
    path('roles/', RolesView.as_view(), name='roles'),
    path('results/', ResultsView.as_view(), name='results'),
]