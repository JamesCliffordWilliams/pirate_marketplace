/*
    returns.js

    Handles return form interactions and submission.
    Updated by James Williams - 10/26/26 - shared photo picker, one request per submit
*/

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("returnsForm");
    const cancelBtn = document.getElementById("cancelBtn");
    const backBtn = document.getElementById("backBtn");
    const damageInput = document.getElementById("damageImage");
    const damagePreview = document.getElementById("damagePreview");
    const feedback = document.getElementById("returnsFeedback");

    function showFeedback(message, tone = "success") {
        if (!feedback) return;
        feedback.textContent = message;
        feedback.classList.toggle("error", tone === "error");
        feedback.style.display = "block";
    }

    function clearFeedback() {
        if (!feedback) return;
        feedback.textContent = "";
        feedback.classList.remove("error");
        feedback.style.display = "none";
    }

    // Added by James Williams 10/26/26 - shared picker (js/image_uploader.js)
    const damagePicker = damageInput
        ? window.ImageUploader.attach(damageInput, { preview: damagePreview })
        : null;

    if (cancelBtn) {
        cancelBtn.addEventListener("click", () => {
            window.location.href = "/storefronts";
        });
    }

    if (backBtn) {
        backBtn.addEventListener("click", () => {
            window.location.href = "/storefronts";
        });
    }

    if (!form) return;

    form.addEventListener("submit", window.ImageUploader.guardSubmit(form, "Submitting…", async () => {
        clearFeedback();

        try {
            const userRes = await fetch("/auth/api/auth/me");
            if (!userRes.ok) {
                window.location.href = "/auth/login";
                return;
            }

            const user = await userRes.json();
            const formData = new FormData(form);
            formData.delete("damage_image");
            if (damagePicker && damagePicker.file) formData.append("damage_image", damagePicker.file);

            const response = await fetch("/returns", {
                method: "POST",
                headers: {
                    "X-User-Id": user.id,
                    "X-User-Role": user.role
                },
                body: formData
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || "Failed to submit return.");
            }

            form.reset();
            if (damagePicker) damagePicker.clear();
            showFeedback("Return submitted successfully");
        } catch (error) {
            console.error("Error submitting return:", error);
            showFeedback(error.message || "Something went wrong while submitting your return.", "error");
        }
    }));
});
