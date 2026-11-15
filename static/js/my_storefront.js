/*
    my_storefront.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by Day Ekoi - Iteration 4 - 3/22/2026
    Implemented & Updated by Day Ekoi - Iteration 5 - 4/9/2026
    Updated by Day Ekoi - Iteration 5 - 4/20/26 - added deactivate storefront button handler
    Updated by Day Ekoi - Iteration 5 - 4/20/26 - guarded optional dashboard buttons after layout cleanup
    Updated by Miles Walker - 11/14/26 - added ability to view deleted listings, to either restore or delete them permanently
    Updated by James Williams - 10/26/26 - listings show their category, plus a banner for listings in "Other"
    Updated by James Williams - 10/26/26 - redesign with a listings table and quick buttons, and small pop-up
    messages instead of alerts. The requests didn't change.

Description:
This is the seller dashboard. It shows your storefront and your listings, with buttons to
edit, hide, delete and add listings, and to edit, view or deactivate the storefront.
*/

(function () {
    const listingGrid = document.getElementById("listingGrid");
    const deletedSection = document.getElementById("deletedSection"); // Miles Walker 11/14/26
    const deletedGrid = document.getElementById("deletedGrid");       // Miles Walker 11/14/26
    const OTHER_CATEGORY_SLUG = "other";
    const STATUS_LABELS = { ACTIVE: "Active", SOLD_OUT: "Sold out", INACTIVE: "Hidden" };
    let currentUser = null;

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function authHeaders() {
        return { "X-User-Id": currentUser?.id || "", "X-User-Role": currentUser?.role || "user" };
    }

    function categoryLabel(item) {
        const category = item.category;
        if (!category || !category.name) return "Other";
        return category.parent_name ? `${category.parent_name} › ${category.name}` : category.name;
    }

    function isInOtherCategory(item) {
        return !item.category || item.category.slug === OTHER_CATEGORY_SLUG;
    }

    // Listings in "Other" are hard to find on the category pages, so this shows the seller a reminder
    function renderCategoryReminder(listings) {
        let banner = document.getElementById("categoryReminderBanner");
        const inOther = listings.filter(isInOtherCategory);
        if (!inOther.length) {
            if (banner) banner.remove();
            return;
        }
        if (!banner) {
            banner = el("div", "pm-notice");
            banner.id = "categoryReminderBanner";
            banner.setAttribute("role", "status");
            listingGrid.before(banner);
        }
        const count = inOther.length;
        const link = el("a", null, "Choose a category");
        link.href = `/listings/${inOther[0].id}/edit`;
        banner.replaceChildren(
            `${count} ${count === 1 ? "listing is" : "listings are"} in Other. Choose a specific category so buyers can find ${count === 1 ? "it" : "them"} in All categories. `,
            link
        );
    }

    function showMessage(title, body, action) {
        const box = el("div", "pm-empty");
        box.append(el("h2", null, title), el("p", null, body));
        if (action) box.appendChild(action);
        listingGrid.setAttribute("aria-busy", "false");
        listingGrid.replaceChildren(box);
    }

    function linkButton(label, href, kind) {
        const link = el("a", `pm-btn pm-btn--${kind}`, label);
        link.href = href;
        return link;
    }

    async function listingAction(item, path, method, failMessage, doneMessage) {
        try {
            const response = await fetch(path, { method, headers: authHeaders() });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(result.error || failMessage);
            VaultListingCard.showToast(doneMessage);
            await loadMyStorefront();
        } catch (error) {
            VaultListingCard.showToast(error.message || failMessage, "error");
        }
    }

    function createListingRow(item) {
        const status = item.status || "ACTIVE";
        const title = item.title || "Untitled";
        const row = el("div", "pm-listing-row");

        const photo = el("div", "pm-listing-row__photo");
        const img = el("img");
        img.alt = "";
        img.src = item.image_url || VaultListingCard.PLACEHOLDER_IMAGE;
        img.addEventListener("error", () => { img.src = VaultListingCard.PLACEHOLDER_IMAGE; }, { once: true });
        photo.appendChild(img);

        const main = el("div", "pm-listing-row__main");
        const name = el("a", "pm-listing-row__title", title);
        name.href = `/listings/${item.id}`;
        main.append(name, el("span", "pm-muted", categoryLabel(item)));

        const price = el("span", "pm-price", `$${Number(item.price || 0).toFixed(2)}`);
        const stock = el("span", "pm-muted", item.is_made_to_order ? "Made to order" : `${Number(item.quantity_on_hand) || 0} in stock`);
        const chip = el("span", `pm-status pm-status--${status.toLowerCase()}`, STATUS_LABELS[status] || status);

        const actions = el("div", "pm-listing-row__actions");
        actions.appendChild(linkButton("Edit", `/listings/${item.id}/edit`, "ghost"));
        const hidden = status === "INACTIVE";
        const toggle = el("button", "pm-btn pm-btn--ghost", hidden ? "Show" : "Hide");
        toggle.type = "button";
        toggle.setAttribute("aria-label", `${hidden ? "Show" : "Hide"} ${title}`);
        toggle.addEventListener("click", () => listingAction(
            item, `/api/listings/${item.id}/${hidden ? "reactivate" : "deactivate"}`, "PATCH",
            `Couldn't ${hidden ? "show" : "hide"} the listing.`, hidden ? "Listing is visible again" : "Listing hidden from shoppers"
        ));
        const remove = el("button", "pm-btn pm-btn--ghost pm-listing-row__delete", "Delete");
        remove.type = "button";
        remove.setAttribute("aria-label", `Delete ${title}`);
        remove.addEventListener("click", () => {
            if (!window.confirm(`Delete "${title}"? Shoppers won't see it anymore.`)) return;
            listingAction(item, `/api/listings/${item.id}`, "DELETE", "Couldn't delete the listing.", "Listing deleted");
        });
        actions.append(toggle, remove);

        row.append(photo, main, price, stock, chip, actions);
        return row;
    }

    // Miles Walker 11/14/26 - one row in the Recently Deleted section
    function createDeletedRow(item) {
        const title = item.title || "Untitled";
        const row = el("div", "pm-deleted-row");

        const info = el("div", "pm-listing-row__main");
        info.append(
            el("span", "pm-listing-row__title", title),
            el("span", "pm-muted", `$${Number(item.price || 0).toFixed(2)}`)
        );

        const restore = el("button", "pm-btn pm-btn--ghost", "Restore");
        restore.type = "button";
        restore.setAttribute("aria-label", `Restore ${title}`);
        restore.addEventListener("click", () => listingAction(
            item, `/api/listings/${item.id}/restore`, "PATCH",
            "Couldn't restore the listing.", "Listing restored"
        ));

        const forever = el("button", "pm-btn pm-btn--ghost pm-listing-row__delete", "Delete forever");
        forever.type = "button";
        forever.setAttribute("aria-label", `Permanently delete ${title}`);
        forever.addEventListener("click", () => {
            if (!window.confirm(`Permanently delete "${title}"? This action cannot be undone.`)) return;
            listingAction(
                item, `/api/listings/${item.id}/permanent`, "DELETE",
                "Couldn't delete the listing.", "Listing permanently deleted"
            );
        });

        const actions = el("div", "pm-listing-row__actions");
        actions.append(restore, forever);
        row.append(info, actions);
        return row;
    }

    // Miles Walker 11/14/26 - show or hide the Recently Deleted section
    function renderDeletedSection(deletedListings) {
        if (!deletedSection || !deletedGrid) return;
        deletedGrid.replaceChildren(...deletedListings.map(createDeletedRow));
        deletedSection.hidden = deletedListings.length === 0;
    }

    function fillHeader(storefront, listings) {
        const name = storefront.brand_name || "My storefront";
        document.getElementById("pageTitle").textContent = name;
        const live = listings.filter((item) => item.status === "ACTIVE" || item.status === "SOLD_OUT").length;
        document.getElementById("storeMeta").textContent =
            `${listings.length} listing${listings.length === 1 ? "" : "s"}, ${live} visible to shoppers`;

        const medallion = document.getElementById("logoCircle");
        medallion.textContent = (name.trim()[0] || "?").toUpperCase();
        if (storefront.logo_url) {
            const logo = el("img");
            logo.alt = "";
            logo.addEventListener("load", () => medallion.replaceChildren(logo), { once: true });
            logo.src = storefront.logo_url;
        }

        const cover = document.getElementById("bannerBox");
        const photos = storefront.banner_url ? [storefront.banner_url] : listings.map((item) => item.image_url).filter(Boolean).slice(0, 3);
        cover.dataset.count = storefront.banner_url ? "banner" : String(photos.length);
        cover.replaceChildren(...photos.map((url) => {
            const img = el("img");
            img.src = url;
            img.alt = "";
            img.addEventListener("error", () => VaultListingCard.dropCoverPhoto(img), { once: true });
            return img;
        }));

        const isActive = storefront.is_active !== false;
        document.getElementById("storefrontStatusBanner").hidden = isActive;
        document.getElementById("editStorefrontBtn").href = `/storefronts/${storefront.id}/edit`;
        const view = document.getElementById("viewStorefrontBtn");
        view.href = `/storefronts/${storefront.id}`;
        view.hidden = !isActive;
        document.getElementById("createListingBtn").hidden = !isActive;
        document.getElementById("storeActions").hidden = false;
        document.getElementById("storeSettings").hidden = !isActive;

        document.getElementById("deactivateStorefrontBtn").onclick = async () => {
            if (!window.confirm("Deactivate your storefront? It and its listings will be hidden from shoppers.")) return;
            try {
                const res = await fetch(`/api/storefronts/${storefront.id}/deactivate`, { method: "PATCH", headers: authHeaders() });
                const result = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(result.error || "Couldn't deactivate the storefront.");
                VaultListingCard.showToast("Storefront deactivated");
                await loadMyStorefront();
            } catch (error) {
                VaultListingCard.showToast(error.message, "error");
            }
        };
    }

    async function loadMyStorefront() {
        try {
            const userRes = await fetch("/auth/api/auth/me");
            if (!userRes.ok) {
                window.location.href = "/auth/login";
                return;
            }
            currentUser = await userRes.json();

            const sfRes = await fetch("/api/storefronts/me", { headers: authHeaders() });
            if (!sfRes.ok) {
                document.getElementById("pageTitle").textContent = "My storefront";
                document.getElementById("bannerBox").hidden = true;
                document.querySelector(".pm-store__head").hidden = true;
                document.getElementById("listingsHeading").parentNode.hidden = true;
                renderDeletedSection([]);
                showMessage("You don't have a storefront yet", "Open one to start selling on campus.",
                    linkButton("Create your storefront", "/storefronts/create", "primary"));
                return;
            }
            const storefront = await sfRes.json();

            /* Added by Miles Walker 11/14/26 - Splits the list of listings into two: normal listings stay
            in the main grid and deleted ones are added to the RecentlyDeleted section*/
            const listRes = await fetch("/api/listings/my?include_deleted=1", { headers: authHeaders() });
            const allListings = listRes.ok ? await listRes.json() : [];
            const everything = Array.isArray(allListings) ? allListings : [];
            const listings = everything.filter((item) => item.status !== "DELETED");
            const deletedListings = everything.filter((item) => item.status === "DELETED");

            fillHeader(storefront, listings);
            renderDeletedSection(deletedListings);
            if (!listRes.ok) {
                showMessage("Couldn't load your listings", "Refresh the page to try again.");
                return;
            }

            renderCategoryReminder(listings);
            document.getElementById("listingCount").textContent = listings.length ? `${listings.length} total` : "";
            if (!listings.length) {
                showMessage("Add your first listing", "Photos, a price and sizes take about a minute.",
                    linkButton("Add listing", "/listings/create", "primary"));
                return;
            }
            listingGrid.setAttribute("aria-busy", "false");
            listingGrid.replaceChildren(...listings.map(createListingRow));
        } catch (error) {
            console.error("Error loading my storefront:", error);
            showMessage("Couldn't load your storefront", "Check your connection and refresh the page.");
        }
    }

    loadMyStorefront();
})();
