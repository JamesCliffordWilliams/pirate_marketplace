/*
    product.js

    Pirate Market
    Created by James Williams - 10/26/26
    Product page: photo thumbnails, size and quantity, Add to bag and Save.
    Uses VaultListingCard.addToBag / setSaved, so the requests match the old card exactly.
    Opening the page counts as a detail_view for the Hot page.
*/

(function () {
    const page = document.getElementById("productPage");
    if (!page) return;

    const listingId = Number(page.dataset.listingId);
    const userId = Number(page.dataset.userId) || null;
    const madeToOrder = page.dataset.madeToOrder === "true";
    const title = page.dataset.title;
    const meta = {
        title,
        price: page.dataset.price,
        image_url: page.dataset.image || VaultListingCard.PLACEHOLDER_IMAGE,
        storefront_name: page.dataset.store
    };

    VaultListingCard.trackDetailView(listingId, userId);

    // ---------- photos ----------
    const mainPhoto = document.getElementById("galleryMain");
    document.querySelectorAll(".pm-gallery__thumb").forEach((thumb, _index, thumbs) => {
        thumb.addEventListener("click", () => {
            mainPhoto.src = thumb.dataset.src;
            thumbs.forEach((other) => other.setAttribute("aria-pressed", String(other === thumb)));
        });
    });

    // ---------- size and quantity ----------
    const form = document.getElementById("buyForm");
    const qtyInput = document.getElementById("qtyInput");
    const sizeError = document.getElementById("sizeError");
    const sizeInputs = Array.from(form.querySelectorAll('input[name="size"]'));

    function selectedSize() {
        return sizeInputs.find((input) => input.type === "hidden" || input.checked) || null;
    }

    function maxQuantity() {
        if (madeToOrder) return 99;
        const size = selectedSize();
        const fromSize = size ? Number(size.dataset.qty) : NaN;
        return Math.max(1, Number.isFinite(fromSize) && fromSize > 0 ? fromSize : Number(page.dataset.max) || 1);
    }

    function setQuantity(value) {
        if (!qtyInput) return;
        const max = maxQuantity();
        const qty = Math.min(max, Math.max(1, Math.round(Number(value)) || 1));
        qtyInput.value = String(qty);
        qtyInput.max = String(max);
        form.querySelector('[data-step="-1"]').disabled = qty <= 1;
        form.querySelector('[data-step="1"]').disabled = qty >= max;
    }

    // one in-stock size: pick it for the shopper
    const available = sizeInputs.filter((input) => input.type === "radio" && !input.disabled);
    if (available.length === 1) available[0].checked = true;

    sizeInputs.forEach((input) => input.addEventListener("change", () => {
        if (sizeError) sizeError.textContent = "";
        setQuantity(qtyInput ? qtyInput.value : 1);
    }));
    form.querySelectorAll("[data-step]").forEach((button) => {
        button.addEventListener("click", () => setQuantity(Number(qtyInput.value) + Number(button.dataset.step)));
    });
    if (qtyInput) {
        qtyInput.addEventListener("change", () => setQuantity(qtyInput.value));
        setQuantity(1);
    }

    // ---------- add to bag ----------
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const addButton = form.querySelector(".pm-product__add");
        if (!addButton || addButton.disabled) return;
        if (!userId) {
            window.location.href = "/auth/login";
            return;
        }
        const size = selectedSize();
        if (!size) {
            sizeError.textContent = "Choose a size.";
            form.querySelector('input[name="size"]:not(:disabled)').focus();
            return;
        }

        addButton.disabled = true;
        addButton.textContent = "Adding…";
        try {
            await VaultListingCard.addToBag({
                listingId,
                title,
                price: page.dataset.price,
                size: size.value,
                quantity: Number(qtyInput.value)
            });
            VaultListingCard.showToast(`Added to bag: ${title}${size.value === "One Size" ? "" : `, size ${size.value}`}`);
        } catch (error) {
            VaultListingCard.showToast(error.message, "error");
        } finally {
            addButton.disabled = false;
            addButton.textContent = "Add to bag";
        }
    });

    // ---------- save ----------
    const saveButton = document.getElementById("saveBtn");

    function renderSaved(saved) {
        saveButton.setAttribute("aria-pressed", String(saved));
        saveButton.textContent = saved ? "Saved" : "Save";
    }

    if (userId) {
        VaultListingCard.getWishlistIdSet(userId).then((ids) => renderSaved(ids.has(String(listingId))));
    }

    saveButton.addEventListener("click", async () => {
        if (!userId) {
            window.location.href = "/auth/login";
            return;
        }
        const save = saveButton.getAttribute("aria-pressed") !== "true";
        saveButton.disabled = true;
        try {
            await VaultListingCard.setSaved(listingId, userId, save, meta);
            renderSaved(save);
        } catch (error) {
            VaultListingCard.showToast(error.message, "error");
        } finally {
            saveButton.disabled = false;
        }
    });
})();
