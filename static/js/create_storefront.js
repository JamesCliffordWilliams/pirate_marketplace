/*
    create_storefront.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by Day Ekoi - Iteration 4 - 3/22/2026
    Updated by Day Ekoi - Iteration 5 4/9/26
    Updated by Day Ekoi - Iteration 5 4/16/26 - S3 image upload integration
    Updated by Day Ekoi - Iteration 5 - 4/20/26 - drag-drop zones, image preview thumbnails, preview_image_1-4 upload support
    Updated by James Williams - 10/26/26 - shared photo picker, one request per submit
    Updated by James Williams - 10/26/26 - redesign with a live store cover preview and errors on the page instead of pop-ups
*/

const form = document.getElementById("storefrontForm");
const cancelBtn = document.getElementById("cancelBtn");
const categoryCheckboxes = Array.from(document.querySelectorAll('input[name="categories"]'));
const categoryValidationMessage = document.getElementById("categoryValidationMessage");
const MAX_CATEGORY_SELECTIONS = 3;

cancelBtn.addEventListener("click", () => {
    window.location.href = "/storefronts";
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


// Guard: redirect away if user already has a storefront - Added by Day Ekoi 4/20/26
(async () => {
    try {
        const userRes = await fetch("/auth/api/auth/me");
        if (!userRes.ok) return;
        const user = await userRes.json();

        const sfRes = await fetch("/api/storefronts/me", {
            headers: { "X-User-Id": user.id, "X-User-Role": user.role }
        });

        if (sfRes.ok) {
            window.location.replace("/storefronts/dashboard"); // each seller only gets one storefront
        }
    } catch (err) {
        // silently allow page to load if check fails
    }
})();


// Added by James Williams 10/26/26 - the shared photo picker and the live store cover preview
const { showError, clearErrors, renderFacade } = window.SellerForm;
const brandNameInput = document.getElementById("brandName");

function setupImagePickers() {
    const attach = (inputId) => window.ImageUploader.attach(document.getElementById(inputId), { onChange: updateFacade });
    return {
        logo: attach("logoUpload"),
        banner: attach("bannerUpload"),
        previews: [1, 2, 3, 4].map((n) => attach(`previewImage${n}`)),
    };
}

function updateFacade() {
    renderFacade({
        name: brandNameInput.value.trim(),
        logo: imagePickers.logo.previewUrl,
        banner: imagePickers.banner.previewUrl,
        images: imagePickers.previews.map((picker) => picker.previewUrl).filter(Boolean)
    });
}

const imagePickers = setupImagePickers();
brandNameInput.addEventListener("input", updateFacade);
updateFacade();
setupCategoryLimitGuard();


// uploads a file to S3 via the Flask backend
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


// form submission
form.addEventListener("submit", window.ImageUploader.guardSubmit(form, "Creating…", async () => {
    clearErrors(form);
    if (!brandNameInput.value.trim()) {
        showError("brandError", "Enter a storefront name.");
        brandNameInput.focus();
        return;
    }
    if (!validateCategoryLimit()) {
        return;
    }

    try {
        const userRes = await fetch("/auth/api/auth/me");
        if (!userRes.ok) {
            window.location.href = "/auth/login";
            return true;
        }
        const user = await userRes.json();

        const formData = new FormData(form);

        // upload logo
        let logoUrl = null;
        const logoFile = imagePickers.logo.file;
        if (logoFile) {
            try { logoUrl = await uploadImageToS3(logoFile, "storefronts/logos"); }
            catch (err) { showError("formError", "The logo didn't upload. Try again."); return; }
        }

        // upload banner
        let bannerUrl = null;
        const bannerFile = imagePickers.banner.file;
        if (bannerFile) {
            try { bannerUrl = await uploadImageToS3(bannerFile, "storefronts/banners"); }
            catch (err) { showError("formError", "The banner didn't upload. Try again."); return; }
        }

        // upload 4 individual preview images - Updated by Day Ekoi 4/20/26
        const previewUrls = [null, null, null, null];
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

        const checkedCategories = Array.from(document.querySelectorAll('input[name="categories"]:checked')).map(cb => cb.value);

        const payload = {
            brand_name: formData.get("brand_name"),
            bio: formData.get("description"),
            contact_info: formData.get("contact_info") || null,
            logo_url: logoUrl,
            banner_url: bannerUrl,
            preview_image_1: previewUrls[0] || null,
            preview_image_2: previewUrls[1] || null,
            preview_image_3: previewUrls[2] || null,
            preview_image_4: previewUrls[3] || null,
            categories: checkedCategories.length > 0 ? checkedCategories.join(",") : null,
        };

        const res = await fetch("/api/storefronts", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-User-Id": user.id,
                "X-User-Role": user.role
            },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (!res.ok) {
            showError("formError", data.error || "The storefront wasn't created. Try again.");
            return;
        }

        VaultListingCard.showToast("Storefront created");
        window.setTimeout(() => { window.location.href = "/storefronts/dashboard"; }, 700);
        return true;

    } catch (err) {
        console.error("Error creating storefront:", err);
        showError("formError", "Couldn't reach Pirate Market. Check your connection and try again.");
    }
}));
