from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.views import View
from django.shortcuts import redirect, render
from django.contrib import messages
from django.contrib.auth import login
from django.views.generic import TemplateView

from accounts.models import User


class RegisterView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('home')
        return render(request, 'accounts/register.html')

    def post(self, request):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        try:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Successfully registered and logged in!')
            return redirect('home')
        except Exception as e:
            return render(request, 'accounts/register.html', {'errors': {'username': [str(e)]}})


class GoogleLoginCallback(View):
    def get(self, request):
        user = request.user
        if user.is_authenticated:
            messages.success(request, 'Successfully logged in with Google!')
            return redirect('home')
        return redirect('login')


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        favorites = self.request.user.favorite_products.all().select_related('group__category').prefetch_related(
            'images')
        paginator = Paginator(favorites, 9)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj
        return context

    def post(self, request, *args, **kwargs):
        user = request.user
        user.email = request.POST.get('email')
        user.phone_number = request.POST.get('phone_number')
        user.address = request.POST.get('address')
        user.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
