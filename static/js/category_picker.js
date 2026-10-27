/*
    category_picker.js

    The Vault Campus Marketplace
    CSC 405 Sp 26'
    Created by James Williams - 10/26/26

Description:
This is the category search box on the Create Listing and Edit Listing forms.
Sellers can only pick a subcategory or "Other", not a main category.
You type to search, use the arrow keys to move, Enter to pick and Escape to close.
Pages add it with CategoryPicker.mount(element, options).

Works with:
- category_picker.css
- create_listing.js, edit_listing.js
*/

(function () {
    const PATH_SEPARATOR = " › ";
    let pickerCount = 0;

    // ________________________________________________________
    // HELPERS (also used by the tests)
    // ________________________________________________________

    // Makes text easy to compare: lowercase, "&" becomes "and"
    function normalize(text) {
        return String(text || "")
            .toLowerCase()
            .replace(/&/g, " and ")
            .replace(/[^a-z0-9]+/g, " ")
            .trim();
    }

    // Turns the category tree into the list the picker shows.
    // Main categories become groups, and a category with no children (like Other) is a normal option
    function buildEntries(tree) {
        const entries = [];
        (tree || []).forEach((node) => {
            const children = Array.isArray(node.children) ? node.children : [];
            if (children.length) {
                entries.push({ type: "group", node, leaves: children.filter((child) => child.is_selectable !== false) });
            } else if (node.is_selectable !== false) {
                entries.push({ type: "leaf", node });
            }
        });
        return entries;
    }

    // Returns the categories that match the search. Every search word has to be in the
    // category name, its main category name, or its keywords
    function filterEntries(entries, query) {
        const searchText = normalize(query);
        const terms = searchText ? searchText.split(" ") : [];
        const matches = (leaf, parent) => {
            const haystack = [normalize(leaf.name), parent ? normalize(parent.name) : "", ...(leaf.keywords || []).map(normalize)].join(" | ");
            return terms.every((term) => haystack.includes(term));
        };

        const results = [];
        entries.forEach((entry) => {
            if (entry.type === "group") {
                const leaves = entry.leaves.filter((leaf) => matches(leaf, entry.node));
                if (leaves.length) results.push({ entry, leaves });
            } else if (matches(entry.node, null)) {
                results.push({ entry, leaves: [entry.node] });
            }
        });
        return results;
    }

    // Finds the option with this id. Main categories can't be picked, so they return null
    function findSelection(entries, id) {
        const wanted = Number(id);
        if (!Number.isInteger(wanted) || wanted <= 0) return null;
        for (const entry of entries) {
            if (entry.type === "group") {
                const leaf = entry.leaves.find((child) => Number(child.id) === wanted);
                if (leaf) return { leaf, parent: entry.node };
            } else if (Number(entry.node.id) === wanted) {
                return { leaf: entry.node, parent: null };
            }
        }
        return null;
    }

    function selectionPath(selection) {
        if (!selection) return "";
        return selection.parent ? `${selection.parent.name}${PATH_SEPARATOR}${selection.leaf.name}` : selection.leaf.name;
    }

    // Splits text so the matching part can be highlighted. Searching "and" also marks "&" and the other way around
    function highlightChunks(text, query) {
        const raw = String(text || "");
        const terms = String(query || "")
            .toLowerCase()
            .split(/\s+/)
            .map((term) => term.replace(/[^a-z0-9&]/g, ""))
            .filter(Boolean);
        if (!terms.length) return [{ text: raw, match: false }];

        const lower = raw.toLowerCase();
        const marks = new Array(raw.length).fill(false);
        terms.forEach((term) => {
            const variants = term === "and" || term === "&" ? ["and", "&"] : [term];
            variants.forEach((variant) => {
                let at = lower.indexOf(variant);
                while (at !== -1) {
                    marks.fill(true, at, at + variant.length);
                    at = lower.indexOf(variant, at + variant.length);
                }
            });
        });

        const chunks = [];
        for (let i = 0; i < raw.length; i += 1) {
            const last = chunks[chunks.length - 1];
            if (last && last.match === marks[i]) {
                last.text += raw[i];
            } else {
                chunks.push({ text: raw[i], match: marks[i] });
            }
        }
        return chunks;
    }

    // ________________________________________________________
    // DOM HELPERS
    // ________________________________________________________

    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    // Fills the element with the text and puts <mark> around the parts that match the search
    function appendHighlighted(container, text, query) {
        container.textContent = "";
        highlightChunks(text, query).forEach((chunk) => {
            container.appendChild(chunk.match ? el("mark", "cp-mark", chunk.text) : document.createTextNode(chunk.text));
        });
    }

    const CHEVRON_SVG = '<svg class="cp-chevron" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

    // ________________________________________________________
    // MOUNT
    // options.hiddenInput gets the picked id, options.onChange runs when the seller picks one,
    // options.onStatusChange gets "loading", "ready" or "error", and autoLoad: false skips loading the list (for tests)
    // ________________________________________________________

    function mount(rootEl, options = {}) {
        pickerCount += 1;
        const uid = `cp${pickerCount}`;
        const hiddenInput = options.hiddenInput;
        const onChange = options.onChange || (() => {});
        const onStatusChange = options.onStatusChange || (() => {});

        let entries = [];
        let selection = null;
        let pendingId = hiddenInput.value || null; // an id set before the list loads
        let status = "loading";
        let isOpen = false;
        let query = "";
        let activeOptionId = null; // id of the highlighted option
        const expandedGroups = new Set();
        let optionEls = []; // the options you can reach with the arrow keys right now

        // ---------- build the picker ----------
        rootEl.classList.add("cp");
        rootEl.textContent = "";

        const trigger = el("button", "cp-trigger");
        trigger.type = "button";
        trigger.id = `${uid}-trigger`;
        trigger.setAttribute("aria-haspopup", "listbox");
        trigger.setAttribute("aria-expanded", "false");
        trigger.setAttribute("aria-controls", `${uid}-popup`);
        const triggerText = el("span", "cp-trigger-text", "Select a category");
        trigger.appendChild(triggerText);
        trigger.insertAdjacentHTML("beforeend", CHEVRON_SVG);

        // Connect the form label to the picker button
        const labelEl = rootEl.id ? document.querySelector(`label[for="${rootEl.id}"]`) : null;
        if (labelEl) {
            labelEl.id = labelEl.id || `${uid}-label`;
            labelEl.htmlFor = trigger.id;
            trigger.setAttribute("aria-labelledby", `${labelEl.id} ${trigger.id}`);
        }

        const helper = el("p", "cp-helper");
        helper.id = `${uid}-helper`;
        helper.hidden = true;

        const statusBox = el("div", "cp-status");
        statusBox.id = `${uid}-status`;
        statusBox.setAttribute("aria-live", "polite");

        const errorBox = el("p", "cp-error");
        errorBox.id = `${uid}-error`;
        errorBox.setAttribute("role", "alert");
        errorBox.hidden = true;

        const popup = el("div", "cp-popup");
        popup.id = `${uid}-popup`;
        popup.hidden = true;

        const search = el("input", "cp-search");
        search.type = "text";
        search.id = `${uid}-search`;
        search.autocomplete = "off";
        search.spellcheck = false;
        search.placeholder = "Search categories (e.g. sneakers, mac, textbook)";
        search.setAttribute("role", "combobox");
        search.setAttribute("aria-label", "Search categories");
        search.setAttribute("aria-autocomplete", "list");
        search.setAttribute("aria-expanded", "false");
        search.setAttribute("aria-controls", `${uid}-list`);

        const list = el("div", "cp-list");
        list.id = `${uid}-list`;
        list.setAttribute("role", "listbox");
        list.setAttribute("aria-label", "Categories");

        popup.append(search, list);

        // Keeps the dropdown right under the button
        const anchor = el("div", "cp-anchor");
        anchor.append(trigger, popup);
        rootEl.append(anchor, helper, statusBox, errorBox);

        // ---------- status ----------
        function setStatus(next) {
            status = next;
            statusBox.textContent = "";
            trigger.disabled = next !== "ready";
            rootEl.classList.toggle("cp--loading", next === "loading");
            rootEl.classList.toggle("cp--failed", next === "error");

            if (next === "loading") {
                statusBox.appendChild(el("span", "cp-status-text", "Loading categories…"));
            } else if (next === "error") {
                statusBox.appendChild(el("span", "cp-status-text cp-status-text--error", "Couldn't load categories."));
                const retry = el("button", "cp-retry", "Retry");
                retry.type = "button";
                retry.addEventListener("click", load);
                statusBox.appendChild(retry);
            }
            onStatusChange(next);
        }

        // ---------- selection and errors ----------
        // Screen readers read the description and the error, but only the ones that are showing
        function updateDescribedBy() {
            const ids = [helper, errorBox].filter((box) => !box.hidden).map((box) => box.id).join(" ");
            if (ids) {
                trigger.setAttribute("aria-describedby", ids);
            } else {
                trigger.removeAttribute("aria-describedby");
            }
        }

        function setError(message) {
            errorBox.textContent = message || "";
            errorBox.hidden = !message;
            trigger.setAttribute("aria-invalid", message ? "true" : "false");
            rootEl.classList.toggle("cp--invalid", Boolean(message));
            updateDescribedBy();
        }

        function applySelection(next) {
            selection = next;
            hiddenInput.value = selection ? String(selection.leaf.id) : "";

            triggerText.textContent = selection ? selectionPath(selection) : "Select a category";
            trigger.classList.toggle("cp-trigger--placeholder", !selection);
            const description = selection && selection.leaf.description;
            helper.textContent = description || "";
            helper.hidden = !description;
            updateDescribedBy();

            if (selection) setError("");
        }

        function setValue(id) {
            if (status !== "ready") {
                pendingId = id;
                return;
            }
            applySelection(findSelection(entries, id));
        }

        // ---------- list ----------
        const hasQuery = () => normalize(query) !== "";
        const findOption = (optionId) => optionEls.find((item) => item.el.id === optionId);

        function addOption(container, leaf, parent, extraClass) {
            const option = el("div", extraClass ? `cp-option ${extraClass}` : "cp-option");
            option.id = `${uid}-opt-${leaf.id}`;
            option.setAttribute("role", "option");
            const isSelected = Boolean(selection && Number(selection.leaf.id) === Number(leaf.id));
            option.setAttribute("aria-selected", isSelected ? "true" : "false");
            option.dataset.id = String(leaf.id);
            appendHighlighted(option, leaf.name, query);

            option.addEventListener("mousedown", (event) => event.preventDefault()); // keeps the cursor in the search box
            option.addEventListener("click", () => choose({ leaf, parent }));
            option.addEventListener("mousemove", () => setActive(option.id, false));
            container.appendChild(option);
            optionEls.push({ el: option, leaf, parent });
        }

        function renderList() {
            list.textContent = "";
            optionEls = [];
            const results = filterEntries(entries, query);

            results.forEach(({ entry, leaves }) => {
                if (entry.type === "leaf") {
                    addOption(list, entry.node, null, "cp-option--top");
                    return;
                }
                const groupId = `${uid}-group-${entry.node.id}`;
                const expanded = hasQuery() || expandedGroups.has(entry.node.id);

                const group = el("div", "cp-group");
                group.setAttribute("role", "group");
                group.setAttribute("aria-labelledby", `${groupId}-label`);

                const header = el("div", "cp-group-header");
                header.id = `${groupId}-label`;
                header.setAttribute("aria-expanded", expanded ? "true" : "false");
                const headerText = el("span", "cp-group-name");
                appendHighlighted(headerText, entry.node.name, query);
                header.appendChild(headerText);
                header.appendChild(el("span", "cp-group-count", String(leaves.length)));
                header.insertAdjacentHTML("beforeend", CHEVRON_SVG);
                header.addEventListener("mousedown", (event) => event.preventDefault());
                header.addEventListener("click", () => toggleGroup(entry.node.id));

                const body = el("div", "cp-group-options");
                body.hidden = !expanded;
                leaves.forEach((leaf) => addOption(body, leaf, entry.node));

                group.append(header, body);
                list.appendChild(group);
            });

            if (!results.length) {
                const empty = el("p", "cp-empty", "No matching categories. Try a broader term or choose Other.");
                empty.setAttribute("role", "presentation");
                list.appendChild(empty);
                // Keep "Other" one click away when nothing matches
                entries.filter((entry) => entry.type === "leaf").forEach((entry) => addOption(list, entry.node, null, "cp-option--top"));
            }

            // keep the active option if it is still listed
            setActive(findOption(activeOptionId) ? activeOptionId : null, false);
        }

        function toggleGroup(nodeId) {
            if (expandedGroups.has(nodeId)) {
                expandedGroups.delete(nodeId);
            } else {
                expandedGroups.add(nodeId);
            }
            renderList();
        }

        function setActive(optionId, scroll) {
            optionEls.forEach((item) => item.el.classList.toggle("is-active", item.el.id === optionId));
            activeOptionId = optionId;
            search.setAttribute("aria-activedescendant", optionId || "");
            const item = findOption(optionId);
            if (item && scroll) item.el.scrollIntoView({ block: "nearest" });
        }

        function moveActive(step) {
            if (!optionEls.length) return;
            let index = optionEls.findIndex((item) => item.el.id === activeOptionId);
            if (index === -1) {
                index = step > 0 ? 0 : optionEls.length - 1;
            } else {
                index = (index + step + optionEls.length) % optionEls.length;
            }
            const item = optionEls[index];
            // Open a closed group when the arrow keys reach it
            if (item.parent && !hasQuery() && !expandedGroups.has(item.parent.id)) {
                expandedGroups.add(item.parent.id);
                activeOptionId = item.el.id;
                renderList();
            }
            setActive(item.el.id, true);
        }

        // ---------- open / close ----------
        function open() {
            if (status !== "ready" || isOpen) return;
            isOpen = true;
            query = "";
            search.value = "";
            expandedGroups.clear();
            if (selection && selection.parent) expandedGroups.add(selection.parent.id);
            activeOptionId = selection ? `${uid}-opt-${selection.leaf.id}` : null;

            popup.hidden = false;
            rootEl.classList.add("cp--open");
            trigger.setAttribute("aria-expanded", "true");
            search.setAttribute("aria-expanded", "true");
            renderList();
            search.focus();
            const item = findOption(activeOptionId);
            if (item) item.el.scrollIntoView({ block: "nearest" });
        }

        function close(returnFocus) {
            if (!isOpen) return;
            isOpen = false;
            popup.hidden = true;
            rootEl.classList.remove("cp--open");
            trigger.setAttribute("aria-expanded", "false");
            search.setAttribute("aria-expanded", "false");
            search.setAttribute("aria-activedescendant", "");
            if (returnFocus) trigger.focus();
        }

        function choose(next) {
            applySelection(next);
            onChange();
            close(true);
        }

        // ---------- events ----------
        trigger.addEventListener("click", () => {
            if (isOpen) {
                close(true);
            } else {
                open();
            }
        });

        trigger.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault();
                open();
            }
        });

        search.addEventListener("input", () => {
            query = search.value;
            activeOptionId = null;
            renderList();
            if (hasQuery() && optionEls.length) setActive(optionEls[0].el.id, true);
        });

        search.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown") {
                event.preventDefault();
                moveActive(1);
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                moveActive(-1);
            } else if (event.key === "Home" && optionEls.length && event.ctrlKey) {
                event.preventDefault();
                setActive(optionEls[0].el.id, true);
            } else if (event.key === "Enter") {
                event.preventDefault(); // never submit the form from the search box
                const item = findOption(activeOptionId);
                if (item) choose({ leaf: item.leaf, parent: item.parent });
            } else if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                close(true);
            } else if (event.key === "Tab") {
                close(false);
            }
        });

        document.addEventListener("mousedown", (event) => {
            if (isOpen && !rootEl.contains(event.target)) close(false);
        });

        rootEl.addEventListener("focusout", (event) => {
            if (isOpen && event.relatedTarget && !rootEl.contains(event.relatedTarget)) close(false);
        });

        // ---------- data ----------
        function setTree(tree) {
            entries = buildEntries(tree);
            // Set the selected category before saying the picker is ready
            const hasPending = pendingId !== null && pendingId !== undefined && pendingId !== "";
            applySelection(findSelection(entries, hasPending ? pendingId : selection && selection.leaf.id));
            pendingId = null;
            setStatus("ready");
            if (isOpen) renderList();
        }

        async function load() {
            setStatus("loading");
            try {
                const response = await fetch("/api/categories", { headers: { Accept: "application/json" } });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const tree = await response.json();
                if (!Array.isArray(tree)) throw new Error("Unexpected category data.");
                setTree(tree);
            } catch (error) {
                console.error("Unable to load categories:", error);
                setStatus("error");
            }
        }

        setStatus("loading");
        if (options.autoLoad !== false) load();

        return {
            setValue,
            getValue: () => (selection ? Number(selection.leaf.id) : null),
            getSelection: () => (selection ? { ...selection, path: selectionPath(selection) } : null),
            hasValue: () => Boolean(selection),
            setTree,
            setError,
            focus: () => trigger.focus()
        };
    }

    window.CategoryPicker = {
        mount,
        _internals: { normalize, buildEntries, filterEntries, findSelection, selectionPath, highlightChunks }
    };
})();
