/*
    listing_card.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by James Williams - 10/26/26
    Moved out of storefront_view.js (original card code by Day Ekoi, Iterations 4-5)
    Updated by James Williams - 10/26/26 - sends a detail_view for the Hot page when the image viewer opens

Description:
The product card used on the storefront page and the category pages:
images, size, count, add to cart, wishlist, and sold out.
Use VaultListingCard.create(item, options) to build a card.
User text is always added as plain text so it can't run as code.

Works with:
- listing_card.css
- storefront_view.js, category_listings.js, hot.js
*/

(function () {
    const AUTH_ME_ENDPOINT = "/auth/api/auth/me";
    const PLACEHOLDER_IMAGE = "/static/images/listing-placeholder.svg";
    const LOCAL_WISHLIST_IMAGE = "/static/images/logo.png";

    const listingImagesCache = new Map();
    const lightboxState = {
        images: [],
        index: 0
    };
    let lightboxElements = null;
    const trackedDetailViews = new Set();

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

    function useFallbackImageOnError(img) {
        img.addEventListener("error", () => {
            if (img.dataset.fallbackApplied === "1") return;
            img.dataset.fallbackApplied = "1";
            img.src = PLACEHOLDER_IMAGE;
        });
    }

    function setImageSource(img, url) {
        img.dataset.fallbackApplied = "0";
        img.src = url || PLACEHOLDER_IMAGE;
    }

    // ________________________________________________________
    // TOAST
    // ________________________________________________________

    function ensureToastRoot() {
        let root = document.getElementById("cartToastRoot");
        if (!root) {
            root = document.createElement("div");
            root.id = "cartToastRoot";
            root.className = "cart-toast-root";
            root.setAttribute("role", "status");
            root.setAttribute("aria-live", "polite");
            document.body.appendChild(root);
        }
        return root;
    }

    function showToast(message, tone = "success") {
        const root = ensureToastRoot();
        const toast = document.createElement("div");
        toast.className = `cart-toast ${tone === "error" ? "error" : "success"}`;
        toast.textContent = message;
        root.appendChild(toast);

        window.setTimeout(() => {
            toast.classList.add("fade-out");
            window.setTimeout(() => toast.remove(), 220);
        }, 2200);
    }

    // ________________________________________________________
    // PRICE + SIZES
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

    function parseSizesFromListing(item) {
        const source = item.sizes_available;

        if (Array.isArray(source)) {
            return source.map((size) => String(size).trim()).filter(Boolean);
        }

        if (typeof source === "string" && source.trim()) {
            try {
                const parsed = JSON.parse(source);
                if (Array.isArray(parsed)) {
                    return parsed.map((size) => String(size).trim()).filter(Boolean);
                }
            } catch (_error) {
                return source
                    .split(",")
                    .map((size) => size.trim())
                    .filter(Boolean);
            }
        }

        return [];
    }

    function sizesFromEntries(entries) {
        return entries
            .map((entry) => String((entry && entry.size) || "").trim())
            .filter(Boolean);
    }

    async function getListingSizeOptions(listingId, item) {
        const inlineSizes = parseSizesFromListing(item);
        if (inlineSizes.length > 0) {
            return inlineSizes;
        }

        // Category pages already include the sizes
        if (Array.isArray(item.sizes)) {
            return sizesFromEntries(item.sizes);
        }

        try {
            const response = await fetch(`/api/listings/${listingId}/sizes`);
            if (!response.ok) {
                return [];
            }

            const data = await response.json();
            if (!Array.isArray(data)) {
                return [];
            }

            return sizesFromEntries(data);
        } catch (error) {
            console.error("Unable to load listing sizes:", error);
            return [];
        }
    }

    // ________________________________________________________
    // IMAGES
    // ________________________________________________________

    async function fetchListingImages(listingId, fallbackImageUrl) {
        if (listingImagesCache.has(listingId)) {
            return listingImagesCache.get(listingId);
        }

        try {
            const response = await fetch(`/api/listings/${listingId}/images`);
            if (!response.ok) {
                throw new Error("Unable to load listing images.");
            }

            const images = await response.json();
            const normalized = Array.isArray(images)
                ? images
                    .map((image) => String(image.image_url || "").trim())
                    .filter(Boolean)
                    .slice(0, 4)
                : [];

            if (normalized.length > 0) {
                listingImagesCache.set(listingId, normalized);
                return normalized;
            }
        } catch (error) {
            console.error(`Unable to load images for listing ${listingId}:`, error);
        }

        const fallback = [fallbackImageUrl || PLACEHOLDER_IMAGE];
        listingImagesCache.set(listingId, fallback);
        return fallback;
    }

    async function getListingImages(listingId, item) {
        // Category pages already include the images
        if (Array.isArray(item.images)) {
            const inline = item.images
                .map((url) => String(url || "").trim())
                .filter(Boolean)
                .slice(0, 4);
            return inline.length > 0 ? inline : [PLACEHOLDER_IMAGE];
        }
        return fetchListingImages(listingId, item.image_url);
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
    // LIGHTBOX (full-size image viewer)
    // ________________________________________________________

    function buildLightboxMarkup() {
        const lightbox = el("div", "listing-lightbox");
        lightbox.id = "listingLightbox";

        const close = el("button", "lightbox-close");
        close.id = "lightboxClose";
        close.type = "button";
        close.setAttribute("aria-label", "Close image preview");
        close.innerHTML = "&times;";

        const prev = el("button", "lightbox-nav lightbox-nav--left");
        prev.id = "lightboxPrev";
        prev.type = "button";
        prev.setAttribute("aria-label", "Previous image");
        prev.innerHTML = "&#10094;";

        const stage = el("div", "lightbox-stage");
        const image = el("img", "lightbox-image");
        image.id = "lightboxImage";
        image.alt = "Listing preview";
        const dots = el("div", "lightbox-dots");
        dots.id = "lightboxDots";
        stage.append(image, dots);

        const next = el("button", "lightbox-nav lightbox-nav--right");
        next.id = "lightboxNext";
        next.type = "button";
        next.setAttribute("aria-label", "Next image");
        next.innerHTML = "&#10095;";

        lightbox.append(close, prev, stage, next);
        document.body.appendChild(lightbox);
        return lightbox;
    }

    function getLightbox() {
        if (lightboxElements) return lightboxElements;

        const lightbox = document.getElementById("listingLightbox") || buildLightboxMarkup();
        lightboxElements = {
            lightbox,
            image: document.getElementById("lightboxImage"),
            dots: document.getElementById("lightboxDots"),
            close: document.getElementById("lightboxClose"),
            prev: document.getElementById("lightboxPrev"),
            next: document.getElementById("lightboxNext")
        };

        if (lightboxElements.image) useFallbackImageOnError(lightboxElements.image);
        if (lightboxElements.close) lightboxElements.close.addEventListener("click", closeLightbox);
        if (lightboxElements.prev) lightboxElements.prev.addEventListener("click", () => shiftLightbox(-1));
        if (lightboxElements.next) lightboxElements.next.addEventListener("click", () => shiftLightbox(1));

        lightbox.addEventListener("click", (event) => {
            if (event.target === lightbox) {
                closeLightbox();
            }
        });

        document.addEventListener("keydown", (event) => {
            if (!lightbox.classList.contains("is-open")) return;
            if (event.key === "Escape") {
                closeLightbox();
            } else if (event.key === "ArrowLeft") {
                shiftLightbox(-1);
            } else if (event.key === "ArrowRight") {
                shiftLightbox(1);
            }
        });

        return lightboxElements;
    }

    function updateDots(container, images, activeIndex, dotClassName, onSelect) {
        if (!container) return;

        container.innerHTML = "";
        if (!Array.isArray(images) || images.length <= 1) {
            return;
        }

        images.forEach((_image, index) => {
            const dot = document.createElement("button");
            dot.type = "button";
            dot.className = `${dotClassName} ${index === activeIndex ? "active" : ""}`;
            dot.setAttribute("aria-label", `Go to image ${index + 1}`);
            dot.addEventListener("click", () => onSelect(index));
            container.appendChild(dot);
        });
    }

    function renderLightbox() {
        const { image, dots, prev, next } = getLightbox();
        if (!image) return;

        const { images, index } = lightboxState;
        if (!images.length) return;

        setImageSource(image, images[index]);
        image.alt = `Listing image ${index + 1}`;
        updateDots(dots, images, index, "lightbox-dot", (nextIndex) => {
            lightboxState.index = nextIndex;
            renderLightbox();
        });

        if (prev) {
            prev.style.display = images.length > 1 ? "inline-flex" : "none";
        }
        if (next) {
            next.style.display = images.length > 1 ? "inline-flex" : "none";
        }
    }

    function openLightbox(images, startIndex = 0) {
        const { lightbox } = getLightbox();
        if (!lightbox || !Array.isArray(images) || !images.length) return;
        lightboxState.images = images;
        lightboxState.index = startIndex;
        renderLightbox();
        lightbox.classList.add("is-open");
        document.body.style.overflow = "hidden";
    }

    function closeLightbox() {
        const { lightbox } = getLightbox();
        if (!lightbox) return;
        lightbox.classList.remove("is-open");
        document.body.style.overflow = "";
    }

    function shiftLightbox(step) {
        if (!lightboxState.images.length) return;
        lightboxState.index = (lightboxState.index + step + lightboxState.images.length) % lightboxState.images.length;
        renderLightbox();
    }

    // ________________________________________________________
    // IMAGE CAROUSEL
    // ________________________________________________________

    function createListingImageCarousel(images, title, onOpen) {
        const shell = document.createElement("div");
        shell.className = "listing-image-shell";

        const image = document.createElement("img");
        image.className = "listing-image";
        image.alt = title;
        useFallbackImageOnError(image);

        const dots = document.createElement("div");
        dots.className = "listing-image-dots";

        const counter = document.createElement("div");
        counter.className = "listing-image-counter";

        let currentIndex = 0;

        const render = () => {
            setImageSource(image, images[currentIndex]);
            counter.textContent = `${currentIndex + 1}/${images.length}`;
            updateDots(dots, images, currentIndex, "listing-image-dot", (nextIndex) => {
                currentIndex = nextIndex;
                render();
            });
        };

        image.addEventListener("click", () => {
            openLightbox(images, currentIndex);
            if (onOpen) onOpen();
        });
        shell.classList.add("is-clickable");
        shell.appendChild(image);

        if (images.length > 1) {
            const prevBtn = document.createElement("button");
            prevBtn.type = "button";
            prevBtn.className = "listing-image-nav listing-image-nav--left";
            prevBtn.setAttribute("aria-label", "Previous image");
            prevBtn.innerHTML = "&#10094;";
            prevBtn.addEventListener("click", (event) => {
                event.stopPropagation();
                currentIndex = (currentIndex - 1 + images.length) % images.length;
                render();
            });

            const nextBtn = document.createElement("button");
            nextBtn.type = "button";
            nextBtn.className = "listing-image-nav listing-image-nav--right";
            nextBtn.setAttribute("aria-label", "Next image");
            nextBtn.innerHTML = "&#10095;";
            nextBtn.addEventListener("click", (event) => {
                event.stopPropagation();
                currentIndex = (currentIndex + 1) % images.length;
                render();
            });

            shell.appendChild(prevBtn);
            shell.appendChild(nextBtn);
            shell.appendChild(dots);
            shell.appendChild(counter);
        }

        render();
        return { shell, getPrimaryImage: () => images[0] || PLACEHOLDER_IMAGE };
    }

    // ________________________________________________________
    // CARD PIECES
    // ________________________________________________________

    // Static icon markup only - no user data goes in here
    const WISHLIST_ICON_SVG = `
        <svg viewBox="0 0 24 24" class="wishlist-lock-icon" aria-hidden="true">
            <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="1.8"/>
            <rect x="8.5" y="11" width="7" height="5.8" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.8"/>
            <path d="M10 11V9.7a2 2 0 1 1 4 0V11" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>
        </svg>
    `;

    const MADE_TO_ORDER_STYLE = "display:inline-block;background:rgba(212,175,55,0.15);border:1px solid rgba(212,175,55,0.5);color:#d4af37;font-size:0.7rem;font-weight:700;letter-spacing:0.5px;padding:0.15rem 0.45rem;border-radius:999px;text-transform:uppercase;margin-top:2px;";
    const ONE_SIZE_STYLE = "color:#d4af37;font-weight:600;padding:0.2rem 0;";
    const SOLD_OUT_STYLE = "display:block;width:100%;padding:0.6rem 1rem;background:#3a3a3a;color:#888888;font-size:0.85rem;font-weight:600;text-align:center;border-radius:6px;cursor:not-allowed;letter-spacing:0.5px;box-sizing:border-box;";

    function buildSizeField(listingId, sizeOptions, isOneSizeItem) {
        const nodes = [];
        if (isOneSizeItem) {
            nodes.push(el("label", "field-label", "Size"));
            const oneSize = el("span", "one-size-label", "One Size");
            oneSize.setAttribute("style", ONE_SIZE_STYLE);
            nodes.push(oneSize);
        } else if (sizeOptions.length > 0) {
            const label = el("label", "field-label", "Size");
            label.htmlFor = `sizeSelect-${listingId}`;
            const select = el("select", "size-select");
            select.id = `sizeSelect-${listingId}`;
            sizeOptions.forEach((size, index) => {
                const option = el("option", null, size);
                option.value = size;
                if (index === 0) option.selected = true;
                select.appendChild(option);
            });
            nodes.push(label, select);
        } else {
            nodes.push(el("label", "field-label", "Size"));
            const select = el("select", "size-select");
            select.disabled = true;
            const option = el("option", null, "No sizes available");
            option.value = "";
            option.disabled = true;
            option.selected = true;
            select.appendChild(option);
            nodes.push(select);
        }
        return nodes;
    }

    function buildStorefrontRow(item) {
        const storefront = item.storefront || {};
        const storefrontId = Number(storefront.id || item.storefront_id);
        const brandName = storefront.brand_name || "Storefront";

        const row = el("a", "listing-store-row");
        row.href = `/storefronts/${storefrontId}`;
        row.setAttribute("aria-label", `Visit ${brandName}`);

        if (storefront.logo_url) {
            const logo = el("img", "listing-store-logo");
            logo.src = storefront.logo_url;
            logo.alt = "";
            logo.addEventListener("error", () => {
                logo.replaceWith(buildStoreInitial(brandName));
            });
            row.appendChild(logo);
        } else {
            row.appendChild(buildStoreInitial(brandName));
        }

        row.appendChild(el("span", "listing-store-name", brandName));
        return row;
    }

    function buildStoreInitial(brandName) {
        const initial = el("span", "listing-store-logo listing-store-logo--initial", (brandName.trim()[0] || "?").toUpperCase());
        initial.setAttribute("aria-hidden", "true");
        return initial;
    }

    // ________________________________________________________
    // CARD
    // ________________________________________________________

    async function create(item, options = {}) {
        const wishlistIds = options.wishlistIds || new Set();
        const currentUserId = options.currentUserId || null;
        const showStorefront = Boolean(options.showStorefront);

        const card = document.createElement("div");
        card.className = showStorefront ? "listing-card listing-card--browse" : "listing-card";

        const listingId = Number(item.id || item.listing_id);
        card.id = `listing-${listingId}`;

        const title = item.title || item.name || "Untitled Listing";
        const numericPrice = toNumericPrice(item.price);
        const price = formatPrice(item.price);
        const storefrontName = item.storefront?.brand_name || options.storefrontName || "Storefront";
        const [images, sizeOptions] = await Promise.all([
            getListingImages(listingId, item),
            getListingSizeOptions(listingId, item)
        ]);
        const primaryImageUrl = images[0] || item.image_url || PLACEHOLDER_IMAGE;
        const isWishlisted = wishlistIds.has(String(listingId));
        const hasSizes = sizeOptions.length > 0;
        const isOneSizeItem = hasSizes && sizeOptions.length === 1 && sizeOptions[0] === "One Size";
        const isMadeToOrder = Boolean(item.is_made_to_order);
        const maxQuantity = isMadeToOrder ? 999 : (item.quantity_on_hand || 1);
        const isSoldOut = !isMadeToOrder && (item.status === "SOLD_OUT" || item.quantity_on_hand === 0);

        // Title, price, badges
        const info = el("div", "listing-info");
        const copy = el("div", "listing-copy");
        copy.appendChild(el("span", "item-name", title));
        copy.appendChild(el("span", "item-price", price));
        if (options.showCategory && item.category && item.category.name) {
            copy.appendChild(el("span", "listing-category-label", item.category.name));
        }
        if (isMadeToOrder) {
            const badge = el("span", "made-to-order-badge", "Made to Order");
            badge.setAttribute("style", MADE_TO_ORDER_STYLE);
            copy.appendChild(badge);
        }

        const actions = el("div", "listing-actions");
        const wishlistBtn = el("button", `wishlist-lock-btn ${isWishlisted ? "active" : ""}`);
        wishlistBtn.type = "button";
        wishlistBtn.setAttribute("aria-label", isWishlisted ? "Remove from wishlist" : "Add to wishlist");
        wishlistBtn.setAttribute("title", isWishlisted ? "Remove from wishlist" : "Add to wishlist");
        wishlistBtn.innerHTML = WISHLIST_ICON_SVG;
        actions.appendChild(wishlistBtn);
        info.append(copy, actions);
        card.appendChild(info);

        if (item.description) {
            card.appendChild(el("p", "listing-description", item.description));
        }

        // Size / count / add to cart
        const panel = el("div", "purchase-panel");
        const fields = el("div", "purchase-fields");
        buildSizeField(listingId, sizeOptions, isOneSizeItem).forEach((node) => fields.appendChild(node));
        const countLabel = el("label", "field-label", "Count");
        countLabel.htmlFor = `countInput-${listingId}`;
        const countInput = el("input", "count-input");
        countInput.id = `countInput-${listingId}`;
        countInput.type = "number";
        countInput.min = "1";
        countInput.max = String(maxQuantity);
        countInput.step = "1";
        countInput.value = "1";
        countInput.setAttribute("inputmode", "numeric");
        fields.append(countLabel, countInput);
        panel.appendChild(fields);

        let addToCartBtn = null;
        if (isSoldOut) {
            const soldOut = el("span", "sold-out-label", "Sold Out");
            soldOut.setAttribute("style", SOLD_OUT_STYLE);
            panel.appendChild(soldOut);
        } else {
            addToCartBtn = el("button", "add-to-cart-btn", "Add to Cart");
            addToCartBtn.type = "button";
            addToCartBtn.disabled = !hasSizes;
            panel.appendChild(addToCartBtn);
        }
        card.appendChild(panel);

        if (showStorefront) {
            const storefrontId = Number(item.storefront?.id || item.storefront_id);
            const viewLink = el("a", "view-in-storefront-link", "View in storefront");
            viewLink.href = `/storefronts/${storefrontId}?listing=${listingId}`;
            card.appendChild(viewLink);
        }

        const carousel = createListingImageCarousel(images, title, () => trackDetailView(listingId, currentUserId));
        card.prepend(carousel.shell);
        if (showStorefront) {
            card.prepend(buildStorefrontRow(item));
        }

        wishlistBtn.addEventListener("click", async () => {
            if (!currentUserId) {
                alert("Please log in to add items to your wishlist.");
                window.location.href = "/auth/login";
                return;
            }

            wishlistBtn.disabled = true;
            const isActive = wishlistBtn.classList.contains("active");

            try {
                const response = await fetch(isActive ? `/api/wishlist/${listingId}` : "/api/wishlist", {
                    method: isActive ? "DELETE" : "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-User-Id": String(currentUserId)
                    },
                    body: isActive ? undefined : JSON.stringify({ listing_id: listingId })
                });

                const result = await response.json().catch(() => ({}));
                if (!response.ok && !(response.status === 400 && /already in wishlist/i.test(result.error || ""))) {
                    throw new Error(result.error || "Unable to update wishlist.");
                }

                const nextState = !isActive;
                wishlistBtn.classList.toggle("active", nextState);
                wishlistBtn.setAttribute("aria-label", nextState ? "Remove from wishlist" : "Add to wishlist");
                wishlistBtn.setAttribute("title", nextState ? "Remove from wishlist" : "Add to wishlist");

                if (nextState) {
                    wishlistIds.add(String(listingId));
                    addLocalWishlistItem({
                        listing_id: listingId,
                        title,
                        price,
                        image_url: primaryImageUrl,
                        storefront_name: storefrontName
                    });
                } else {
                    wishlistIds.delete(String(listingId));
                    removeLocalWishlistItem(listingId);
                }
            } catch (error) {
                console.error("Wishlist update failed:", error);
                alert(error.message || "Unable to update wishlist right now.");
            } finally {
                wishlistBtn.disabled = false;
            }
        });

        const sizeSelect = card.querySelector(".size-select");

        if (addToCartBtn) {
            addToCartBtn.addEventListener("click", async () => {
                if (!currentUserId) {
                    alert("Please log in to add items to your cart.");
                    window.location.href = "/auth/login";
                    return;
                }

                const selectedSize = isOneSizeItem ? "One Size" : (sizeSelect ? sizeSelect.value : "");
                const selectedCount = Number.parseInt(countInput.value, 10);
                const effectiveMax = isMadeToOrder ? Number.POSITIVE_INFINITY : (item.quantity_on_hand || 1);

                if (!selectedSize) {
                    showToast("Please select a size.", "error");
                    return;
                }

                if (!Number.isInteger(selectedCount) || selectedCount < 1) {
                    showToast("Count must be at least 1.", "error");
                    countInput.value = "1";
                    return;
                }

                if (!isMadeToOrder && selectedCount > effectiveMax) {
                    showToast(`Maximum available quantity is ${effectiveMax}.`, "error");
                    countInput.value = String(effectiveMax);
                    return;
                }

                addToCartBtn.disabled = true;

                try {
                    const formData = new FormData();
                    formData.append("item_id", String(listingId));
                    formData.append("item_name", title);
                    formData.append("price", String(numericPrice));
                    formData.append("quantity", String(selectedCount));
                    formData.append("size", selectedSize);

                    const response = await fetch("/auth/add_to_cart", {
                        method: "POST",
                        body: formData,
                        redirect: "follow"
                    });

                    if (!response.ok) {
                        let errorMsg = "Unable to add item to cart right now.";
                        try {
                            const errData = await response.json();
                            if (errData && errData.error) errorMsg = errData.error;
                        } catch (_) {}
                        throw new Error(errorMsg);
                    }

                    showToast(`${title} (${selectedSize}) x${selectedCount} added to cart.`);
                } catch (error) {
                    console.error("Add to cart failed:", error);
                    showToast(error.message || "Unable to add to cart.", "error");
                } finally {
                    addToCartBtn.disabled = false;
                }
            });
        }

        return card;
    }

    window.VaultListingCard = {
        create,
        getCurrentSessionUser,
        getWishlistIdSet,
        trackDetailView,
        showToast,
        escapeHtml,
        formatPrice,
        PLACEHOLDER_IMAGE
    };
})();
