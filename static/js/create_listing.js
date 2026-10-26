/*
create_listing.js

The Vault Campus Marketplace
CSC 405 Sp 26
Created by Elali McNair - Iteration 4
Updated by Day Ekoi - Iteration 5 4/9/26
Updated by Day Ekoi - Iteration 5 4/22/26 - One Size mode, per-size quantities, Made-to-Order
Updated by James Williams - 10/26/26 - added the required category picker
Updated by James Williams - 10/26/26 - shared photo picker, one request per submit

Purpose:
Handles form submission for Create Listing page. Supports:
- One Size mode (single quantity, no other sizes selectable)
- Multi-size mode (per-size quantity inputs)
- Made-to-Order flag (bypasses inventory limits)
- Required product category
*/

document.addEventListener('DOMContentLoaded', function() {

  function ensureToastRoot() {
    let root = document.getElementById("toastRoot");
    if (!root) {
      root = document.createElement("div");
      root.id = "toastRoot";
      root.className = "toast-root";
      document.body.appendChild(root);
    }
    return root;
  }

  function showListingToast(message, tone = "success") {
    const root = ensureToastRoot();
    const toast = document.createElement("div");
    toast.className = `toast ${tone === "success" ? "success" : "error"}`;
    toast.textContent = message;
    root.appendChild(toast);

    window.setTimeout(() => {
      toast.classList.add("fade-out");
      window.setTimeout(() => toast.remove(), 220);
    }, 2200);
  }

  const listingForm = document.getElementById("listingForm");
  const cancelBtn = document.getElementById("cancelBtn");
  const storefrontSelect = document.getElementById("storefrontSelect");
  const previewInputs = [1, 2, 3, 4].map((index) => document.getElementById(`previewImage${index}`));
  let currentUser = null; // loaded once with the storefronts

  // ── Size mode elements ──────────────────────────────────────
  const oneSizeToggle = document.getElementById("oneSizeToggle");
  const multiSizeGrid = document.getElementById("multiSizeGrid");
  const oneSizeQtyRow = document.getElementById("oneSizeQtyRow");
  const oneSizeQty = document.getElementById("oneSizeQty");
  const madeToOrderToggle = document.getElementById("madeToOrderToggle");

  // ── Category picker ─────────────────────────────────────────
  // Added by James Williams 10/26/26
  // Category errors from the server show under the picker instead of in an alert
  const CATEGORY_ERROR_MESSAGES = [
    "Please choose a category.",
    "Choose a specific subcategory, not a main category.",
    "That category doesn't exist."
  ];
  const submitBtn = listingForm ? listingForm.querySelector("button[type='submit']") : null;
  let categoriesReady = false;
  let formLocked = false; // true when the user has no storefront

  function updateSubmitState() {
    if (submitBtn) submitBtn.disabled = formLocked || !categoriesReady;
  }

  const categoryPicker = window.CategoryPicker.mount(document.getElementById("categoryPicker"), {
    hiddenInput: document.getElementById("categoryId"),
    onStatusChange: (status) => {
      categoriesReady = status === "ready";
      updateSubmitState();
    }
  });

  function applyOneSizeMode(enabled) {
    if (!multiSizeGrid || !oneSizeQtyRow) return;
    if (enabled) {
      // Hide multi-size grid, clear all checkboxes and qty inputs
      multiSizeGrid.style.display = "none";
      multiSizeGrid.querySelectorAll('input[name="sizes"]').forEach(cb => {
        cb.checked = false;
      });
      multiSizeGrid.querySelectorAll(".size-qty-input").forEach(inp => {
        inp.value = "";
        inp.style.display = "none";
      });
      oneSizeQtyRow.style.display = "block";
    } else {
      multiSizeGrid.style.display = "";
      oneSizeQtyRow.style.display = "none";
      if (oneSizeQty) oneSizeQty.value = "";
    }
  }

  if (oneSizeToggle) {
    oneSizeToggle.addEventListener("change", () => {
      applyOneSizeMode(oneSizeToggle.checked);
    });
  }

  // Show/hide per-size quantity input when a size checkbox is toggled
  if (multiSizeGrid) {
    multiSizeGrid.querySelectorAll('input[name="sizes"]').forEach(cb => {
      cb.addEventListener("change", () => {
        const row = cb.closest(".size-qty-row");
        if (!row) return;
        const qtyInput = row.querySelector(".size-qty-input");
        if (qtyInput) {
          qtyInput.style.display = cb.checked ? "inline-block" : "none";
          if (!cb.checked) qtyInput.value = "";
        }
      });
    });
  }

  // ── Image pickers ────────────────────────────────────────────
  // Added by James Williams 10/26/26 - shared picker (js/image_uploader.js)
  const imagePickers = previewInputs.map((input, index) => window.ImageUploader.attach(input, {
    preview: document.getElementById(`previewPreview${index + 1}`)
  }));

  if (storefrontSelect) {
    loadUserStorefronts();
  }

  // ── Form submission ──────────────────────────────────────────

  if (listingForm) {
    // Updated by James Williams 10/26/26 - one request per submit; the user comes from page load
    listingForm.addEventListener("submit", window.ImageUploader.guardSubmit(listingForm, "Publishing…", async () => {
      const user = currentUser || await fetchCurrentUser();
      if (!user) {
        alert("You must be logged in to create a listing.");
        window.location.href = "/auth/login";
        return true;
      }

      const storefrontId = document.getElementById("storefrontSelect").value;
      const listingName = document.getElementById("listingName").value.trim();
      const price = parseFloat(document.getElementById("price").value);
      const isOneSizeMode = oneSizeToggle && oneSizeToggle.checked;
      const isMadeToOrder = madeToOrderToggle && madeToOrderToggle.checked;

      if (!storefrontId) {
        alert("Please select a storefront for this listing.");
        return;
      }

      if (!listingName || price < 0 || isNaN(price)) {
        alert("Please fill in all required fields with valid values.");
        return;
      }

      // Added by James Williams 10/26/26
      const categoryId = document.getElementById("categoryId").value.trim();
      if (!categoryId || !categoryPicker.hasValue()) {
        categoryPicker.setError("Please choose a category.");
        categoryPicker.focus();
        return;
      }

      // Collect sizes and per-size quantities
      let sizes = [];
      const sizeQuantities = {};

      if (isOneSizeMode) {
        const qty = parseInt(oneSizeQty ? oneSizeQty.value : "0", 10);
        if (!isMadeToOrder && (isNaN(qty) || qty < 0)) {
          alert("Please enter a valid quantity for One Size.");
          return;
        }
        sizes = ["One Size"];
        sizeQuantities["One Size"] = isMadeToOrder ? 0 : (qty || 0);
      } else {
        const sizeCheckboxes = document.querySelectorAll("input[name='sizes']:checked");
        sizes = Array.from(sizeCheckboxes).map(cb => cb.value);
        if (sizes.length === 0) {
          alert("Please select at least one size.");
          return;
        }
        for (const size of sizes) {
          const qtyInput = multiSizeGrid
            ? multiSizeGrid.querySelector(`.size-qty-input[data-size="${size}"]`)
            : null;
          const qty = qtyInput ? parseInt(qtyInput.value, 10) : NaN;
          if (!isMadeToOrder && (isNaN(qty) || qty < 0)) {
            alert(`Please enter a valid quantity for size ${size}.`);
            return;
          }
          sizeQuantities[size] = isMadeToOrder ? 0 : (isNaN(qty) ? 0 : qty);
        }
      }

      const totalQty = isMadeToOrder ? 0 : Object.values(sizeQuantities).reduce((a, b) => a + b, 0);

      const listingImages = imagePickers.map((picker) => picker.file).filter(Boolean);
      if (listingImages.length === 0) {
        alert("Please upload at least one listing image.");
        return;
      }

      try {
        const formData = new FormData();
        formData.append("storefront_id", storefrontId);
        formData.append("title", listingName);
        formData.append("quantity_on_hand", totalQty);
        formData.append("price", price);
        formData.append("fulfillment_type", "IN_STOCK");
        formData.append("status", "ACTIVE");
        formData.append("is_made_to_order", isMadeToOrder ? "true" : "false");
        formData.append("sizes_available", JSON.stringify(sizes));
        formData.append("size_quantities", JSON.stringify(sizeQuantities));
        formData.append("category_id", String(categoryId)); // Added by James Williams 10/26/26
        listingImages.forEach(file => formData.append("listing_images", file));

        const response = await fetch("/api/listings/create", {
          method: "POST",
          headers: {
            "X-User-Id": user.id,
            "X-User-Role": user.role
          },
          body: formData,
        });

        if (response.status === 401) {
          window.location.href = "/auth/login";
          return true;
        }
        const result = await response.json();

        if (response.ok) {
          showListingToast(`Listing "${listingName}" created successfully!`);
          window.setTimeout(() => {
            window.location.href = "/my-storefront";
          }, 2500);
          return true;
        } else if (CATEGORY_ERROR_MESSAGES.includes(result.error)) { // Added by James Williams 10/26/26
          categoryPicker.setError(result.error);
          categoryPicker.focus();
        } else {
          alert("Error creating listing: " + (result.error || "Unknown error"));
        }
      } catch (error) {
        console.error("Error submitting form:", error);
        alert("Error creating listing: " + error.message);
      }
    }));
  }

  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      window.location.href = "/storefronts";
    });
  }

  async function fetchCurrentUser() {
    const userRes = await fetch("/auth/api/auth/me");
    currentUser = userRes.ok ? await userRes.json() : null;
    return currentUser;
  }

  async function loadUserStorefronts() {
    try {
      const user = await fetchCurrentUser();
      if (!user) {
        window.location.href = "/auth/login";
        return;
      }

      const response = await fetch("/api/storefronts/me", {
        method: "GET",
        headers: {
          "X-User-Id": user.id,
          "X-User-Role": user.role
        },
      });

      if (response.ok) {
        const storefrontData = await response.json();
        const storefronts = Array.isArray(storefrontData)
          ? storefrontData
          : storefrontData && storefrontData.id
            ? [storefrontData]
            : [];

        storefrontSelect.innerHTML = "";

        if (storefronts.length > 0) {
          const defaultOption = document.createElement("option");
          defaultOption.value = "";
          defaultOption.textContent = "Select a storefront";
          defaultOption.disabled = true;
          defaultOption.selected = true;
          storefrontSelect.appendChild(defaultOption);

          storefronts.forEach(storefront => {
            const option = document.createElement("option");
            option.value = storefront.id;
            option.textContent = storefront.brand_name || storefront.name || `Storefront #${storefront.id}`;
            storefrontSelect.appendChild(option);
          });
        } else {
          storefrontSelect.innerHTML = '<option value="" disabled>No storefronts found - create one first</option>';
          formLocked = true;
          if (listingForm) {
            listingForm.querySelectorAll("input, select, button[type='submit'], .cp-trigger").forEach(el => {
              el.disabled = true;
            });
          }
          const messageDiv = document.createElement("div");
          messageDiv.style.cssText = "color: #d4af37; margin-top: 10px; font-weight: bold; text-align:center;";
          messageDiv.innerHTML = `You must create a storefront before creating listings. <a href="/storefronts/create" style="color:#fff; text-decoration:underline;">Create one here</a>`;
          storefrontSelect.parentNode.appendChild(messageDiv);
        }
      } else if (response.status === 404) {
        storefrontSelect.innerHTML = '<option value="" disabled>No storefronts found - create one first</option>';
        formLocked = true;
        if (listingForm) {
          listingForm.querySelectorAll("input, select, button[type='submit'], .cp-trigger").forEach(el => {
            el.disabled = true;
          });
        }
        const messageDiv = document.createElement("div");
        messageDiv.style.cssText = "color: #d4af37; margin-top: 10px; font-weight: bold; text-align:center;";
        messageDiv.innerHTML = `You must create a storefront before creating listings. <a href="/storefronts/create" style="color:#fff; text-decoration:underline;">Create one here</a>`;
        storefrontSelect.parentNode.appendChild(messageDiv);
      } else {
        console.error("Failed to load storefronts");
        storefrontSelect.innerHTML = '<option value="">Error loading storefronts</option>';
      }
    } catch (error) {
      console.error("Error loading storefronts:", error);
      storefrontSelect.innerHTML = '<option value="">Error loading storefronts</option>';
    }
  }
});
