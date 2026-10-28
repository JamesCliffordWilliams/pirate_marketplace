/*
    checkout.js
    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Updated by Day Ekoi - 4/22/26
    - Reads cart from session via /auth/cart/json
    - Displays items with size, qty, and subtotals
    - Submits buyer details to /api/checkout/complete
    - Redirects to order confirmation on success
    Updated by James Williams - 10/26/26 - redesign, the item rows are added as plain text and the wording is simpler
*/

document.addEventListener("DOMContentLoaded", async () => {
    const itemsList = document.getElementById("checkoutItemsList");
    const totalDisplay = document.querySelector(".total-amount");
    const submitBtn = document.getElementById("submitCheckoutBtn");
    const errorMsg = document.getElementById("checkoutError");

    function showError(msg) {
        if (!errorMsg) return;
        errorMsg.textContent = msg;
        errorMsg.style.display = "block";
        errorMsg.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideError() {
        if (errorMsg) errorMsg.style.display = "none";
    }

    // Load cart from Flask session
    let cart = [];
    try {
        const res = await fetch("/auth/cart/json");
        if (res.ok) cart = await res.json();
    } catch (e) {
        console.error("Failed to load cart:", e);
    }

    if (!Array.isArray(cart) || cart.length === 0) {
        if (itemsList) {
            const empty = document.createElement("p");
            empty.className = "pm-muted";
            empty.textContent = "Your bag is empty. ";
            const link = document.createElement("a");
            link.href = "/storefronts";
            link.textContent = "Browse storefronts";
            empty.appendChild(link);
            itemsList.replaceChildren(empty);
        }
        if (totalDisplay) totalDisplay.textContent = "$0.00";
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Your bag is empty";
        }
        return;
    }

    // Render cart items in order summary
    let total = 0;
    if (itemsList) {
        itemsList.replaceChildren();
        cart.forEach((item) => {
            const price = parseFloat(item.price || 0);
            const qty = parseInt(item.quantity || 1, 10);
            const subtotal = price * qty;
            total += subtotal;

            const row = document.createElement("div");
            row.className = "pm-summary__item";
            const info = document.createElement("div");
            const name = document.createElement("span");
            name.className = "pm-summary__name";
            name.textContent = item.name || "Item";
            const meta = document.createElement("span");
            meta.className = "pm-muted";
            const size = item.size === "One Size" ? "One size" : (item.size ? `Size ${item.size}` : "");
            meta.textContent = [size, `Qty ${qty}`].filter(Boolean).join(", ");
            info.append(name, meta);
            const amount = document.createElement("span");
            amount.className = "pm-price";
            amount.textContent = `$${subtotal.toFixed(2)}`;
            row.append(info, amount);
            itemsList.appendChild(row);
        });
    }

    if (totalDisplay) totalDisplay.textContent = `$${total.toFixed(2)}`;

    // Handle form submission
    const form = document.getElementById("checkoutForm");
    if (!form) return;

    let placing = false; // stops the same order from being placed twice if the button gets double clicked
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (placing) return;
        hideError();

        const firstName = (document.getElementById("firstName")?.value || "").trim();
        const lastName = (document.getElementById("lastName")?.value || "").trim();
        const email = (document.getElementById("buyerEmail")?.value || "").trim();
        const contact = (document.getElementById("contactNumber")?.value || "").trim();
        const meetingLocation = (document.getElementById("meetingLocation")?.value || "").trim();

        if (!firstName || !lastName || !email || !contact || !meetingLocation) {
            showError("Fill in every field so the seller can reach you.");
            return;
        }

        placing = true;
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = "Placing order…";
        }

        try {
            const res = await fetch("/api/checkout/complete", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    first_name: firstName,
                    last_name: lastName,
                    email,
                    contact,
                    meeting_location: meetingLocation,
                }),
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.error || "Your order wasn't placed. Try again.");
            }

            window.location.href = `/order-confirmation?conf=${encodeURIComponent(data.confirmation_number)}`;
        } catch (err) {
            showError(err.message || "Your order wasn't placed. Try again.");
            placing = false;
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.textContent = "Place order";
            }
        }
    });
});
