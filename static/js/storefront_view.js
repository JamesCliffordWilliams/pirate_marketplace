/*
    storefront_view.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by Day Ekoi - Iteration 4
    3/22/2026
    Updated by Day Ekoi - Iteration 5 4/9/26
    Updated by Day Ekoi - Iteration 5 - 4/20/26 - fixed wishlistIds undefined crash and isWishlisted undefined in createListingCard
    Updated by Day E - April 22nd - multi-image listing display, lightbox preview, and contain-based image handling
    Updated by James Williams - 10/26/26 - card code moved to listing_card.js; added ?listing= scroll and highlight
    Updated by James Williams - 10/26/26 - redesign: cover (banner, else the store's product photos),
    medallion, sortable product tiles; old ?listing= links open the product page

Description:
The public storefront page. Loads the storefront and its listings from the API.
All store text is set with textContent.
*/

(function () {
    const page = document.getElementById("storefrontPage");
    if (!page) return;

    const storefrontId = Number(page.dataset.storefrontId);
    const userId = Number(page.dataset.userId) || null;
    const grid = document.getElementById("listingGrid");
    const sortSelect = document.getElementById("listingSort");
    let listings = [];
    let viewer = { wishlistIds: new Set(), currentUserId: userId };

    // Links from before the product page existed pointed here with ?listing=<id>
    const linkedId = new URLSearchParams(window.location.search).get("listing");
    if (linkedId && /^\d+$/.test(linkedId)) {
        window.location.replace(`/listings/${linkedId}`);
        return;
    }

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function showMessage(title, body) {
        const box = el("div", "pm-empty");
        box.append(el("h2", null, title), el("p", null, body));
        grid.setAttribute("aria-busy", "false");
        grid.replaceChildren(box);
    }

    function fillCover(storefront) {
        const cover = document.getElementById("storeCover");
        const photos = storefront.banner_url
            ? [storefront.banner_url]
            : listings.map((item) => item.image_url).filter(Boolean).slice(0, 3);
        cover.dataset.count = storefront.banner_url ? "banner" : String(photos.length);
        photos.forEach((url) => {
            const img = el("img");
            img.src = url;
            img.alt = "";
            img.addEventListener("error", () => img.remove(), { once: true });
            cover.appendChild(img);
        });
    }

    function fillHead(storefront) {
        const name = storefront.brand_name || "Unnamed storefront";
        document.title = `${name} | Pirate Market`;
        document.getElementById("pageTitle").textContent = name;
        const count = listings.length;
        document.getElementById("storeMeta").textContent = count ? `${count} item${count === 1 ? "" : "s"}` : "No items yet";
        document.getElementById("storeDescription").textContent = storefront.bio || "";
        document.getElementById("contactInfo").textContent = storefront.contact_info ? `Contact: ${storefront.contact_info}` : "";

        const medallion = document.getElementById("storeMedallion");
        medallion.textContent = (name.trim()[0] || "?").toUpperCase();
        if (storefront.logo_url) {
            const logo = el("img");
            logo.alt = "";
            logo.addEventListener("load", () => medallion.replaceChildren(logo), { once: true });
            logo.src = storefront.logo_url;
        }
    }

    async function renderGrid() {
        const sorted = listings.slice();
        if (sortSelect.value === "price_asc") sorted.sort((a, b) => Number(a.price) - Number(b.price));
        if (sortSelect.value === "price_desc") sorted.sort((a, b) => Number(b.price) - Number(a.price));
        const tiles = await Promise.all(sorted.map((item) => VaultListingCard.create(item, { ...viewer, showStorefront: false })));
        grid.setAttribute("aria-busy", "false");
        grid.replaceChildren(...tiles);
    }

    async function load() {
        let storefront;
        try {
            const [storeResponse, listResponse, wishlistIds] = await Promise.all([
                fetch(`/api/storefronts/${storefrontId}`),
                fetch(`/api/storefronts/${storefrontId}/listings`),
                VaultListingCard.getWishlistIdSet(userId)
            ]);
            if (!storeResponse.ok) {
                document.getElementById("pageTitle").textContent = "Storefront not found";
                showMessage("This storefront isn't available", "It may have closed. Browse the other storefronts instead.");
                return;
            }
            storefront = await storeResponse.json();
            const data = listResponse.ok ? await listResponse.json() : [];
            listings = (Array.isArray(data) ? data : []).filter((item) => item.status === "ACTIVE" || item.status === "SOLD_OUT");
            viewer = { wishlistIds, currentUserId: userId };
        } catch (error) {
            console.error("Error loading storefront:", error);
            showMessage("Couldn't load this storefront", "Check your connection and refresh the page.");
            return;
        }

        fillHead(storefront);
        fillCover(storefront);
        if (!listings.length) {
            showMessage("No products yet", "This store hasn't listed anything. Check back soon.");
            return;
        }
        renderGrid();
    }

    sortSelect.addEventListener("change", renderGrid);

    document.getElementById("shareBtn").addEventListener("click", async () => {
        const url = window.location.origin + window.location.pathname;
        try {
            if (navigator.share) {
                await navigator.share({ title: document.title, url });
            } else {
                await navigator.clipboard.writeText(url);
                VaultListingCard.showToast("Link copied");
            }
        } catch (_error) {
            // the shopper closed the share sheet
        }
    });

    load();
})();
