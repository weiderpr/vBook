from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    path('checkout/<int:plan_id>/', views.checkout_view, name='checkout'),
    path('process-payment/', views.process_payment_view, name='process_payment'),
    path('create-stripe-intent/', views.create_stripe_intent_view, name='create_stripe_intent'),
    path('payment-status/<str:mp_payment_id>/', views.payment_status_view, name='payment_status'),
    path('success/', views.payment_success_view, name='payment_success'),
    path('webhook/', views.webhook_view, name='mp_webhook'),
    path('webhook/stripe/', views.stripe_webhook_view, name='stripe_webhook'),
    path('simular-aprovacao/<str:payment_id>/', views.simulate_approval_view, name='simulate_approval'),
]
