from django.urls import path

from .utils.utils import DownloadTemplateView, SaveImportedQuestionsView, ImportQuestionsView, ExportQuestionsView
from .view.category import CategoriesView, AddCategoryView, EditCategoryView, GetCategoryTestsView, \
    GetTestQuestionsCountView
from .view.hemis_users import ImportStudentsFromHemisStreamView, ImportStaffFromHemisStreamView
from .view.site import site_settings_view
from .view.test import QuestionView, AddQuestionView, DeleteTestView, EditTestView, AddQuestionTestView, AssignTestView, \
    ToggleActiveView, AddAssignTestView, DeleteAssignmentView
from .views import MainView, UsersView, ResultsView, AddUserView, EditUserView, ViewTestDetailsView, \
    assign_students_to_test, GenerateFaceEncodingsView
from .view.roles import RolesView

urlpatterns = [
    # Asosiy sahifalar
    path('main/', MainView.as_view(), name='main'),
    path('site-settings/', site_settings_view, name='site_settings'),

    # Foydalanuvchi bilan bog‘liq yo‘nalishlar
    path('users/', UsersView.as_view(), name='users'),
    path('add-users/', AddUserView.as_view(), name='add-user'),
    path('edit-users/<int:id>/', EditUserView.as_view(), name='edit-user'),
    path('delete/<int:id>/', UsersView.as_view(), name='delete-user'),
    path('generate-face-encodings/', GenerateFaceEncodingsView.as_view(), name='generate_face_encodings'),

    # Kategoriya bilan bog‘liq yo‘nalishlar
    path('categories/', CategoriesView.as_view(), name='categories'),
    path('add-category/', AddCategoryView.as_view(), name='add-category'),
    path('categories/edit/<int:category_id>/', EditCategoryView.as_view(), name='edit-category'),
    path('categories/delete/<int:category_id>/', CategoriesView.as_view(), name='delete-category'),
    path('category-tests/', GetCategoryTestsView.as_view(), name='category-tests'),
    path('test-questions-count/', GetTestQuestionsCountView.as_view(), name='test-questions-count'),

    # Test va savollar bilan bog‘liq yo‘nalishlar
    path('question/', QuestionView.as_view(), name='question'),
    path('add-question/', AddQuestionView.as_view(), name='add-question'),
    path('tests/<int:test_id>/add-question/', AddQuestionTestView.as_view(), name='add-question-test'),
    path('question/edit/<int:test_id>/', EditTestView.as_view(), name='edit-test'),
    path('question/delete/<int:test_id>/', DeleteTestView.as_view(), name='delete-test'),
    path('test/<int:test_id>/details/', ViewTestDetailsView.as_view(), name='view-test-details'),
    path('test/<int:test_id>/import-questions/', ImportQuestionsView.as_view(), name='import-questions'),
    path('save-imported-questions/', SaveImportedQuestionsView.as_view(), name='save-imported-questions'),
    path('download-template/', DownloadTemplateView.as_view(), name='download-template'),
    path('test/<int:test_id>/export/<str:format_type>/', ExportQuestionsView.as_view(), name='export-questions'),

    # Test tayinlash bilan bog‘liq yo‘nalishlar
    path('assign-test/', AssignTestView.as_view(), name='assign-test'),
    path('add-assign-test/', AddAssignTestView.as_view(), name='add-assign-test'),
    path('assignments/delete/<int:assignment_id>/', DeleteAssignmentView.as_view(), name='delete-assignment'),
    path('test/<int:test_id>/assign-students/', assign_students_to_test, name='assign-students-to-test'),
    path('assignments/toggle-active/<int:assignment_id>/', ToggleActiveView.as_view(), name='toggle-active'),

    # HEMIS importlari
    path('import/students/', ImportStudentsFromHemisStreamView.as_view(), name='import_students'),
    path('import/staff/', ImportStaffFromHemisStreamView.as_view(), name='import_staff'),

    # Natijalar va rollar
    path('results/', ResultsView.as_view(), name='results'),
    path('roles/', RolesView.as_view(), name='roles'),
]
