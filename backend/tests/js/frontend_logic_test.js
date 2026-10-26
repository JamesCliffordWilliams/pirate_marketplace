/*
    frontend_logic_test.js

    The Vault Campus Marketplace
    Created by James Williams - 10/26/26
    Pure-logic tests for category_picker.js and listing_card.js.
    Run by tests/test_frontend_js.py with JavaScriptCore (`jsc`); no browser or DOM needed.
    Usage: jsc frontend_logic_test.js -- <repo root>
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

// normalize: case, & == and, punctuation
same(P.normalize("T-Shirts & Tops"), "t shirts and tops", "normalize ampersand + hyphen");
same(P.normalize("  MOVIES, Music  "), "movies music", "normalize case/commas/spaces");

// entries: parents become groups, Other is a top-level leaf, parents are not options
same(entries.map(function (e) { return e.type; }), ["group", "group", "leaf"], "entry types");

// search
same(matchIds(""), [2, 3, 5, 9], "empty query lists every selectable option");
same(matchIds("mac"), [2], "keyword: mac -> Laptops & Computers");
same(matchIds("ELECTRONICS"), [2, 3], "parent name matches all its leaves, case-insensitive");
same(matchIds("sandals and slides"), [5], "'and' matches '&'");
same(matchIds("sandals & slides"), [5], "'&' matches '&'");
same(matchIds("electronics phone"), [3], "every term must match");
same(matchIds("zzzz"), [], "no matches");
same(matchIds("other"), [9], "Other is searchable");

// selection: only leaves, never parents
check(P.findSelection(entries, 1) === null, "parent id is not selectable");
check(P.findSelection(entries, "4") === null, "parent id string is not selectable");
same(P.selectionPath(P.findSelection(entries, 2)), "Electronics & Technology › Laptops & Computers", "leaf path");
same(P.selectionPath(P.findSelection(entries, "9")), "Other", "Other path");
check(P.findSelection(entries, 777) === null, "unknown id");
check(P.findSelection(entries, "abc") === null, "non-numeric id");
check(P.findSelection(entries, null) === null, "null id");

// highlight chunks
same(P.highlightChunks("Laptops & Computers", "comp"),
    [{ text: "Laptops & ", match: false }, { text: "Comp", match: true }, { text: "uters", match: false }],
    "highlight substring");
same(P.highlightChunks("Sandals & Slides", "and"),
    [{ text: "S", match: false }, { text: "and", match: true }, { text: "als ", match: false },
     { text: "&", match: true }, { text: " Slides", match: false }],
    "highlight 'and' also marks '&'");
same(P.highlightChunks("Phones", ""), [{ text: "Phones", match: false }], "no query, no highlight");

// listing card helpers
var C = window.VaultListingCard;
same(C.escapeHtml('<img src=x onerror="alert(1)">&\''), "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;&amp;&#39;", "escapeHtml");
same(C.formatPrice(5), "$5.00", "price 2 decimals");
same(C.formatPrice("12.5"), "$12.50", "string price 2 decimals");
same(C.formatPrice(1234.567), "$1234.57", "price rounding");
same(C.PLACEHOLDER_IMAGE, "/static/images/listing-placeholder.svg", "placeholder path");

// ---------- mount() with a minimal fake DOM ----------
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
FakeNode.prototype.dispatchEvent = function () { return true; };
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
    addEventListener: function () {}
};
var Event = function (type) { this.type = type; };

// Edit page race: the listing's category id arrives (setValue) BEFORE the tree loads.
// When onStatusChange("ready") fires, the pending selection must already be applied,
// otherwise the edit page shows a false "category is no longer offered" note.
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

// A parent id or unknown id never becomes a value, even via setValue
picker.setValue(1);
check(!picker.hasValue() && hidden.value === "", "parent id via setValue is rejected");
picker.setValue(9);
same(hidden.value, "9", "Other via setValue");

print("OK " + passed);
