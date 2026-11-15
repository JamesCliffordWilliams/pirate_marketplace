
"""
services/saved_payment_method_service.py

Purpose:
Handles business logic for users' saved payment methods.

Only payment methods retrieved and verified through
the Stripe backend should be passed to the save function.
"""

from models.saved_payment_method_model import (
    add_saved_payment_method,
    get_saved_payment_methods,
    get_saved_payment_method_by_id,
    delete_saved_payment_method,
)


def save_payment_method_service(user_id, payment_method):
    """
    Saves a Stripe PaymentMethod object after the controller
    has verified that it belongs to the user's Stripe customer.

    Never pass raw card information from a frontend form.
    """

    if not user_id:
        raise ValueError("User must be logged in.")

    if not payment_method:
        raise ValueError("Payment method was not provided.")

    # Stripe PaymentMethod objects contain a card property
    # when the payment method is a card.
    card = payment_method.card

    if not card:
        raise ValueError("Only card payment methods can be saved.")

    payment_method_id = payment_method.id

    if not payment_method_id or not payment_method_id.startswith("pm_"):
        raise ValueError("Invalid Stripe payment method.")

    return add_saved_payment_method(
        user_id=user_id,
        stripe_payment_method_id=payment_method_id,
        card_brand=card.brand,
        last_four=card.last4,
        expiration_month=card.exp_month,
        expiration_year=card.exp_year,
    )


def get_saved_cards_service(user_id):
    """Returns all saved cards belonging to the logged-in user."""

    if not user_id:
        raise ValueError("User must be logged in.")

    return get_saved_payment_methods(user_id)


def remove_saved_card_service(user_id, payment_method_id):
    """Removes a saved card belonging to the logged-in user."""

    if not user_id:
        raise ValueError("User must be logged in.")

    if not payment_method_id:
        raise ValueError("A saved card ID is required.")

    saved_card = get_saved_payment_method_by_id(
        user_id,
        payment_method_id
    )

    if not saved_card:
        raise ValueError("Saved card not found.")

    return delete_saved_payment_method(
        user_id,
        payment_method_id
    )
