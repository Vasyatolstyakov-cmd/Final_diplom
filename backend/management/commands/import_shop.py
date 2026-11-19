from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from rest_framework.exceptions import ValidationError as ImportValidationError

from backend.importers import import_price_list, load_price_list
from backend.models import User


class Command(BaseCommand):
    help = "Загружает YAML-прайс поставщика"

    def add_arguments(self, parser):
        parser.add_argument("price_file", type=Path)
        parser.add_argument("--email", required=True, help="Email поставщика")

    def handle(self, *args, **options):
        path = options["price_file"]
        email = options["email"].strip().lower()
        try:
            validate_email(email)
            content = path.read_bytes()
        except ValidationError as error:
            raise CommandError("Укажите корректный email поставщика") from error
        except OSError as error:
            raise CommandError(f"Не удалось открыть прайс: {error}") from error
        try:
            document = load_price_list(content)
            with transaction.atomic():
                supplier = User.objects.filter(email__iexact=email).first()
                if supplier is None:
                    supplier = User.objects.create_user(email, type=User.Type.SHOP)
                result = import_price_list(supplier, document, filename=path.name)
        except ImportValidationError as error:
            raise CommandError(str(error.detail)) from error
        self.stdout.write(
            self.style.SUCCESS(
                f"Прайс загружен: категорий - {result['categories']}, "
                f"новых предложений - {result['created']}, "
                f"обновлено - {result['updated']}, "
                f"снято с продажи - {result['deactivated']}"
            )
        )
