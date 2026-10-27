/*
nav_pane.js

  The Vault Campus Marketplace
  CSC 405 Sp 26
  Created by James Williams - 10/26/26 (moved out of storefront.js, original code by Day Ekoi 3/22/26)
  Updated by James Williams - 10/26/26 - drawer for the new header: Esc, overlay click, focus trap,
  scroll lock, focus goes back to the menu button

Description: Opens and closes the menu drawer. Used by every page with the shared nav.
*/

(function () {
  const menuBtn = document.querySelector(".menu-btn");
  const navPane = document.getElementById("navPane");
  const navOverlay = document.getElementById("navOverlay");
  if (!menuBtn || !navPane || !navOverlay) return;

  const FOCUSABLE = "a[href], button:not([disabled]), input, select, textarea";
  let closeTimer = null;

  function isOpen() {
    return menuBtn.getAttribute("aria-expanded") === "true";
  }

  function setOpen(open) {
    window.clearTimeout(closeTimer);
    menuBtn.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("pm-scroll-locked", open);
    if (open) {
      navPane.hidden = navOverlay.hidden = false;
      // next frame, so the slide-in transition runs
      window.requestAnimationFrame(() => {
        navPane.dataset.open = navOverlay.dataset.open = "true";
        navPane.querySelector(FOCUSABLE).focus();
      });
    } else {
      navPane.dataset.open = navOverlay.dataset.open = "false";
      closeTimer = window.setTimeout(() => { navPane.hidden = navOverlay.hidden = true; }, 250);
      menuBtn.focus();
    }
  }

  menuBtn.addEventListener("click", () => setOpen(!isOpen()));
  navOverlay.addEventListener("click", () => setOpen(false));
  navPane.querySelector("[data-nav-close]").addEventListener("click", () => setOpen(false));

  document.addEventListener("keydown", (event) => {
    if (!isOpen()) return;
    if (event.key === "Escape") {
      setOpen(false);
      return;
    }
    if (event.key !== "Tab") return;
    // keep Tab inside the drawer
    const items = Array.from(navPane.querySelectorAll(FOCUSABLE));
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  // the drawer is only for narrow screens; close it if the window gets wide
  window.matchMedia("(min-width: 900px)").addEventListener("change", (query) => {
    if (query.matches && isOpen()) setOpen(false);
  });
})();
