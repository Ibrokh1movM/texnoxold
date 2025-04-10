from django.urls import path
from .views import RegisterView, GoogleLoginCallback, ProfileView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('google/callback/', GoogleLoginCallback.as_view(), name='google_callback'),
    path('profile/', ProfileView.as_view(), name='profile'),
]
