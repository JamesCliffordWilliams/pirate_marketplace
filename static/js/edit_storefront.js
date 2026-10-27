/*
    edit_storefront.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by Day Ekoi - Iteration 5 4/16/2026
    Updated by Day Ekoi - Iteration 5 - 4/20/26 - drag-drop zones, image preview thumbnails, preview_image_1-4 upload + pre-fill, existing preview image display
    Updated by James Williams - 10/26/26 - shared photo picker, one request per save
    Updated by James Williams - 10/26/26 - redesign: saved photos in their tiles, live facade preview, inline errors

Handles the Edit Storefront page:
- Loads current storefront data and pre-fills the form
- Shows existing preview images
- Uploads new logo/banner/preview images to S3 only if new files are selected
- Sends PUT /api/storefronts/<id> with updated fields
- Redirects to dashboard on success
*/

const form = document.getElementById("storefrontForm");
const cancelBtn = document.getElementById("cancelBtn");
const deactivateBtn = document.getElementById("deactivateBtn");
const categoryCheckboxes = Array.from(document.querySelectorAll('input[name="categories"]'));
const categoryValidationMessage = document.getElementById("categoryValidationMessage");
const MAX_CATEGORY_SELECTIONS = 3;

const storefrontId = parseInt(window.location.pathname.split("/")[2]);

cancelBtn.addEventListener("click", () => {
    window.location.href = "/storefronts/dashboard";
});


function getSelectedCategories() {
    return categoryCheckboxes.filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);
}


function showCategoryValidation(message = "") {
    if (!categoryValidationMessage) return;
    categoryValidationMessage.textContent = message;
}


function validateCategoryLimit() {
    const selected = getSelectedCategories();
    if (selected.length > MAX_CATEGORY_SELECTIONS) {
        showCategoryValidation(`You can select up to ${MAX_CATEGORY_SELECTIONS} categories.`);
        return false;
    }
    showCategoryValidation("");
    return true;
}


function setupCategoryLimitGuard() {
    categoryCheckboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            if (getSelectedCategories().length > MAX_CATEGORY_SELECTIONS) {
                checkbox.checked = false;
                showCategoryValidation(`You can select up to ${MAX_CATEGORY_SELECTIONS} categories.`);
                return;
            }
            validateCategoryLimit();
        });
    });
}


function configureStorefrontStatusButton(storefront, user) {
    if (!deactivateBtn) return;

    const isActive = storefront?.is_active !== false;
    deactivateBtn.textContent = isActive ? "Deactivate" : "Reactivate";
    deactivateBtn.classList.toggle("pm-btn--danger", isActive);
    deactivateBtn.classList.toggle("pm-btn--secondary", !isActive);

    deactivateBtn.onclick = async () => {
        const action = isActive ? "deactivate" : "reactivate";
        const confirmed = confirm(`Are you sure you want to ${action} this storefront?`);
        if (!confirmed) return;

        try {
            const res = await fetch(`/api/storefronts/${storefrontId}/${action}`, {
                method: "PATCH",
                headers: {
                    "X-User-Id": user.id,
                    "X-User-Role": user.role
                }
            });

            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data.error || `Failed to ${action} storefront.`);
            }

            window.location.href = "/storefronts/dashboard";
        } catch (error) {
            VaultListingCard.showToast(error.message || `Couldn't ${action} the storefront.`, "error");
        }
    };
}


// Added by James Williams 10/26/26 - shared picker (js/image_uploader.js) and the live facade preview.
// Saved photos show in their tiles until a new file replaces them.
const { showError, clearErrors, renderFacade } = window.SellerForm;
const saved = { logo: null, banner: null, previews: [null, null, null, null] };
let imagePickers = null;

function setupImagePickers() {
    const attach = (inputId) => window.ImageUploader.attach(document.getElementById(inputId), { onChange: updateFacade });
    return {
        logo: attach("logoUpload"),
        banner: attach("bannerUpload"),
        previews: [1, 2, 3, 4].map((n) => attach(`previewImage${n}`)),
    };
}

function showSavedPhoto(zoneId, url) {
    if (!url) return;
    const zone = document.getElementById(zoneId);
    zone.classList.add("has-image");
    zone.style.setProperty("--preview-image", `url("${encodeURI(url)}")`);
}

function updateFacade() {
    const shown = (picker, url) => (picker && picker.previewUrl) || url;
    renderFacade({
        name: document.getElementById("brandName").value.trim(),
        logo: shown(imagePickers && imagePickers.logo, saved.logo),
        banner: shown(imagePickers && imagePickers.banner, saved.banner),
        images: saved.previews.map((url, i) => shown(imagePickers && imagePickers.previews[i], url)).filter(Boolean)
    });
}


async function uploadImageToS3(file, folder) {
    const uploadData = new FormData();
    uploadData.append("file", file);
    uploadData.append("folder", folder);

    const res = await fetch("/api/storefronts/upload-image", {
        method: "POST",
        body: uploadData
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload failed");
    return data.url;
}


async function loadStorefront(userId, userRole) {
    const res = await fetch(`/api/storefronts/${storefrontId}`, {
        headers: { "X-User-Id": userId, "X-User-Role": userRole }
    });

    if (!res.ok) {
        showError("formError", "This storefront couldn't be loaded. Go back to your dashboard and try again.");
        return null;
    }

    const sf = await res.json();

    document.getElementById("brandName").value = sf.brand_name || "";
    document.getElementById("storeDescription").value = sf.bio || "";
    document.getElementById("contactInfo").value = sf.contact_info || "";

    // show the current banner, logo and previews in their tiles
    saved.logo = sf.logo_url || null;
    saved.banner = sf.banner_url || null;
    saved.previews = [sf.preview_image_1, sf.preview_image_2, sf.preview_image_3, sf.preview_image_4].map((url) => url || null);
    showSavedPhoto("logoZone", saved.logo);
    showSavedPhoto("bannerZone", saved.banner);
    saved.previews.forEach((url, i) => showSavedPhoto(`previewZone${i + 1}`, url));

    // pre-check saved categories - Added by Day Ekoi 4/20/26
    if (sf.categories) {
        const saved = sf.categories.split(",").map(c => c.trim());
        saved.forEach(val => {
            const cb = document.querySelector(`input[name="categories"][value="${val}"]`);
            if (cb) cb.checked = true;
        });
        validateCategoryLimit();
    }

    return sf;
}


async function init() {
    try {
        const userRes = await fetch("/auth/api/auth/me");
        if (!userRes.ok) {
            window.location.href = "/auth/login";
            return;
        }
        const user = await userRes.json();
        const currentStorefront = await loadStorefront(user.id, user.role);
        if (!currentStorefront) return;

        imagePickers = setupImagePickers();
        document.getElementById("brandName").addEventListener("input", updateFacade);
        updateFacade();
        setupCategoryLimitGuard();
        configureStorefrontStatusButton(currentStorefront, user);

        form.addEventListener("submit", window.ImageUploader.guardSubmit(form, "Saving…", async () => {
            clearErrors(form);
            if (!document.getElementById("brandName").value.trim()) {
                showError("brandError", "Enter a storefront name.");
                document.getElementById("brandName").focus();
                return;
            }
            if (!validateCategoryLimit()) {
                return;
            }

            const logoFile = imagePickers.logo.file;
            const bannerFile = imagePickers.banner.file;

            let logoUrl = currentStorefront.logo_url;
            let bannerUrl = currentStorefront.banner_url;

            if (logoFile) {
                try { logoUrl = await uploadImageToS3(logoFile, "storefronts/logos"); }
                catch (err) { showError("formError", "The logo didn't upload. Try again."); return; }
            }

            if (bannerFile) {
                try { bannerUrl = await uploadImageToS3(bannerFile, "storefronts/banners"); }
                catch (err) { showError("formError", "The banner didn't upload. Try again."); return; }
            }

            // upload each preview slot independently, keep existing if no new file - Updated by Day Ekoi 4/20/26
            const existingPreviewUrls = [
                currentStorefront.preview_image_1,
                currentStorefront.preview_image_2,
                currentStorefront.preview_image_3,
                currentStorefront.preview_image_4,
            ];
            const previewUrls = [...existingPreviewUrls];
            for (let i = 0; i < 4; i++) {
                const file = imagePickers.previews[i].file;
                if (file) {
                    try {
                        previewUrls[i] = await uploadImageToS3(file, "storefronts/previews");
                    } catch (err) {
                        showError("formError", `Preview ${i + 1} didn't upload. Try again.`);
                        return;
                    }
                }
            }

            const formData = new FormData(form);
            const checkedCategories = Array.from(document.querySelectorAll('input[name="categories"]:checked')).map(cb => cb.value);

            const payload = {
                brand_name: formData.get("brand_name"),
                bio: formData.get("description"),
                contact_info: formData.get("contact_info"),
                logo_url: logoUrl,
                banner_url: bannerUrl,
                preview_image_1: previewUrls[0] || null,
                preview_image_2: previewUrls[1] || null,
                preview_image_3: previewUrls[2] || null,
                preview_image_4: previewUrls[3] || null,
                categories: checkedCategories.length > 0 ? checkedCategories.join(",") : null,
            };

            const res = await fetch(`/api/storefronts/${storefrontId}`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    "X-User-Id": user.id,
                    "X-User-Role": user.role
                },
                body: JSON.stringify(payload)
            });

            const data = await res.json();

            if (!res.ok) {
                showError("formError", data.error || "Your changes weren't saved. Try again.");
                return;
            }

            VaultListingCard.showToast("Changes saved");
            window.setTimeout(() => { window.location.href = "/storefronts/dashboard"; }, 700);
            return true;
        }));

    } catch (err) {
        console.error("Error initializing edit page:", err);
        showError("formError", "Couldn't reach Pirate Market. Check your connection and refresh the page.");
    }
}

init();
