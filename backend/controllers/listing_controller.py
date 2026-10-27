# The Vault Campus Marketplace
# CSC 405 Sp 26'
# Created by Day Ekoi - Iteration 3 
# Dates: 2/25-2/26
# Updated by Day Ekoi - Iteration 5 4/10/26 - S3 image upload integration
# Updated by James Williams - 10/26/26 - required categories; the form create checks everything before
#   uploading and saves the listing, photos and sizes together, once per request key

"""
controllers/listing_controller.py

Purpose:
Defines HTTP API endpoints for listing actions.

This layer should stay thin:
- parse request input (JSON, params)
- get current_user (temporary headers until auth is wired)
- call service functions
- return JSON responses

All system rules + permission checks happen in services/listing_service.py.
"""

from flask import Blueprint, request, jsonify
from werkzeug.exceptions import RequestEntityTooLarge  # Added by James Williams 10/26/26

from services.listing_service import (
    create_listing_service,
    build_listing_fields,  # Added by James Williams 10/26/26
    get_listing_by_id_service,
    get_listings_for_storefront_service,
    get_listings_for_storefront_with_options_service,
    update_listing_service,
    delete_listing_service,
    deactivate_listing_service,
    reactivate_listing_service,
    restore_deleted_listing_service,
    # listing images services (merged into listing_service.py)
    add_listing_image_service,
    get_listing_images_service,
    set_primary_image_service,
    delete_listing_image_service,
    # listing sizes services (merged into listing_service.py)
    upsert_listing_size_service,
    get_listing_sizes_service,
    delete_listing_size_service
)
from services.storefront_service import get_my_storefront_service
from services.listing_create_service import CreateError, create_listing_once, parse_idempotency_key  # Added by James Williams 10/26/26

listing_bp = Blueprint("listing_bp", __name__, url_prefix="/api")


def get_current_user():
    """
    Temporary user identity method (until real auth is connected):
    Read user from headers.

    Required header for protected routes:
      X-User-Id: <int>

    """
    user_id = request.headers.get("X-User-Id")
    role = request.headers.get("X-User-Role", "user")

    if not user_id:
        return None

    try:
        return {"id": int(user_id), "role": role}
    except Exception:
        return None


# __________________________________________________________
# CREATE LISTING FROM FORM (with file upload)
# POST /api/listings/create
# Handles form submission from Create Listing page
# __________________________________________________________

@listing_bp.post("/listings/create")
def create_listing_from_form():
    """
    Creates a listing from form data including file upload.
    Expects multipart/form-data with the following fields:
    - storefront_name: name of the storefront (for reference)
    - title: listing title/name
    - quantity_on_hand: quantity available
    - price: listing price
    - fulfillment_type: IN_STOCK or PREORDER
    - status: ACTIVE or INACTIVE
    - sizes_available: JSON string array of sizes ["S", "M", "L"]
    - category_id: the listing's subcategory
    - listing_image: image file upload
    """
    import json

    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

    try:
        # Get user's storefront to validate ownership
        user_storefront = get_my_storefront_service(current_user)
        if user_storefront is None:
            return jsonify({"error": "You must create a storefront before creating listings."}), 400

        # Get form fields
        title = request.form.get("title", "").strip()
        storefront_id = user_storefront["id"]
        price = request.form.get("price", type=float)
        fulfillment_type = request.form.get("fulfillment_type", "IN_STOCK").strip()
        status = request.form.get("status", "ACTIVE").strip()
        sizes_json = request.form.get("sizes_available", "[]")
        size_quantities_json = request.form.get("size_quantities", "{}")
        is_made_to_order = request.form.get("is_made_to_order", "false").lower() in ("true", "1", "yes")

        # Validate required fields
        if not title:
            return jsonify({"error": "title is required."}), 400

        # Parse sizes
        try:
            sizes_available = json.loads(sizes_json)
            if not isinstance(sizes_available, list) or len(sizes_available) == 0:
                return jsonify({"error": "At least one size must be selected."}), 400
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid sizes_available format."}), 400

        # Parse per-size quantities (maps size name → quantity)
        try:
            size_quantities = json.loads(size_quantities_json) if size_quantities_json else {}
            if not isinstance(size_quantities, dict):
                size_quantities = {}
        except json.JSONDecodeError:
            size_quantities = {}

        # Calculate total quantity as sum of all size quantities
        quantity_on_hand = request.form.get("quantity_on_hand", type=int)
        if size_quantities:
            calculated_total = sum(int(v) for v in size_quantities.values() if str(v).isdigit() or isinstance(v, int))
            quantity_on_hand = calculated_total if calculated_total > 0 else (quantity_on_hand or 0)
        elif quantity_on_hand is None:
            quantity_on_hand = 0

        # Updated by James Williams 10/26/26 - everything is checked before any upload, then
        # the listing, images and sizes are saved together, once per Idempotency-Key
        key = parse_idempotency_key(request.headers.get("Idempotency-Key"))

        upload_files = [f for f in request.files.getlist("listing_images") if f and f.filename]
        # Backward compatibility for existing clients sending one file as listing_image.
        if not upload_files and "listing_image" in request.files and request.files["listing_image"].filename:
            upload_files = [request.files["listing_image"]]
        if not upload_files:
            return jsonify({"error": "At least one listing image is required."}), 400
        if len(upload_files) > 4:
            return jsonify({"error": "You can upload up to 4 listing images."}), 400
        if any(not f.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")) for f in upload_files):
            return jsonify({"error": "Image must be PNG, JPG, JPEG, GIF, or WebP."}), 400

        fields = build_listing_fields(current_user, storefront_id, {
            "title": title,
            "quantity_on_hand": quantity_on_hand,
            "price": price,
            "fulfillment_type": fulfillment_type,
            "status": status,
            "description": "",
            "sizes_available": sizes_available,
            "is_made_to_order": is_made_to_order,
            "category_id": request.form.get("category_id"),
        })

        # Per-size quantity if provided, else the total
        size_rows = []
        for size in sizes_available:
            if size is None or str(size).strip() == "":
                return jsonify({"error": "size is required."}), 400
            size_qty = size_quantities.get(size, quantity_on_hand) if size_quantities else quantity_on_hand
            try:
                size_qty = int(size_qty)
            except (TypeError, ValueError):
                size_qty = quantity_on_hand or 0
            if size_qty < 0:
                return jsonify({"error": "quantity cannot be negative."}), 400
            size_rows.append((str(size).strip(), size_qty))

    except CreateError as e:
        return jsonify({"error": str(e)}), e.status
    except RequestEntityTooLarge:
        raise  # app-level 413 handler explains the limit
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        return jsonify({"error": str(e)}), 400

    try:
        listing, status_code = create_listing_once(current_user["id"], key, fields, size_rows, upload_files)
    except CreateError as e:
        return jsonify({"error": str(e)}), e.status
    except Exception as e:
        print(f"Create listing failed: {e}")
        return jsonify({"error": "The listing couldn't be saved. Nothing was created; please try again."}), 500
    return jsonify(listing), status_code


#_________________
# LISTING ROUTES
# Purpose:
# Core listing CRUD routes (create/read/update/delete).
#_________________

# __________________________________________________________
# CREATE LISTING (Owner/Admin)
# POST /api/storefronts/<storefront_id>/listings
#___________________________________________________________

@listing_bp.post("/storefronts/<int:storefront_id>/listings")
def create_listing_route(storefront_id):
    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

    data = request.get_json(silent=True) or {}

    try:
        listing = create_listing_service(current_user, storefront_id, data)
        return jsonify(listing), 201
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


# __________________________________________________________
# GET LISTINGS FOR STOREFRONT (Public)
# GET /api/storefronts/<storefront_id>/listings
# ___________________________________________________________

@listing_bp.get("/storefronts/<int:storefront_id>/listings")
def get_storefront_listings_route(storefront_id):
    try:
        listings = get_listings_for_storefront_service(storefront_id)
        return jsonify(listings), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# __________________________________________________________
# GET MY LISTINGS (Owner/Admin)
# GET /api/listings/my
# ___________________________________________________________

@listing_bp.get("/listings/my")
def get_my_listings_route():
    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

    try:
        user_storefront = get_my_storefront_service(current_user)
        if user_storefront is None:
            return jsonify([]), 200

        include_deleted = request.args.get("include_deleted", "0").lower() in {"1", "true", "yes"}
        listings = get_listings_for_storefront_with_options_service(
            user_storefront["id"],
            include_deleted=include_deleted
        )
        return jsonify(listings), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# _________________________________________________________
# GET SINGLE LISTING (Public)
# GET /api/listings/<listing_id>
# _________________________________________________________

@listing_bp.get("/listings/<int:listing_id>")
def get_listing_route(listing_id):
    try:
        listing = get_listing_by_id_service(listing_id)
        return jsonify(listing), 200
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


#__________________________________________________________
# UPDATE LISTING (Owner/Admin)
# PUT /api/listings/<listing_id>
# _________________________________________________________

@listing_bp.put("/listings/<int:listing_id>")
def update_listing_route(listing_id):
    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

    data = request.get_json(silent=True) or {}

    try:
        updated = update_listing_service(current_user, listing_id, data)
        return jsonify(updated), 200
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


# __________________________________________________________
# DELETE LISTING (Owner/Admin)
# DELETE /api/listings/<listing_id>
# ___________________________________________________________

@listing_bp.delete("/listings/<int:listing_id>")
def delete_listing_route(listing_id):
    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

    try:
        deleted = delete_listing_service(current_user, listing_id)
        return jsonify(deleted), 200
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


# Updated by Day E - April 22nd
# PATCH /api/listings/<listing_id>/deactivate
@listing_bp.patch("/listings/<int:listing_id>/deactivate")
def deactivate_listing_route(listing_id):
    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

    try:
        updated = deactivate_listing_service(current_user, listing_id)
        return jsonify(updated), 200
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


# Updated by Day E - April 22nd
# PATCH /api/listings/<listing_id>/reactivate
@listing_bp.patch("/listings/<int:listing_id>/reactivate")
def reactivate_listing_route(listing_id):
    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

    try:
        updated = reactivate_listing_service(current_user, listing_id)
        return jsonify(updated), 200
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


# Updated by Day E - April 22nd
# PATCH /api/listings/<listing_id>/restore
@listing_bp.patch("/listings/<int:listing_id>/restore")
def restore_deleted_listing_route(listing_id):
    current_user = get_current_user()
    if current_user is None:
        return jsonify({"error": "Unauthorized: missing/invalid X-User-Id"}), 401

    try:
        updated = restore_deleted_listing_service(current_user, listing_id)
        return jsonify(updated), 200
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


#_________________
# LISTING IMAGES ROUTES
# Purpose:
# Routes for adding/removing images and setting the primary image for a listing.
#_________________

# Add image
# POST /api/listings/<listing_id>/images
@listing_bp.post("/listings/<int:listing_id>/images")
def add_image_route(listing_id):
    current_user = get_current_user()
    data = request.get_json(silent=True) or {}

    try:
        result = add_listing_image_service(
            current_user,
            listing_id,
            data.get("image_url"),
            data.get("is_primary", False)
        )
        return jsonify(result), 201
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


# Get images
# GET /api/listings/<listing_id>/images
@listing_bp.get("/listings/<int:listing_id>/images")
def get_images_route(listing_id):
    try:
        result = get_listing_images_service(listing_id)
        return jsonify(result), 200
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


# Set primary
# PATCH /api/listings/<listing_id>/images/<image_id>/primary
@listing_bp.patch("/listings/<int:listing_id>/images/<int:image_id>/primary")
def set_primary_route(listing_id, image_id):
    current_user = get_current_user()

    try:
        result = set_primary_image_service(current_user, listing_id, image_id)
        return jsonify(result), 200
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


# Delete image
# DELETE /api/listings/<listing_id>/images/<image_id>
@listing_bp.delete("/listings/<int:listing_id>/images/<int:image_id>")
def delete_image_route(listing_id, image_id):
    current_user = get_current_user()

    try:
        result = delete_listing_image_service(current_user, listing_id, image_id)
        return jsonify(result), 200
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


#_________________
# LISTING SIZE ROUTES
# Purpose:
# Routes for managing size-based inventory for a listing.
#_________________

# Add / Update size
# POST /api/listings/<listing_id>/sizes
@listing_bp.post("/listings/<int:listing_id>/sizes")
def upsert_size_route(listing_id):
    current_user = get_current_user()
    data = request.get_json(silent=True) or {}

    try:
        result = upsert_listing_size_service(
            current_user,
            listing_id,
            data.get("size"),
            data.get("quantity")
        )
        return jsonify(result), 200
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


# Get sizes
# GET /api/listings/<listing_id>/sizes
@listing_bp.get("/listings/<int:listing_id>/sizes")
def get_sizes_route(listing_id):
    try:
        result = get_listing_sizes_service(listing_id)
        return jsonify(result), 200
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400


# Delete size
# DELETE /api/listings/<listing_id>/sizes/<size>
@listing_bp.delete("/listings/<int:listing_id>/sizes/<string:size>")
def delete_size_route(listing_id, size):
    current_user = get_current_user()

    try:
        result = delete_listing_size_service(current_user, listing_id, size)
        return jsonify(result), 200
    except Exception as e:
        msg = str(e).lower()
        if "unauthorized" in msg:
            return jsonify({"error": str(e)}), 403
        if "not found" in msg:
            return jsonify({"error": str(e)}), 404
        return jsonify({"error": str(e)}), 400
