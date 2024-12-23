from rest_framework import serializers
from .models import Product, ProductImage, Price, Stock
from django.db.models import Q

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image_data']

class ProductSerializer(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    stock = serializers.SerializerMethodField()
    # Дополнительно можно выводить view_count, если это требуется в детальном представлении
    view_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'images', 'price', 'stock', 'view_count']

    def get_images(self, obj):
        request = self.context.get('request')
        user = request.user
        store = getattr(getattr(user, 'profile', None), 'store', None)
        city = store.city if store else None

        # Если есть city-specific изображения, берем их:
        if city:
            city_images = obj.images.filter(city=city)
            if city_images.exists():
                return ProductImageSerializer(city_images, many=True).data

        # Иначе берем все изображения без указания города
        generic_images = obj.images.filter(city__isnull=True)
        return ProductImageSerializer(generic_images, many=True).data

    def get_price(self, obj):
        request = self.context.get('request')
        user = request.user
        store = getattr(getattr(user, 'profile', None), 'store', None)
        if store:
            price = obj.prices.filter(store=store).first()
            if price:
                return str(price.amount)
        return None

    def get_stock(self, obj):
        request = self.context.get('request')
        user = request.user
        store = getattr(getattr(user, 'profile', None), 'store', None)
        if store:
            stock = obj.stocks.filter(store=store).first()
            if stock:
                return stock.quantity
        return 0

class StockUpdateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    store_id = serializers.IntegerField()
    quantity = serializers.IntegerField()
