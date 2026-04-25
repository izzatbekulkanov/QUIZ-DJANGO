from django.urls import path
from . import views

urlpatterns = [
    # Yangi API endpoint
    path('all-test-results/', views.all_test_results, name='all_test_results'),
]