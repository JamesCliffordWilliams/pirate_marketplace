/*
    hot.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by James Williams - 10/26/26

Description:
Loads the Hot page with one request and shows Hot Right Now and Rising
as product cards. Shows loading, empty, and error states.

Works with:
- hot.html, hot.css
- listing_card.js
*/

(function () {
    const SECTION_KEYS = ["hot", "rising"];
    const SKELETON_COUNT = 4;

    // ________________________________________________________
    // SECTION STATES
    // ________________________________________________________

    // Hot and Rising collapse to one quiet line when empty
    function sectionStates(data) {
        const counts = {};
        SECTION_KEYS.forEach((key) => {
            counts[key] = data && Array.isArray(data[key]) ? data[key].length : 0;
        });

        if (counts.hot + counts.rising === 0) {
            return { page: "empty", hot: "hidden", rising: "hidden" };
        }
        return {
            page: "content",
            hot: counts.hot ? "cards" : "collapsed",
            rising: counts.rising ? "cards" : "collapsed"
        };
    }

    window.VaultHot = { _internals: { sectionStates } };

    const root = document.getElementById("hotPage");
    if (!root) return;

    const pageState = document.getElementById("hotPageState");
    const sections = {
        hot: { section: document.getElementById("hotSection"), grid: document.getElementById("hotGrid") },
        rising: { section: document.getElementById("risingSection"), grid: document.getElementById("risingGrid") }
    };
    const isLoggedIn = root.dataset.loggedIn === "true";

    let viewerPromise = null;
    let requestToken = 0;

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

    function skeletonCards() {
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
        return nodes;
    }

    function setSectionState(key, state, cards) {
        const { section, grid } = sections[key];
        const quiet = section.querySelector(".hot-section-quiet");

        section.hidden = state === "hidden";
        section.classList.toggle("is-collapsed", state === "collapsed");
        if (quiet) quiet.hidden = state !== "collapsed";
        grid.hidden = state !== "cards" && state !== "loading";
        grid.setAttribute("aria-busy", state === "loading" ? "true" : "false");
        grid.replaceChildren(...(cards || []));
    }

    function showLoading() {
        pageState.hidden = true;
        pageState.replaceChildren();
        setSectionState("hot", "loading", skeletonCards());
        setSectionState("rising", "loading", skeletonCards());
    }

    function showPageMessage(title, actions) {
        SECTION_KEYS.forEach((key) => setSectionState(key, "hidden"));

        const box = document.createElement("div");
        box.className = "cat-state-message";

        const heading = document.createElement("p");
        heading.className = "cat-state-title";
        heading.textContent = title;
        box.appendChild(heading);

        const row = document.createElement("div");
        row.className = "cat-state-actions";
        actions.forEach((action) => row.appendChild(action));
        box.appendChild(row);

        pageState.replaceChildren(box);
        pageState.hidden = false;
    }

    function linkAction(label, href) {
        const link = document.createElement("a");
        link.href = href;
        link.textContent = label;
        return link;
    }

    function showEmpty() {
        showPageMessage("Nothing's trending yet.", [
            linkAction("All categories", "/categories"),
            linkAction("Storefronts", "/storefronts")
        ]);
    }

    function showError() {
        const retry = document.createElement("button");
        retry.type = "button";
        retry.textContent = "Retry";
        retry.addEventListener("click", () => load());
        showPageMessage("Couldn't load what's hot.", [retry]);
    }

    function buildCards(items, viewer) {
        return Promise.all(items.map((item) => VaultListingCard.create(item, {
            wishlistIds: viewer.wishlistIds,
            currentUserId: viewer.userId,
            showStorefront: true,
            showCategory: true
        })));
    }

    // ________________________________________________________
    // LOAD (one request fills every section)
    // ________________________________________________________

    async function load() {
        const token = ++requestToken;
        showLoading();

        try {
            // no-cache: never show a listing that sold out since the browser last asked
            const [response, viewer] = await Promise.all([fetch("/api/hot", { cache: "no-cache" }), getViewer()]);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();
            if (token !== requestToken) return;

            const states = sectionStates(data);
            if (states.page === "empty") {
                showEmpty();
                return;
            }

            const built = await Promise.all(SECTION_KEYS.map((key) => (
                states[key] === "cards" ? buildCards(data[key], viewer) : Promise.resolve([])
            )));
            if (token !== requestToken) return;

            SECTION_KEYS.forEach((key, index) => setSectionState(key, states[key], built[index]));
        } catch (error) {
            if (token !== requestToken) return;
            console.error("Error loading the Hot page:", error);
            showError();
        }
    }

    load();
})();
