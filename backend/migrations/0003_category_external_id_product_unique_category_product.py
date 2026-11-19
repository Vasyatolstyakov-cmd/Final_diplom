from django.db import migrations, models
from django.db.models import Count


def merge_duplicate_products(apps, schema_editor):
    alias = schema_editor.connection.alias
    products = apps.get_model("backend", "Product").objects.using(alias)
    offers = apps.get_model("backend", "ProductInfo").objects.using(alias)
    duplicate_keys = list(
        products.order_by()
        .values("category_id", "name")
        .annotate(product_count=Count("pk"))
        .filter(product_count__gt=1)
    )
    for key in duplicate_keys:
        same_product = products.filter(category_id=key["category_id"], name=key["name"])
        first, *duplicates = same_product.order_by("pk")
        descriptions = dict.fromkeys(
            product.description
            for product in (first, *duplicates)
            if product.description
        )
        first.description = "\n\n".join(descriptions)
        first.save(using=alias, update_fields=("description",))

        # Заказы ссылаются на предложения, поэтому переносим их без смены ID.
        duplicate_ids = [product.pk for product in duplicates]
        offers.filter(product_id__in=duplicate_ids).update(product_id=first.pk)
        same_product.filter(pk__in=duplicate_ids).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("backend", "0002_category_confirmemailtoken_contact_order_orderitem_and_more"),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_products, migrations.RunPython.noop),
        # PostgreSQL должен проверить изменённые ссылки до добавления ограничения.
        migrations.RunSQL("SET CONSTRAINTS ALL IMMEDIATE", migrations.RunSQL.noop),
        migrations.AddField(
            model_name="category",
            name="external_id",
            field=models.PositiveBigIntegerField(
                blank=True, null=True, unique=True, verbose_name="ID в прайсе"
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                fields=("category", "name"), name="unique_category_product"
            ),
        ),
    ]
