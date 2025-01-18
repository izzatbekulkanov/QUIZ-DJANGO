from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View

@method_decorator(login_required, name='dispatch')
class DashboardView(View):
    def get(self, request):
        dark_mode = request.COOKIES.get('dark_mode', 'false')
        return render(request, 'dashboard/views/main.html', {
            'user': request.user,
            'dark_mode': dark_mode,
        })