import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from catalog.models import City, Store, Product, Stock, Price, UserProfile, ProductImage
from django.urls import reverse


@pytest.mark.django_db
def test_catalog_api():
    user = User.objects.create_user(username='testuser', password='testpass')
    city = City.objects.create(name="TestCity")
    store = Store.objects.create(name="TestStore", city=city)
    product = Product.objects.create(name="TestProduct", description="Desc")
    Price.objects.create(product=product, store=store, amount=10.0)
    Stock.objects.create(product=product, store=store, quantity=100)

    # Создаём профиль вручную
    UserProfile.objects.create(user=user, store=store)

    client = APIClient()
    # Получаем JWT токен
    token_resp = client.post('/api/v1/token/', {'username': 'testuser', 'password': 'testpass'}, format='json')
    access_token = token_resp.data['access']

    client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)
    resp = client.get('/api/v1/catalog/')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]['name'] == "TestProduct"
    assert data[0]['price'] == "10.00"
    assert data[0]['stock'] == 100

@pytest.mark.django_db
def test_product_detail_view_count():
    """
    Проверяем, что при обращении к детальному эндпоинту товара
    его счетчик просмотров (view_count) инкрементируется на 1.
    """
    user = User.objects.create_user(username='john', password='test123')
    city = City.objects.create(name="CityA")
    store = Store.objects.create(name="StoreA", city=city)

    # Привязываем профиль
    UserProfile.objects.create(user=user, store=store)

    product = Product.objects.create(name="Laptop Pro", description="Powerful laptop")
    price = Price.objects.create(product=product, store=store, amount=1000.0)
    stock = Stock.objects.create(product=product, store=store, quantity=10)

    client = APIClient()
    token_resp = client.post('/api/v1/token/', {'username': 'john', 'password': 'test123'}, format='json')
    assert token_resp.status_code == 200
    access_token = token_resp.data['access']
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)

    # Сначала проверим начальное значение view_count = 0
    assert product.view_count == 0

    # Запрос к детальному эндпоинту
    detail_url = f"/api/v1/product/{product.pk}/"
    resp = client.get(detail_url)
    assert resp.status_code == 200
    data = resp.json()

    # Проверяем, что в ответе вернулся view_count=1
    # (т.к. в коде после get_object() мы инкрементируем)
    updated_product = Product.objects.get(pk=product.pk)
    assert updated_product.view_count == 1
    assert data['view_count'] == 1


@pytest.mark.django_db
def test_product_search_view():
    """
    Тестируем эндпоинт поиска /api/v1/search/?q=...:
    - учитывает склад пользователя (store)
    - приоритезирует товары, которые есть на складе user'а
    - фильтрует товары по подстроке
    """
    user = User.objects.create_user(username='alice', password='testpass')
    city = City.objects.create(name="CitySearch")
    store = Store.objects.create(name="StoreSearch", city=city)

    # Второй склад, чтобы проверить приоритет
    another_store = Store.objects.create(name="AnotherStore", city=city)

    # Товар 1 - подходит под поиск, есть остаток в user.store
    product1 = Product.objects.create(name="Laptop Search", description="Powerful device")
    Price.objects.create(product=product1, store=store, amount=999.0)
    Stock.objects.create(product=product1, store=store, quantity=5)

    # Товар 2 - тоже подходит под поиск, есть остаток, но в другом складе
    product2 = Product.objects.create(name="Laptop for Everyone", description="Cool device")
    Price.objects.create(product=product2, store=another_store, amount=888.0)
    Stock.objects.create(product=product2, store=another_store, quantity=10)

    # Товар 3 - не подходит под поисковую подстроку
    product3 = Product.objects.create(name="Headphones", description="Noise cancelling")
    Price.objects.create(product=product3, store=store, amount=100.0)
    Stock.objects.create(product=product3, store=store, quantity=3)

    # Привязываем alice к store
    UserProfile.objects.create(user=user, store=store)

    client = APIClient()
    token_resp = client.post('/api/v1/token/', {'username': 'alice', 'password': 'testpass'}, format='json')
    access_token = token_resp.data['access']
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)

    # Поиск по подстроке "Laptop"
    resp = client.get("/api/v1/search/?q=Laptop")
    assert resp.status_code == 200
    results = resp.json()

    # Ожидаем 2 результата: product1 и product2 (а не product3)
    assert len(results) == 2
    # При этом product1 должен идти первым (in_user_store=1), product2 - вторым
    assert results[0]['id'] == product1.id
    assert results[1]['id'] == product2.id

    # Проверяем, что stock и price отдаются корректно
    assert results[0]['stock'] == 5
    assert results[0]['price'] == "999.00"
    assert results[1]['stock'] == 0
    assert results[1]['price'] == None  # None, так как user.store != another_store => get_price вернёт None


@pytest.mark.django_db
def test_stock_update_view():
    """
    Тестируем массовое обновление остатков через /api/v1/catalog/update/stocks.
    """
    user = User.objects.create_user(username='admin', password='adminpass')
    city = City.objects.create(name="CityX")
    store1 = Store.objects.create(name="StoreX", city=city)
    store2 = Store.objects.create(name="StoreY", city=city)

    product = Product.objects.create(name="Mass Update Product", description="Bulk update test")
    stock1 = Stock.objects.create(product=product, store=store1, quantity=10)
    stock2 = Stock.objects.create(product=product, store=store2, quantity=20)

    client = APIClient()
    token_resp = client.post('/api/v1/token/', {'username': 'admin', 'password': 'adminpass'}, format='json')
    access_token = token_resp.data['access']
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)

    # Обновляем остатки для product в двух магазинах
    update_data = [
        {"product_id": product.id, "store_id": store1.id, "quantity": 999},
        {"product_id": product.id, "store_id": store2.id, "quantity": 555},
    ]
    resp = client.post('/api/v1/catalog/update/stocks', update_data, format='json')
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Stocks updated"

    # Проверяем, что значения обновились
    stock1.refresh_from_db()
    stock2.refresh_from_db()
    assert stock1.quantity == 999
    assert stock2.quantity == 555


@pytest.mark.django_db
def test_city_specific_images():
    """
    Тестируем логику выбора city-specific изображений:
    - если у товара есть изображения, привязанные к конкретному city,
      отдаются они,
    - иначе отдаются изображения, у которых city = None.
    """
    user = User.objects.create_user(username='tom', password='tompass')
    city1 = City.objects.create(name="CityPhotos")
    city2 = City.objects.create(name="OtherCity")
    store = Store.objects.create(name="PhotoStore", city=city1)
    UserProfile.objects.create(user=user, store=store)

    product = Product.objects.create(name="PhotoProduct", description="Check images")
    # city-specific фото
    ProductImage.objects.create(product=product, city=city1, image_data="base64_city1")
    # общее фото
    ProductImage.objects.create(product=product, city=None, image_data="base64_generic")

    # Добавим второй товар с только generic фото
    product2 = Product.objects.create(name="NoCityPhoto", description="Only generic images")
    ProductImage.objects.create(product=product2, city=None, image_data="base64_generic_2")

    # Пропишем какую-нибудь цену/остаток, чтобы товар был виден в каталоге
    Price.objects.create(product=product, store=store, amount=100)
    Stock.objects.create(product=product, store=store, quantity=5)

    Price.objects.create(product=product2, store=store, amount=200)
    Stock.objects.create(product=product2, store=store, quantity=10)

    client = APIClient()
    token_resp = client.post('/api/v1/token/', {'username': 'tom', 'password': 'tompass'}, format='json')
    access_token = token_resp.data['access']
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)

    resp = client.get("/api/v1/catalog/")
    assert resp.status_code == 200
    data = resp.json()

    # Ищем product1 и product2 в результате
    p1_data = next((item for item in data if item['id'] == product.id), None)
    p2_data = next((item for item in data if item['id'] == product2.id), None)

    assert p1_data is not None
    assert p2_data is not None

    # Для p1_data должно отдаваться city-specific фото (т.к. user.store.city = city1)
    assert len(p1_data['images']) == 1
    assert p1_data['images'][0]['image_data'] == "base64_city1"

    # Для p2_data нет city-specific фото, должны вернуться все generic (1 шт.)
    assert len(p2_data['images']) == 1
    assert p2_data['images'][0]['image_data'] == "base64_generic_2"
