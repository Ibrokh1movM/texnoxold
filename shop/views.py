from django.contrib.auth.decorators import login_required
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.db.models import Q, Count
from .models import Product, Category, Group, Cart, Comment, Order
from .serializers import ProductSerializer, CategorySerializer, GroupSerializer, CartSerializer, CommentSerializer
from .permissions import IsAdminOrReadOnly
import stripe
from django.conf import settings
from .tasks import send_order_confirmation_email
import json
from django.http import JsonResponse

stripe.api_key = settings.STRIPE_SECRET_KEY


class HomeView(ListView):
    model = Product
    template_name = 'index.html'
    context_object_name = 'page_obj'
    paginate_by = 9

    def get_queryset(self):
        queryset = Product.objects.all().select_related('group__category').prefetch_related('images',
                                                                                            'favorites').order_by(
            '-created_at')
        category_id = self.request.GET.get('category')
        group_id = self.request.GET.get('group')
        min_price = self.request.GET.get('min_price')
        max_price = self.request.GET.get('max_price')
        search_query = self.request.GET.get('search', '')

        if category_id:
            queryset = queryset.filter(group__category_id=category_id)
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        if min_price:
            queryset = queryset.filter(final_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(final_price__lte=max_price)
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(group__name__icontains=search_query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all().prefetch_related('groups')
        return context


class ProductDetailView(DetailView):
    model = Product
    template_name = 'product_detail.html'
    context_object_name = 'product'
    slug_field = 'slug'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['related_products'] = Product.objects.filter(group=self.object.group).exclude(
            id=self.object.id).prefetch_related('images')[:4]
        context['comments'] = self.object.comments.all().select_related('user')
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = request.POST.get('action')

        if action == 'add_comment':
            if not request.user.is_authenticated:
                messages.error(request, 'You must be logged in to comment.')
                return redirect('product_detail', slug=self.object.slug)

            content = request.POST.get('content')
            Comment.objects.create(user=request.user, product=self.object, content=content)
            messages.success(request, 'Comment added successfully!')
            return redirect('product_detail', slug=self.object.slug)

        elif action == 'like_comment':
            if not request.user.is_authenticated:
                messages.error(request, 'You must be logged in to like a comment.')
                return redirect('product_detail', slug=self.object.slug)

            comment_id = request.POST.get('comment_id')
            comment = get_object_or_404(Comment, id=comment_id)
            if request.user in comment.likes.all():
                comment.likes.remove(request.user)
            else:
                comment.likes.add(request.user)
            return redirect('product_detail', slug=self.object.slug)

        return super().get(request, *args, **kwargs)


from django.http import HttpResponseRedirect


class CartView(LoginRequiredMixin, TemplateView):
    template_name = 'shop/cart.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart_items = Cart.objects.filter(user=self.request.user).select_related('product')
        total = sum(item.total_price for item in cart_items)
        context['cart_items'] = cart_items
        context['total'] = total
        context['cart_count'] = cart_items.count()
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        product_id = request.POST.get('product_id')

        if action == 'add':
            product = get_object_or_404(Product, id=product_id)
            cart_item, created = Cart.objects.get_or_create(user=request.user, product=product)
            if not created:
                cart_item.quantity += 1
                cart_item.save()
            messages.success(request, 'Product added to cart!')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', 'home'))

        cart_item = get_object_or_404(Cart, user=request.user, product_id=product_id)

        if action == 'remove':
            cart_item.delete()
            messages.success(request, 'Product removed from cart!')
        elif action == 'update_quantity':
            change = request.POST.get('change')
            if change == 'increase':
                cart_item.quantity += 1
            elif change == 'decrease' and cart_item.quantity > 1:
                cart_item.quantity -= 1
            else:
                cart_item.delete()
                messages.success(request, 'Product removed from cart!')
                return redirect('cart')
            cart_item.save()
            messages.success(request, 'Quantity updated!')
        return redirect('cart')


class CheckoutView(LoginRequiredMixin, TemplateView):
    template_name = 'checkout.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart_items = Cart.objects.filter(user=self.request.user).select_related('product')
        total_price = sum(item.total_price for item in cart_items)
        context['cart_items'] = cart_items
        context['total_price'] = total_price
        context['stripe_publishable_key'] = settings.STRIPE_PUBLISHABLE_KEY
        return context

    def post(self, request, *args, **kwargs):
        cart_items = Cart.objects.filter(user=request.user).select_related('product')
        total_price = sum(item.total_price for item in cart_items)

        try:
            data = json.loads(request.body)
            payment_method = data.get('payment_method')
            intent = stripe.PaymentIntent.create(
                amount=int(total_price * 100),
                currency='usd',
                payment_method=payment_method,
                confirm=True,
                off_session=True,
                metadata={'user_id': request.user.id},
            )
            order = Order.objects.create(
                user=request.user,
                address=request.user.address or "Default Address",
                total_price=total_price,
                status='completed'
            )
            for item in cart_items:
                order.items.create(
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.final_price
                )
            cart_items.delete()
            send_order_confirmation_email.delay(request.user.email)
            return JsonResponse({'success': True})
        except stripe.error.StripeError as e:
            return JsonResponse({'error': str(e)}, status=400)


from django.contrib.auth.mixins import UserPassesTestMixin

from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView
from shop.models import Product, Category, Group, Comment


class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


class ProductManageView(AdminRequiredMixin, TemplateView):
    template_name = 'product_manage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.all()
        context['categories'] = Category.objects.all()
        context['groups'] = Group.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        if 'delete' in request.POST:
            product_id = request.POST.get('product_id')
            product = get_object_or_404(Product, id=product_id)
            product.delete()
            messages.success(request, 'Product deleted successfully!')
        else:
            name = request.POST.get('name')
            description = request.POST.get('description')
            price = request.POST.get('price')
            discount = request.POST.get('discount', '0')
            group_id = request.POST.get('group')
            try:
                price = float(price) if price else 0.0
                discount = float(discount) if discount else 0.0
            except ValueError:
                messages.error(request, 'Price and discount must be valid numbers.')
                return redirect('product_manage')

            if not group_id:
                messages.error(request, 'Please select a group.')
                return redirect('product_manage')

            group = get_object_or_404(Group, id=group_id)

            try:
                Product.objects.create(
                    name=name,
                    description=description,
                    price=price,
                    discount=discount,
                    group=group
                )
                messages.success(request, 'Product added successfully!')
            except Exception as e:
                messages.error(request, f'Error adding product: {str(e)}')
                return redirect('product_manage')

        return redirect('product_manage')


class ProductEditView(LoginRequiredMixin, TemplateView):
    template_name = 'product_edit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = get_object_or_404(Product, pk=self.kwargs['pk'])
        context['product'] = product
        context['categories'] = Category.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('product_manage')

        product = get_object_or_404(Product, pk=self.kwargs['pk'])
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        discount = request.POST.get('discount', 0)
        description = request.POST.get('description')

        group = Group.objects.filter(category_id=category_id).first()
        if not group:
            messages.error(request, 'Please select a valid category with a group.')
            return redirect('product_manage')

        product.name = name
        product.group = group
        product.price = price
        product.discount = discount
        product.description = description
        product.save()
        messages.success(request, 'Product updated successfully!')
        return redirect('product_manage')


class ProductDeleteView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('product_manage')

        product = get_object_or_404(Product, pk=self.kwargs['pk'])
        product.delete()
        messages.success(request, 'Product deleted successfully!')
        return redirect('product_manage')


class CategoryManageView(LoginRequiredMixin, TemplateView):
    template_name = 'category_manage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('category_manage')

        name = request.POST.get('name')
        Category.objects.create(name=name)
        messages.success(request, 'Category added successfully!')
        return redirect('category_manage')


class CategoryEditView(LoginRequiredMixin, TemplateView):
    template_name = 'category_edit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category = get_object_or_404(Category, pk=self.kwargs['pk'])
        context['category'] = category
        context['categories'] = Category.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('category_manage')

        category = get_object_or_404(Category, pk=self.kwargs['pk'])
        name = request.POST.get('name')
        category.name = name
        category.save()
        messages.success(request, 'Category updated successfully!')
        return redirect('category_manage')


class CategoryDeleteView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('category_manage')

        category = get_object_or_404(Category, pk=self.kwargs['pk'])
        category.delete()
        messages.success(request, 'Category deleted successfully!')
        return redirect('category_manage')


class GroupManageView(LoginRequiredMixin, TemplateView):
    template_name = 'group_manage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['groups'] = Group.objects.all().select_related('category')
        context['categories'] = Category.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('group_manage')

        name = request.POST.get('name')
        category_id = request.POST.get('category')
        category = get_object_or_404(Category, id=category_id)
        Group.objects.create(name=name, category=category)
        messages.success(request, 'Group added successfully!')
        return redirect('group_manage')


class GroupEditView(LoginRequiredMixin, TemplateView):
    template_name = 'group_edit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = get_object_or_404(Group, pk=self.kwargs['pk'])
        context['group'] = group
        context['categories'] = Category.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('group_manage')

        group = get_object_or_404(Group, pk=self.kwargs['pk'])
        name = request.POST.get('name')
        category_id = request.POST.get('category')
        category = get_object_or_404(Category, id=category_id)
        group.name = name
        group.category = category
        group.save()
        messages.success(request, 'Group updated successfully!')
        return redirect('group_manage')


class GroupDeleteView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('group_manage')

        group = get_object_or_404(Group, pk=self.kwargs['pk'])
        group.delete()
        messages.success(request, 'Group deleted successfully!')
        return redirect('group_manage')


class CommentManageView(LoginRequiredMixin, TemplateView):
    template_name = 'comment_manage.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = Comment.objects.all().select_related('user', 'product')
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('comment_manage')

        product_id = request.POST.get('product')
        content = request.POST.get('content')
        product = get_object_or_404(Product, id=product_id)
        Comment.objects.create(user=request.user, product=product, content=content)
        messages.success(request, 'Comment added successfully!')
        return redirect('comment_manage')


class CommentEditView(LoginRequiredMixin, TemplateView):
    template_name = 'comment_edit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        comment = get_object_or_404(Comment, pk=self.kwargs['pk'])
        context['comment'] = comment
        context['products'] = Product.objects.all()
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('comment_manage')

        comment = get_object_or_404(Comment, pk=self.kwargs['pk'])
        product_id = request.POST.get('product')
        content = request.POST.get('content')
        product = get_object_or_404(Product, id=product_id)
        comment.product = product
        comment.content = content
        comment.save()
        messages.success(request, 'Comment updated successfully!')
        return redirect('comment_manage')


class CommentDeleteView(LoginRequiredMixin, TemplateView):
    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('comment_manage')

        comment = get_object_or_404(Comment, pk=self.kwargs['pk'])
        comment.delete()
        messages.success(request, 'Comment deleted successfully!')
        return redirect('comment_manage')


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.filter(is_available=True).select_related('group__category').prefetch_related('images',
                                                                                                            'attributes',
                                                                                                            'comments')
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['group__category', 'group', 'price', 'discount']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at']

    @method_decorator(cache_page(60 * 15))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def add_to_favorites(self, request, pk=None):
        product = self.get_object()
        if request.user in product.favorites.all():
            product.favorites.remove(request.user)
            return Response({'status': 'removed from favorites'})
        product.favorites.add(request.user)
        return Response({'status': 'added to favorites'})


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().prefetch_related('groups')
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all().select_related('category')
    serializer_class = GroupSerializer
    permission_classes = [IsAdminOrReadOnly]


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user).select_related('product')


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all().select_related('user', 'product')
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


from django.http import JsonResponse


@login_required
def add_to_favorites(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.user in product.favorites.all():
        product.favorites.remove(request.user)
        messages.success(request, 'Removed from favorites!')
        action = 'removed'
    else:
        product.favorites.add(request.user)
        messages.success(request, 'Added to favorites!')
        action = 'added'

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'action': action})
    return redirect('home')
