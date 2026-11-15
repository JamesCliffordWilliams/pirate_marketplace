/*
    new_message.js

    Pirate Market
    Created by Aniya Hopson - 10/27/26

    Runs the pencil (New Message) button on the Messages page.
   
*/

(function () {
  "use strict";

  const button = document.getElementById("composeBtn");
  const sheet = document.getElementById("newMessageSheet");
  const cancel = document.getElementById("newMessageCancel");
  const search = document.getElementById("recipientSearch");
  const status = document.getElementById("recipientStatus");
  const list = document.getElementById("recipientList");

  // Stop early with a clear message if the HTML is missing a piece
  if (!button || !sheet || !cancel || !search || !status || !list) {
    console.error("New Message: an element is missing from messages.html (check the ids).");
    return;
  }

  let brands = null; // loaded the first time the pencil is clicked

  async function loadBrands() {
    if (brands) return;

    const [meResponse, brandResponse] = await Promise.all([
      fetch("/auth/api/auth/me"),
      fetch("/api/storefronts"),
    ]);
    if (!brandResponse.ok) throw new Error("Could not load student brands. Please try again.");

    const me = meResponse.ok ? await meResponse.json() : {};
    const data = await brandResponse.json();

    brands = (Array.isArray(data) ? data : [])
      .filter((brand) => brand.owner_id !== me.id) // can't message your own brand
      .sort((a, b) => (a.brand_name || "").localeCompare(b.brand_name || ""));
  }

  function showBrands() {
    const query = search.value.trim().toLowerCase();
    const matches = brands.filter((brand) => (brand.brand_name || "").toLowerCase().includes(query));

    list.replaceChildren();
    status.hidden = matches.length > 0;
    status.textContent = query ? `No brands match "${search.value.trim()}".` : "No other student brands yet.";

    matches.forEach((brand) => {
      const choose = document.createElement("button");
      choose.type = "button";
      choose.className = "msg-recipient";
      choose.textContent = brand.brand_name;
      choose.addEventListener("click", () => {
        window.location.href = `/messages?to=${brand.owner_id}`;
      });

      const item = document.createElement("li");
      item.append(choose);
      list.append(item);
    });
  }

  button.addEventListener("click", async () => {
    search.value = "";
    list.replaceChildren();
    status.textContent = "Loading brands...";
    status.hidden = false;
    sheet.showModal();
    search.focus();

    try {
      await loadBrands();
      showBrands();
    } catch (error) {
      status.textContent = error.message;
    }
  });

  cancel.addEventListener("click", () => sheet.close());

  // Clicking the dark area outside the sheet closes it
  sheet.addEventListener("click", (event) => {
    if (event.target === sheet) sheet.close();
  });

  search.addEventListener("input", () => {
    if (brands) showBrands();
  });
})();