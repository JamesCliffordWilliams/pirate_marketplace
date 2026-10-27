/*
    account.js

    Pirate Market
    Created by James Williams - 10/26/26 (moved out of account.html, original by Madison Boyd 3/23/2026)
    This is the account page. It shows your past orders and the items you saved.
    Everything is added as plain text, never as HTML.
*/

(function () {
    const el = (tag, className, text) => {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    };

    const sentenceCase = (text) => text ? text.charAt(0) + text.slice(1).toLowerCase().replace(/_/g, " ") : "";

    // ---------- tabs, the arrow keys switch between them ----------
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
    const loaded = new Set();

    function selectTab(tab) {
        tabs.forEach((other) => {
            const selected = other === tab;
            other.setAttribute("aria-selected", String(selected));
            other.tabIndex = selected ? 0 : -1;
            document.getElementById(other.getAttribute("aria-controls")).hidden = !selected;
        });
        const panel = tab.getAttribute("aria-controls");
        if (!loaded.has(panel)) {
            loaded.add(panel);
            (panel === "wishlist" ? loadSaved : loadPurchases)();
        }
    }

    tabs.forEach((tab, index) => {
        tab.addEventListener("click", () => selectTab(tab));
        tab.addEventListener("keydown", (event) => {
            if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
            const next = tabs[(index + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
            next.focus();
            selectTab(next);
        });
    });

    // ---------- purchases ----------
    async function loadPurchases() {
        const status = document.getElementById("purchasesEmptyState");
        const container = document.getElementById("purchasesContainer");
        try {
            const res = await fetch("/api/orders/my");
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Failed to load orders");
            const orders = Array.isArray(data.orders) ? data.orders : [];
            if (!orders.length) {
                status.replaceChildren("No orders yet. ");
                const browse = el("a", null, "Browse storefronts");
                browse.href = "/storefronts";
                status.appendChild(browse);
                return;
            }
            status.hidden = true;
            container.replaceChildren(...orders.map((order) => {
                const link = el("a", "pm-order");
                link.href = `/order-confirmation?conf=${encodeURIComponent(order.confirmation_number)}`;
                const date = order.created_at
                    ? new Date(order.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })
                    : "";
                const info = el("span", "pm-order__info");
                info.append(el("span", "pm-order__number", order.confirmation_number),
                    el("span", "pm-muted", [date, sentenceCase(order.order_status)].filter(Boolean).join(", ")));
                link.append(info, el("span", "pm-price", `$${parseFloat(order.total_amount || 0).toFixed(2)}`));
                return link;
            }));
        } catch (error) {
            console.error("Error loading purchases:", error);
            status.textContent = "Your orders didn't load. Refresh the page to try again.";
        }
    }

    // ---------- saved items ----------
    async function loadSaved() {
        const status = document.getElementById("wishlistEmptyState");
        const container = document.getElementById("wishlistItemsContainer");
        const user = await VaultListingCard.getCurrentSessionUser();
        const userId = user ? user.id : null;
        try {
            const res = await fetch("/api/wishlist", { headers: { "X-User-Id": String(userId || "") } });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Failed to load wishlist");
            const items = Array.isArray(data.wishlist) ? data.wishlist : [];
            if (!items.length) {
                status.textContent = "Nothing saved yet. Tap the heart on any product to keep it here.";
                return;
            }
            status.hidden = true;
            const wishlistIds = new Set(items.map((item) => String(item.listing_id || item.id)));
            const tiles = await Promise.all(items.map((item) => VaultListingCard.create({
                ...item,
                id: item.listing_id || item.id,
                storefront: { brand_name: item.storefront_name || item.storefront?.brand_name || "" }
            }, { wishlistIds, currentUserId: userId })));
            container.replaceChildren(...tiles);
        } catch (error) {
            console.error("Error loading saved items:", error);
            status.textContent = "Your saved items didn't load. Refresh the page to try again.";
        }
    }

    selectTab(tabs[0]);
})();
