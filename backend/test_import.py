from copy import deepcopy
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from backend.importers import import_price_list, load_price_list
from backend.models import Category, Order, OrderItem, Product, ProductInfo, Shop, User


def price_list():
    return {
        "shop": "Магазин телефонов",
        "categories": [{"id": 224, "name": "Телефоны"}],
        "goods": [
            {
                "id": 101,
                "category": 224,
                "name": "Телефон",
                "model": "phone/one",
                "quantity": 5,
                "price": "100.10",
                "price_rrc": "120.20",
                "parameters": {
                    "Цвет": "чёрный",
                    "Память": 128,
                    "Диагональ": 6.5,
                    "NFC": True,
                },
            }
        ],
    }


class PriceImportTests(TestCase):
    def setUp(self):
        self.supplier = User.objects.create_user(
            "supplier@example.com", type=User.Type.SHOP
        )

    def test_imports_all_fields_and_records_filename(self):
        result = import_price_list(self.supplier, price_list(), filename="price.yaml")
        offer = ProductInfo.objects.get()
        self.assertEqual(
            result, {"categories": 1, "created": 1, "updated": 0, "deactivated": 0}
        )
        self.assertEqual(offer.external_id, 101)
        self.assertEqual(offer.product.category.external_id, 224)
        self.assertEqual(offer.product.category.name, "Телефоны")
        self.assertEqual(offer.product.name, "Телефон")
        self.assertEqual(offer.name, "Телефон")
        self.assertEqual(offer.model, "phone/one")
        self.assertEqual(offer.quantity, 5)
        self.assertEqual(offer.price, Decimal("100.10"))
        self.assertEqual(offer.price_rrc, Decimal("120.20"))
        self.assertEqual(offer.shop.filename, "price.yaml")
        self.assertEqual(offer.shop.categories.get(), offer.product.category)
        self.assertEqual(
            dict(offer.product_parameters.values_list("parameter__name", "value")),
            {
                "Цвет": "чёрный",
                "Память": "128",
                "Диагональ": "6.5",
                "NFC": "True",
            },
        )

    def test_repeated_import_preserves_ids_without_duplicates(self):
        import_price_list(self.supplier, price_list())
        original = ProductInfo.objects.get()
        parameter_ids = list(
            original.product_parameters.order_by("id").values_list("id", flat=True)
        )
        result = import_price_list(self.supplier, price_list())
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(ProductInfo.objects.get().pk, original.pk)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(
            list(
                original.product_parameters.order_by("id").values_list("id", flat=True)
            ),
            parameter_ids,
        )

    def test_update_preserves_order_price_and_replaces_parameters(self):
        import_price_list(self.supplier, price_list())
        offer = ProductInfo.objects.get()
        buyer = User.objects.create_user("buyer@example.com")
        order = Order.objects.create(user=buyer, status=Order.Status.NEW)
        item = OrderItem.objects.create(
            order=order, product_info=offer, quantity=2, price=offer.price
        )
        document = price_list()
        document["goods"][0].update(
            price="150.50", quantity=3, parameters={"Цвет": "белый"}
        )
        import_price_list(self.supplier, document, filename="new.yaml")
        offer.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(offer.price, Decimal("150.50"))
        self.assertEqual(offer.quantity, 3)
        self.assertEqual(item.product_info_id, offer.pk)
        self.assertEqual(order.total, Decimal("200.20"))
        self.assertEqual(
            dict(offer.product_parameters.values_list("parameter__name", "value")),
            {"Цвет": "белый"},
        )

    def test_removed_offer_stays_in_order_with_zero_stock(self):
        document = price_list()
        import_price_list(self.supplier, document)
        offer = ProductInfo.objects.get()
        order = Order.objects.create(
            user=User.objects.create_user("buyer@example.com"), status=Order.Status.NEW
        )
        item = OrderItem.objects.create(
            order=order, product_info=offer, quantity=1, price=offer.price
        )
        document["goods"] = []
        result = import_price_list(self.supplier, document)
        offer.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(result["deactivated"], 1)
        self.assertEqual(offer.quantity, 0)
        self.assertEqual(item.product_info_id, offer.pk)
        self.assertEqual(order.total, Decimal("100.10"))

    def test_second_shop_has_separate_price_for_same_product(self):
        import_price_list(self.supplier, price_list())
        other = User.objects.create_user("other@example.com", type=User.Type.SHOP)
        document = price_list()
        document["shop"] = "Другой магазин"
        document["goods"][0]["price"] = "200.00"
        import_price_list(other, document)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductInfo.objects.count(), 2)
        category = Category.objects.get()
        self.assertEqual(category.shops.count(), 2)
        self.assertEqual(
            self.supplier.shop.product_infos.get().price, Decimal("100.10")
        )
        self.assertEqual(other.shop.product_infos.get().price, Decimal("200.00"))

    def test_cannot_import_as_buyer_or_take_another_shop(self):
        buyer = User.objects.create_user("buyer@example.com")
        with self.assertRaises(ValidationError):
            import_price_list(buyer, price_list())
        import_price_list(self.supplier, price_list())
        other = User.objects.create_user("other@example.com", type=User.Type.SHOP)
        with self.assertRaises(ValidationError):
            import_price_list(other, price_list())
        self.assertEqual(Shop.objects.get().user_id, self.supplier.pk)
        self.assertEqual(ProductInfo.objects.count(), 1)

    def test_cannot_rename_supplier_shop_through_price_list(self):
        import_price_list(self.supplier, price_list())
        document = price_list()
        document["shop"] = "Другое название"
        with self.assertRaises(ValidationError):
            import_price_list(self.supplier, document)
        self.assertEqual(Shop.objects.get().name, "Магазин телефонов")

    def test_invalid_values_do_not_change_existing_catalog(self):
        import_price_list(self.supplier, price_list(), filename="old.yaml")
        cases = [
            ("quantity", -1),
            ("quantity", 1.5),
            ("quantity", True),
            ("price", -1),
            ("price", "1.234"),
            ("price", "NaN"),
            ("price_rrc", -1),
            ("category", 999),
            ("id", 0),
            ("name", "x" * 256),
            ("parameters", {"Цвет": ["чёрный"]}),
            ("parameters", {"NFC": None}),
            ("parameters", {"Вес": float("inf")}),
        ]
        for field, value in cases:
            document = price_list()
            document["goods"][0][field] = value
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(ValidationError),
            ):
                import_price_list(self.supplier, document, filename="bad.yaml")
            self.assertEqual(ProductInfo.objects.get().price, Decimal("100.10"))
            self.assertEqual(Shop.objects.get().filename, "old.yaml")

    def test_duplicate_ids_are_rejected(self):
        for section in ("categories", "goods"):
            document = price_list()
            document[section].append(deepcopy(document[section][0]))
            with self.subTest(section=section), self.assertRaises(ValidationError):
                import_price_list(self.supplier, document)
            self.assertFalse(Shop.objects.exists())

    def test_failure_rolls_back_shop_and_categories(self):
        Category.objects.create(external_id=224, name="Существующая категория")
        document = price_list()
        document["categories"].insert(0, {"id": 15, "name": "Новая категория"})
        with self.assertRaises(ValidationError):
            import_price_list(self.supplier, document, filename="bad.yaml")
        self.assertFalse(Shop.objects.exists())
        self.assertEqual(
            list(Category.objects.values_list("external_id", flat=True)), [224]
        )
        self.assertFalse(Product.objects.exists())

    def test_omitted_category_link_does_not_affect_other_shops(self):
        import_price_list(self.supplier, price_list())
        other = User.objects.create_user("other@example.com", type=User.Type.SHOP)
        document = price_list()
        document["shop"] = "Другой магазин"
        import_price_list(other, document)
        empty = {"shop": price_list()["shop"], "categories": [], "goods": []}
        import_price_list(self.supplier, empty)
        self.assertEqual(self.supplier.shop.categories.count(), 0)
        self.assertEqual(other.shop.categories.count(), 1)
        self.assertEqual(other.shop.product_infos.get().quantity, 5)

    def test_file_import_replaces_previous_url(self):
        shop = Shop.objects.create(
            user=self.supplier,
            name=price_list()["shop"],
            url="https://example.com/price.yaml",
        )
        import_price_list(self.supplier, price_list(), filename="price.yaml")
        shop.refresh_from_db()
        self.assertEqual(shop.url, "")
        self.assertEqual(shop.filename, "price.yaml")


class ImportCommandTests(TestCase):
    def run_import(self, document, email="supplier@example.com"):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "price.yaml"
            path.write_text(yaml.safe_dump(document, allow_unicode=True))
            output = StringIO()
            call_command("import_shop", str(path), email=email, stdout=output)
            return output.getvalue()

    def test_command_loads_file_and_reuses_supplier(self):
        output = self.run_import(price_list())
        supplier = User.objects.get()
        self.assertFalse(supplier.has_usable_password())
        self.assertEqual(supplier.type, User.Type.SHOP)
        self.assertEqual(supplier.shop.filename, "price.yaml")
        self.assertIn("новых предложений - 1", output)
        self.run_import(price_list(), email="SUPPLIER@EXAMPLE.COM")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(ProductInfo.objects.count(), 1)

    def test_invalid_import_does_not_leave_created_supplier(self):
        with self.assertRaises(CommandError):
            self.run_import({"shop": "Магазин"})
        self.assertFalse(User.objects.exists())

    def test_missing_file_and_invalid_email_have_readable_errors(self):
        with self.assertRaisesRegex(CommandError, "Не удалось открыть прайс"):
            call_command(
                "import_shop", "/missing/price.yaml", email="supplier@example.com"
            )
        with self.assertRaisesRegex(CommandError, "корректный email"):
            self.run_import(price_list(), email="wrong")

    def test_malformed_yaml_and_python_tags_are_rejected(self):
        for content in (b"shop: [", b"!!python/object:builtins.object {}", b"\xff"):
            with self.subTest(content=content), self.assertRaises(ValidationError):
                load_price_list(content)

    def test_empty_document_and_wrong_root_are_rejected(self):
        for document in (None, [], "text"):
            with self.subTest(document=document), self.assertRaises(CommandError):
                self.run_import(document)
        self.assertFalse(User.objects.exists())
