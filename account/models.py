import json
import pickle
from django.contrib.auth.models import AbstractUser
from django.db import models
class CustomUser(AbstractUser):
    # Asosiy
    full_name = models.CharField(max_length=255, null=True, blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    second_name = models.CharField(max_length=100, null=True, blank=True)
    third_name = models.CharField(max_length=100, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    # Aloqa
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    contact_email = models.EmailField(null=True, blank=True)

    # Profil rasmi
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)

    # Jins va fuqarolik
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female')], null=True, blank=True)
    nationality = models.CharField(max_length=100, null=True, blank=True)
    citizenship = models.CharField(max_length=100, null=True, blank=True)

    # Talaba va Hodim flag
    is_student = models.BooleanField(default=False)
    is_teacher = models.BooleanField(default=False)

    # Hodimga oid
    job_title = models.CharField(max_length=100, null=True, blank=True)
    company_name = models.CharField(max_length=100, null=True, blank=True)
    department = models.CharField(max_length=255, null=True, blank=True)
    academic_degree = models.CharField(max_length=100, null=True, blank=True)
    academic_rank = models.CharField(max_length=100, null=True, blank=True)
    staff_position = models.CharField(max_length=100, null=True, blank=True)
    employee_id_number = models.IntegerField(null=True, blank=True)

    # Talabaga oid
    student_id_number = models.CharField(max_length=100, null=True, blank=True)
    group_name = models.CharField(max_length=100, null=True, blank=True)
    specialty = models.CharField(max_length=255, null=True, blank=True)
    specialty_name = models.CharField(max_length=255, null=True, blank=True)
    education_level = models.CharField(max_length=100, null=True, blank=True)
    education_type = models.CharField(max_length=100, null=True, blank=True)
    education_form_name = models.CharField(max_length=100, null=True, blank=True)
    payment_form = models.CharField(max_length=100, null=True, blank=True)
    education_year = models.CharField(max_length=20, null=True, blank=True)
    department_name = models.CharField(max_length=255, null=True, blank=True)
    level_name = models.CharField(max_length=100, null=True, blank=True)

    # Boshqa
    bio = models.TextField(null=True, blank=True)
    emergency_contact = models.CharField(max_length=15, null=True, blank=True)

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if not self.full_name and self.first_name and self.second_name:
            self.full_name = f"{self.first_name} {self.second_name}"
        super().save(*args, **kwargs)



class FaceEncoding(models.Model):
    user = models.OneToOneField('CustomUser', on_delete=models.CASCADE, related_name='face_encoding')
    encoding = models.BinaryField(null=True, blank=True)
    facial_features = models.BinaryField(null=True, blank=True)
    image_resolution = models.CharField(max_length=20, null=True, blank=True)
    encoding_version = models.CharField(max_length=20, null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Face Encoding"

    def get_encoding(self):
        return pickle.loads(self.encoding) if self.encoding else None

    def get_facial_features(self):
        return pickle.loads(self.facial_features) if self.facial_features else None
