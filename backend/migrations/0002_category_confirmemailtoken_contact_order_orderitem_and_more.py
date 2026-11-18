import django.core.validators
import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models

import backend.models


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("backend", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=120, verbose_name="Название")),
            ],
            options={
                "verbose_name": "Категория",
                "verbose_name_plural": "Категории",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="ConfirmEmailToken",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Создан"),
                ),
                (
                    "key",
                    models.CharField(
                        default=backend.models.generate_confirmation_key,
                        editable=False,
                        max_length=64,
                        unique=True,
                        verbose_name="Токен",
                    ),
                ),
            ],
            options={
                "verbose_name": "Токен подтверждения email",
                "verbose_name_plural": "Токены подтверждения email",
            },
        ),
        migrations.CreateModel(
            name="Contact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("city", models.CharField(max_length=100, verbose_name="Город")),
                ("street", models.CharField(max_length=150, verbose_name="Улица")),
                ("house", models.CharField(max_length=20, verbose_name="Дом")),
                (
                    "building",
                    models.CharField(blank=True, max_length=20, verbose_name="Корпус"),
                ),
                (
                    "structure",
                    models.CharField(
                        blank=True, max_length=20, verbose_name="Строение"
                    ),
                ),
                (
                    "apartment",
                    models.CharField(
                        blank=True, max_length=20, verbose_name="Квартира"
                    ),
                ),
            ],
            options={
                "verbose_name": "Адрес доставки",
                "verbose_name_plural": "Адреса доставки",
            },
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "dt",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Дата создания"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("basket", "Корзина"),
                            ("new", "Новый"),
                            ("confirmed", "Подтверждён"),
                            ("assembled", "Собран"),
                            ("sent", "Отправлен"),
                            ("delivered", "Доставлен"),
                            ("canceled", "Отменён"),
                        ],
                        default="basket",
                        max_length=12,
                        verbose_name="Статус",
                    ),
                ),
            ],
            options={
                "verbose_name": "Заказ",
                "verbose_name_plural": "Заказы",
                "ordering": ("-dt",),
            },
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("quantity", models.PositiveIntegerField(verbose_name="Количество")),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2, max_digits=12, verbose_name="Цена в заказе"
                    ),
                ),
            ],
            options={
                "verbose_name": "Позиция заказа",
                "verbose_name_plural": "Позиции заказа",
            },
        ),
        migrations.CreateModel(
            name="Parameter",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=120, unique=True, verbose_name="Название"
                    ),
                ),
            ],
            options={
                "verbose_name": "Характеристика",
                "verbose_name_plural": "Характеристики",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255, verbose_name="Название")),
                ("description", models.TextField(blank=True, verbose_name="Описание")),
            ],
            options={
                "verbose_name": "Товар",
                "verbose_name_plural": "Товары",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="ProductInfo",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "external_id",
                    models.PositiveBigIntegerField(verbose_name="ID в прайсе"),
                ),
                (
                    "name",
                    models.CharField(max_length=255, verbose_name="Название в прайсе"),
                ),
                (
                    "model",
                    models.CharField(blank=True, max_length=120, verbose_name="Модель"),
                ),
                ("quantity", models.PositiveIntegerField(verbose_name="Остаток")),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2, max_digits=12, verbose_name="Цена"
                    ),
                ),
                (
                    "price_rrc",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        verbose_name="Рекомендуемая розничная цена",
                    ),
                ),
            ],
            options={
                "verbose_name": "Предложение магазина",
                "verbose_name_plural": "Предложения магазинов",
            },
        ),
        migrations.CreateModel(
            name="ProductParameter",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("value", models.CharField(max_length=255, verbose_name="Значение")),
            ],
            options={
                "verbose_name": "Характеристика предложения",
                "verbose_name_plural": "Характеристики предложений",
            },
        ),
        migrations.CreateModel(
            name="Shop",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=120, unique=True, verbose_name="Название"
                    ),
                ),
                (
                    "url",
                    models.URLField(
                        blank=True, max_length=2048, verbose_name="URL прайса"
                    ),
                ),
                (
                    "filename",
                    models.CharField(
                        blank=True, max_length=255, verbose_name="Имя файла прайса"
                    ),
                ),
                (
                    "state",
                    models.BooleanField(default=True, verbose_name="Принимает заказы"),
                ),
            ],
            options={
                "verbose_name": "Магазин",
                "verbose_name_plural": "Магазины",
                "ordering": ("name",),
            },
        ),
        migrations.AlterModelOptions(
            name="user",
            options={
                "ordering": ("email",),
                "verbose_name": "Пользователь",
                "verbose_name_plural": "Пользователи",
            },
        ),
        migrations.AddField(
            model_name="user",
            name="company",
            field=models.CharField(blank=True, max_length=120, verbose_name="Компания"),
        ),
        migrations.AddField(
            model_name="user",
            name="middle_name",
            field=models.CharField(blank=True, max_length=150, verbose_name="Отчество"),
        ),
        migrations.AddField(
            model_name="user",
            name="phone",
            field=models.CharField(
                blank=True,
                max_length=20,
                validators=[
                    django.core.validators.RegexValidator(
                        "^\\+?[0-9][0-9 ()-]{6,19}$", "Укажите корректный телефон"
                    )
                ],
                verbose_name="Телефон",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="position",
            field=models.CharField(
                blank=True, max_length=120, verbose_name="Должность"
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="type",
            field=models.CharField(
                choices=[("buyer", "Покупатель"), ("shop", "Поставщик")],
                default="buyer",
                max_length=5,
                verbose_name="Тип пользователя",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="is_active",
            field=models.BooleanField(default=False, verbose_name="Активен"),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("email"),
                name="user_email_case_insensitive",
            ),
        ),
        migrations.AddField(
            model_name="confirmemailtoken",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="confirmation_tokens",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Пользователь",
            ),
        ),
        migrations.AddField(
            model_name="contact",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="contacts",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Пользователь",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="contact",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="backend.contact",
                verbose_name="Адрес",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="orders",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Покупатель",
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="order",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="backend.order",
                verbose_name="Заказ",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="products",
                to="backend.category",
                verbose_name="Категория",
            ),
        ),
        migrations.AddField(
            model_name="productinfo",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="product_infos",
                to="backend.product",
                verbose_name="Товар",
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="product_info",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="order_items",
                to="backend.productinfo",
                verbose_name="Предложение магазина",
            ),
        ),
        migrations.AddField(
            model_name="productparameter",
            name="parameter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="product_parameters",
                to="backend.parameter",
                verbose_name="Характеристика",
            ),
        ),
        migrations.AddField(
            model_name="productparameter",
            name="product_info",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="product_parameters",
                to="backend.productinfo",
                verbose_name="Предложение",
            ),
        ),
        migrations.AddField(
            model_name="shop",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="shop",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Поставщик",
            ),
        ),
        migrations.AddField(
            model_name="productinfo",
            name="shop",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="product_infos",
                to="backend.shop",
                verbose_name="Магазин",
            ),
        ),
        migrations.AddField(
            model_name="category",
            name="shops",
            field=models.ManyToManyField(
                blank=True,
                related_name="categories",
                to="backend.shop",
                verbose_name="Магазины",
            ),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "basket")),
                fields=("user",),
                name="one_basket_per_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.UniqueConstraint(
                fields=("order", "product_info"), name="unique_order_offer"
            ),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("quantity__gt", 0)), name="order_quantity_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("price__gte", 0)), name="order_price_nonnegative"
            ),
        ),
        migrations.AddConstraint(
            model_name="productparameter",
            constraint=models.UniqueConstraint(
                fields=("product_info", "parameter"), name="unique_offer_parameter"
            ),
        ),
        migrations.AddConstraint(
            model_name="productinfo",
            constraint=models.UniqueConstraint(
                fields=("shop", "external_id"), name="unique_shop_offer"
            ),
        ),
        migrations.AddConstraint(
            model_name="productinfo",
            constraint=models.CheckConstraint(
                condition=models.Q(("price__gte", 0)), name="offer_price_nonnegative"
            ),
        ),
        migrations.AddConstraint(
            model_name="productinfo",
            constraint=models.CheckConstraint(
                condition=models.Q(("price_rrc__gte", 0)), name="offer_rrc_nonnegative"
            ),
        ),
    ]
