/*
    category_listings.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by James Williams - 10/26/26

Description:
Loads the products for a category page and shows them as cards.
Sort and page are saved in the URL, so Back/Forward and shared links work.
Shows loading, empty, and error states.

Works with:
- category_listings.html
- listing_card.js
*/

(function () {
    const root = document.getElementById("categoryListingsPage");
    if (!root) return;

    const PER_PAGE = 24;
    const SKELETON_COUNT = 8;
    const SORTS = ["newest", "price_asc", "price_desc"];

    const slug = root.dataset.slug;
    const categoryName = root.dataset.categoryName || "this category";
    const parentName = root.dataset.parentName || "";
    const parentUrl = root.dataset.parentUrl || "/categories";
    const isSub = root.dataset.isSub === "true";
    const showCategory = root.dataset.showCategory === "true";
    const isLoggedIn = root.dataset.loggedIn === "true";

    const grid = document.getElementById("categoryGrid");
    const toolbar = root.querySelector(".cat-toolbar");
    const resultsCount = document.getElementById("resultsCount");
    const sortSelect = document.getElementById("sortSelect");
    const pagination = document.getElementById("categoryPagination");
    const prevBtn = document.getElementById("prevPageBtn");
    const nextBtn = document.getElementById("nextPageBtn");
    const pageIndicator = document.getElementById("pageIndicator");

    let currentState = readState();
    let lastPagination = null;
    let requestToken = 0;
    let viewerPromise = null;

    // ________________________________________________________
    // URL STATE
    // ________________________________________________________

    function readState() {
        const params = new URLSearchParams(window.location.search);
        const sort = SORTS.includes(params.get("sort")) ? params.get("sort") : "newest";
        const page = Number.parseInt(params.get("page"), 10);
        return { sort, page: Number.isInteger(page) && page >= 1 ? page : 1 };
    }

    function urlFor(state) {
        const params = new URLSearchParams(window.location.search);
        params.delete("sort");
        params.delete("page");
        if (state.sort !== "newest") params.set("sort", state.sort);
        if (state.page > 1) params.set("page", String(state.page));
        const query = params.toString();
        return window.location.pathname + (query ? `?${query}` : "");
    }

    function pushState(state) {
        currentState = state;
        window.history.pushState(state, "", urlFor(state));
    }

    // Keep the current sort when clicking a subcategory or the breadcrumb
    function syncSortLinks(sort) {
        root.querySelectorAll(".cat-chip, .cat-breadcrumb a").forEach((link) => {
            const url = new URL(link.getAttribute("href"), window.location.origin);
            if (url.pathname === "/categories") return;
            url.searchParams.delete("page");
            if (sort === "newest") {
                url.searchParams.delete("sort");
            } else {
                url.searchParams.set("sort", sort);
            }
            link.setAttribute("href", url.pathname + url.search);
        });
    }

    // ________________________________________________________
    // CURRENT USER (for wishlist and cart)
    // ________________________________________________________

    function getViewer() {
        if (!viewerPromise) {
            viewerPromise = (async () => {
                let userId = Number(root.dataset.userId) || null;
                if (!userId && isLoggedIn) {
                    const user = await VaultListingCard.getCurrentSessionUser();
                    userId = user?.id || null;
                }
                const wishlistIds = await VaultListingCard.getWishlistIdSet(userId);
                return { userId, wishlistIds };
            })();
        }
        return viewerPromise;
    }

    // ________________________________________________________
    // RENDERING
    // ________________________________________________________

    function renderSkeletons() {
        const nodes = [];
        for (let i = 0; i < SKELETON_COUNT; i += 1) {
            const card = document.createElement("div");
            card.className = "cat-skeleton-card";
            card.setAttribute("aria-hidden", "true");
            ["image", "line", "short", "button"].forEach((part) => {
                const block = document.createElement("div");
                block.className = `cat-skeleton-block cat-skeleton-block--${part}`;
                card.appendChild(block);
            });
            nodes.push(card);
        }
        grid.replaceChildren(...nodes);
    }

    function renderMessage(title, actions) {
        const box = document.createElement("div");
        box.className = "cat-state-message";

        const heading = document.createElement("p");
        heading.className = "cat-state-title";
        heading.textContent = title;
        box.appendChild(heading);

        if (actions.length) {
            const row = document.createElement("div");
            row.className = "cat-state-actions";
            actions.forEach((action) => row.appendChild(action));
            box.appendChild(row);
        }

        grid.replaceChildren(box);
    }

    function linkAction(label, href, onClick) {
        const link = document.createElement("a");
        link.href = href;
        link.textContent = label;
        if (onClick) {
            link.addEventListener("click", (event) => {
                event.preventDefault();
                onClick();
            });
        }
        return link;
    }

    function buttonAction(label, onClick) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.addEventListener("click", onClick);
        return button;
    }

    function setResultsCount(total) {
        resultsCount.textContent = `${total} ${total === 1 ? "item" : "items"}`;
    }

    function renderPagination(info) {
        lastPagination = info;
        if (!info || info.total_pages <= 1) {
            pagination.hidden = true;
            return;
        }
        pagination.hidden = false;
        pageIndicator.textContent = `Page ${info.page} of ${info.total_pages}`;
        prevBtn.disabled = info.page <= 1;
        nextBtn.disabled = info.page >= info.total_pages;
    }

    function scrollToGridTop() {
        const target = toolbar || grid;
        const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        target.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" });
    }

    function goToPage(page, options = {}) {
        const state = { sort: currentState.sort, page };
        pushState(state);
        load(state, { scroll: options.scroll !== false });
    }

    function renderEmpty() {
        const actions = [];
        if (isSub) {
            actions.push(linkAction(`Browse all ${parentName}`, parentUrl));
        }
        actions.push(linkAction("Explore storefronts", "/storefronts"));
        renderMessage(`No items in ${categoryName} yet.`, actions);
    }

    function renderPastEnd() {
        renderMessage("No more items.", [
            linkAction("Back to page 1", urlFor({ sort: currentState.sort, page: 1 }), () => goToPage(1))
        ]);
    }

    function renderError() {
        renderMessage("Couldn't load items.", [
            buttonAction("Retry", () => load(currentState, { scroll: false }))
        ]);
    }

    // ________________________________________________________
    // LOAD
    // ________________________________________________________

    async function load(state, options = {}) {
        const token = ++requestToken;
        grid.setAttribute("aria-busy", "true");
        renderSkeletons();
        if (options.scroll) scrollToGridTop();

        try {
            const params = new URLSearchParams({
                sort: state.sort,
                page: String(state.page),
                per_page: String(PER_PAGE)
            });
            const [response, viewer] = await Promise.all([
                fetch(`/api/categories/${encodeURIComponent(slug)}/listings?${params.toString()}`),
                getViewer()
            ]);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            if (token !== requestToken) return;

            const listings = Array.isArray(data.listings) ? data.listings : [];
            const info = data.pagination || { page: state.page, total: 0, total_pages: 0 };
            setResultsCount(info.total || 0);

            if (!listings.length) {
                renderPagination(null);
                if (info.total > 0) {
                    renderPastEnd();
                } else {
                    renderEmpty();
                }
                return;
            }

            const cards = await Promise.all(listings.map((item) => VaultListingCard.create(item, {
                wishlistIds: viewer.wishlistIds,
                currentUserId: viewer.userId,
                showStorefront: true,
                showCategory
            })));
            if (token !== requestToken) return;

            grid.replaceChildren(...cards);
            renderPagination(info);
        } catch (error) {
            if (token !== requestToken) return;
            console.error("Error loading category listings:", error);
            renderPagination(null);
            renderError();
        } finally {
            if (token === requestToken) {
                grid.setAttribute("aria-busy", "false");
            }
        }
    }

    // ________________________________________________________
    // EVENTS
    // ________________________________________________________

    sortSelect.addEventListener("change", () => {
        const sort = SORTS.includes(sortSelect.value) ? sortSelect.value : "newest";
        const state = { sort, page: 1 };
        pushState(state);
        syncSortLinks(sort);
        load(state, { scroll: false });
    });

    prevBtn.addEventListener("click", () => {
        if (lastPagination && lastPagination.page > 1) goToPage(lastPagination.page - 1);
    });

    nextBtn.addEventListener("click", () => {
        if (lastPagination && lastPagination.page < lastPagination.total_pages) goToPage(lastPagination.page + 1);
    });

    window.addEventListener("popstate", () => {
        currentState = readState();
        sortSelect.value = currentState.sort;
        syncSortLinks(currentState.sort);
        load(currentState, { scroll: false });
    });

    // initial render
    sortSelect.value = currentState.sort;
    syncSortLinks(currentState.sort);
    window.history.replaceState(currentState, "", window.location.href);
    load(currentState, { scroll: false });
})();
