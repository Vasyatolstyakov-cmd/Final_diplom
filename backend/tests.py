from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.core.exceptions import ValidationError
from django.db import IntegrityError, connections, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase

from backend.models import (
    Category,
    ConfirmEmailToken,
    Contact,
    Order,
    OrderItem,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)


class UserTests(TestCase):
    def test_email_login_and_hashed_password(self):
        user = User.objects.create_user("Buyer@EXAMPLE.COM", "Password-742!")
        self.assertEqual(user.email, "buyer@example.com")
        self.assertEqual(user.USERNAME_FIELD, "email")
        self.assertTrue(user.check_password("Password-742!"))
        self.assertFalse(user.is_active)

    def test_email_is_required_and_case_insensitively_unique(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("")
        User.objects.create_user("buyer@example.com")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email="BUYER@example.com")

    def test_superuser_is_active_and_has_both_permissions(self):
        user = User.objects.create_superuser("admin@example.com", "Password-742!")
        self.assertTrue(user.is_active and user.is_staff and user.is_superuser)
        for flag in ("is_active", "is_staff", "is_superuser"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                User.objects.create_superuser("other@example.com", **{flag: False})

    def test_phone_is_one_user_field_and_can_be_changed(self):
        user = User.objects.create_user("buyer@example.com", phone="+7 999 123-45-67")
        user.full_clean()
        user.phone = "+7 999 765-43-21"
        user.save(update_fields=("phone",))
        user.refresh_from_db()
        self.assertEqual(user.phone, "+7 999 765-43-21")
        user.phone = "не телефон"
        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_confirmation_tokens_are_generated_per_record(self):
        user = User.objects.create_user("buyer@example.com")
        first = ConfirmEmailToken.objects.create(user=user)
        second = ConfirmEmailToken.objects.create(user=user)
        self.assertNotEqual(first.key, second.key)
        self.assertGreaterEqual(len(first.key), 32)
        first.refresh_from_db()
        first.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ConfirmEmailToken.objects.create(user=user, key=first.key)


class ContactTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("buyer@example.com")

    def address(self, user=None, **fields):
        data = {"city": "Москва", "street": "Лесная", "house": "1"}
        data.update(fields)
        return Contact.objects.create(user=user or self.user, **data)

    def test_sixth_address_is_rejected_but_existing_address_can_be_edited(self):
        addresses = [self.address(house=str(number)) for number in range(1, 6)]
        with self.assertRaises(ValidationError):
            self.address(house="6")
        addresses[0].house = "10"
        addresses[0].save()
        addresses[0].refresh_from_db()
        self.assertEqual(addresses[0].house, "10")
        self.assertEqual(self.user.contacts.count(), 5)

    def test_changing_owner_cannot_add_a_sixth_address(self):
        for number in range(5):
            self.address(house=str(number + 1))
        other = User.objects.create_user("other@example.com")
        address = self.address(user=other)
        address.user = self.user
        with self.assertRaises(ValidationError):
            address.save()
        address.refresh_from_db()
        self.assertEqual(address.user, other)
        self.assertEqual(self.user.contacts.count(), 5)

    def test_changing_owner_with_free_slot_and_reusing_deleted_slot(self):
        address = self.address()
        other = User.objects.create_user("other@example.com")
        address.user = other
        address.save()
        self.assertEqual(self.user.contacts.count(), 0)
        self.assertEqual(other.contacts.count(), 1)
        for _ in range(5):
            self.address()
        self.user.contacts.first().delete()
        self.address()
        self.assertEqual(self.user.contacts.count(), 5)

    def test_address_fields_and_display(self):
        address = self.address(building="2", structure="3", apartment="4")
        self.assertEqual(str(address), "Москва, Лесная, д. 1, корп. 2, стр. 3, кв. 4")
        address.city = ""
        with self.assertRaises(ValidationError):
            address.save()


class CatalogAndOrderTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user("buyer@example.com")
        self.shops = [
            Shop.objects.create(
                user=User.objects.create_user(
                    f"supplier{number}@example.com", type=User.Type.SHOP
                ),
                name=f"Магазин {number}",
            )
            for number in (1, 2)
        ]
        self.category = Category.objects.create(name="Смартфоны")
        self.category.shops.add(*self.shops)
        self.product = Product.objects.create(
            category=self.category, name="Телефон", description="Описание"
        )
        self.offers = [
            ProductInfo.objects.create(
                product=self.product,
                shop=shop,
                external_id=101,
                name="Телефон",
                model="phone/one",
                quantity=10,
                price=price,
                price_rrc=Decimal("200.00"),
            )
            for shop, price in zip(self.shops, [Decimal("100.10"), Decimal("120.20")])
        ]

    def test_category_and_product_can_belong_to_multiple_shops(self):
        self.assertEqual(self.category.shops.count(), 2)
        self.assertEqual(self.product.product_infos.count(), 2)
        self.assertEqual(self.offers[0].external_id, self.offers[1].external_id)
        self.assertNotEqual(self.offers[0].price, self.offers[1].price)

    def test_shop_source_and_acceptance_state_are_saved(self):
        shop = self.shops[0]
        shop.url = "https://example.com/price.yaml"
        shop.state = False
        shop.full_clean()
        shop.save()
        shop.refresh_from_db()
        self.assertFalse(shop.state)
        self.assertEqual(shop.url, "https://example.com/price.yaml")
        shop.url = ""
        shop.filename = "shop1.yaml"
        shop.full_clean()
        shop.save()
        shop.refresh_from_db()
        self.assertEqual(shop.filename, "shop1.yaml")
        shop.user = self.buyer
        with self.assertRaises(ValidationError):
            shop.full_clean()

    def test_supplier_cannot_have_two_shops(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Shop.objects.create(user=self.shops[0].user, name="Другой магазин")

    def test_offer_identity_prices_and_stock_constraints(self):
        offer = self.offers[0]
        for fields in ({"price": -1}, {"price_rrc": -1}, {"quantity": -1}):
            with (
                self.subTest(fields=fields),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                ProductInfo.objects.filter(pk=offer.pk).update(**fields)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductInfo.objects.create(
                product=self.product,
                shop=offer.shop,
                external_id=101,
                name="Дубликат",
                quantity=1,
                price=1,
                price_rrc=1,
            )

    def test_arbitrary_parameters_are_unique_within_offer(self):
        color = Parameter.objects.create(name="Цвет")
        size = Parameter.objects.create(name="Диагональ")
        ProductParameter.objects.create(
            product_info=self.offers[0], parameter=color, value="чёрный"
        )
        ProductParameter.objects.create(
            product_info=self.offers[1], parameter=color, value="белый"
        )
        ProductParameter.objects.create(
            product_info=self.offers[0], parameter=size, value="6.5"
        )
        self.assertEqual(self.offers[0].product_parameters.count(), 2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductParameter.objects.create(
                product_info=self.offers[0], parameter=color, value="красный"
            )

    def test_one_order_contains_multiple_shops_and_keeps_its_prices(self):
        order = Order.objects.create(user=self.buyer)
        self.assertEqual(order.total, Decimal("0.00"))
        for offer in self.offers:
            OrderItem.objects.create(
                order=order, product_info=offer, quantity=2, price=offer.price
            )
        self.assertEqual(order.total, Decimal("440.60"))
        ProductInfo.objects.filter(pk=self.offers[0].pk).update(price=500)
        self.assertEqual(order.total, Decimal("440.60"))
        self.assertEqual(
            set(order.items.values_list("product_info__shop_id", flat=True)),
            {s.pk for s in self.shops},
        )

    def test_one_basket_and_all_order_statuses(self):
        order = Order.objects.create(user=self.buyer)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.create(user=self.buyer)
        for status in Order.Status.values:
            order.status = status
            order.full_clean()
            order.save()
            order.refresh_from_db()
            self.assertEqual(order.status, status)
        Order.objects.create(user=self.buyer)
        self.assertEqual(self.buyer.orders.count(), 2)

    def test_order_item_quantity_price_and_uniqueness(self):
        order = Order.objects.create(user=self.buyer)
        item = OrderItem.objects.create(
            order=order, product_info=self.offers[0], quantity=1, price=100
        )
        for fields in ({"quantity": 0}, {"quantity": -1}, {"price": -1}):
            with (
                self.subTest(fields=fields),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                OrderItem.objects.filter(pk=item.pk).update(**fields)
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=order, product_info=self.offers[0], quantity=1, price=100
            )

    def test_order_contact_must_belong_to_buyer(self):
        own = Contact.objects.create(
            user=self.buyer, city="Москва", street="Лесная", house="1"
        )
        other = Contact.objects.create(
            user=self.shops[0].user, city="Тула", street="Мира", house="2"
        )
        order = Order(user=self.buyer, contact=own)
        order.full_clean()
        order.contact = other
        with self.assertRaises(ValidationError):
            order.full_clean()

    def test_offer_used_in_order_cannot_be_deleted(self):
        order = Order.objects.create(user=self.buyer)
        OrderItem.objects.create(
            order=order, product_info=self.offers[0], quantity=1, price=100
        )
        with self.assertRaises(ProtectedError):
            self.offers[0].delete()


class ConcurrentAddressTests(TransactionTestCase):
    def test_two_requests_cannot_both_take_the_last_slot(self):
        user = User.objects.create_user("buyer@example.com")
        for number in range(4):
            Contact.objects.create(
                user=user, city="Москва", street="Лесная", house=str(number + 1)
            )
        barrier = Barrier(2)

        def add_address():
            try:
                barrier.wait(timeout=10)
                Contact.objects.create(
                    user_id=user.pk, city="Москва", street="Лесная", house="5"
                )
                return True
            except ValidationError:
                return False
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: add_address(), range(2)))
        self.assertCountEqual(results, [True, False])
        self.assertEqual(user.contacts.count(), 5)
