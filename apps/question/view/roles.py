from django.contrib.auth.models import Group, Permission
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

@method_decorator(login_required, name='dispatch')
class RolesView(View):
    template_name = 'question/views/roles.html'

    def get(self, request):
        # Barcha guruhlar va ularga birikkan foydalanuvchilar
        groups = Group.objects.prefetch_related('permissions', 'user_set').all()

        # Barcha ruxsatlar
        permissions = Permission.objects.all()

        context = {
            'groups': groups,  # Guruhlar
            'permissions': permissions,  # Barcha mavjud ruxsatlar
        }
        return render(request, self.template_name, context)