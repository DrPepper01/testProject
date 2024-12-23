from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVector

User = get_user_model()

class City(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

class Store(models.Model):
    name = models.CharField(max_length=255)
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='stores')

    def __str__(self):
        return f"{self.name} ({self.city.name})"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    store = models.ForeignKey(Store, on_delete=models.SET_NULL, null=True, blank=True)
    # По желанию можно добавить поля для адреса (улица, дом и т.д.)
    # address_line = models.CharField(max_length=255, null=True, blank=True)
    # postcode = models.CharField(max_length=20, null=True, blank=True)
    # и т.д.

    def __str__(self):
        return f"Profile of {self.user.username} - Store: {self.store if self.store else 'None'}"

class Product(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    view_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.search_vector = SearchVector('name', 'description')
        super().save(*args, **kwargs)

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_images')
    # Храним изображение в base64 формате для экономии места:
    image_data = models.TextField()

    def __str__(self):
        city_str = f"city: {self.city.name}" if self.city else "generic"
        return f"Image of {self.product.name}, {city_str}"

class Price(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='prices')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='prices')
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('product', 'store')

    def __str__(self):
        return f"Price of {self.product.name} in {self.store.name}: {self.amount}"

class Stock(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stocks')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='stocks')
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('product', 'store')

    def __str__(self):
        return f"Stock of {self.product.name} in {self.store.name}: {self.quantity}"
