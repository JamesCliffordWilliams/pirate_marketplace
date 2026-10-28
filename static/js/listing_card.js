/*
    listing_card.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by James Williams - 10/26/26
    Moved out of storefront_view.js, the original card code is by Day Ekoi (Iterations 4-5)
    Updated by James Williams - 10/26/26 - counts a view for the Hot page when the image viewer opens

    Updated by James Williams - 10/26/26 - smaller product tile, buying moved to the product page

Description:
This builds the little product tile with the photo, title and price. It's used on the storefront,
category, Hot and storefront list pages. Anything a user typed goes in as plain text so it can't run as code.
It also has the Add to bag and Save code the product page uses, and the loading cards and
current shopper lookup the Hot and category pages share.

Works with:
- theme.css (.pm-tile), listing_card.css
- storefront_view.js, category_listings.js, hot.js, storefront.js, product.js
*/

(function () {
    const PLACEHOLDER_IMAGE = "/static/images/listing-placeholder.svg";
    // The saved listing ids are kept in the browser too, so the hearts still show if the wishlist doesn't load
    const SAVED_IDS_KEY = "vaultWishlistListingIds";

    const trackedDetailViews = new Set(); // Added by James Williams 10/26/26
    let viewerPromise = null;

    // Makes an element. Text always goes in as plain text
    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    // ________________________________________________________
    // PRICE
    // ________________________________________________________

    function toNumericPrice(priceValue) {
        if (typeof priceValue === "number") return priceValue;
        if (typeof priceValue === "string") {
            const parsed = Number(priceValue.replace(/\$/g, "").trim());
            if (!Number.isNaN(parsed)) return parsed;
        }
        return 0;
    }

    // A price that already has a "$" is shown as it is
    function formatPrice(priceValue) {
        if (typeof priceValue === "string" && priceValue.includes("$")) return priceValue;
        return `$${toNumericPrice(priceValue).toFixed(2)}`;
    }

    // ________________________________________________________
    // SAVED ITEMS AND THE CURRENT USER
    // ________________________________________________________

    function readSavedIds() {
        try {
            return JSON.parse(localStorage.getItem(SAVED_IDS_KEY)) || [];
        } catch (error) {
            console.error("Unable to read local wishlist:", error);
            return [];
        }
    }

    function writeSavedIds(ids) {
        try {
            localStorage.setItem(SAVED_IDS_KEY, JSON.stringify(ids));
        } catch (error) {
            console.error("Unable to save local wishlist:", error);
        }
    }

    async function getCurrentSessionUser() {
        try {
            const response = await fetch("/auth/api/auth/me");
            return response.ok ? await response.json() : null;
        } catch (error) {
            console.error("Unable to determine current user:", error);
            return null;
        }
    }

    // Returns the ids of the listings this user saved, as strings
    async function getWishlistIdSet(userId) {
        if (!userId) return new Set();

        try {
            const response = await fetch("/api/wishlist", { headers: { "X-User-Id": String(userId) } });
            if (!response.ok) throw new Error("Failed to load wishlist status");

            const data = await response.json();
            const items = Array.isArray(data.wishlist) ? data.wishlist : [];
            const ids = items.map((item) => String(item.listing_id || item.id));
            writeSavedIds(ids);
            return new Set(ids);
        } catch (error) {
            console.error("Unable to load wishlist ids:", error);
            return new Set(readSavedIds());
        }
    }

    // Finds the logged in shopper and what they saved, for the Hot and category pages.
    // It only asks the server once, even when the page loads its cards again
    function getViewer(page) {
        if (!viewerPromise) {
            viewerPromise = (async () => {
                let userId = Number(page.dataset.userId) || null;
                if (!userId && page.dataset.loggedIn === "true") {
                    const user = await getCurrentSessionUser();
                    userId = user?.id || null;
                }
                const wishlistIds = await getWishlistIdSet(userId);
                return { userId, wishlistIds };
            })();
        }
        return viewerPromise;
    }

    // ________________________________________________________
    // DETAIL VIEW TRACKING (Hot page)
    // Added by James Williams 10/26/26
    // ________________________________________________________

    // Counts a view for the Hot page. It only counts once per listing per page load, and only for logged in shoppers.
    // If the request fails we just ignore it so the shopper isn't bothered
    function trackDetailView(listingId, currentUserId) {
        const id = Number(listingId);
        if (!currentUserId || !Number.isInteger(id) || id <= 0 || trackedDetailViews.has(id)) {
            return false;
        }
        trackedDetailViews.add(id);
        fetch(`/api/listings/${id}/interest`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ kind: "detail_view" }),
            credentials: "same-origin",
            keepalive: true
        }).catch(() => {});
        return true;
    }

    // ________________________________________________________
    // SHARED ACTIONS (tile heart, product page)
    // ________________________________________________________

    // This code is responsible for the Add to bag button. It sends the same request the old
    // Add to Cart button did and throws an error if it doesn't work
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

        // updates the bag count up in the header
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

    // Saves or unsaves a listing. It throws an error with a message if it doesn't work.
    // Saving something that's already saved counts as working
    async function setSaved(listingId, userId, save) {
        const response = await fetch(save ? "/api/wishlist" : `/api/wishlist/${listingId}`, {
            method: save ? "POST" : "DELETE",
            headers: { "Content-Type": "application/json", "X-User-Id": String(userId) },
            body: save ? JSON.stringify({ listing_id: listingId }) : undefined
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok && !(response.status === 400 && /already in wishlist/i.test(result.error || ""))) {
            throw new Error(result.error || "Couldn't update your saved items.");
        }
        const otherIds = readSavedIds().filter((id) => String(id) !== String(listingId));
        writeSavedIds(save ? [String(listingId), ...otherIds] : otherIds);
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

    // Wide photos, and photos with a plain light border, are shown whole. Other photos fill the box.
    // To check the border we shrink the photo to 24x24 and look at the outside ring of pixels.
    // The browser won't let us read some photos from other sites, so those just go by the shape
    function chooseFit(img) {
        let fit = img.naturalWidth / img.naturalHeight > 1.15 ? "contain" : "cover";
        try {
            const size = 24;
            const canvas = document.createElement("canvas");
            canvas.width = canvas.height = size;
            const context = canvas.getContext("2d");
            context.drawImage(img, 0, 0, size, size);
            const pixels = context.getImageData(0, 0, size, size).data;

            let edgePixels = 0;
            let lightPixels = 0;
            for (let y = 0; y < size; y += 1) {
                for (let x = 0; x < size; x += 1) {
                    const onEdge = x === 0 || y === 0 || x === size - 1 || y === size - 1;
                    if (!onEdge) continue;
                    const i = (y * size + x) * 4; // each pixel is red, green, blue, alpha
                    edgePixels += 1;
                    if (pixels[i] > 225 && pixels[i + 1] > 225 && pixels[i + 2] > 225) lightPixels += 1;
                }
            }
            if (lightPixels / edgePixels > 0.85) fit = "contain";
        } catch (_error) {
            // we can't read this photo, so we keep the choice based on shape
        }
        img.dataset.fit = fit;
    }

    // ________________________________________________________
    // TILE
    // ________________________________________________________

    // This is just the heart icon, no user data goes in here
    const WISHLIST_ICON_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>';

    function buildHeart(listingId, title, options) {
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
                await setSaved(listingId, options.currentUserId, save);
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

    // Builds one product tile. options.wishlistIds and options.currentUserId set up the heart,
    // and showStorefront: false hides the store name (on the store's own page)
    async function create(item, options = {}) {
        const listingId = Number(item.id || item.listing_id);
        const title = item.title || item.name || "Untitled listing";
        const storeName = (item.storefront && item.storefront.brand_name) || "";
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
        const showPlaceholder = () => {
            img.src = PLACEHOLDER_IMAGE;
            img.className = "is-placeholder";
        };
        if (imageUrl) {
            img.addEventListener("load", () => chooseFit(img), { once: true });
            img.addEventListener("error", showPlaceholder, { once: true });
            img.src = imageUrl;
        } else {
            showPlaceholder();
        }
        photo.appendChild(img);
        if (isSoldOut || isMadeToOrder) {
            photo.appendChild(el("span", "pm-tile__badge", isSoldOut ? "Sold out" : "Made to order"));
        }
        tile.appendChild(photo);

        tile.appendChild(buildHeart(listingId, title, options));

        const link = el("a", "pm-tile__link pm-tile__title", title);
        link.href = `/listings/${listingId}`;
        tile.appendChild(link);
        tile.appendChild(el("span", "pm-tile__price pm-price", formatPrice(item.price)));
        if (storeName && options.showStorefront !== false) {
            tile.appendChild(el("span", "pm-tile__store", storeName));
        }
        return tile;
    }

    // The gray cards that show while a page loads its products
    function skeletonCards(count) {
        const cards = [];
        for (let i = 0; i < count; i += 1) {
            const card = el("div", "cat-skeleton-card");
            card.setAttribute("aria-hidden", "true");
            ["image", "line", "short", "button"].forEach((part) => {
                card.appendChild(el("div", `cat-skeleton-block cat-skeleton-block--${part}`));
            });
            cards.push(card);
        }
        return cards;
    }

    // If a store cover photo doesn't load, this removes it and updates the photo count
    function dropCoverPhoto(img) {
        const cover = img.parentNode;
        img.remove();
        if (cover) cover.dataset.count = String(Math.min(cover.querySelectorAll("img").length, 3));
    }

    window.VaultListingCard = {
        create,
        skeletonCards,
        dropCoverPhoto,
        addToBag,
        setSaved,
        getCurrentSessionUser,
        getWishlistIdSet,
        getViewer,
        trackDetailView, // Added by James Williams 10/26/26
        showToast,
        formatPrice,
        PLACEHOLDER_IMAGE
    };
})();
