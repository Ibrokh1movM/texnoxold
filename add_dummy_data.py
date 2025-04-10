import random
from django.utils.text import slugify
from faker import Faker
from shop.models import (
    Category, Group, Product, ProductImage,
    Attribute, AttributeValue, ProductAttribute,
    Comment, Cart, Order, OrderItem, User
)

fake = Faker()


def create_test_data():
    # 1. Foydalanuvchilar yaratish
    users = []
    for _ in range(50):
        user = User.objects.create_user(
            username=fake.user_name(),
            email=fake.email(),
            password='testpass123'
        )
        users.append(user)

    # 2. Kategoriyalar yaratish
    categories = []
    for name in ['Elektronika', 'Kiyim-kechak', 'Uy jihozlari', 'Kitoblar', 'Go\'zallik']:
        category = Category.objects.create(name=name)
        categories.append(category)

    # 3. Gruppalar yaratish
    groups = []
    group_names = {
        'Elektronika': ['Smartfonlar', 'Noutbuklar', 'Televizorlar', 'Aqlli soatlar'],
        'Kiyim-kechak': ['Erkaklar', 'Ayollar', 'Bolalar', 'Oyoq kiyim'],
        'Uy jihozlari': ['Mebellar', 'Idishlar', 'Matolar', 'Dekor'],
        'Kitoblar': ['Badiiy', 'Ilmiy', 'Darsliklar', 'Detektiv'],
        'Go\'zallik': ['Parfyumeriya', 'Kosmetika', 'Soch mahsulotlari']
    }

    for category in categories:
        for group_name in group_names[category.name]:
            group = Group.objects.create(
                name=group_name,
                category=category
            )
            groups.append(group)

    # 4. Atributlar va qiymatlar yaratish
    attributes = []
    attribute_values = {}

    color_attr = Attribute.objects.create(name='Rang')
    size_attr = Attribute.objects.create(name='Hajm')
    material_attr = Attribute.objects.create(name='Material')

    attributes.extend([color_attr, size_attr, material_attr])

    # Rang qiymatlari
    colors = ['Qora', 'Oq', 'Qizil', 'Ko\'k', 'Yashil', 'Sariq']
    for color in colors:
        AttributeValue.objects.create(attribute=color_attr, value=color)

    # Hajm qiymatlari
    sizes = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
    for size in sizes:
        AttributeValue.objects.create(attribute=size_attr, value=size)

    # Material qiymatlari
    materials = ['Charm', 'Mato', 'Plastik', 'Metall', 'Shisha']
    for material in materials:
        AttributeValue.objects.create(attribute=material_attr, value=material)

    # 5. Mahsulotlar yaratish (2000 ta)
    products = []
    for i in range(2000):
        group = random.choice(groups)
        price = random.randint(10000, 5000000)
        discount = random.choice([0, 5, 10, 15, 20, 25, 30])

        product = Product.objects.create(
            name=f"{fake.word().capitalize()} {fake.word().capitalize()} {i}",
            group=group,
            price=price,
            discount=discount,
            description=fake.text(),
            is_available=random.choice([True, False])
        )
        products.append(product)

        # Mahsulot rasmlari
        for img_num in range(random.randint(1, 5)):
            ProductImage.objects.create(
                product=product,
                image=f'product_images/test_{img_num}.jpg',
                is_primary=(img_num == 0)
            )

        # Mahsulot atributlari
        color_value = random.choice(AttributeValue.objects.filter(attribute=color_attr))
        ProductAttribute.objects.create(
            product=product,
            attribute=color_attr,
            value=color_value
        )

        if group.category.name in ['Kiyim-kechak', 'Uy jihozlari']:
            size_value = random.choice(AttributeValue.objects.filter(attribute=size_attr))
            ProductAttribute.objects.create(
                product=product,
                attribute=size_attr,
                value=size_value
            )

        if group.category.name in ['Kiyim-kechak', 'Uy jihozlari']:
            material_value = random.choice(AttributeValue.objects.filter(attribute=material_attr))
            ProductAttribute.objects.create(
                product=product,
                attribute=material_attr,
                value=material_value
            )

    # 6. Kommentariyalar yaratish
    for product in random.sample(products, 500):
        for _ in range(random.randint(1, 10)):
            comment = Comment.objects.create(
                product=product,
                user=random.choice(users),
                content=fake.text()
            )
            # Like'lar qo'shish
            for user in random.sample(users, random.randint(0, 15)):
                comment.likes.add(user)

    # 7. Savatlar yaratish
    for user in random.sample(users, 30):
        for _ in range(random.randint(1, 10)):
            product = random.choice(products)
            Cart.objects.create(
                user=user,
                product=product,
                quantity=random.randint(1, 5)
            )

    # 8. Buyurtmalar yaratish
    for user in random.sample(users, 20):
        order = Order.objects.create(
            user=user,
            address=fake.address(),
            total_price=0,
            status=random.choice(['pending', 'completed'])
        )

        total = 0
        for _ in range(random.randint(1, 7)):
            product = random.choice(products)
            quantity = random.randint(1, 3)
            price = product.final_price * quantity
            total += price

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.final_price
            )

        order.total_price = total
        order.save()

    print("Test ma'lumotlari muvaffaqiyatli yaratildi!")


if __name__ == '__main__':
    create_test_data()
