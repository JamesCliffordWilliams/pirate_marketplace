/*
    hot.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by James Williams - 10/26/26

Description:
This loads the Hot page with one request and shows Hot Right Now and Rising
as product cards. It also shows the loading, empty and error screens.

Works with:
- hot.html, hot.css
- listing_card.js
*/

(function () {
    const SECTION_KEYS = ["hot", "rising"];

    // ________________________________________________________
    // SECTION STATES
    // ________________________________________________________

    // If Hot or Rising is empty, it shrinks down to one short line
    function sectionStates(data) {
        const hasHot = Boolean(data && Array.isArray(data.hot) && data.hot.length);
        const hasRising = Boolean(data && Array.isArray(data.rising) && data.rising.length);
        if (!hasHot && !hasRising) {
            return { page: "empty", hot: "hidden", rising: "hidden" };
        }
        return { page: "content", hot: hasHot ? "cards" : "collapsed", rising: hasRising ? "cards" : "collapsed" };
    }

    window.VaultHot = { _internals: { sectionStates } };

    const root = document.getElementById("hotPage");
    if (!root) return;

    const pageState = document.getElementById("hotPageState");
    const sections = {
        hot: { section: document.getElementById("hotSection"), grid: document.getElementById("hotGrid") },
        rising: { section: document.getElementById("risingSection"), grid: document.getElementById("risingGrid") }
    };
    let requestToken = 0;

    // ________________________________________________________
    // RENDERING
    // ________________________________________________________

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
        setSectionState("hot", "loading", VaultListingCard.skeletonCards(4));
        setSectionState("rising", "loading", VaultListingCard.skeletonCards(4));
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
            currentUserId: viewer.userId
        })));
    }

    // ________________________________________________________
    // LOAD (one request fills every section)
    // ________________________________________________________

    async function load() {
        const token = ++requestToken;
        showLoading();

        try {
            // skips the browser cache so we don't show something that already sold out
            const [response, viewer] = await Promise.all([fetch("/api/hot", { cache: "no-cache" }), VaultListingCard.getViewer(root)]);
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
