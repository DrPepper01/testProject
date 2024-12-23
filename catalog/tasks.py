# catalog/tasks.py
from celery import shared_task
from django.db import transaction
from django.db.models import Q
from catalog.models import Stock

@shared_task
def bulk_update_stocks_task(validated_data):
    """
    Асинхронная задача для обновления остатков.
    validated_data — список словарей вида [{product_id, store_id, quantity}, ...]
    """
    updates_map = {(item['product_id'], item['store_id']): item['quantity'] for item in validated_data}

    with transaction.atomic():
        stocks_to_update = Stock.objects.filter(
            Q(product_id__in=[i['product_id'] for i in validated_data]),
            Q(store_id__in=[i['store_id'] for i in validated_data])
        )
        for s in stocks_to_update:
            key = (s.product_id, s.store_id)
            s.quantity = updates_map[key]

        Stock.objects.bulk_update(stocks_to_update, ['quantity'])

    return len(stocks_to_update)  # Можно вернуть число обновлённых записей
