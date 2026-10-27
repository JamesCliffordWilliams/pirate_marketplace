/*
    frontend_logic_test.js

    The Vault Campus Marketplace
    Created by James Williams - 10/26/26
    Tests the logic in category_picker.js, listing_card.js and hot.js.
    Updated by James Williams - 10/26/26 - Hot page view tracking and sections
    Updated by James Williams - 10/26/26 - photo picker type and GPS checks
    tests/test_frontend_js.py runs this with jsc, so no browser is needed.
    To run it by hand: jsc frontend_logic_test.js -- <repo root>
*/

var window = this;
var root = arguments[0];
load(root + "/static/js/category_picker.js");
load(root + "/static/js/listing_card.js");

var passed = 0;
function check(condition, message) {
    if (!condition) throw new Error("FAILED: " + message);
    passed += 1;
}
function same(actual, expected, message) {
    check(JSON.stringify(actual) === JSON.stringify(expected),
        message + " (expected " + JSON.stringify(expected) + ", got " + JSON.stringify(actual) + ")");
}

var P = window.CategoryPicker._internals;
var TREE = [
    { id: 1, name: "Electronics & Technology", is_selectable: false, keywords: [], children: [
        { id: 2, name: "Laptops & Computers", is_selectable: true, keywords: ["mac", "macbook"], children: [] },
        { id: 3, name: "Phones", is_selectable: true, keywords: ["iphone"], children: [], description: "Cell phones" }
    ] },
    { id: 4, name: "Shoes & Footwear", is_selectable: false, keywords: [], children: [
        { id: 5, name: "Sandals & Slides", is_selectable: true, keywords: [], children: [] }
    ] },
    { id: 9, name: "Other", is_selectable: true, keywords: [], children: [] }
];
var entries = P.buildEntries(TREE);

function matchIds(query) {
    var ids = [];
    P.filterEntries(entries, query).forEach(function (result) {
        result.leaves.forEach(function (leaf) { ids.push(leaf.id); });
    });
    return ids;
}

// This checks that search text ignores case and punctuation, and & matches "and"
same(P.normalize("T-Shirts & Tops"), "t shirts and tops", "normalize ampersand + hyphen");
same(P.normalize("  MOVIES, Music  "), "movies music", "normalize case/commas/spaces");

// Parent categories become groups and Other stays a normal option
same(entries.map(function (e) { return e.type; }), ["group", "group", "leaf"], "entry types");

// Search
same(matchIds(""), [2, 3, 5, 9], "empty query lists every selectable option");
same(matchIds("mac"), [2], "keyword: mac -> Laptops & Computers");
same(matchIds("ELECTRONICS"), [2, 3], "parent name matches all its leaves, case-insensitive");
same(matchIds("sandals and slides"), [5], "'and' matches '&'");
same(matchIds("sandals & slides"), [5], "'&' matches '&'");
same(matchIds("electronics phone"), [3], "every term must match");
same(matchIds("zzzz"), [], "no matches");
same(matchIds("other"), [9], "Other is searchable");

// Only the smallest categories can be picked, never a parent
check(P.findSelection(entries, 1) === null, "parent id is not selectable");
check(P.findSelection(entries, "4") === null, "parent id string is not selectable");
same(P.selectionPath(P.findSelection(entries, 2)), "Electronics & Technology › Laptops & Computers", "leaf path");
same(P.selectionPath(P.findSelection(entries, "9")), "Other", "Other path");
check(P.findSelection(entries, 777) === null, "unknown id");
check(P.findSelection(entries, "abc") === null, "non-numeric id");
check(P.findSelection(entries, null) === null, "null id");

// Highlighting the search match
same(P.highlightChunks("Laptops & Computers", "comp"),
    [{ text: "Laptops & ", match: false }, { text: "Comp", match: true }, { text: "uters", match: false }],
    "highlight substring");
same(P.highlightChunks("Sandals & Slides", "and"),
    [{ text: "S", match: false }, { text: "and", match: true }, { text: "als ", match: false },
     { text: "&", match: true }, { text: " Slides", match: false }],
    "highlight 'and' also marks '&'");
same(P.highlightChunks("Phones", ""), [{ text: "Phones", match: false }], "no query, no highlight");

// Listing card helpers
var C = window.VaultListingCard;
same(C.formatPrice(5), "$5.00", "price 2 decimals");
same(C.formatPrice("12.5"), "$12.50", "string price 2 decimals");
same(C.formatPrice(1234.567), "$1234.57", "price rounding");
same(C.PLACEHOLDER_IMAGE, "/static/images/listing-placeholder.svg", "placeholder path");

// ---------- mount() with a small fake page ----------
function FakeNode(tag) {
    this.tagName = String(tag).toUpperCase();
    this.children = []; this.attributes = {}; this.dataset = {}; this.style = {};
    this.listeners = {}; this.hidden = false; this.disabled = false; this.value = "";
    this._text = ""; this.className = "";
    var self = this;
    this.classList = {
        add: function (c) { if ((" " + self.className + " ").indexOf(" " + c + " ") < 0) self.className = (self.className + " " + c).trim(); },
        remove: function (c) { self.className = (" " + self.className + " ").replace(" " + c + " ", " ").trim(); },
        toggle: function (c, on) { if (on === undefined) on = (" " + self.className + " ").indexOf(" " + c + " ") < 0; on ? this.add(c) : this.remove(c); },
        contains: function (c) { return (" " + self.className + " ").indexOf(" " + c + " ") >= 0; }
    };
}
FakeNode.prototype.appendChild = function (n) { this.children.push(n); n.parentNode = this; return n; };
FakeNode.prototype.append = function () { for (var i = 0; i < arguments.length; i++) this.appendChild(arguments[i]); };
FakeNode.prototype.setAttribute = function (k, v) { this.attributes[k] = String(v); };
FakeNode.prototype.getAttribute = function (k) { return k in this.attributes ? this.attributes[k] : null; };
FakeNode.prototype.removeAttribute = function (k) { delete this.attributes[k]; };
FakeNode.prototype.addEventListener = function (e, f) { (this.listeners[e] = this.listeners[e] || []).push(f); };
FakeNode.prototype.insertAdjacentHTML = function () {};
FakeNode.prototype.contains = function () { return false; };
FakeNode.prototype.focus = function () {};
FakeNode.prototype.scrollIntoView = function () {};
Object.defineProperty(FakeNode.prototype, "textContent", {
    get: function () { return this._text + this.children.map(function (c) { return c.textContent; }).join(""); },
    set: function (v) { this._text = String(v); this.children = []; }
});
var document = {
    createElement: function (t) { return new FakeNode(t); },
    createTextNode: function (t) { var n = new FakeNode("#text"); n._text = String(t); return n; },
    querySelector: function () { return null; },
    getElementById: function () { return null; }, // Added by James Williams 10/26/26
    addEventListener: function () {}
};

// On the edit page the category id can show up before the category list loads.
// This makes sure it's already picked by the time "ready" fires, or the page
// wrongly says the category is no longer offered.
var seen = null;
var hidden = new FakeNode("input");
var picker = window.CategoryPicker.mount(new FakeNode("div"), {
    hiddenInput: hidden,
    autoLoad: false,
    onStatusChange: function (status) {
        if (status === "ready") seen = { hasValue: picker.hasValue(), value: picker.getValue() };
    }
});
picker.setValue(2);
picker.setTree(TREE);
same(seen, { hasValue: true, value: 2 }, "selection applied before 'ready' is announced");
same(hidden.value, "2", "hidden input holds the leaf id");
same(picker.getSelection().path, "Electronics & Technology › Laptops & Computers", "selection path after setTree");

// A parent id can't be picked through setValue either
picker.setValue(1);
check(!picker.hasValue() && hidden.value === "", "parent id via setValue is rejected");
picker.setValue(9);
same(hidden.value, "9", "Other via setValue");

// ---------- detail_view tracking (listing_card.js) ----------
// Added by James Williams 10/26/26
var fetchCalls = [];
window.fetch = function (url, options) {
    fetchCalls.push({ url: url, options: options });
    return Promise.resolve({ ok: true });
};
check(C.trackDetailView(5, null) === false, "logged out: no detail_view");
same(fetchCalls.length, 0, "logged out: nothing sent");
check(C.trackDetailView(5, 7) === true, "first lightbox open sends");
same(fetchCalls[0].url, "/api/listings/5/interest", "interest url");
same(fetchCalls[0].options.method, "POST", "POST");
same(fetchCalls[0].options.keepalive, true, "keepalive");
same(fetchCalls[0].options.headers["Content-Type"], "application/json", "JSON content type");
same(JSON.parse(fetchCalls[0].options.body), { kind: "detail_view" }, "detail_view body");
check(C.trackDetailView(5, 7) === false, "second open of the same listing is ignored");
check(C.trackDetailView("5", 7) === false, "same listing as a string is ignored");
check(C.trackDetailView(6, 7) === true, "a different listing sends");
check(C.trackDetailView("abc", 7) === false, "bad id");
check(C.trackDetailView(0, 7) === false, "zero id");
same(fetchCalls.length, 2, "one request per listing per page load");

// ---------- Hot page section states (hot.js) ----------
// Added by James Williams 10/26/26
load(root + "/static/js/hot.js");
var H = window.VaultHot._internals;
function items(n) { var list = []; for (var i = 0; i < n; i++) list.push({ id: i + 1 }); return list; }
same(H.sectionStates({ hot: [], rising: [] }),
    { page: "empty", hot: "hidden", rising: "hidden" }, "everything empty");
same(H.sectionStates(null),
    { page: "empty", hot: "hidden", rising: "hidden" }, "no data counts as empty");
same(H.sectionStates({ hot: items(2), rising: [] }),
    { page: "content", hot: "cards", rising: "collapsed" }, "only Hot");
same(H.sectionStates({ hot: items(4), rising: items(1) }),
    { page: "content", hot: "cards", rising: "cards" }, "full page");
same(H.sectionStates({ hot: [], rising: items(1) }),
    { page: "content", hot: "collapsed", rising: "cards" }, "only Rising");

// ---------- photo picker (image_uploader.js) ----------
// Added by James Williams 10/26/26
load(root + "/static/js/image_uploader.js");
var U = window.ImageUploader._internals;
same(U.imageType({ name: "a.jpg", type: "image/jpeg" }), "image/jpeg", "jpeg by type");
same(U.imageType({ name: "a.PNG", type: "" }), "image/png", "png by extension when type is empty");
same(U.imageType({ name: "a.webp", type: "image/webp" }), "image/webp", "webp");
same(U.imageType({ name: "a.gif", type: "image/gif" }), "image/gif", "gif");
same(U.imageType({ name: "IMG_1.HEIC", type: "image/heic" }), null, "heic refused");
same(U.imageType({ name: "IMG_1.heic", type: "" }), null, "heic by extension refused");
same(U.imageType({ name: "a.svg", type: "image/svg+xml" }), null, "svg refused");
same(U.imageType({ name: "a.jpg", type: "application/pdf" }), null, "type wins over extension");

// This builds a tiny fake JPEG, with or without one photo info tag
function jpeg(tag, littleEndian) {
    var b = [0xFF, 0xD8];
    if (tag) {
        var tiff = littleEndian
            ? [0x49, 0x49, 0x2A, 0x00, 8, 0, 0, 0, 1, 0, tag & 0xFF, tag >> 8, 4, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            : [0x4D, 0x4D, 0x00, 0x2A, 0, 0, 0, 8, 0, 1, tag >> 8, tag & 0xFF, 0, 4, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0];
        var body = [0x45, 0x78, 0x69, 0x66, 0, 0].concat(tiff);
        var len = body.length + 2;
        b = b.concat([0xFF, 0xE1, len >> 8, len & 0xFF]).concat(body);
    }
    b = b.concat([0xFF, 0xDB, 0x00, 0x04, 0x00, 0x00, 0xFF, 0xDA, 0x00, 0x02]);
    return new Uint8Array(b).buffer;
}
same(U.jpegHasGps(jpeg(0x8825, true)), true, "GPS tag found (little endian)");
same(U.jpegHasGps(jpeg(0x8825, false)), true, "GPS tag found (big endian)");
same(U.jpegHasGps(jpeg(0x0112, true)), false, "orientation only: no GPS");
same(U.jpegHasGps(jpeg(0)), false, "no EXIF: no GPS");
same(U.jpegHasGps(jpeg(0x0112, true).slice(0, 12)), true, "cut-off metadata is treated as GPS");
same(U.jpegHasGps(new Uint8Array([0x89, 0x50]).buffer), true, "not a JPEG is treated as GPS");

// ---------- saved listings kept in the browser (listing_card.js) ----------
// If the wishlist doesn't load, the hearts use the ids saved in the browser last time
var stored = {};
var localStorage = {
    getItem: function (key) { return key in stored ? stored[key] : null; },
    setItem: function (key, value) { stored[key] = String(value); }
};
var console = { error: function () {} };
function reply(ok, body) {
    return Promise.resolve({ ok: ok, status: ok ? 200 : 500, json: function () { return Promise.resolve(body); } });
}
window.fetch = function () { return reply(true, { wishlist: [{ listing_id: 5 }, { id: 7 }] }); };
C.getWishlistIdSet(1).then(function (ids) {
    same(Array.from(ids), ["5", "7"], "wishlist ids come back as strings");
    return C.setSaved(9, 1, true);
}).then(function () {
    return C.setSaved(5, 1, false);
}).then(function () {
    window.fetch = function () { return reply(false, {}); };
    return C.getWishlistIdSet(1);
}).then(function (ids) {
    same(Array.from(ids), ["9", "7"], "saving and unsaving update the ids kept in the browser");
    return C.getWishlistIdSet(null);
}).then(function (ids) {
    same(ids.size, 0, "logged out: nothing saved");
    print("OK " + passed);
}).catch(function (error) {
    print(error.message);
});
