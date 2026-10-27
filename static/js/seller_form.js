/*
    seller_form.js

    Pirate Market
    Created by James Williams - 10/26/26
    Shared by the seller pages (listing fields come from partials/listing_form.html):
    - photoTiles(): the four photo tiles (several files at once fill the empty tiles, remove buttons)
    - showError() / clearErrors(): inline field errors instead of alert()
    - renderPreview(): the live product tile beside the form, built by VaultListingCard
    - renderFacade(): the live storefront facade beside the storefront form
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

    // inputs: the 4 file inputs. options.onChange(file, picker) runs after any tile changes.
    function photoTiles(inputs, options = {}) {
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
                onChange: (file, changed) => {
                    remove.hidden = !file;
                    tile.classList.toggle("has-photo", Boolean(file));
                    if (file) showError("photosError", "");
                    if (options.onChange) options.onChange(file, changed);
                }
            });
            picker.input = input;
            remove.addEventListener("click", () => picker.clear());
            pickers.push(picker);
        });
        return pickers;
    }

    async function renderPreview(container, { title, price, image, store }) {
        if (!container || !window.VaultListingCard) return;
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

    // Storefront editors: the facade preview (cover photos, logo medallion, name)
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

    window.SellerForm = { photoTiles, showError, clearErrors, renderPreview, renderFacade };
})();
