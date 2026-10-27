/*
    storefront_view.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by Day Ekoi - Iteration 4
    3/22/2026
    Updated by Day Ekoi - Iteration 5 4/9/26
    Updated by Day Ekoi - Iteration 5 - 4/20/26 - fixed wishlistIds undefined crash and isWishlisted undefined in createListingCard
    Updated by Day E - April 22nd - multi-image listing display, lightbox preview, and contain-based image handling
    Updated by James Williams - 10/26/26 - card code moved to listing_card.js; added ?listing= scroll and highlight
    Updated by James Williams - 10/26/26 - a followed ?listing= link counts as a detail_view for the Hot page

Description:
This file handles the functionality for the public storefront view page.
Fetches real storefront and listing data from the Flask API using the
storefront ID from the URL. Renders storefront banner, logo, description,
and listing cards dynamically.

Works with:
- storefront_view.html
- storefront_view.css
- listing_card.js / listing_card.css
*/

const storefrontId = window.location.pathname.split("/").pop();

const pageTitle = document.getElementById("pageTitle");
const contactInfo = document.getElementById("contactInfo");
const storeDescription = document.getElementById("storeDescription");
const storefrontLogo = document.getElementById("storefrontLogo");
const logoFallback = document.getElementById("logoFallback");
const listingGrid = document.getElementById("listingGrid");

const LISTING_HIGHLIGHT_MS = 2000;

function renderEmpty(message) {
    listingGrid.innerHTML = `<p style="color:#c9c9c9; font-style:italic; text-align:center; grid-column: 1/-1;">${message}</p>`;
}

// Added by James Williams 10/26/26
// "View in storefront" links here with ?listing=<id>: scroll to that card and highlight it
function focusLinkedListing(currentUserId) {
    const linkedId = new URLSearchParams(window.location.search).get("listing");
    if (!linkedId || !/^\d+$/.test(linkedId)) return;

    const card = document.getElementById(`listing-${linkedId}`);
    if (!card) return;

    VaultListingCard.trackDetailView(linkedId, currentUserId); // Added by James Williams 10/26/26

    const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    card.scrollIntoView({ block: "center", behavior: reduceMotion ? "auto" : "smooth" });
    card.classList.add("listing-card--highlight");
    window.setTimeout(() => card.classList.remove("listing-card--highlight"), LISTING_HIGHLIGHT_MS);
}

async function loadStorefrontView() {
    let storefront;
    try {
        const sfRes = await fetch(`/api/storefronts/${storefrontId}`);
        if (!sfRes.ok) throw new Error("Storefront not found");
        storefront = await sfRes.json();
    } catch (error) {
        console.error("Error loading storefront:", error);
        if (pageTitle) pageTitle.textContent = "Storefront Unavailable";
        storeDescription.textContent = "Could not load storefront details. Please try again.";
        renderEmpty("Could not load listings.");
        return;
    }

    if (pageTitle) pageTitle.textContent = storefront.brand_name || "Unnamed Storefront";
    storeDescription.textContent = storefront.bio || storefront.description || "No description provided.";
    contactInfo.textContent = storefront.contact_info || "";

    if (storefront.logo_url) {
        storefrontLogo.src = storefront.logo_url;
        storefrontLogo.style.display = "block";
        logoFallback.style.display = "none";
    }

    if (storefront.banner_url) {
        document.getElementById("storefrontBanner").style.backgroundImage = `url('${storefront.banner_url}')`;
        document.getElementById("storefrontBanner").style.backgroundSize = "cover";
        document.getElementById("storefrontBanner").style.backgroundPosition = "center";
    }

    const brandName = storefront.brand_name || "Unnamed Storefront";
    const sessionUser = await VaultListingCard.getCurrentSessionUser();
    const wishlistIds = await VaultListingCard.getWishlistIdSet(sessionUser?.id || null, brandName);

    try {
        const listRes = await fetch(`/api/storefronts/${storefrontId}/listings`);
        if (!listRes.ok) throw new Error("Could not load listings");
        const listings = await listRes.json();

        listingGrid.innerHTML = "";
        const activeListings = Array.isArray(listings)
            ? listings.filter((item) => item.status !== "DELETED" && item.status !== "INACTIVE")
            : [];

        if (!activeListings.length) {
            renderEmpty("No listings available for this storefront yet.");
            return;
        }

        const cards = await Promise.all(
            activeListings.map((item) => VaultListingCard.create(item, {
                wishlistIds,
                currentUserId: sessionUser?.id || null,
                storefrontName: brandName
            }))
        );
        cards.forEach((card) => listingGrid.appendChild(card));
        focusLinkedListing(sessionUser?.id || null); // Added by James Williams 10/26/26
    } catch (error) {
        console.error("Error loading listings:", error);
        renderEmpty("Could not load listings. Please try again.");
    }
}

loadStorefrontView();
