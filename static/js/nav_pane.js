/*
nav_pane.js

  The Vault Campus Marketplace
  CSC 405 Sp 26
  Created by James Williams - 10/26/26 (moved out of storefront.js, original code by Day Ekoi 3/22/26)

Description: Opens and closes the side menu. Used by every page with the shared nav.
*/

(function () {
  const menuBtn = document.querySelector(".menu-btn");
  const navPane = document.getElementById("navPane");
  const navOverlay = document.getElementById("navOverlay");

  // open menu
  if (menuBtn && navPane && navOverlay) {
    menuBtn.addEventListener("click", () => {
      navPane.classList.toggle("active");
      navOverlay.classList.toggle("active");
    });
  }

  // close when clicking overlay
  if (navOverlay && navPane) {
    navOverlay.addEventListener("click", () => {
      navPane.classList.remove("active");
      navOverlay.classList.remove("active");
    });
  }
})();
