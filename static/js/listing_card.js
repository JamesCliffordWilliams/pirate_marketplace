/*
    listing_card.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by James Williams - 10/26/26
    Moved out of storefront_view.js (original card code by Day Ekoi, Iterations 4-5)
    Updated by James Williams - 10/26/26 - sends a detail_view for the Hot page when the image viewer opens

    Updated by James Williams - 10/26/26 - compact product tile (photo, title, price, store, save);
    buying moved to the product page, which shares addToBag() and setSaved() from here

Description:
The product tile used on the storefront, category, Hot and storefront directory pages.
Use VaultListingCard.create(item, options) to build a tile; it links to /listings/<id>.
User text is always added as plain text so it can't run as code.

Works with:
- theme.css (.pm-tile), listing_card.css
- storefront_view.js, category_listings.js, hot.js, storefront.js, product.js
*/

(function () {
    const AUTH_ME_ENDPOINT = "/auth/api/auth/me";
    const PLACEHOLDER_IMAGE = "/static/images/listing-placeholder.svg";
    const LOCAL_WISHLIST_IMAGE = "/static/images/logo.png";

    const trackedDetailViews = new Set(); // Added by James Williams 10/26/26

    // ________________________________________________________
    // SMALL DOM HELPERS
    // ________________________________________________________

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    // Creates an element; text is always set via textContent
    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = String(text);
        return node;
    }


    // ________________________________________________________
    // PRICE
    // ________________________________________________________

    function toNumericPrice(priceValue) {
        if (typeof priceValue === "number") return priceValue;
        if (typeof priceValue === "string") {
            const cleaned = priceValue.replace(/\$/g, "").trim();
            const parsed = Number(cleaned);
            if (!Number.isNaN(parsed)) return parsed;
        }
        return 0;
    }

    function formatPrice(priceValue) {
        if (typeof priceValue === "string" && priceValue.includes("$")) {
            return priceValue;
        }
        return `$${toNumericPrice(priceValue).toFixed(2)}`;
    }

    // ________________________________________________________
    // LOCAL WISHLIST CACHE + SESSION
    // ________________________________________________________

    function getLocalWishlistItems() {
        try {
            const raw = localStorage.getItem("vaultWishlistLocalItems");
            return raw ? JSON.parse(raw) : [];
        } catch (error) {
            console.error("Unable to read local wishlist:", error);
            return [];
        }
    }

    function setLocalWishlistItems(items, fallbackStorefrontName) {
        const normalized = items.map((item) => ({
            listing_id: Number(item.listing_id || item.id),
            title: item.title || item.name || item.listing?.title || "Untitled Listing",
            price: item.price ?? item.listing?.price ?? 0,
            image_url: item.image_url || item.listing?.image_url || item.storefront?.logo_url || LOCAL_WISHLIST_IMAGE,
            storefront_name: item.storefront_name || item.storefront?.brand_name || fallbackStorefrontName || "Storefront"
        }));

        try {
            localStorage.setItem("vaultWishlistLocalItems", JSON.stringify(normalized));
            localStorage.setItem("vaultWishlistListingIds", JSON.stringify(normalized.map((item) => String(item.listing_id))));
        } catch (error) {
            console.error("Unable to save local wishlist:", error);
        }
    }

    function addLocalWishlistItem(item) {
        const items = getLocalWishlistItems();
        const listingId = String(item.listing_id || item.id);
        const filtered = items.filter((existing) => String(existing.listing_id || existing.id) !== listingId);
        filtered.unshift({
            listing_id: Number(listingId),
            title: item.title || item.name || "Untitled Listing",
            price: item.price,
            image_url: item.image_url || LOCAL_WISHLIST_IMAGE,
            storefront_name: item.storefront_name || "Storefront"
        });
        setLocalWishlistItems(filtered);
    }

    function removeLocalWishlistItem(listingId) {
        const updated = getLocalWishlistItems().filter((item) => String(item.listing_id || item.id) !== String(listingId));
        setLocalWishlistItems(updated);
    }

    async function getCurrentSessionUser() {
        try {
            const response = await fetch(AUTH_ME_ENDPOINT);
            if (!response.ok) return null;

            const user = await response.json();
            if (user && user.id) {
                localStorage.setItem("vaultUserId", String(user.id));
                sessionStorage.setItem("vaultUserId", String(user.id));
            }
            return user;
        } catch (error) {
            console.error("Unable to determine current user:", error);
            return null;
        }
    }

    async function getWishlistIdSet(userId, fallbackStorefrontName) {
        if (!userId) {
            return new Set();
        }

        try {
            const response = await fetch("/api/wishlist", {
                headers: {
                    "X-User-Id": String(userId)
                }
            });

            if (!response.ok) {
                throw new Error("Failed to load wishlist status");
            }

            const data = await response.json();
            const wishlistItems = Array.isArray(data.wishlist) ? data.wishlist : [];
            setLocalWishlistItems(wishlistItems, fallbackStorefrontName);

            return new Set(wishlistItems.map((item) => String(item.listing_id || item.id)));
        } catch (error) {
            console.error("Unable to load wishlist ids:", error);
            return new Set(getLocalWishlistItems().map((item) => String(item.listing_id || item.id)));
        }
    }

    // ________________________________________________________
    // DETAIL VIEW TRACKING (Hot page)
    // Added by James Williams 10/26/26
    // ________________________________________________________

    // Once per listing per page load, logged-in shoppers only. Never shown to the shopper.
    function trackDetailView(listingId, currentUserId) {
        const id = Number(listingId);
        if (!currentUserId || !Number.isInteger(id) || id <= 0 || trackedDetailViews.has(id)) {
            return false;
        }
        trackedDetailViews.add(id);
        try {
            fetch(`/api/listings/${id}/interest`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ kind: "detail_view" }),
                credentials: "same-origin",
                keepalive: true
            }).catch(() => {});
        } catch (_error) {
            // tracking never gets in the shopper's way
        }
        return true;
    }

    // ________________________________________________________
    // SHARED ACTIONS (tile heart, product page)
    // ________________________________________________________

    // Same request the old card's "Add to Cart" sent. Resolves, or throws an Error with a message.
    async function addToBag({ listingId, title, price, size, quantity }) {
        const formData = new FormData();
        formData.append("item_id", String(listingId));
        formData.append("item_name", title);
        formData.append("price", String(toNumericPrice(price)));
        formData.append("quantity", String(quantity));
        formData.append("size", size);

        const response = await fetch("/auth/add_to_cart", { method: "POST", body: formData, redirect: "follow" });
        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || "Couldn't add this to your bag. Try again.");
        }

        // keep the header's bag count in step
        const bag = document.querySelector(".pm-header__bag");
        if (bag) {
            let count = bag.querySelector(".pm-header__count");
            if (!count) {
                count = el("span", "pm-header__count", "0");
                count.setAttribute("aria-hidden", "true");
                bag.appendChild(count);
            }
            const total = (Number(count.textContent) || 0) + Number(quantity);
            count.textContent = String(total);
            bag.setAttribute("aria-label", `Bag, ${total} item${total === 1 ? "" : "s"}`);
        }
    }

    // Saves or unsaves a listing (same wishlist requests as before). Throws an Error with a message.
    async function setSaved(listingId, userId, save, meta = {}) {
        const response = await fetch(save ? "/api/wishlist" : `/api/wishlist/${listingId}`, {
            method: save ? "POST" : "DELETE",
            headers: { "Content-Type": "application/json", "X-User-Id": String(userId) },
            body: save ? JSON.stringify({ listing_id: listingId }) : undefined
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok && !(response.status === 400 && /already in wishlist/i.test(result.error || ""))) {
            throw new Error(result.error || "Couldn't update your saved items.");
        }
        if (save) {
            addLocalWishlistItem({ listing_id: listingId, ...meta });
        } else {
            removeLocalWishlistItem(listingId);
        }
    }

    function showToast(message, tone = "success") {
        let root = document.querySelector(".pm-toasts");
        if (!root) {
            root = el("div", "pm pm-toasts");
            root.setAttribute("role", "status");
            root.setAttribute("aria-live", "polite");
            document.body.appendChild(root);
        }
        const toast = el("div", `pm-toast${tone === "error" ? " pm-toast--error" : ""}`, message);
        root.appendChild(toast);
        window.setTimeout(() => toast.remove(), 2600);
    }

    // ________________________________________________________
    // PHOTO FIT
    // ________________________________________________________

    // Studio shots (plain light edges) and wide photos sit whole on the mat; lifestyle shots fill it.
    // Edge pixels can only be read from same-origin or CORS-enabled images; otherwise shape decides.
    function chooseFit(img) {
        const ratio = img.naturalWidth / img.naturalHeight;
        let fit = ratio > 1.15 ? "contain" : "cover";
        try {
            const size = 24;
            const canvas = document.createElement("canvas");
            canvas.width = canvas.height = size;
            const context = canvas.getContext("2d");
            context.drawImage(img, 0, 0, size, size);
            const data = context.getImageData(0, 0, size, size).data;
            let light = 0;
            let edge = 0;
            for (let y = 0; y < size; y += 1) {
                for (let x = 0; x < size; x += 1) {
                    if (x !== 0 && y !== 0 && x !== size - 1 && y !== size - 1) continue;
                    const i = (y * size + x) * 4;
                    edge += 1;
                    if (data[i] > 225 && data[i + 1] > 225 && data[i + 2] > 225) light += 1;
                }
            }
            if (light / edge > 0.85) fit = "contain";
        } catch (_error) {
            // cross-origin photo: keep the shape-based choice
        }
        img.dataset.fit = fit;
    }

    // ________________________________________________________
    // TILE
    // ________________________________________________________

    // Static icon markup only - no user data goes in here
    const WISHLIST_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>';

    function buildHeart(listingId, title, options, meta) {
        const heart = el("button", "pm-heart");
        heart.type = "button";
        heart.innerHTML = WISHLIST_ICON_SVG;
        const render = (saved) => {
            heart.setAttribute("aria-pressed", String(saved));
            heart.setAttribute("aria-label", saved ? `Remove ${title} from saved` : `Save ${title}`);
        };
        const wishlistIds = options.wishlistIds || new Set();
        render(wishlistIds.has(String(listingId)));

        heart.addEventListener("click", async () => {
            if (!options.currentUserId) {
                window.location.href = "/auth/login";
                return;
            }
            const save = heart.getAttribute("aria-pressed") !== "true";
            heart.disabled = true;
            try {
                await setSaved(listingId, options.currentUserId, save, meta);
                render(save);
                if (save) wishlistIds.add(String(listingId)); else wishlistIds.delete(String(listingId));
            } catch (error) {
                showToast(error.message, "error");
            } finally {
                heart.disabled = false;
            }
        });
        return heart;
    }

    async function create(item, options = {}) {
        const listingId = Number(item.id || item.listing_id);
        const title = item.title || item.name || "Untitled listing";
        const storeName = (item.storefront && item.storefront.brand_name) || options.storefrontName || "";
        const imageUrl = (Array.isArray(item.images) && item.images.find(Boolean)) || item.image_url || null;
        const isMadeToOrder = Boolean(item.is_made_to_order);
        const isSoldOut = !isMadeToOrder && (item.status === "SOLD_OUT" || item.quantity_on_hand === 0);

        const tile = el("article", "pm-tile");
        tile.id = `listing-${listingId}`;

        const photo = el("div", "pm-tile__photo");
        const img = el("img");
        img.alt = "";
        img.loading = "lazy";
        img.decoding = "async";
        if (imageUrl) {
            img.addEventListener("load", () => chooseFit(img), { once: true });
            img.addEventListener("error", () => {
                img.src = PLACEHOLDER_IMAGE;
                img.className = "is-placeholder";
            }, { once: true });
            img.src = imageUrl;
        } else {
            img.src = PLACEHOLDER_IMAGE;
            img.className = "is-placeholder";
        }
        photo.appendChild(img);
        if (isSoldOut || isMadeToOrder) {
            photo.appendChild(el("span", "pm-tile__badge", isSoldOut ? "Sold out" : "Made to order"));
        }
        tile.appendChild(photo);

        tile.appendChild(buildHeart(listingId, title, options, {
            title,
            price: item.price,
            image_url: imageUrl || PLACEHOLDER_IMAGE,
            storefront_name: storeName || "Storefront"
        }));

        const link = el("a", "pm-tile__link pm-tile__title", title);
        link.href = `/listings/${listingId}`;
        tile.appendChild(link);
        tile.appendChild(el("span", "pm-tile__price pm-price", formatPrice(item.price)));
        if (storeName && options.showStorefront !== false) {
            tile.appendChild(el("span", "pm-tile__store", storeName));
        }
        return tile;
    }

    // A storefront cover photo that fails to load is removed and the mosaic re-counts its photos
    function dropCoverPhoto(img) {
        const cover = img.parentNode;
        img.remove();
        if (cover) cover.dataset.count = String(Math.min(cover.querySelectorAll("img").length, 3));
    }

    window.VaultListingCard = {
        create,
        dropCoverPhoto,
        addToBag,
        setSaved,
        getCurrentSessionUser,
        getWishlistIdSet,
        trackDetailView, // Added by James Williams 10/26/26
        showToast,
        escapeHtml,
        formatPrice,
        PLACEHOLDER_IMAGE
    };
})();
