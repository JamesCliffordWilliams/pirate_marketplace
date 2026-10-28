/*
storefront.js

  The Vault Campus Marketplace
  CSC 405 Sp 26
  Created by Day Ekoi - Iteration 4
  Date: 3/18/2026 - 3/22/2026
  Updated by Day Ekoi - Iteration 5 - 4/20/26 - fetchStorefronts now maps preview_image_1-4 to card carousel; falls back to banner_url if no previews set
  Updated by Day Ekoi - Iteration 5 - 4/20/26 - removed add-to-cart form from storefront cards (size, qty, add to bag); kept version history via comments
  Updated by James Williams - 10/26/26 - store covers, sorting, header search and page numbers
  Updated by Cletus Hyacinth - Iteration 3 10/26/26 - added brandSearch input to filter storefronts by brand name in addition to searchInput
  Updated by James Williams - 10/27/26 - renderStorefronts() and filterStorefronts() for CJ's brand search (his code is at the bottom)

Description: This is the storefront directory on homepage.html. Store names and other text
are added as plain text, never as HTML.
*/

(function () {
  const grid = document.getElementById("storefrontGrid");
  if (!grid) return;

  const PER_PAGE = 24;
  const sortSelect = document.getElementById("storefrontSort");
  const countLabel = document.getElementById("storefrontCount");
  const pager = document.getElementById("storefrontPager");
  let storefronts = [];
  let page = 1;
  let brandQuery = "";

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function initial(name) {
    return (String(name).trim()[0] || "?").toUpperCase();
  }

  // Picks the cover photos. It tries the preview photos first, then the banner, then the store's
  // product photos. A banner takes up the whole cover
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
      img.addEventListener("error", () => VaultListingCard.dropCoverPhoto(img), { once: true });
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
    const query = currentQuery().toLowerCase();
    const list = storefronts.filter((store) => !query || String(store.brand_name || "").toLowerCase().includes(query));
    const sort = sortSelect.value;
    return list.sort((a, b) => {
      if (sort === "name") return String(a.brand_name).localeCompare(String(b.brand_name));
      if (sort === "newest") return String(b.created_at).localeCompare(String(a.created_at));
      return (Number(b.item_count) || 0) - (Number(a.item_count) || 0);
    });
  }

  // This is the text from CJ's Explore Brands search
  function currentQuery() {
    return brandQuery;
  }

  function render() {
    const list = visibleStorefronts();
    const pages = Math.max(1, Math.ceil(list.length / PER_PAGE));
    page = Math.min(page, pages);
    const query = currentQuery();

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

  sortSelect.addEventListener("change", () => { page = 1; render(); });
  document.getElementById("prevPageBtn").addEventListener("click", () => { page -= 1; render(); grid.scrollIntoView({ block: "start" }); });
  document.getElementById("nextPageBtn").addEventListener("click", () => { page += 1; render(); grid.scrollIntoView({ block: "start" }); });

  // These are the two functions CJ's brand search below calls
  window.renderStorefronts = () => { brandQuery = ""; page = 1; render(); };
  window.filterStorefronts = (query) => { brandQuery = query; page = 1; render(); };

  loadStorefronts();
})();

// SEARCH BAR FUNCTIONALITY
// Added by Day E 4/9/26
// filters storefront cards in real time as the user types in the search bar

const searchInput = document.getElementById("searchInput");
const brandSearch = document.getElementById("brandSearch");

//  input changes
if(searchInput){
    searchInput.addEventListener("input", () => {
        const query = searchInput.value.trim();
        if (!query) {
            renderStorefronts(); // show all if search is cleared
        } else {
            filterStorefronts(query);
        }
    });

  }
  if(brandSearch) 
  { brandSearch.addEventListener("input", () => {
        const query = brandSearch.value.trim();
        if (!query) {
            renderStorefronts(); // show all if search is cleared
        } else {
            filterStorefronts(query);
        }
    });
  }
