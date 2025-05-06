from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget

from .models import Test, SystemSetting


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
    image = forms.ImageField(
        label="Savol rasmi (ixtiyoriy)",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*", "class": "form-control"})
    )
    answers = forms.CharField(
        label="Variantlar",
        widget=forms.HiddenInput,
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        answers = self.data.getlist('answers[]')  # Variantlar (answers[])
        is_correct_flags = self.data.getlist('is_correct[]')  # To'g'ri javoblar bayroqlari

        # Kamida 2 ta variant bo'lishi kerakligini tekshirish
        if not answers or len(answers) < 2:
            raise forms.ValidationError("Kamida 2 ta variant kiritishingiz kerak!")

        # Kamida 1 ta to'g'ri javob bo'lishini tekshirish
        if not any(flag.lower() == 'true' for flag in is_correct_flags):
            raise forms.ValidationError("Hech bo'lmaganda bitta to'g'ri javob belgilanmashi kerak!")

        cleaned_data['answers'] = answers
        cleaned_data['is_correct_flags'] = is_correct_flags
        return cleaned_data


