from django.urls import path
from catalog.views import CatalogListView, ProductDetailView, ProductSearchView, StockUpdateView

urlpatterns = [
    path('catalog/', CatalogListView.as_view(), name='catalog'),
    path('product/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
    path('search/', ProductSearchView.as_view(), name='product-search'),
    path('catalog/update/stocks', StockUpdateView.as_view(), name='stock-update'),
]
