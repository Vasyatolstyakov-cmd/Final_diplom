import math

import yaml
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import transaction
from rest_framework import serializers

from backend.models import (
    Category,
    Parameter,
    Product,
    ProductInfo,
    ProductParameter,
    Shop,
    User,
)


class CategoryData(serializers.Serializer):
    id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    name = serializers.CharField(max_length=120, trim_whitespace=False)


class ProductData(serializers.Serializer):
    id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    category = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    name = serializers.CharField(max_length=255, trim_whitespace=False)
    model = serializers.CharField(
        max_length=120, allow_blank=True, trim_whitespace=False
    )
    quantity = serializers.IntegerField(min_value=0, max_value=2**31 - 1)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    price_rrc = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    parameters = serializers.DictField()

    def validate_parameters(self, parameters):
        values = {}
        for name, value in parameters.items():
            if not isinstance(name, str) or not name.strip() or len(name) > 120:
                raise serializers.ValidationError(
                    "Название характеристики должно содержать от 1 до 120 символов"
                )
            if not isinstance(value, (str, int, float, bool)):
                raise serializers.ValidationError(
                    f"Недопустимое значение характеристики '{name}'"
                )
            if isinstance(value, float) and not math.isfinite(value):
                raise serializers.ValidationError(
                    f"Характеристика '{name}' должна содержать конечное число"
                )
            text = str(value)
            if not text or len(text) > 255:
                raise serializers.ValidationError(
                    f"Значение характеристики '{name}' должно содержать от 1 до 255 символов"
                )
            values[name] = text
        return values


class PriceData(serializers.Serializer):
    shop = serializers.CharField(max_length=120, trim_whitespace=False)
    categories = CategoryData(many=True)
    goods = ProductData(many=True)

    def validate(self, data):
        category_ids = [category["id"] for category in data["categories"]]
        product_ids = [item["id"] for item in data["goods"]]
        if len(category_ids) != len(set(category_ids)):
            raise serializers.ValidationError(
                "ID категорий в прайсе не должны повторяться"
            )
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "ID товаров в прайсе не должны повторяться"
            )
        unknown = {item["category"] for item in data["goods"]} - set(category_ids)
        if unknown:
            raise serializers.ValidationError(
                f"Не описаны категории: {sorted(unknown)}"
            )
        return data


def load_price_list(content):
    try:
        return yaml.safe_load(content)
    except (yaml.YAMLError, UnicodeError) as error:
        raise serializers.ValidationError("Не удалось прочитать YAML-прайс") from error


@transaction.atomic
def import_price_list(supplier, document, *, filename=""):
    serializer = PriceData(data=document)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    supplier = User.objects.select_for_update().get(pk=supplier.pk)
    if supplier.type != User.Type.SHOP:
        raise serializers.ValidationError("Импортировать прайс может только поставщик")
    if Shop.objects.filter(name=data["shop"]).exclude(user=supplier).exists():
        raise serializers.ValidationError(
            "Магазин с таким названием принадлежит другому поставщику"
        )
    shop, _ = Shop.objects.get_or_create(user=supplier, defaults={"name": data["shop"]})
    if shop.name != data["shop"]:
        raise serializers.ValidationError(
            "Название магазина в прайсе не совпадает с магазином поставщика"
        )
    shop = Shop.objects.select_for_update().get(pk=shop.pk)
    if filename:
        shop.filename = filename
        shop.url = ""
    try:
        shop.full_clean()
    except ModelValidationError as error:
        raise serializers.ValidationError(error.message_dict) from error
    shop.save(update_fields=("filename", "url"))

    categories = {}
    for row in data["categories"]:
        category, _ = Category.objects.get_or_create(
            external_id=row["id"],
            defaults={"name": row["name"]},
        )
        if category.name != row["name"]:
            raise serializers.ValidationError(
                f"Категория {row['id']} уже записана с другим названием"
            )
        categories[row["id"]] = category
    shop.categories.set(categories.values())

    created = 0
    for row in data["goods"]:
        product, _ = Product.objects.get_or_create(
            category=categories[row["category"]],
            name=row["name"],
        )
        offer, is_new = ProductInfo.objects.update_or_create(
            shop=shop,
            external_id=row["id"],
            defaults={
                "product": product,
                "name": row["name"],
                "model": row["model"],
                "quantity": row["quantity"],
                "price": row["price"],
                "price_rrc": row["price_rrc"],
            },
        )
        created += is_new
        parameters = []
        for name, value in row["parameters"].items():
            parameter, _ = Parameter.objects.get_or_create(name=name)
            ProductParameter.objects.update_or_create(
                product_info=offer,
                parameter=parameter,
                defaults={"value": value},
            )
            parameters.append(parameter.pk)
        offer.product_parameters.exclude(parameter_id__in=parameters).delete()

    # Исчезнувшие из прайса товары остаются в базе, на них могут ссылаться заказы.
    retired = shop.product_infos.exclude(
        external_id__in=[row["id"] for row in data["goods"]]
    )
    deactivated = retired.exclude(quantity=0).update(quantity=0)
    return {
        "categories": len(categories),
        "created": created,
        "updated": len(data["goods"]) - created,
        "deactivated": deactivated,
    }
