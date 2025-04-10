from django.urls import path
from .views import (
    HomeView, ProductDetailView, CartView, CheckoutView,
    ProductManageView, ProductEditView, ProductDeleteView,
    CategoryManageView, CategoryEditView, CategoryDeleteView,
    GroupManageView, GroupEditView, GroupDeleteView,
    CommentManageView, CommentEditView, CommentDeleteView,
    add_to_favorites
)

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('product/<slug:slug>/', ProductDetailView.as_view(), name='product_detail'),
    path('cart/', CartView.as_view(), name='cart'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('products/manage/', ProductManageView.as_view(), name='product_manage'),
    path('products/edit/<int:pk>/', ProductEditView.as_view(), name='product_edit'),
    path('products/delete/<int:pk>/', ProductDeleteView.as_view(), name='product_delete'),
    path('categories/manage/', CategoryManageView.as_view(), name='category_manage'),
    path('categories/edit/<int:pk>/', CategoryEditView.as_view(), name='category_edit'),
    path('categories/delete/<int:pk>/', CategoryDeleteView.as_view(), name='category_delete'),
    path('groups/manage/', GroupManageView.as_view(), name='group_manage'),
    path('groups/edit/<int:pk>/', GroupEditView.as_view(), name='group_edit'),
    path('groups/delete/<int:pk>/', GroupDeleteView.as_view(), name='group_delete'),
    path('comments/manage/', CommentManageView.as_view(), name='comment_manage'),
    path('comments/edit/<int:pk>/', CommentEditView.as_view(), name='comment_edit'),
    path('comments/delete/<int:pk>/', CommentDeleteView.as_view(), name='comment_delete'),
    path('product/<int:pk>/add-to-favorites/', add_to_favorites, name='add_to_favorites'),
]
