from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.utils.html import strip_tags

from .models import Test, SystemSetting


def _has_meaningful_rich_text(value):
    text = strip_tags(value or "").replace("\xa0", " ").strip()
    return bool(text)


class TestForm(forms.ModelForm):
    class Meta:
        model = Test
        fields = ['name', 'description', 'category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Test nomini kiriting'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Test taʼrifini kiriting', 'rows': 4}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }


class AddQuestionForm(forms.Form):
    text = forms.CharField(
        label="Savol matni",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "placeholder": "Savol matnini kiriting",
            "rows": 5
        }),
        required=True,
    )
    answers = forms.CharField(
        label="Variantlar",
        widget=forms.HiddenInput,
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        question_text = cleaned_data.get("text") or ""
        if not _has_meaningful_rich_text(question_text):
            self.add_error("text", "Savol matni bo'sh bo'lmasligi kerak.")

        answers = self.data.getlist('answers[]')
        is_correct_flags = self.data.getlist('is_correct[]')

        normalized_answers = []
        normalized_flags = []
        for index, answer in enumerate(answers):
            if not _has_meaningful_rich_text(answer):
                continue
            normalized_answers.append(answer.strip())
            normalized_flags.append(
                (is_correct_flags[index] if index < len(is_correct_flags) else "false").lower()
            )

        if len(normalized_answers) < 2:
            raise forms.ValidationError("Kamida 2 ta variant kiritishingiz kerak!")

        if not any(flag == 'true' for flag in normalized_flags):
            raise forms.ValidationError("Hech bo'lmaganda bitta to'g'ri javob belgilanmashi kerak!")

        cleaned_data['answers'] = normalized_answers
        cleaned_data['is_correct_flags'] = normalized_flags
        return cleaned_data


class RoleGroupManageForm(forms.Form):
    name = forms.CharField(
        label="Guruh nomi",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Masalan: Administratorlar",
            }
        ),
    )
    permissions = forms.ModelMultipleChoiceField(
        label="Ruxsatlar",
        queryset=Permission.objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-select searchable-multi",
                "data-placeholder": "Ruxsatlarni yozib qidiring",
            }
        ),
    )
    users = forms.ModelMultipleChoiceField(
        label="Foydalanuvchilar",
        queryset=get_user_model().objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-select searchable-multi",
                "data-placeholder": "Foydalanuvchilarni yozib qidiring",
            }
        ),
    )

    def __init__(
        self,
        *args,
        group_instance=None,
        permission_queryset=None,
        user_queryset=None,
        include_users=True,
        **kwargs,
    ):
        self.group_instance = group_instance
        self.include_users = include_users
        super().__init__(*args, **kwargs)

        self.fields["permissions"].queryset = permission_queryset or Permission.objects.none()
        self.fields["users"].queryset = user_queryset or get_user_model().objects.none()

        if not include_users:
            self.fields.pop("users")

        if group_instance and not self.is_bound:
            self.initial.setdefault("name", group_instance.name)
            self.initial.setdefault(
                "permissions",
                list(group_instance.permissions.values_list("id", flat=True)),
            )
            if include_users:
                self.initial.setdefault(
                    "users",
                    list(group_instance.user_set.values_list("id", flat=True)),
                )

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError("Guruh nomini kiriting.")

        queryset = Group.objects.filter(name__iexact=name)
        if self.group_instance:
            queryset = queryset.exclude(pk=self.group_instance.pk)

        if queryset.exists():
            raise forms.ValidationError("Bu nomdagi guruh allaqachon mavjud.")

        return name


