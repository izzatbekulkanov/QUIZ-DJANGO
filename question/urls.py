from django.urls import path

from .view.category import CategoriesView, AddCategoryView, EditCategoryView
from .view.test import QuestionView, AddQuestionView, DeleteTestView, EditTestView, AddQuestionTestView, FetchTestsView, \
    AddAssignTestView, AssignTestView, ToggleActiveView
from .views import MainView, UsersView, \
    ResultsView, AddUserView, EditUserView
from .view.roles import RolesView

urlpatterns = [
    path('main/', MainView.as_view(), name='main'),
    path('users/', UsersView.as_view(), name='users'),
    path('add-users/', AddUserView.as_view(), name='add-user'),
    path('edit-users/<int:id>/', EditUserView.as_view(), name='edit-user'),
    path('delete/<int:id>/', UsersView.as_view(), name='delete-user'),
    path('assign-test/', AssignTestView.as_view(), name='assign-test'),
    path('add-assign-test/', AddAssignTestView.as_view(), name='add-assign-test'),

    path('assignments/toggle-active/<int:assignment_id>/', ToggleActiveView.as_view(), name='toggle-active'),
    path('fetch/tests/', FetchTestsView.as_view(), name='fetch-tests'),
    path('categories/', CategoriesView.as_view(), name='categories'),
    path('categories/edit/<int:category_id>/', EditCategoryView.as_view(), name='edit-category'),
    path('categories/delete/<int:category_id>/', CategoriesView.as_view(), name='delete-category'),
    path('add-category/', AddCategoryView.as_view(), name='add-category'),
    path('question/', QuestionView.as_view(), name='question'),
    path('add-question/', AddQuestionView.as_view(), name='add-question'),
    path('question/delete/<int:test_id>/', DeleteTestView.as_view(), name='delete-test'),
    path('question/edit/<int:test_id>/', EditTestView.as_view(), name='edit-test'),
    path('tests/<int:test_id>/add-question/', AddQuestionTestView.as_view(), name='add-question-test'),
    path('roles/', RolesView.as_view(), name='roles'),
    path('results/', ResultsView.as_view(), name='results'),
]