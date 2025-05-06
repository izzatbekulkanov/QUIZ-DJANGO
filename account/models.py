# account/models.py
from django.contrib.auth.models import AbstractUser, Group, Permission
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
    education_level = models.CharField(max_length=100, null=True, blank=True)
    education_type = models.CharField(max_length=100, null=True, blank=True)
    payment_form = models.CharField(max_length=100, null=True, blank=True)
    education_year = models.CharField(max_length=20, null=True, blank=True)

    # Boshqa
    bio = models.TextField(null=True, blank=True)
    emergency_contact = models.CharField(max_length=15, null=True, blank=True)

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if not self.full_name and self.first_name and self.second_name:
            self.full_name = f"{self.first_name} {self.second_name}"
        super().save(*args, **kwargs)