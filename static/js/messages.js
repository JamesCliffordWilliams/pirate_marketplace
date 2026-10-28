/*
    messages.js

    Pirate Market
    Created by Aniya Hopson- 10/27/26

    Runs the Messages page: the conversation list, the chat thread, and the
    reply box. Messages older than 60 days are hidden

    Talks to the messaging API in backend/controllers/message_controller.py:
      GET  /api/messages               -> inbox (one entry per conversation)
      GET  /api/message/<other_id>     -> all messages with that user
      POST /api/messages               -> send { receiver_id, body, listing_id }
      GET  /api/messages/unread-count  -> { unread }
    The API identifies the user from the Flask session, so no user ID is sent.
*/

(function () {
  "use strict";

  const RETENTION_DAYS = 60;   // messages are deleted 60 days after sending
  const WARN_DAYS = 7;         // label messages with this many days or fewer left
  const MAX_LEN = 2000;        // matches MessageService.MAX_LEN
  const POLL_MS = 10000;       // check for new messages every 10 seconds
  const DAY_MS = 86400000;     // milliseconds in one day

  // Page elements
  const app = document.getElementById("msgApp");
  const convoList = document.getElementById("convoList");
  const inboxEmpty = document.getElementById("inboxEmpty");
  const unreadBadge = document.getElementById("unreadBadge");
  const backBtn = document.getElementById("backBtn");
  const threadAvatar = document.getElementById("threadAvatar");
  const threadName = document.getElementById("threadName");
  const scrollEl = document.getElementById("threadScroll");
  const placeholder = document.getElementById("threadPlaceholder");
  const messageList = document.getElementById("messageList");
  const composer = document.getElementById("composer");
  const messageInput = document.getElementById("messageInput");
  const sendBtn = document.getElementById("sendBtn");
  const composerError = document.getElementById("composerError");
  const charCount = document.getElementById("charCount");
  const composeBtn = document.getElementById("composeBtn");                 // NEW
  const newMessageSheet = document.getElementById("newMessageSheet");       // NEW
  const newMessageCancel = document.getElementById("newMessageCancel");     // NEW
  const recipientSearch = document.getElementById("recipientSearch");       // NEW
  const recipientStatus = document.getElementById("recipientStatus");       // NEW
  const recipientList = document.getElementById("recipientList");           // NEW

  let me = null;               // the logged-in user { id, username, role }
  let conversations = [];      // latest inbox data
  let activeId = null;         // user ID of the open conversation
  let activeName = "";
  let lastSignature = "";      // detects whether the thread actually changed
  let pendingListingId = null; // from ?listing= in the URL
  let storefronts = null;      // student brands for "New Message" (loaded once)   // NEW
  
  // ---------- Helpers ----------

  async function api(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });

    if (response.status === 401) {
      window.location.href = "/auth/login";
      throw new Error("Please log in again.");
    }

    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error((data && data.error) || "Something went wrong. Please try again.");
    }
    return data;
  }

  function makeEl(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function initial(name) {
    return (name || "?").trim().charAt(0).toUpperCase() || "?";
  }

  // ---------- 60-day retention ----------

  function daysLeft(createdAt) {
    const created = new Date(createdAt).getTime();
    if (Number.isNaN(created)) return RETENTION_DAYS;
    return Math.ceil((created + RETENTION_DAYS * DAY_MS - Date.now()) / DAY_MS);
  }

  function isExpired(createdAt) {
    return daysLeft(createdAt) <= 0;
  }

  // ---------- Dates ----------

  function startOfDay(date) {
    const copy = new Date(date);
    copy.setHours(0, 0, 0, 0);
    return copy;
  }

  function daysAgo(value) {
    return Math.round((startOfDay(new Date()) - startOfDay(new Date(value))) / DAY_MS);
  }

  function timeOf(value) {
    return new Date(value).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  }

  // Inbox: "3:42 PM", "Yesterday", "Monday", or "10/2/26"
  function shortTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const ago = daysAgo(value);
    if (ago === 0) return timeOf(value);
    if (ago === 1) return "Yesterday";
    if (ago < 7) return date.toLocaleDateString("en-US", { weekday: "long" });
    return date.toLocaleDateString("en-US", { month: "numeric", day: "numeric", year: "2-digit" });
  }

  // Thread separators: "Today 3:42 PM", "Yesterday 9:10 AM", "Mon, Oct 26 1:05 PM"
  function dayLabel(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const ago = daysAgo(value);
    let day;
    if (ago === 0) day = "Today";
    else if (ago === 1) day = "Yesterday";
    else day = date.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
    return `${day} ${timeOf(value)}`;
  }

  // ---------- Inbox ----------

  async function loadInbox() {
    try {
      const data = await api("/api/messages");
      conversations = (Array.isArray(data) ? data : []).filter((c) => !isExpired(c.created_at));
      renderInbox();
    } catch (error) {
      if (!convoList.children.length) {
        inboxEmpty.textContent = error.message;
        inboxEmpty.hidden = false;
      }
    }
  }

  function renderInbox() {
    convoList.replaceChildren();

    if (conversations.length === 0) {
        inboxEmpty.textContent = "No conversations yet. Tap the pencil to message a student brand.";
        inboxEmpty.hidden = false;
        return;
    }
    inboxEmpty.hidden = true;

    conversations.forEach((c) => {
      const sentByMe = c.last_sender_id === me.id;
      const unread = !c.is_read && !sentByMe;

      const button = makeEl("button", "msg-convo");
      button.type = "button";
      if (c.other_user_id === activeId) button.setAttribute("aria-current", "true");
      if (unread) button.classList.add("is-unread");

      const avatar = makeEl("span", "msg-avatar", initial(c.other_username));
      avatar.setAttribute("aria-hidden", "true");

      const body = makeEl("span", "msg-convo-body");
      const top = makeEl("span", "msg-convo-top");
      top.append(
        makeEl("span", "msg-convo-name", c.other_username),
        makeEl("span", "msg-convo-time", shortTime(c.created_at))
      );
      body.append(top, makeEl("span", "msg-convo-preview", (sentByMe ? "You: " : "") + c.last_message));

      button.append(avatar, body);

      if (unread) {
        const dot = makeEl("span", "msg-dot");
        dot.setAttribute("aria-hidden", "true");
        button.append(dot, makeEl("span", "visually-hidden", "Unread"));
      }

      button.addEventListener("click", () => openConversation(c.other_user_id, c.other_username));

      const item = makeEl("li");
      item.append(button);
      convoList.append(item);
    });
  }

  async function loadUnread() {
    try {
      const data = await api("/api/messages/unread-count");
      const count = Number(data.unread) || 0;
      unreadBadge.textContent = String(count);
      unreadBadge.setAttribute("aria-label", `${count} unread`);
      unreadBadge.hidden = count === 0;
    } catch (error) {
      unreadBadge.hidden = true;
    }
  }

  // ---------- Thread ----------

  async function openConversation(userId, name) {
    activeId = userId;
    activeName = name || "New message";
    lastSignature = "";

    threadName.textContent = activeName;
    threadAvatar.textContent = initial(activeName);
    threadAvatar.hidden = false;
    placeholder.hidden = true;
    composer.hidden = false;
    composerError.textContent = "";
    messageList.replaceChildren();
    app.dataset.view = "thread";

    convoList.querySelectorAll(".msg-convo").forEach((button, index) => {
      const isActive = conversations[index] && conversations[index].other_user_id === userId;
      if (isActive) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    });

    await loadThread(true);
    messageInput.focus();
    loadInbox();   // opening a conversation marks it read on the server
    loadUnread();
  }

  function closeConversation() {
    activeId = null;
    app.dataset.view = "list";
    composer.hidden = true;
    threadAvatar.hidden = true;
    threadName.textContent = "Select a conversation";
    messageList.replaceChildren();
    placeholder.hidden = false;
    renderInbox();
  }

  async function loadThread(forceScroll) {
    if (activeId === null) return;
    const requestedId = activeId;

    try {
      const data = await api(`/api/message/${requestedId}`);
      if (requestedId !== activeId) return; // user switched conversations while loading

      const messages = (Array.isArray(data) ? data : []).filter((m) => !isExpired(m.created_at));
      const last = messages[messages.length - 1];
      const signature = `${messages.length}:${last ? last.id : 0}:${last ? last.is_read : ""}`;
      if (signature === lastSignature) return; // nothing new, don't redraw
      lastSignature = signature;

      const nearBottom = scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight < 80;
      renderThread(messages);
      if (forceScroll || nearBottom) scrollEl.scrollTop = scrollEl.scrollHeight;
    } catch (error) {
      composerError.textContent = error.message;
    }
  }

  function renderThread(messages) {
    messageList.replaceChildren();
    messageList.append(makeEl("p", "msg-day", `Messages are deleted ${RETENTION_DAYS} days after they're sent.`));

    if (messages.length === 0) {
      messageList.append(makeEl("p", "msg-placeholder", `Send ${activeName} your first message.`));
      return;
    }

    let currentDay = null;

    messages.forEach((m, index) => {
      const day = startOfDay(new Date(m.created_at)).getTime();
      if (day !== currentDay) {
        messageList.append(makeEl("p", "msg-day", dayLabel(m.created_at)));
        currentDay = day;
      }

      const mine = m.sender_id === me.id;
      const row = makeEl("div", `msg-row ${mine ? "is-mine" : "is-theirs"}`);
      const bubble = makeEl("p", "msg-bubble", m.body);
      bubble.title = new Date(m.created_at).toLocaleString("en-US");
      row.append(bubble);

      const notes = [];
      const left = daysLeft(m.created_at);
      if (left <= WARN_DAYS) notes.push(`Deletes in ${left} ${left === 1 ? "day" : "days"}`);
      if (mine && index === messages.length - 1 && m.is_read) notes.push("Read");
      if (notes.length) row.append(makeEl("p", "msg-note", notes.join(" · ")));

      messageList.append(row);
    });
  }

  // ---------- Composer ----------

  function autoGrow() {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 140)}px`;
  }

  function updateComposer() {
    const length = messageInput.value.length;
    charCount.textContent = length > MAX_LEN - 200 ? `${length}/${MAX_LEN}` : "";
    sendBtn.disabled = messageInput.value.trim() === "" || length > MAX_LEN;
    autoGrow();
  }

  async function handleSend(event) {
    event.preventDefault();

    const body = messageInput.value.trim();
    if (!body || activeId === null) return;
    if (body.length > MAX_LEN) {
      composerError.textContent = `Messages can be up to ${MAX_LEN} characters.`;
      return;
    }

    sendBtn.disabled = true;
    composerError.textContent = "";

    const payload = { receiver_id: activeId, body };
    if (pendingListingId !== null) payload.listing_id = pendingListingId;

    try {
      await api("/api/messages", { method: "POST", body: JSON.stringify(payload) });
      messageInput.value = "";
      pendingListingId = null;
      await Promise.all([loadThread(true), loadInbox()]);
    } catch (error) {
      composerError.textContent = error.message;
    } finally {
      updateComposer();
      messageInput.focus();
    }
  }

    // ---------- New message ----------

  // Loads the student brands once. Each storefront's owner_id is the user ID
  // the messaging API needs as receiver_id.
  async function loadStorefronts() {
    if (storefronts !== null) return;
    const data = await api("/api/storefronts");
    storefronts = (Array.isArray(data) ? data : [])
      .filter((s) => s.owner_id !== me.id)   // you can't message your own brand
      .sort((a, b) => (a.brand_name || "").localeCompare(b.brand_name || ""));
  }

  function matchingStorefronts() {
    const query = recipientSearch.value.trim().toLowerCase();
    return (storefronts || []).filter((s) => (s.brand_name || "").toLowerCase().includes(query));
  }

  function buildAvatar(storefront) {
    const avatar = makeEl("span", "msg-avatar");
    avatar.setAttribute("aria-hidden", "true");

    if (storefront.logo_url) {
      const img = document.createElement("img");
      img.src = storefront.logo_url;
      img.alt = "";
      // If the logo fails to load, show the brand's first letter instead
      img.addEventListener("error", () => {
        avatar.textContent = initial(storefront.brand_name);
      });
      avatar.append(img);
    } else {
      avatar.textContent = initial(storefront.brand_name);
    }
    return avatar;
  }

  function renderRecipients() {
    if (storefronts === null) return; // still loading

    recipientList.replaceChildren();
    const matches = matchingStorefronts();
    const query = recipientSearch.value.trim();

    if (matches.length === 0) {
      recipientStatus.textContent = query ? `No brands match "${query}".` : "No other student brands yet.";
      recipientStatus.hidden = false;
      return;
    }
    recipientStatus.hidden = true;

    matches.forEach((storefront) => {
      const count = Number(storefront.item_count) || 0;

      const button = makeEl("button", "msg-recipient");
      button.type = "button";

      const text = makeEl("span");
      text.append(
        makeEl("span", "msg-recipient-name", storefront.brand_name),
        makeEl("span", "msg-recipient-sub", `${count} ${count === 1 ? "item" : "items"}`)
      );

      button.append(buildAvatar(storefront), text);
      button.addEventListener("click", () => chooseRecipient(storefront));

      const item = makeEl("li");
      item.append(button);
      recipientList.append(item);
    });
  }

  function chooseRecipient(storefront) {
    newMessageSheet.close();
    // If you've already talked to this seller, reopen that conversation
    const existing = conversations.find((c) => c.other_user_id === storefront.owner_id);
    openConversation(storefront.owner_id, existing ? existing.other_username : storefront.brand_name);
  }

  async function openNewMessage() {
    recipientSearch.value = "";
    recipientList.replaceChildren();
    recipientStatus.textContent = "Loading brands...";
    recipientStatus.hidden = false;
    newMessageSheet.showModal();
    recipientSearch.focus();

    try {
      await loadStorefronts();
      renderRecipients();
    } catch (error) {
      recipientStatus.textContent = error.message;
    }
  }

  // ---------- Start up ----------

  async function init() {
    composer.addEventListener("submit", handleSend);
    messageInput.addEventListener("input", updateComposer);
    messageInput.addEventListener("keydown", (event) => {
      // Enter sends, Shift+Enter adds a new line
      if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        composer.requestSubmit();
      }
    });
    backBtn.addEventListener("click", closeConversation);

    // New message sheet                                                         // NEW
    composeBtn.addEventListener("click", openNewMessage);                        // NEW
    newMessageCancel.addEventListener("click", () => newMessageSheet.close());  // NEW
    newMessageSheet.addEventListener("click", (event) => {                       // NEW
      if (event.target === newMessageSheet) newMessageSheet.close();             // NEW
    });                                                                          // NEW
    recipientSearch.addEventListener("input", renderRecipients);                 // NEW
    recipientSearch.addEventListener("keydown", (event) => {                     // NEW
      if (event.key === "Enter") {                                               // NEW
        event.preventDefault();                                                  // NEW
        const first = matchingStorefronts()[0];                                  // NEW
        if (first) chooseRecipient(first);                                       // NEW
      }                                                                          // NEW
    });                                                                          // NEW
    try {
      me = await api("/auth/api/auth/me");
    } catch (error) {
      inboxEmpty.textContent = error.message;
      return;
    }

    await Promise.all([loadInbox(), loadUnread()]);

    // Optional: /messages?to=<user_id>&listing=<listing_id>
    const params = new URLSearchParams(window.location.search);
    const toId = Number.parseInt(params.get("to"), 10);
    const listingId = Number.parseInt(params.get("listing"), 10);
    if (Number.isInteger(listingId)) pendingListingId = listingId;

    if (Number.isInteger(toId) && toId !== me.id) {
      const existing = conversations.find((c) => c.other_user_id === toId);
      openConversation(toId, existing ? existing.other_username : "New message");
    }

    // Check for new messages, but only while the tab is visible
    setInterval(() => {
      if (document.hidden) return;
      loadThread(false);
      loadInbox();
      loadUnread();
    }, POLL_MS);
  }

  init();
})();