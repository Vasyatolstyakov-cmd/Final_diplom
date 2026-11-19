import secrets
from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models.functions import Lower

from backend.managers import UserManager


class User(AbstractUser):
    class Type(models.TextChoices):
        BUYER = "buyer", "Покупатель"
        SHOP = "shop", "Поставщик"

    username = None
    email = models.EmailField("Email", unique=True)
    middle_name = models.CharField("Отчество", max_length=150, blank=True)
    company = models.CharField("Компания", max_length=120, blank=True)
    position = models.CharField("Должность", max_length=120, blank=True)
    phone = models.CharField(
        "Телефон",
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(r"^\+?[0-9][0-9 ()-]{6,19}$", "Укажите корректный телефон")
        ],
    )
    type = models.CharField(
        "Тип пользователя", max_length=5, choices=Type.choices, default=Type.BUYER
    )
    is_active = models.BooleanField("Активен", default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ()
    objects = UserManager()

    class Meta:
        ordering = ("email",)
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        constraints = (
            models.UniqueConstraint(Lower("email"), name="user_email_case_insensitive"),
        )

    def __str__(self):
        return self.email


class Shop(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.PROTECT, related_name="shop", verbose_name="Поставщик"
    )
    name = models.CharField("Название", max_length=120, unique=True)
    url = models.URLField("URL прайса", max_length=2048, blank=True)
    filename = models.CharField("Имя файла прайса", max_length=255, blank=True)
    state = models.BooleanField("Принимает заказы", default=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"

    def clean(self):
        super().clean()
        if self.user_id and self.user.type != User.Type.SHOP:
            raise ValidationError({"user": "Владельцем магазина должен быть поставщик"})

    def __str__(self):
        return self.name


class Category(models.Model):
    external_id = models.PositiveBigIntegerField(
        "ID в прайсе", null=True, blank=True, unique=True
    )
    name = models.CharField("Название", max_length=120)
    shops = models.ManyToManyField(
        Shop, related_name="categories", blank=True, verbose_name="Магазины"
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Категория",
    )
    name = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        constraints = (
            models.UniqueConstraint(
                fields=("category", "name"), name="unique_category_product"
            ),
        )

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="product_infos",
        verbose_name="Товар",
    )
    shop = models.ForeignKey(
        Shop,
        on_delete=models.PROTECT,
        related_name="product_infos",
        verbose_name="Магазин",
    )
    external_id = models.PositiveBigIntegerField("ID в прайсе")
    name = models.CharField("Название в прайсе", max_length=255)
    model = models.CharField("Модель", max_length=120, blank=True)
    quantity = models.PositiveIntegerField("Остаток")
    price = models.DecimalField("Цена", max_digits=12, decimal_places=2)
    price_rrc = models.DecimalField(
        "Рекомендуемая розничная цена", max_digits=12, decimal_places=2
    )

    class Meta:
        verbose_name = "Предложение магазина"
        verbose_name_plural = "Предложения магазинов"
        constraints = (
            models.UniqueConstraint(
                fields=("shop", "external_id"), name="unique_shop_offer"
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="offer_price_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(price_rrc__gte=0), name="offer_rrc_nonnegative"
            ),
        )

    def __str__(self):
        return f"{self.name} - {self.shop}"


class Parameter(models.Model):
    name = models.CharField("Название", max_length=120, unique=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Характеристика"
        verbose_name_plural = "Характеристики"

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(
        ProductInfo,
        on_delete=models.CASCADE,
        related_name="product_parameters",
        verbose_name="Предложение",
    )
    parameter = models.ForeignKey(
        Parameter,
        on_delete=models.PROTECT,
        related_name="product_parameters",
        verbose_name="Характеристика",
    )
    value = models.CharField("Значение", max_length=255)

    class Meta:
        verbose_name = "Характеристика предложения"
        verbose_name_plural = "Характеристики предложений"
        constraints = (
            models.UniqueConstraint(
                fields=("product_info", "parameter"), name="unique_offer_parameter"
            ),
        )

    def __str__(self):
        return f"{self.parameter}: {self.value}"


class Contact(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="contacts",
        verbose_name="Пользователь",
    )
    city = models.CharField("Город", max_length=100)
    street = models.CharField("Улица", max_length=150)
    house = models.CharField("Дом", max_length=20)
    building = models.CharField("Корпус", max_length=20, blank=True)
    structure = models.CharField("Строение", max_length=20, blank=True)
    apartment = models.CharField("Квартира", max_length=20, blank=True)

    class Meta:
        verbose_name = "Адрес доставки"
        verbose_name_plural = "Адреса доставки"

    def clean(self):
        super().clean()
        if (
            self.user_id
            and Contact.objects.filter(user_id=self.user_id).exclude(pk=self.pk).count()
            >= 5
        ):
            raise ValidationError("Можно сохранить не больше пяти адресов")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            # Блокировка не даёт двум параллельным запросам добавить шестой адрес пользователю.
            User.objects.select_for_update().filter(pk=self.user_id).first()
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        parts = [self.city, self.street, f"д. {self.house}"]
        if self.building:
            parts.append(f"корп. {self.building}")
        if self.structure:
            parts.append(f"стр. {self.structure}")
        if self.apartment:
            parts.append(f"кв. {self.apartment}")
        return ", ".join(parts)


class Order(models.Model):
    class Status(models.TextChoices):
        BASKET = "basket", "Корзина"
        NEW = "new", "Новый"
        CONFIRMED = "confirmed", "Подтверждён"
        ASSEMBLED = "assembled", "Собран"
        SENT = "sent", "Отправлен"
        DELIVERED = "delivered", "Доставлен"
        CANCELED = "canceled", "Отменён"

    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="orders", verbose_name="Покупатель"
    )
    dt = models.DateTimeField("Дата создания", auto_now_add=True)
    status = models.CharField(
        "Статус", max_length=12, choices=Status.choices, default=Status.BASKET
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Адрес"
    )

    class Meta:
        ordering = ("-dt",)
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        constraints = (
            models.UniqueConstraint(
                fields=("user",),
                condition=models.Q(status="basket"),
                name="one_basket_per_user",
            ),
        )

    def clean(self):
        super().clean()
        if self.contact_id and self.contact.user_id != self.user_id:
            raise ValidationError({"contact": "Выберите адрес покупателя этого заказа"})

    @property
    def total(self):
        return sum((item.total for item in self.items.all()), Decimal("0.00"))

    def __str__(self):
        return f"Заказ {self.pk}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ"
    )
    product_info = models.ForeignKey(
        ProductInfo,
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name="Предложение магазина",
    )
    quantity = models.PositiveIntegerField("Количество")
    price = models.DecimalField("Цена в заказе", max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"
        constraints = (
            models.UniqueConstraint(
                fields=("order", "product_info"), name="unique_order_offer"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="order_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="order_price_nonnegative"
            ),
        )

    @property
    def total(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.product_info}, {self.quantity} шт."


def generate_confirmation_key():
    return secrets.token_urlsafe(32)


class ConfirmEmailToken(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="confirmation_tokens",
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    key = models.CharField(
        "Токен",
        max_length=64,
        unique=True,
        default=generate_confirmation_key,
        editable=False,
    )

    class Meta:
        verbose_name = "Токен подтверждения email"
        verbose_name_plural = "Токены подтверждения email"

    def __str__(self):
        return f"Подтверждение email для {self.user}"
