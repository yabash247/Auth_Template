from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views_webhooks import StripeWebhookView
from .views_webhooks_paypal import PayPalWebhookView
from .views_test_webhook import TestWebhookView
from .views_transactions import PaymentTransactionViewSet, CreditWalletViewSet, BuyCoinsView

router = DefaultRouter()
router.register(r"transactions", PaymentTransactionViewSet, basename="transactions")
router.register(r"wallet", CreditWalletViewSet, basename="wallet")

urlpatterns = [
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("webhooks/paypal/", PayPalWebhookView.as_view(), name="paypal-webhook"),
    path("test-webhook/", TestWebhookView.as_view(), name="test-webhook"),
    path("wallet/buy-coins/", BuyCoinsView.as_view(), name="buy-coins"),

]
urlpatterns += router.urls
