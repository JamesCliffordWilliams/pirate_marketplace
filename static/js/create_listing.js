/*
create_listing.js

The Vault Campus Marketplace
CSC 405 Sp 26
Created by Elali McNair - Iteration 4
Updated by Day Ekoi - Iteration 5 4/9/26
Updated by Day Ekoi - Iteration 5 4/22/26 - One Size mode, per-size quantities, Made-to-Order
Updated by James Williams - 10/26/26 - added the required category picker
Updated by James Williams - 10/26/26 - shared photo picker, one request per submit
Updated by James Williams - 10/26/26 - request key so a retried create can't make a duplicate
Updated by James Williams - 10/26/26 - redesign: photo tiles, live preview, inline errors instead of alerts

Purpose:
Handles form submission for Create Listing page. Supports:
- One Size mode (single quantity, no other sizes selectable)
- Multi-size mode (per-size quantity inputs)
- Made-to-Order flag (bypasses inventory limits)
- Required product category
The request sent to /api/listings/create is unchanged.
*/

document.addEventListener("DOMContentLoaded", function () {
  const { photoTiles, showError, clearErrors, renderPreview } = window.SellerForm;

  const listingForm = document.getElementById("listingForm");
  const cancelBtn = document.getElementById("cancelBtn");
  const storefrontSelect = document.getElementById("storefrontSelect");
  const listingName = document.getElementById("listingName");
  const priceInput = document.getElementById("price");
  const previewInputs = [1, 2, 3, 4].map((index) => document.getElementById(`previewImage${index}`));
  const livePreview = document.getElementById("livePreview");
  let currentUser = null; // loaded once with the storefronts

  // ── Size mode elements ──────────────────────────────────────
  const oneSizeToggle = document.getElementById("oneSizeToggle");
  const multiSizeGrid = document.getElementById("multiSizeGrid");
  const oneSizeQtyRow = document.getElementById("oneSizeQtyRow");
  const oneSizeQty = document.getElementById("oneSizeQty");
  const madeToOrderToggle = document.getElementById("madeToOrderToggle");

  // ── Category picker ─────────────────────────────────────────
  // Category errors from the server show under the picker instead of in an alert
  const CATEGORY_ERROR_MESSAGES = [
    "Please choose a category.",
    "Choose a specific subcategory, not a main category.",
    "That category doesn't exist."
  ];
  const submitBtn = listingForm.querySelector("button[type='submit']");
  let categoriesReady = false;
  let formLocked = false; // true when the user has no storefront

  function updateSubmitState() {
    submitBtn.disabled = formLocked || !categoriesReady;
  }

  const categoryPicker = window.CategoryPicker.mount(document.getElementById("categoryPicker"), {
    hiddenInput: document.getElementById("categoryId"),
    onStatusChange: (status) => {
      categoriesReady = status === "ready";
      updateSubmitState();
    }
  });

  function applyOneSizeMode(enabled) {
    if (enabled) {
      multiSizeGrid.style.display = "none";
      multiSizeGrid.querySelectorAll('input[name="sizes"]').forEach(cb => { cb.checked = false; });
      multiSizeGrid.querySelectorAll(".size-qty-input").forEach(inp => {
        inp.value = "";
        inp.style.display = "none";
      });
      oneSizeQtyRow.style.display = "";
    } else {
      multiSizeGrid.style.display = "";
      oneSizeQtyRow.style.display = "none";
      oneSizeQty.value = "";
    }
  }

  oneSizeToggle.addEventListener("change", () => applyOneSizeMode(oneSizeToggle.checked));

  // Show/hide the stock input beside a size chip
  multiSizeGrid.querySelectorAll('input[name="sizes"]').forEach(cb => {
    cb.addEventListener("change", () => {
      const qtyInput = cb.closest(".size-qty-row").querySelector(".size-qty-input");
      qtyInput.style.display = cb.checked ? "inline-block" : "none";
      if (cb.checked) qtyInput.focus(); else qtyInput.value = "";
    });
  });

  // ── Photos and live preview ──────────────────────────────────
  const imagePickers = photoTiles(previewInputs, { onChange: updatePreview });

  function updatePreview() {
    const cover = imagePickers.find((picker) => picker.file);
    const store = storefrontSelect.selectedOptions[0];
    renderPreview(livePreview, {
      title: listingName.value.trim(),
      price: priceInput.value,
      image: cover ? cover.previewUrl : null,
      store: store && store.value ? store.textContent : ""
    });
  }

  [listingName, priceInput].forEach((input) => input.addEventListener("input", updatePreview));
  storefrontSelect.addEventListener("change", updatePreview);
  updatePreview();

  loadUserStorefronts();

  // ── Validation (everything is checked before anything is sent) ──
  function collectListing() {
    clearErrors(listingForm);
    let firstInvalid = null;
    const fail = (errorId, message, field) => {
      showError(errorId, message);
      firstInvalid = firstInvalid || field;
    };

    const storefrontId = storefrontSelect.value;
    const title = listingName.value.trim();
    const price = parseFloat(priceInput.value);
    const isOneSizeMode = oneSizeToggle.checked;
    const isMadeToOrder = madeToOrderToggle.checked;
    const categoryId = document.getElementById("categoryId").value.trim();
    const listingImages = imagePickers.map((picker) => picker.file).filter(Boolean);

    if (!listingImages.length) fail("photosError", "Add at least one photo.", previewInputs[0]);
    if (!title) fail("nameError", "Enter a listing name.", listingName);
    if (!storefrontId) fail("storefrontError", "Choose the storefront to list this in.", storefrontSelect);
    if (!categoryId || !categoryPicker.hasValue()) {
      categoryPicker.setError("Please choose a category.");
      firstInvalid = firstInvalid || { focus: () => categoryPicker.focus() };
    }
    if (priceInput.value === "" || isNaN(price) || price < 0) fail("priceError", "Enter a price of 0 or more.", priceInput);

    // sizes and per-size stock
    let sizes = [];
    const sizeQuantities = {};
    if (isOneSizeMode) {
      const qty = parseInt(oneSizeQty.value || "0", 10);
      if (!isMadeToOrder && (isNaN(qty) || qty < 0)) fail("sizesError", "Enter how many you have (0 or more).", oneSizeQty);
      sizes = ["One Size"];
      sizeQuantities["One Size"] = isMadeToOrder ? 0 : (qty || 0);
    } else {
      sizes = Array.from(multiSizeGrid.querySelectorAll("input[name='sizes']:checked")).map(cb => cb.value);
      if (!sizes.length) {
        fail("sizesError", "Pick at least one size, or turn on One size.", multiSizeGrid.querySelector("input[name='sizes']"));
      }
      for (const size of sizes) {
        const qtyInput = multiSizeGrid.querySelector(`.size-qty-input[data-size="${size}"]`);
        const qty = parseInt(qtyInput.value, 10);
        if (!isMadeToOrder && (isNaN(qty) || qty < 0)) {
          fail("sizesError", `Enter how many you have in size ${size} (0 or more).`, qtyInput);
          break;
        }
        sizeQuantities[size] = isMadeToOrder ? 0 : (isNaN(qty) ? 0 : qty);
      }
    }

    if (firstInvalid) {
      firstInvalid.focus();
      return null;
    }
    const totalQty = isMadeToOrder ? 0 : Object.values(sizeQuantities).reduce((a, b) => a + b, 0);
    return { storefrontId, title, price, isMadeToOrder, categoryId, listingImages, sizes, sizeQuantities, totalQty };
  }

  // ── Form submission ──────────────────────────────────────────
  // One request per submit; the user comes from page load
  listingForm.addEventListener("submit", window.ImageUploader.guardSubmit(listingForm, "Publishing…", async () => {
    const user = currentUser || await fetchCurrentUser();
    if (!user) {
      window.location.href = "/auth/login";
      return true;
    }

    const listing = collectListing();
    if (!listing) return;

    try {
      const formData = new FormData();
      formData.append("storefront_id", listing.storefrontId);
      formData.append("title", listing.title);
      formData.append("quantity_on_hand", listing.totalQty);
      formData.append("price", listing.price);
      formData.append("fulfillment_type", "IN_STOCK");
      formData.append("status", "ACTIVE");
      formData.append("is_made_to_order", listing.isMadeToOrder ? "true" : "false");
      formData.append("sizes_available", JSON.stringify(listing.sizes));
      formData.append("size_quantities", JSON.stringify(listing.sizeQuantities));
      formData.append("category_id", String(listing.categoryId));
      listing.listingImages.forEach(file => formData.append("listing_images", file));

      const response = await sendCreateRequest(formData, user);
      if (response.status === 401) {
        window.location.href = "/auth/login";
        return true;
      }
      const result = await response.json().catch(() => ({}));

      if (response.ok) {
        VaultListingCard.showToast("Listing published");
        window.setTimeout(() => {
          window.location.href = result.id ? `/listings/${result.id}` : "/my-storefront";
        }, 900);
        return true;
      }
      if (CATEGORY_ERROR_MESSAGES.includes(result.error)) {
        categoryPicker.setError(result.error);
        categoryPicker.focus();
      } else {
        showError("formError", result.error || "The listing wasn't published. Try again.");
      }
    } catch (error) {
      console.error("Error submitting form:", error);
      showError("formError", "Couldn't reach Pirate Market. Check your connection and try again.");
    }
  }));

  cancelBtn.addEventListener("click", () => {
    window.location.href = "/my-storefront";
  });

  // One key per submit. The same key is only reused to retry when no response arrived,
  // or the server says this listing is still being created (409), so it can't be made twice.
  function newRequestKey() {
    if (window.crypto.randomUUID) return window.crypto.randomUUID();
    const bytes = window.crypto.getRandomValues(new Uint8Array(16)); // randomUUID needs https
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  async function sendCreateRequest(formData, user) {
    const key = newRequestKey();
    for (let attempt = 1; ; attempt++) {
      try {
        const response = await fetch("/api/listings/create", {
          method: "POST",
          headers: { "X-User-Id": user.id, "X-User-Role": user.role, "Idempotency-Key": key },
          body: formData,
        });
        if (response.status !== 409 || attempt >= 5) return response;
      } catch (error) {
        if (attempt >= 3) throw error; // still offline
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
    }
  }

  async function fetchCurrentUser() {
    const userRes = await fetch("/auth/api/auth/me");
    currentUser = userRes.ok ? await userRes.json() : null;
    return currentUser;
  }

  function lockForNoStorefront() {
    storefrontSelect.innerHTML = '<option value="" disabled selected>No storefront yet</option>';
    formLocked = true;
    listingForm.querySelectorAll("input, select, button[type='submit'], .cp-trigger").forEach(el => { el.disabled = true; });
    updateSubmitState();
    const notice = document.createElement("div");
    notice.className = "pm-notice";
    notice.append("You need a storefront before you can list products. ");
    const link = document.createElement("a");
    link.href = "/storefronts/create";
    link.textContent = "Create your storefront";
    notice.appendChild(link);
    listingForm.prepend(notice);
  }

  async function loadUserStorefronts() {
    try {
      const user = await fetchCurrentUser();
      if (!user) {
        window.location.href = "/auth/login";
        return;
      }

      const response = await fetch("/api/storefronts/me", {
        headers: { "X-User-Id": user.id, "X-User-Role": user.role },
      });

      if (response.status === 404) {
        lockForNoStorefront();
        return;
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const storefrontData = await response.json();
      const storefronts = Array.isArray(storefrontData)
        ? storefrontData
        : storefrontData && storefrontData.id ? [storefrontData] : [];
      if (!storefronts.length) {
        lockForNoStorefront();
        return;
      }

      storefrontSelect.replaceChildren();
      storefronts.forEach(storefront => {
        const option = document.createElement("option");
        option.value = storefront.id;
        option.textContent = storefront.brand_name || storefront.name || `Storefront #${storefront.id}`;
        storefrontSelect.appendChild(option);
      });
      updatePreview();
    } catch (error) {
      console.error("Error loading storefronts:", error);
      storefrontSelect.innerHTML = '<option value="">Couldn\'t load your storefronts</option>';
      showError("storefrontError", "Refresh the page to try again.");
    }
  }
});
