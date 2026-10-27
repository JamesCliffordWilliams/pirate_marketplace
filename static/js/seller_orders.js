/*
    seller_orders.js

    Pirate Market Campus Marketplace
    Created by Aniya Hopson - 10/27/26

Description:
Shows the Incoming Orders section on the seller dashboard (my_storefront.html)
and lets the seller mark an order picked up.

Buyer-typed text is added with textContent (not innerHTML), so a name like
<script>... shows as plain text instead of running as code.
*/

const ordersList = document.getElementById("ordersList");
const ordersMessage = document.getElementById("ordersMessage");


// Small helper: makes an element with a class and text
function makeEl(tag, className, text) {
    const el = document.createElement(tag);
    el.className = className;
    el.textContent = text;
    return el;
}


function showOrder(order) {
    const card = makeEl("div", "order-card", "");

    card.appendChild(makeEl("p", "order-number", `${order.confirmation_number}  ·  ${order.order_status}`));
    card.appendChild(makeEl("p", "order-line", `Buyer: ${order.buyer_name}  ·  ${order.buyer_contact}`));
    card.appendChild(makeEl("p", "order-line", `Meeting spot: ${order.buyer_meeting_location}`));

    order.items.forEach((item) => {
        const size = item.selected_size ? ` (size ${item.selected_size})` : "";
        const done = item.picked_up ? "  ✓ picked up" : "";
        card.appendChild(makeEl("p", "order-item", `${item.quantity} × ${item.item_name}${size}${done}`));
    });

    // Only open orders where this seller still has items to hand over get a button
    const waiting = order.items.some((item) => !item.picked_up);
    if (order.order_status === "SUBMITTED" && waiting) {
        card.appendChild(makeEl("p", "order-deadline", `Pick up by ${order.pickup_by}`));

        const button = makeEl("button", "action-btn", "Mark as Picked Up");
        button.addEventListener("click", () => markPickedUp(order));
        card.appendChild(button);
    }

    ordersList.appendChild(card);
}


async function loadOrders() {
    const res = await fetch("/api/seller/orders");
    const data = await res.json();

    if (!res.ok) {
        ordersMessage.textContent = data.error || "Unable to load orders.";
        return;
    }

    ordersList.innerHTML = "";
    ordersMessage.textContent = data.orders.length ? "" : "No orders yet.";
    data.orders.forEach(showOrder);
}


async function markPickedUp(order) {
    if (!confirm(`Did you hand over the items for order ${order.confirmation_number}?`)) return;

    const res = await fetch(`/api/seller/orders/${order.id}/complete`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) alert(data.error);

    loadOrders();  // refresh the list
}


loadOrders();