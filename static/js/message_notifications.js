/*
 * Pirate Market - Message Notifications
 * CJ Hyacinth
 *
 * Displays unread-message counts in the desktop
 * and mobile navigation menus.
 */

(() => {
    const badges = document.querySelectorAll("[data-message-count]");

    if (!badges.length) return;

    // Update both navigation badges with the unread count.
    function updateBadges(count) {
        badges.forEach((badge) => {
            badge.textContent = count > 99 ? "99+" : String(count);
            badge.hidden = count === 0;
            badge.setAttribute(
                "aria-label",
                `${count} unread messages`
            );
        });
    }

    // Retrieve the unread count from the existing messaging API.
    async function checkUnreadMessages() {
        try {
            const response = await fetch("/api/messages/unread-count", {
                credentials: "same-origin",
                cache: "no-store"
            });

            if (!response.ok) {
                updateBadges(0);
                return;
            }

            const data = await response.json();
            const count = Math.max(0, Number(data.unread) || 0);

            updateBadges(count);
        } catch (error) {
            console.error("Unable to check message notifications:", error);
            updateBadges(0);
        }
    }

    // Check immediately and every 10 seconds while the page is visible.
    checkUnreadMessages();

    setInterval(() => {
        if (!document.hidden) {
            checkUnreadMessages();
        }
    }, 10000);

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) checkUnreadMessages();
    });
})();
