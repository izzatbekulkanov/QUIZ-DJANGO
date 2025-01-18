from django.shortcuts import render
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

@method_decorator(login_required, name='dispatch')
class MainView(View):
    template_name = 'question/views/main.html'

    def get(self, request):
        return render(request, self.template_name)


@method_decorator(login_required, name='dispatch')
class UsersView(View):
    template_name = 'question/views/users.html'

    def get(self, request):
        return render(request, self.template_name)

@method_decorator(login_required, name='dispatch')
class AnswerQuestionView(View):
    template_name = 'question/views/answer-questions.html'

    def get(self, request):
        return render(request, self.template_name)

@method_decorator(login_required, name='dispatch')
class CategoriesView(View):
    template_name = 'question/views/categories.html'

    def get(self, request):
        return render(request, self.template_name)

@method_decorator(login_required, name='dispatch')
class LogsView(View):
    template_name = 'question/views/logs.html'

    def get(self, request):
        return render(request, self.template_name)

@method_decorator(login_required, name='dispatch')
class QuestionView(View):
    template_name = 'question/views/questions.html'

    def get(self, request):
        return render(request, self.template_name)

@method_decorator(login_required, name='dispatch')
class RolesView(View):
    template_name = 'question/views/roles.html'

    def get(self, request):
        return render(request, self.template_name)

@method_decorator(login_required, name='dispatch')
class ResultsView(View):
    template_name = 'question/views/results.html'

    def get(self, request):
        return render(request, self.template_name)