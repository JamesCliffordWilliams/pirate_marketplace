/*
storefront.js

  The Vault Campus Marketplace
  CSC 405 Sp 26
  Created by Day Ekoi - Iteration 4
  Date: 3/18/2026 - 3/22/2026
  Updated by Day Ekoi - Iteration 5 - 4/20/26 - fetchStorefronts now maps preview_image_1-4 to card carousel; falls back to banner_url if no previews set
  Updated by Day Ekoi - Iteration 5 - 4/20/26 - removed add-to-cart form from storefront cards (size, qty, add to bag); kept version history via comments
  Updated by James Williams - 10/26/26 - storefront facades (cover: previews, then banner, then the
  store's product photos, then a monogram), sort, header search, inline pages, Hot rail

Description: the storefront directory (homepage.html). Store names and other text are set with
textContent, never as HTML.
*/

(function () {
  const root = document.getElementById("storefrontDirectory");
  const grid = document.getElementById("storefrontGrid");
  if (!root || !grid) return;

  const PER_PAGE = 24;
  const searchInput = document.getElementById("siteSearch");
  const sortSelect = document.getElementById("storefrontSort");
  const countLabel = document.getElementById("storefrontCount");
  const pager = document.getElementById("storefrontPager");
  let storefronts = [];
  let page = 1;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function initial(name) {
    return (String(name).trim()[0] || "?").toUpperCase();
  }

  // Cover photos, in order of preference; a banner fills the whole cover
  function coverFor(store) {
    const previews = [store.preview_image_1, store.preview_image_2, store.preview_image_3, store.preview_image_4].filter(Boolean);
    if (previews.length) return { images: previews.slice(0, 3), count: String(Math.min(previews.length, 3)) };
    if (store.banner_url) return { images: [store.banner_url], count: "banner" };
    const products = Array.isArray(store.cover_images) ? store.cover_images.filter(Boolean) : [];
    return { images: products.slice(0, 3), count: String(Math.min(products.length, 3)) };
  }

  function createFacade(store) {
    const name = store.brand_name || "Unnamed storefront";
    const facade = el("article", "pm-facade");

    const cover = el("div", "pm-facade__cover");
    const { images, count } = coverFor(store);
    cover.dataset.count = count;
    images.forEach((url) => {
      const img = el("img");
      img.src = url;
      img.alt = "";
      img.loading = "lazy";
      img.addEventListener("error", () => img.remove(), { once: true });
      cover.appendChild(img);
    });

    const body = el("div", "pm-facade__body");
    const medallion = el("span", "pm-medallion", store.logo_url ? undefined : initial(name));
    if (store.logo_url) {
      const logo = el("img");
      logo.src = store.logo_url;
      logo.alt = "";
      logo.addEventListener("error", () => { medallion.textContent = initial(name); }, { once: true });
      medallion.appendChild(logo);
    }
    const link = el("a", "pm-facade__link pm-facade__name", name);
    link.href = `/storefronts/${Number(store.id)}`;
    const items = Number(store.item_count) || 0;
    const meta = el("span", "pm-facade__meta", items ? `${items} item${items === 1 ? "" : "s"}` : "No items yet");
    body.append(medallion, link, meta);

    facade.append(cover, body);
    return facade;
  }

  function visibleStorefronts() {
    const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
    const list = storefronts.filter((store) => !query || String(store.brand_name || "").toLowerCase().includes(query));
    const sort = sortSelect.value;
    return list.sort((a, b) => {
      if (sort === "name") return String(a.brand_name).localeCompare(String(b.brand_name));
      if (sort === "newest") return String(b.created_at).localeCompare(String(a.created_at));
      return (Number(b.item_count) || 0) - (Number(a.item_count) || 0);
    });
  }

  function render() {
    const list = visibleStorefronts();
    const pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
    page = Math.min(page, pages);
    const query = searchInput ? searchInput.value.trim() : "";

    grid.replaceChildren();
    grid.setAttribute("aria-busy", "false");
    countLabel.textContent = query
      ? `${list.length} result${list.length === 1 ? "" : "s"} for "${query}"`
      : `${list.length} storefront${list.length === 1 ? "" : "s"}`;

    if (!list.length) {
      const empty = el("div", "pm-empty");
      empty.append(
        el("h2", null, query ? "No storefronts match" : "No storefronts yet"),
        el("p", null, query ? "Check the spelling, or clear the search to see every store." : "Open the first one and start selling.")
      );
      const action = el("a", "pm-btn pm-btn--primary", query ? "Show all storefronts" : "Create a storefront");
      action.href = query ? "/storefronts" : "/storefronts/create";
      empty.appendChild(action);
      grid.appendChild(empty);
    } else {
      list.slice((page - 1) * PER_PAGE, page * PER_PAGE).forEach((store) => grid.appendChild(createFacade(store)));
    }

    pager.hidden = pages <= 1;
    document.getElementById("pageIndicator").textContent = `Page ${page} of ${pages}`;
    document.getElementById("prevPageBtn").disabled = page <= 1;
    document.getElementById("nextPageBtn").disabled = page >= pages;
  }

  function showLoadError() {
    grid.setAttribute("aria-busy", "false");
    const box = el("div", "pm-empty");
    box.append(el("h2", null, "Couldn't load storefronts"), el("p", null, "Check your connection and try again."));
    const retry = el("button", "pm-btn pm-btn--secondary", "Try again");
    retry.type = "button";
    retry.addEventListener("click", () => window.location.reload());
    box.appendChild(retry);
    grid.replaceChildren(box);
  }

  async function loadStorefronts() {
    try {
      const response = await fetch("/api/storefronts");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      storefronts = Array.isArray(data) ? data : [];
      render();
    } catch (error) {
      console.error("Error loading storefronts:", error);
      showLoadError();
    }
  }

  async function loadHotRail() {
    try {
      const userId = Number(root.dataset.userId) || null;
      const [response, wishlistIds] = await Promise.all([
        fetch("/api/hot", { cache: "no-cache" }),
        VaultListingCard.getWishlistIdSet(userId)
      ]);
      if (!response.ok) return;
      const data = await response.json();
      const items = (data.hot && data.hot.length ? data.hot : data.just_listed || []).slice(0, 5);
      if (!items.length) return;
      const tiles = await Promise.all(items.map((item) => VaultListingCard.create(item, { wishlistIds, currentUserId: userId })));
      document.getElementById("hotRailGrid").replaceChildren(...tiles);
      document.getElementById("hotRail").hidden = false;
    } catch (error) {
      console.error("Error loading the Hot rail:", error); // the rail just stays hidden
    }
  }

  if (searchInput) {
    searchInput.addEventListener("input", () => { page = 1; render(); });
    searchInput.form.addEventListener("submit", (event) => { event.preventDefault(); page = 1; render(); });
  }
  sortSelect.addEventListener("change", () => { page = 1; render(); });
  document.getElementById("prevPageBtn").addEventListener("click", () => { page -= 1; render(); grid.scrollIntoView({ block: "start" }); });
  document.getElementById("nextPageBtn").addEventListener("click", () => { page += 1; render(); grid.scrollIntoView({ block: "start" }); });

  loadStorefronts();
  loadHotRail();
})();
