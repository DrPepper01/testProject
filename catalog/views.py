from django.db import transaction
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, generics
from .models import Product, Stock
from .serializers import ProductSerializer, StockUpdateSerializer
from django.core.cache import cache
from django.db.models import Q, Case, When, IntegerField, ExpressionWrapper
from .tasks import bulk_update_stocks_task

class CatalogListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductSerializer

    def get_queryset(self):
        user = self.request.user
        store = user.profile.store if hasattr(user, 'profile') and user.profile.store else None

        # Фильтруем товары по наличию (Stock > 0)
        # Если store не назначен пользователю, возможно логика по умолчанию: пустой или все товары.
        # Допустим, если нет store - возвращаем пустой список.
        if not store:
            return Product.objects.none()

        # Получаем id товаров, которые есть в наличии в данном store
        product_ids_with_stock = Stock.objects.filter(store=store, quantity__gt=0).values_list('product_id', flat=True)
        return Product.objects.filter(id__in=product_ids_with_stock).select_related().prefetch_related('images', 'prices', 'stocks')


class ProductDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductSerializer
    queryset = Product.objects.all()

    def get_object(self):
        product = super().get_object()
        product.view_count += 1
        product.save()
        return product


class ProductSearchView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProductSerializer

    def get_queryset(self):
        query_str = self.request.GET.get('q', '').strip()
        user = self.request.user
        store = getattr(getattr(user, 'profile', None), 'store', None)

        if not query_str:
            # Нет поискового запроса - пустой результат
            return Product.objects.none()

        # Находим товары, в которых встречается подстрока query_str (нечувствительно к регистру)
        # Используем Q для поиска по name или description:
        qs = Product.objects.filter(
            Q(name__icontains=query_str) | Q(description__icontains=query_str)
        )

        # Фильтруем только товары, у которых есть остатки в каком-либо магазине
        qs = qs.filter(stocks__quantity__gt=0).distinct()

        if store:
            # Аннотируем товары полем, показывающим есть ли товар в user's store
            qs = qs.annotate(
                in_user_store=ExpressionWrapper(
                    Case(
                        When(stocks__store=store, stocks__quantity__gt=0, then=1),
                        default=0,
                        output_field=IntegerField()
                    ),
                    output_field=IntegerField()
                )
            ).order_by('-in_user_store')
            # Товары у которых in_user_store=1 будут выше в списке.
        else:
            # Если у пользователя нет store, просто возвращаем товары, найденные по поиску и имеющие остаток.
            # Можно добавить сортировку по имени или как удобно, но приоритет уже не требуется.
            # qs = qs.order_by('name')  # например, по алфавиту, если нужно
            pass

        return qs


class StockUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response({"detail": "Invalid data format"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = StockUpdateSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        # Отправляем задачу в очередь RabbitMQ
        task = bulk_update_stocks_task.delay(validated_data)

        # Возвращаем быстрый ответ (202 Accepted)
        return Response(
            {"detail": "Stocks update task queued", "task_id": task.id},
            status=status.HTTP_202_ACCEPTED
        )
