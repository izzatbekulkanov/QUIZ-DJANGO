from django.urls import path
from .views import DashboardView, DashboardCategoriesView, CategoryAssignmentsView, StartTestView

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
    path('categories', DashboardCategoriesView.as_view(), name='dashboard-categories'),
    path('category/<int:category_id>/assignments/', CategoryAssignmentsView.as_view(), name='category-assignments'),

    path('start-test/<int:assignment_id>/', StartTestView.as_view(), name='start-test'),
]
