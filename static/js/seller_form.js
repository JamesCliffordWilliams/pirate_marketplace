/*
    seller_form.js

    Pirate Market
    Created by James Williams - 10/26/26
    This is shared code for the seller pages. It has the four photo tiles, the sizes, the error messages
    under each field, and the live previews that show up next to the form.
*/

(function () {
    function showError(errorId, message) {
        const error = document.getElementById(errorId);
        if (!error) return;
        error.textContent = message || "";
        document.querySelectorAll(`[aria-describedby~="${errorId}"]`).forEach((field) => {
            if (message) field.setAttribute("aria-invalid", "true");
            else field.removeAttribute("aria-invalid");
        });
    }

    function clearErrors(form) {
        form.querySelectorAll(".pm-error").forEach((error) => showError(error.id, ""));
    }

    // This sets up the four photo tiles. onChange runs whenever a tile changes
    function photoTiles(inputs, onChange) {
        const pickers = [];

        function isOpen(picker) {
            const tile = picker.input.closest(".pm-photo");
            return !tile.hidden && !picker.file && !picker.input.closest(".drop-zone").classList.contains("is-processing");
        }

        function fillEmpty(files) {
            showError("photosError", "");
            for (const file of files) {
                const next = pickers.find(isOpen);
                if (!next) {
                    showError("photosError", "Only 4 photos fit. Remove one to add another.");
                    return;
                }
                next.pick(file);
            }
        }

        inputs.forEach((input) => {
            const tile = input.closest(".pm-photo");
            const remove = tile.querySelector("[data-remove-slot]");
            const picker = window.ImageUploader.attach(input, {
                onExtraFiles: fillEmpty,
                onChange: (file) => {
                    remove.hidden = !file;
                    tile.classList.toggle("has-photo", Boolean(file));
                    if (file) showError("photosError", "");
                    onChange();
                }
            });
            remove.addEventListener("click", () => picker.clear());
            pickers.push(picker);
        });
        return pickers;
    }

    // This shows or hides the stock box next to each size when it's checked
    function watchSizeBoxes(multiSizeGrid) {
        multiSizeGrid.querySelectorAll('input[name="sizes"]').forEach((cb) => {
            cb.addEventListener("change", () => {
                const qtyInput = cb.closest(".size-qty-row").querySelector(".size-qty-input");
                qtyInput.style.display = cb.checked ? "inline-block" : "none";
                if (cb.checked) qtyInput.focus(); else qtyInput.value = "";
            });
        });
    }

    // Reads the sizes and how many of each. Made to order listings always save 0.
    // If something is wrong it calls fail(errorId, message, field) like the other checks on the page
    function readSizes({ oneSizeToggle, oneSizeQty, multiSizeGrid, isMadeToOrder }, fail) {
        let sizes = [];
        const sizeQuantities = {};
        if (oneSizeToggle.checked) {
            const qty = parseInt(oneSizeQty.value || "0", 10);
            if (!isMadeToOrder && (isNaN(qty) || qty < 0)) fail("sizesError", "Enter how many you have (0 or more).", oneSizeQty);
            sizes = ["One Size"];
            sizeQuantities["One Size"] = isMadeToOrder ? 0 : (qty || 0);
        } else {
            sizes = Array.from(multiSizeGrid.querySelectorAll('input[name="sizes"]:checked')).map((cb) => cb.value);
            if (!sizes.length) {
                fail("sizesError", "Pick at least one size, or turn on One size.", multiSizeGrid.querySelector('input[name="sizes"]'));
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
        const totalQty = isMadeToOrder ? 0 : Object.values(sizeQuantities).reduce((a, b) => a + b, 0);
        return { sizes, sizeQuantities, totalQty };
    }

    async function renderPreview(container, { title, price, image, store }) {
        const tile = await VaultListingCard.create({
            id: 0,
            title: title || "Listing name",
            price: price || 0,
            image_url: image || null,
            storefront: { brand_name: store || "Your storefront" }
        }, {});
        tile.removeAttribute("id");
        container.replaceChildren(tile);
    }

    // This builds the store cover preview with the photos, logo and name
    function renderFacade({ name, logo, images, banner }) {
        const cover = document.getElementById("facadeCover");
        const medallion = document.getElementById("facadeLogo");
        const photos = images.length ? images.slice(0, 3) : (banner ? [banner] : []);
        cover.dataset.count = images.length ? String(photos.length) : (banner ? "banner" : "0");
        cover.replaceChildren(...photos.map((url) => {
            const img = document.createElement("img");
            img.src = url;
            img.alt = "";
            return img;
        }));
        document.getElementById("facadeName").textContent = name || "Your storefront";
        if (logo) {
            const img = document.createElement("img");
            img.src = logo;
            img.alt = "";
            medallion.replaceChildren(img);
        } else {
            medallion.textContent = ((name || "?").trim()[0] || "?").toUpperCase();
        }
    }

    window.SellerForm = { photoTiles, watchSizeBoxes, readSizes, showError, clearErrors, renderPreview, renderFacade };
})();
