from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from shop.views import ProductViewSet, CategoryViewSet, GroupViewSet, CartViewSet, CommentViewSet
# from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.contrib.auth.views import LoginView, LogoutView

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'comments', CommentViewSet, basename='comment')

schema_view = get_schema_view(
    openapi.Info(
        title="Online Shop API",
        default_version='v1',
        description="Olcha.uz ga o'xshash online do'kon API",
    ),
    public=True,
)

urlpatterns = [
                  path('adminka/', admin.site.urls),
                  path('api/', include(router.urls)),
                  # path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
                  # path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
                  path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
                  path('', include('shop.urls')),
                  path('accounts/', include('accounts.urls')),
                  path('social-auth/', include('social_django.urls', namespace='social')),
                  path('login/', LoginView.as_view(template_name='registration/login.html', next_page='home'),
                       name='login'),
                  path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
