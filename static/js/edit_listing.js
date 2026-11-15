/*
    edit_listing.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Updated by Day Ekoi - Iteration 5 4/22/26
    - One Size mode: loads correctly from existing data
    - Per-size quantity inputs
    - Made-to-Order toggle
    Updated by Day E - April 22nd - multi-image edit management using existing S3 and listing image routes
    Updated by James Williams - 10/26/26 - added the category picker, and saving doesn't turn
    hidden listings back on anymore
    Updated by James Williams - 10/26/26 - shared photo picker, one request per save
    Updated by James Williams - 10/26/26 - redesign with saved photos as tiles, a live preview, and errors
    on the page instead of pop-ups. The requests didn't change.
*/

document.addEventListener("DOMContentLoaded", async () => {
    const { photoTiles, watchSizeBoxes, readSizes, showError, clearErrors, renderPreview } = window.SellerForm;

    const form = document.getElementById("editListingForm");
    const cancelBtn = document.getElementById("cancelBtn");
    const listingId = Number(window.location.pathname.split("/")[2]);
    const listingName = document.getElementById("listingName");
    const priceInput = document.getElementById("price");
    const storefrontName = document.getElementById("storefrontName");
    const livePreview = document.getElementById("livePreview");

    const oneSizeToggle = document.getElementById("oneSizeToggle");
    const multiSizeGrid = document.getElementById("multiSizeGrid");
    const oneSizeQtyRow = document.getElementById("oneSizeQtyRow");
    const oneSizeQty = document.getElementById("oneSizeQty");
    const madeToOrderToggle = document.getElementById("madeToOrderToggle");
    const currentImageGallery = document.getElementById("currentImageGallery");
    const imageFallback = document.getElementById("imageFallback");

    const previewInputs = [1, 2, 3, 4].map((index) => document.getElementById(`previewImage${index}`));

    let currentUser = null;
    let existingImages = [];
    let sizesArray = [];
    let loadedListing = null;

    // ── Category picker ─────────────────────────────────────────
    const CATEGORY_ERROR_MESSAGES = [
        "Please choose a category.",
        "Choose a specific subcategory, not a main category.",
        "That category doesn't exist."
    ];
    const submitBtn = form.querySelector("button[type='submit']");
    const categoryPickerRoot = document.getElementById("categoryPicker");
    let categoriesReady = false;

    function updateSubmitState() {
        submitBtn.disabled = !categoriesReady || !loadedListing;
    }

    // If the listing's category isn't in the list anymore, this tells the seller. Saving still keeps the old one
    function noteRetiredCategory() {
        if (!categoriesReady || !loadedListing || !loadedListing.category_id || categoryPicker.hasValue()) return;
        let note = document.getElementById("retiredCategoryNote");
        if (!note) {
            note = document.createElement("p");
            note.id = "retiredCategoryNote";
            note.className = "pm-hint";
            categoryPickerRoot.parentNode.appendChild(note);
        }
        const name = loadedListing.category?.name;
        note.textContent = `${name ? `"${name}"` : "This listing's category"} is no longer offered. Choose a new category, or save to keep it.`;
    }

    const categoryPicker = window.CategoryPicker.mount(categoryPickerRoot, {
        hiddenInput: document.getElementById("categoryId"),
        onStatusChange: (status) => {
            categoriesReady = status === "ready";
            updateSubmitState();
            noteRetiredCategory();
        },
        onChange: () => {
            const note = document.getElementById("retiredCategoryNote");
            if (note) note.remove();
        }
    });
    updateSubmitState();

    // Hidden or deleted listings don't send a status, so saving doesn't turn them back on
    function computeSaveStatus(currentStatus, isMadeToOrder, totalQty) {
        if (currentStatus !== "ACTIVE" && currentStatus !== "SOLD_OUT") {
            return undefined; // server keeps the current status
        }
        return !isMadeToOrder && totalQty === 0 ? "SOLD_OUT" : "ACTIVE";
    }

    cancelBtn.addEventListener("click", () => {
        window.location.href = "/storefronts/dashboard";
    });

    // ── Sizes ────────────────────────────────────────────────────
    function applyOneSizeMode(enabled) {
        if (enabled) {
            multiSizeGrid.style.display = "none";
            multiSizeGrid.querySelectorAll('input[name="sizes"]').forEach((cb) => { cb.checked = false; });
            multiSizeGrid.querySelectorAll(".size-qty-input").forEach((inp) => {
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
    watchSizeBoxes(multiSizeGrid);

    // ── Photos: saved ones, plus a tile for each free spot ──────
    const imagePickers = photoTiles(previewInputs, updatePreview);

    function queuedFiles() {
        return imagePickers.map((picker) => picker.file).filter(Boolean);
    }

    function showFreeSpots() {
        const free = Math.max(0, 4 - existingImages.length);
        imagePickers.forEach((picker, index) => {
            const tile = picker.input.closest(".pm-photo");
            tile.hidden = index >= free;
            if (tile.hidden && picker.file) picker.clear();
        });
    }

    function updatePreview() {
        const cover = existingImages[0]?.image_url || imagePickers.find((picker) => picker.file)?.previewUrl;
        renderPreview(livePreview, {
            title: listingName.value.trim(),
            price: priceInput.value,
            image: cover,
            store: storefrontName.value
        });
    }

    [listingName, priceInput].forEach((input) => input.addEventListener("input", updatePreview));

    function photoButton(label, onClick, disabled) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "pm-btn pm-btn--ghost";
        button.textContent = label;
        button.disabled = Boolean(disabled);
        button.addEventListener("click", onClick);
        return button;
    }

    function authHeaders() {
        return { "X-User-Id": currentUser.id, "X-User-Role": currentUser.role };
    }

    async function imageRequest(url, method, failMessage) {
        showError("photosError", "");
        try {
            const response = await fetch(url, { method, headers: authHeaders() });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(result.error || failMessage);
            await refreshListingImages();
        } catch (error) {
            console.error(failMessage, error);
            showError("photosError", error.message || failMessage);
        }
    }

    function renderExistingImages() {
        currentImageGallery.replaceChildren();
        imageFallback.style.display = existingImages.length ? "none" : "";

        existingImages.forEach((image, index) => {
            const card = document.createElement("div");
            card.className = "pm-saved-photo";

            const frame = document.createElement("div");
            frame.className = "pm-saved-photo__img";
            const img = document.createElement("img");
            img.src = image.image_url;
            img.alt = `Saved photo ${index + 1}`;
            frame.appendChild(img);

            const actions = document.createElement("div");
            actions.className = "pm-saved-photo__actions";
            if (image.is_primary) {
                const cover = document.createElement("span");
                cover.className = "pm-hint";
                cover.textContent = "Cover";
                actions.appendChild(cover);
            } else {
                actions.appendChild(photoButton("Make cover", () => imageRequest(
                    `/api/listings/${listingId}/images/${image.id}/primary`, "PATCH", "Couldn't change the cover photo."
                ), image.is_legacy));
            }
            actions.appendChild(photoButton("Remove", () => {
                if (!window.confirm("Remove this photo from the listing?")) return;
                imageRequest(`/api/listings/${listingId}/images/${image.id}`, "DELETE", "Couldn't remove the photo.");
            }, existingImages.length <= 1 || image.is_legacy));

            card.append(frame, actions);
            currentImageGallery.appendChild(card);
        });
        showFreeSpots();
        updatePreview();
    }

    async function fetchListingImages() {
        const response = await fetch(`/api/listings/${listingId}/images`);
        if (!response.ok) return [];
        const images = await response.json();
        return Array.isArray(images) ? images.slice(0, 4) : [];
    }

    async function refreshListingImages() {
        existingImages = await fetchListingImages();
        renderExistingImages();
    }

    async function uploadListingImageFile(file) {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("folder", "listings");
        const response = await fetch("/api/storefronts/upload-image", { method: "POST", body: formData });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || "Couldn't upload a photo.");
        return data.url;
    }

    async function saveQueuedImages() {
        const queuedImages = queuedFiles();
        if (existingImages.length + queuedImages.length > 4) {
            throw new Error("Only 4 photos fit. Remove one to add another.");
        }
        for (let index = 0; index < queuedImages.length; index += 1) {
            const imageUrl = await uploadListingImageFile(queuedImages[index]);
            const response = await fetch(`/api/listings/${listingId}/images`, {
                method: "POST",
                headers: { "Content-Type": "application/json", ...authHeaders() },
                body: JSON.stringify({ image_url: imageUrl, is_primary: existingImages.length === 0 && index === 0 })
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(result.error || "Couldn't save a photo.");
        }
    }

    // ── Load ─────────────────────────────────────────────────────
    try {
        const userRes = await fetch("/auth/api/auth/me");
        if (!userRes.ok) {
            window.location.href = "/auth/login";
            return;
        }
        currentUser = await userRes.json();

        const [listingRes, sizesRes, myStorefrontRes] = await Promise.all([
            fetch(`/api/listings/${listingId}`),
            fetch(`/api/listings/${listingId}/sizes`),
            fetch("/api/storefronts/me", { headers: authHeaders() })
        ]);
        if (!listingRes.ok) throw new Error("This listing couldn't be loaded.");

        const listing = await listingRes.json();
        loadedListing = listing;
        categoryPicker.setValue(listing.category_id);
        updateSubmitState();
        noteRetiredCategory();
        sizesArray = sizesRes.ok ? await sizesRes.json() : [];
        const myStorefront = myStorefrontRes.ok ? await myStorefrontRes.json() : null;

        listingName.value = listing.title || "";
        priceInput.value = Number(listing.price || 0).toFixed(2);
        storefrontName.value = myStorefront?.brand_name || `Storefront #${listing.storefront_id}`;
        madeToOrderToggle.checked = Boolean(listing.is_made_to_order);

        existingImages = await fetchListingImages();
        if (!existingImages.length && listing.image_url) {
            existingImages = [{ id: `legacy-${listing.id}`, image_url: listing.image_url, is_primary: true, is_legacy: true }];
        }
        renderExistingImages();

        const isOneSize = Array.isArray(sizesArray) && sizesArray.length === 1 && sizesArray[0].size === "One Size";
        if (isOneSize) {
            oneSizeToggle.checked = true;
            applyOneSizeMode(true);
            oneSizeQty.value = sizesArray[0].quantity || 0;
        } else {
            const sizeMap = {};
            sizesArray.forEach((sizeEntry) => { sizeMap[sizeEntry.size] = sizeEntry.quantity; });
            multiSizeGrid.querySelectorAll('input[name="sizes"]').forEach((cb) => {
                if (!Object.prototype.hasOwnProperty.call(sizeMap, cb.value)) return;
                cb.checked = true;
                const qtyInput = cb.closest(".size-qty-row").querySelector(".size-qty-input");
                qtyInput.style.display = "inline-block";
                qtyInput.value = sizeMap[cb.value];
            });
        }
    } catch (error) {
        console.error("Error loading edit listing page:", error);
        showError("formError", `${error.message || "This listing couldn't be loaded."} Go back to your storefront and try again.`);
        form.querySelectorAll("input, select, button[type='submit']").forEach((el) => { el.disabled = true; });
        return;
    }

    // ── Save ─────────────────────────────────────────────────────
    form.addEventListener("submit", window.ImageUploader.guardSubmit(form, "Saving…", async () => {
        clearErrors(form);
        const isMadeToOrder = madeToOrderToggle.checked;
        const price = Number(priceInput.value);
        const title = listingName.value.trim();
        const queuedImages = queuedFiles();
        let firstInvalid = null;
        const fail = (errorId, message, field) => {
            showError(errorId, message);
            firstInvalid = firstInvalid || field;
        };

        if (existingImages.length + queuedImages.length === 0) fail("photosError", "Keep at least one photo.", previewInputs[0]);
        if (!title) fail("nameError", "Enter a listing name.", listingName);
        if (priceInput.value === "" || isNaN(price) || price < 0) fail("priceError", "Enter a price of 0 or more.", priceInput);

        const { sizes: checkedSizes, sizeQuantities, totalQty } = readSizes({ oneSizeToggle, oneSizeQty, multiSizeGrid, isMadeToOrder }, fail);

        const categoryId = document.getElementById("categoryId").value.trim();
        if (!categoryId && !loadedListing.category_id) {
            categoryPicker.setError("Please choose a category.");
            firstInvalid = firstInvalid || { focus: () => categoryPicker.focus() };
        }
        if (firstInvalid) {
            firstInvalid.focus();
            return;
        }

        const updateBody = {
            title,
            price,
            quantity_on_hand: totalQty,
            fulfillment_type: "IN_STOCK",
            sizes_available: checkedSizes,
            is_made_to_order: isMadeToOrder,
        };
        const saveStatus = computeSaveStatus(loadedListing.status, isMadeToOrder, totalQty);
        if (saveStatus) updateBody.status = saveStatus;
        // If the old category was removed, leaving it out keeps it
        if (categoryId) updateBody.category_id = /^\d+$/.test(categoryId) ? Number(categoryId) : categoryId;

        try {
            const updateRes = await fetch(`/api/listings/${listingId}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json", ...authHeaders() },
                body: JSON.stringify(updateBody)
            });
            const updateData = await updateRes.json().catch(() => ({}));
            if (!updateRes.ok) {
                if (CATEGORY_ERROR_MESSAGES.includes(updateData.error)) {
                    categoryPicker.setError(updateData.error);
                    categoryPicker.focus();
                } else {
                    showError("formError", updateData.error || "Your changes weren't saved. Try again.");
                }
                return;
            }

            const existingSizeSet = new Set((Array.isArray(sizesArray) ? sizesArray : []).map((s) => String(s.size)));
            const newSizeSet = new Set(checkedSizes);
            for (const size of checkedSizes) {
                await fetch(`/api/listings/${listingId}/sizes`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json", ...authHeaders() },
                    body: JSON.stringify({ size, quantity: sizeQuantities[size] || 0 })
                });
            }
            for (const existing of existingSizeSet) {
                if (newSizeSet.has(existing)) continue;
                await fetch(`/api/listings/${listingId}/sizes/${existing}`, { method: "DELETE", headers: authHeaders() });
            }

            await saveQueuedImages();
        } catch (error) {
            showError("formError", error.message || "Your changes weren't fully saved. Try again.");
            return;
        }
        VaultListingCard.showToast("Changes saved");
        window.setTimeout(() => { window.location.href = "/storefronts/dashboard"; }, 700);
        return true;
    }));
});
