/*
    edit_storefront.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by Day Ekoi - Iteration 5 4/16/2026
    Updated by Day Ekoi - Iteration 5 - 4/20/26 - drag-drop zones, image preview thumbnails, preview_image_1-4 upload + pre-fill, existing preview image display
    Updated by James Williams - 10/26/26 - shared photo picker, one request per save

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
    deactivateBtn.classList.toggle("danger-btn", isActive);
    deactivateBtn.classList.toggle("reactivate-btn", !isActive);

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
            alert(error.message || `Could not ${action} storefront.`);
        }
    };
}


// shows existing S3 URLs as thumbnails (for pre-filled images)
function showExistingImages(containerId, urls) {
    const container = document.getElementById(containerId);
    container.innerHTML = "";
    urls.filter(Boolean).forEach((url, i) => {
        const wrap = document.createElement("div");
        wrap.className = "thumb-wrap";

        const img = document.createElement("img");
        img.src = url;
        img.alt = `Preview ${i + 1}`;

        const label = document.createElement("span");
        label.className = "thumb-name";
        label.textContent = `Preview ${i + 1}`;

        wrap.appendChild(img);
        wrap.appendChild(label);
        container.appendChild(wrap);
    });
}


// Added by James Williams 10/26/26 - shared picker (js/image_uploader.js)
function setupImagePickers() {
    const attach = (inputId, previewId) => window.ImageUploader.attach(
        document.getElementById(inputId), { preview: document.getElementById(previewId) }
    );
    return {
        logo: attach("logoUpload", "logoPreview"),
        banner: attach("bannerUpload", "bannerPreview"),
        previews: [1, 2, 3, 4].map((n) => attach(`previewImage${n}`, `previewPreview${n}`)),
    };
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
        alert("Could not load storefront data.");
        window.location.href = "/storefronts/dashboard";
        return null;
    }

    const sf = await res.json();

    document.getElementById("brandName").value = sf.brand_name || "";
    document.getElementById("storeDescription").value = sf.bio || "";
    document.getElementById("contactInfo").value = sf.contact_info || "";

    // show current banner
    if (sf.banner_url) {
        document.getElementById("bannerPreviewImg").src = sf.banner_url;
        document.getElementById("bannerCurrentPreview").style.display = "block";
    }

    // show current logo
    if (sf.logo_url) {
        document.getElementById("logoPreviewImg").src = sf.logo_url;
        document.getElementById("logoCurrentPreview").style.display = "block";
    }

    // pre-check saved categories - Added by Day Ekoi 4/20/26
    if (sf.categories) {
        const saved = sf.categories.split(",").map(c => c.trim());
        saved.forEach(val => {
            const cb = document.querySelector(`input[name="categories"][value="${val}"]`);
            if (cb) cb.checked = true;
        });
        validateCategoryLimit();
    }

    // show existing preview images in individual slots - Updated by Day Ekoi 4/20/26
    const existingPreviews = [sf.preview_image_1, sf.preview_image_2, sf.preview_image_3, sf.preview_image_4];
    existingPreviews.forEach((url, i) => {
        if (url) {
            const slotDiv = document.getElementById(`existingPreview${i + 1}`);
            const slotImg = document.getElementById(`existingImg${i + 1}`);
            if (slotDiv && slotImg) {
                slotImg.src = url;
                slotDiv.style.display = "block";
            }
        }
    });

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

        const imagePickers = setupImagePickers();
        setupCategoryLimitGuard();
        configureStorefrontStatusButton(currentStorefront, user);

        form.addEventListener("submit", window.ImageUploader.guardSubmit(form, "Saving…", async () => {
            if (!validateCategoryLimit()) {
                return;
            }

            const logoFile = imagePickers.logo.file;
            const bannerFile = imagePickers.banner.file;

            let logoUrl = currentStorefront.logo_url;
            let bannerUrl = currentStorefront.banner_url;

            if (logoFile) {
                try { logoUrl = await uploadImageToS3(logoFile, "storefronts/logos"); }
                catch (err) { alert("Failed to upload logo. Please try again."); return; }
            }

            if (bannerFile) {
                try { bannerUrl = await uploadImageToS3(bannerFile, "storefronts/banners"); }
                catch (err) { alert("Failed to upload banner. Please try again."); return; }
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
                        alert(`Failed to upload preview image ${i + 1}. Please try again.`);
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
                alert(data.error || "Failed to update storefront.");
                return;
            }

            window.location.href = "/storefronts/dashboard";
            return true;
        }));

    } catch (err) {
        console.error("Error initializing edit page:", err);
        alert("Something went wrong. Please try again.");
    }
}

init();
