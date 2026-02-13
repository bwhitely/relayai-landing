(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Configuration — read from the <script> tag's data attributes
  // ---------------------------------------------------------------------------
  var scriptTag = document.currentScript;
  if (!scriptTag) {
    console.error("[ChatWidget] Could not find the current script tag.");
    return;
  }

  var TENANT_ID = scriptTag.getAttribute("data-tenant-id");
  var API_KEY = scriptTag.getAttribute("data-api-key");
  if (!TENANT_ID || !API_KEY) {
    console.error(
      "[ChatWidget] data-tenant-id and data-api-key are required."
    );
    return;
  }

  var API_URL = scriptTag.getAttribute("data-api-url") || window.location.origin;
  var TITLE = scriptTag.getAttribute("data-title") || "Chat with us";
  var ACCENT = scriptTag.getAttribute("data-accent-color") || "#D97706";

  // Strip trailing slash from API URL
  API_URL = API_URL.replace(/\/+$/, "");

  // ---------------------------------------------------------------------------
  // Sender ID — persist per tenant in localStorage
  // ---------------------------------------------------------------------------
  var STORAGE_KEY = "chat_widget_sender_" + TENANT_ID;
  var senderId = null;

  function getSenderId() {
    if (senderId) return senderId;
    try {
      senderId = localStorage.getItem(STORAGE_KEY);
    } catch (_) {
      // localStorage may be unavailable
    }
    if (!senderId) {
      senderId = generateId();
      try {
        localStorage.setItem(STORAGE_KEY, senderId);
      } catch (_) {
        // ignore
      }
    }
    return senderId;
  }

  function generateId() {
    // Simple random ID without crypto dependency
    var chars = "abcdefghijklmnopqrstuvwxyz0123456789";
    var id = "web_";
    for (var i = 0; i < 20; i++) {
      id += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return id;
  }

  // ---------------------------------------------------------------------------
  // CSS
  // ---------------------------------------------------------------------------
  var CSS = /* css */ '\
    :host {\
      all: initial;\
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,\
        Oxygen, Ubuntu, Cantarell, "Helvetica Neue", Arial, sans-serif;\
      font-size: 14px;\
      line-height: 1.5;\
      color: #1a1a1a;\
      box-sizing: border-box;\
    }\
    *, *::before, *::after { box-sizing: border-box; }\
    \
    .cw-bubble {\
      position: fixed;\
      bottom: 20px;\
      right: 20px;\
      width: 56px;\
      height: 56px;\
      border-radius: 50%;\
      background: ' + ACCENT + ';\
      border: none;\
      cursor: pointer;\
      box-shadow: 0 4px 12px rgba(0,0,0,0.25);\
      display: flex;\
      align-items: center;\
      justify-content: center;\
      transition: transform 0.2s ease, box-shadow 0.2s ease;\
      z-index: 2147483646;\
      padding: 0;\
    }\
    .cw-bubble:hover {\
      transform: scale(1.08);\
      box-shadow: 0 6px 20px rgba(0,0,0,0.3);\
    }\
    .cw-bubble:focus-visible {\
      outline: 2px solid ' + ACCENT + ';\
      outline-offset: 3px;\
    }\
    .cw-bubble svg {\
      width: 26px;\
      height: 26px;\
      fill: #fff;\
      transition: transform 0.25s ease, opacity 0.2s ease;\
    }\
    .cw-bubble .cw-icon-close {\
      position: absolute;\
      transform: rotate(90deg) scale(0);\
      opacity: 0;\
    }\
    .cw-bubble.cw-open .cw-icon-chat {\
      transform: rotate(-90deg) scale(0);\
      opacity: 0;\
    }\
    .cw-bubble.cw-open .cw-icon-close {\
      transform: rotate(0) scale(1);\
      opacity: 1;\
    }\
    \
    .cw-panel {\
      position: fixed;\
      bottom: 88px;\
      right: 20px;\
      width: 400px;\
      height: 500px;\
      max-height: calc(100vh - 108px);\
      background: #fff;\
      border-radius: 12px;\
      box-shadow: 0 8px 30px rgba(0,0,0,0.2);\
      display: flex;\
      flex-direction: column;\
      overflow: hidden;\
      z-index: 2147483646;\
      opacity: 0;\
      transform: translateY(16px) scale(0.95);\
      pointer-events: none;\
      transition: opacity 0.25s ease, transform 0.25s ease;\
    }\
    .cw-panel.cw-visible {\
      opacity: 1;\
      transform: translateY(0) scale(1);\
      pointer-events: auto;\
    }\
    \
    .cw-header {\
      background: #1a1a1a;\
      color: #fff;\
      padding: 14px 16px;\
      display: flex;\
      align-items: center;\
      justify-content: space-between;\
      flex-shrink: 0;\
    }\
    .cw-header-title {\
      font-size: 15px;\
      font-weight: 600;\
      margin: 0;\
      letter-spacing: 0.01em;\
    }\
    .cw-header-close {\
      background: none;\
      border: none;\
      cursor: pointer;\
      color: #999;\
      padding: 4px;\
      display: flex;\
      align-items: center;\
      justify-content: center;\
      border-radius: 4px;\
      transition: color 0.15s ease, background 0.15s ease;\
    }\
    .cw-header-close:hover {\
      color: #fff;\
      background: rgba(255,255,255,0.1);\
    }\
    .cw-header-close:focus-visible {\
      outline: 2px solid ' + ACCENT + ';\
      outline-offset: 1px;\
    }\
    .cw-header-close svg {\
      width: 18px;\
      height: 18px;\
      fill: currentColor;\
    }\
    \
    .cw-messages {\
      flex: 1;\
      overflow-y: auto;\
      padding: 16px;\
      display: flex;\
      flex-direction: column;\
      gap: 10px;\
      background: #fafafa;\
    }\
    .cw-messages::-webkit-scrollbar {\
      width: 5px;\
    }\
    .cw-messages::-webkit-scrollbar-track {\
      background: transparent;\
    }\
    .cw-messages::-webkit-scrollbar-thumb {\
      background: #ccc;\
      border-radius: 3px;\
    }\
    \
    .cw-msg {\
      max-width: 80%;\
      padding: 10px 14px;\
      border-radius: 12px;\
      font-size: 14px;\
      line-height: 1.45;\
      word-wrap: break-word;\
      overflow-wrap: break-word;\
      white-space: pre-wrap;\
    }\
    .cw-msg-user {\
      align-self: flex-end;\
      background: ' + ACCENT + ';\
      color: #fff;\
      border-bottom-right-radius: 4px;\
    }\
    .cw-msg-bot {\
      align-self: flex-start;\
      background: #e8e8e8;\
      color: #1a1a1a;\
      border-bottom-left-radius: 4px;\
    }\
    \
    .cw-typing {\
      align-self: flex-start;\
      display: flex;\
      align-items: center;\
      gap: 4px;\
      padding: 10px 14px;\
      background: #e8e8e8;\
      border-radius: 12px;\
      border-bottom-left-radius: 4px;\
    }\
    .cw-typing-dot {\
      width: 7px;\
      height: 7px;\
      border-radius: 50%;\
      background: #999;\
      animation: cw-bounce 1.2s ease-in-out infinite;\
    }\
    .cw-typing-dot:nth-child(2) { animation-delay: 0.15s; }\
    .cw-typing-dot:nth-child(3) { animation-delay: 0.3s; }\
    @keyframes cw-bounce {\
      0%, 60%, 100% { transform: translateY(0); }\
      30% { transform: translateY(-4px); }\
    }\
    \
    .cw-input-area {\
      display: flex;\
      align-items: flex-end;\
      padding: 12px;\
      border-top: 1px solid #e5e5e5;\
      background: #fff;\
      gap: 8px;\
      flex-shrink: 0;\
    }\
    .cw-textarea {\
      flex: 1;\
      border: 1px solid #ddd;\
      border-radius: 8px;\
      padding: 10px 12px;\
      font-family: inherit;\
      font-size: 14px;\
      line-height: 1.4;\
      resize: none;\
      outline: none;\
      max-height: 100px;\
      overflow-y: auto;\
      transition: border-color 0.15s ease;\
      background: #fff;\
      color: #1a1a1a;\
    }\
    .cw-textarea::placeholder {\
      color: #999;\
    }\
    .cw-textarea:focus {\
      border-color: ' + ACCENT + ';\
    }\
    .cw-send {\
      background: ' + ACCENT + ';\
      border: none;\
      border-radius: 8px;\
      width: 38px;\
      height: 38px;\
      cursor: pointer;\
      display: flex;\
      align-items: center;\
      justify-content: center;\
      flex-shrink: 0;\
      transition: opacity 0.15s ease, transform 0.1s ease;\
      padding: 0;\
    }\
    .cw-send:hover { opacity: 0.85; }\
    .cw-send:active { transform: scale(0.94); }\
    .cw-send:disabled {\
      opacity: 0.4;\
      cursor: default;\
      transform: none;\
    }\
    .cw-send:focus-visible {\
      outline: 2px solid ' + ACCENT + ';\
      outline-offset: 2px;\
    }\
    .cw-send svg {\
      width: 18px;\
      height: 18px;\
      fill: #fff;\
    }\
    \
    .cw-error {\
      align-self: center;\
      font-size: 12px;\
      color: #b91c1c;\
      background: #fef2f2;\
      padding: 6px 12px;\
      border-radius: 6px;\
      text-align: center;\
    }\
    \
    .cw-welcome {\
      text-align: center;\
      color: #888;\
      font-size: 13px;\
      padding: 20px 16px 8px;\
    }\
    \
    @media (max-width: 639px) {\
      .cw-panel {\
        bottom: 0;\
        right: 0;\
        left: 0;\
        top: 0;\
        width: 100%;\
        height: 100%;\
        max-height: 100vh;\
        border-radius: 0;\
      }\
      .cw-bubble.cw-open {\
        display: none;\
      }\
    }\
  ';

  // ---------------------------------------------------------------------------
  // SVG Icons
  // ---------------------------------------------------------------------------
  var ICON_CHAT =
    '<svg viewBox="0 0 24 24" class="cw-icon-chat" aria-hidden="true"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.17L4 17.17V4h16v12z"/><path d="M7 9h10v2H7zm0-3h10v2H7zm0 6h7v2H7z"/></svg>';

  var ICON_CLOSE =
    '<svg viewBox="0 0 24 24" class="cw-icon-close" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';

  var ICON_CLOSE_SM =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>';

  var ICON_SEND =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';

  // ---------------------------------------------------------------------------
  // Build DOM inside Shadow DOM
  // ---------------------------------------------------------------------------
  var host = document.createElement("div");
  host.setAttribute("id", "chat-widget-host");
  document.body.appendChild(host);

  var shadow = host.attachShadow({ mode: "closed" });

  // Inject styles
  var styleEl = document.createElement("style");
  styleEl.textContent = CSS;
  shadow.appendChild(styleEl);

  // -- Bubble button --
  var bubble = document.createElement("button");
  bubble.className = "cw-bubble";
  bubble.setAttribute("aria-label", "Open chat");
  bubble.setAttribute("type", "button");
  bubble.innerHTML = ICON_CHAT + ICON_CLOSE;
  shadow.appendChild(bubble);

  // -- Panel --
  var panel = document.createElement("div");
  panel.className = "cw-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", TITLE);
  panel.setAttribute("aria-hidden", "true");

  // Header
  var header = document.createElement("div");
  header.className = "cw-header";

  var headerTitle = document.createElement("h2");
  headerTitle.className = "cw-header-title";
  headerTitle.textContent = TITLE;

  var headerClose = document.createElement("button");
  headerClose.className = "cw-header-close";
  headerClose.setAttribute("aria-label", "Close chat");
  headerClose.setAttribute("type", "button");
  headerClose.innerHTML = ICON_CLOSE_SM;

  header.appendChild(headerTitle);
  header.appendChild(headerClose);
  panel.appendChild(header);

  // Messages area
  var messages = document.createElement("div");
  messages.className = "cw-messages";
  messages.setAttribute("role", "log");
  messages.setAttribute("aria-live", "polite");
  messages.setAttribute("aria-label", "Chat messages");

  // Welcome message
  var welcome = document.createElement("div");
  welcome.className = "cw-welcome";
  welcome.textContent = "Send a message to start the conversation.";
  messages.appendChild(welcome);

  panel.appendChild(messages);

  // Input area
  var inputArea = document.createElement("div");
  inputArea.className = "cw-input-area";

  var textarea = document.createElement("textarea");
  textarea.className = "cw-textarea";
  textarea.setAttribute("placeholder", "Type a message\u2026");
  textarea.setAttribute("aria-label", "Message input");
  textarea.setAttribute("rows", "1");

  var sendBtn = document.createElement("button");
  sendBtn.className = "cw-send";
  sendBtn.setAttribute("aria-label", "Send message");
  sendBtn.setAttribute("type", "button");
  sendBtn.disabled = true;
  sendBtn.innerHTML = ICON_SEND;

  inputArea.appendChild(textarea);
  inputArea.appendChild(sendBtn);
  panel.appendChild(inputArea);

  shadow.appendChild(panel);

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  var isOpen = false;
  var isSending = false;
  var typingIndicator = null;

  // ---------------------------------------------------------------------------
  // Open / Close
  // ---------------------------------------------------------------------------
  function openPanel() {
    isOpen = true;
    panel.classList.add("cw-visible");
    panel.setAttribute("aria-hidden", "false");
    bubble.classList.add("cw-open");
    bubble.setAttribute("aria-label", "Close chat");
    // Focus the input
    setTimeout(function () {
      textarea.focus();
    }, 280);
  }

  function closePanel() {
    isOpen = false;
    panel.classList.remove("cw-visible");
    panel.setAttribute("aria-hidden", "true");
    bubble.classList.remove("cw-open");
    bubble.setAttribute("aria-label", "Open chat");
    bubble.focus();
  }

  bubble.addEventListener("click", function () {
    if (isOpen) {
      closePanel();
    } else {
      openPanel();
    }
  });

  headerClose.addEventListener("click", function () {
    closePanel();
  });

  // Close on Escape
  shadow.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && isOpen) {
      closePanel();
    }
  });

  // ---------------------------------------------------------------------------
  // Auto-resize textarea
  // ---------------------------------------------------------------------------
  textarea.addEventListener("input", function () {
    // Reset to 1 row to measure
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 100) + "px";
    sendBtn.disabled = !textarea.value.trim();
  });

  // ---------------------------------------------------------------------------
  // Send message
  // ---------------------------------------------------------------------------
  function sendMessage() {
    var text = textarea.value.trim();
    if (!text || isSending) return;

    // Remove welcome if present
    if (welcome && welcome.parentNode) {
      welcome.parentNode.removeChild(welcome);
      welcome = null;
    }

    appendMessage(text, "user");

    textarea.value = "";
    textarea.style.height = "auto";
    sendBtn.disabled = true;

    isSending = true;
    showTyping();

    var endpoint =
      API_URL + "/webhooks/generic/" + encodeURIComponent(TENANT_ID);

    var xhr = new XMLHttpRequest();
    xhr.open("POST", endpoint, true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.setRequestHeader("X-API-Key", API_KEY);
    xhr.timeout = 60000; // 60s timeout

    xhr.onload = function () {
      hideTyping();
      isSending = false;

      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          var data = JSON.parse(xhr.responseText);
          appendMessage(data.response, "bot");
        } catch (_) {
          appendError("Received an unexpected response. Please try again.");
        }
      } else if (xhr.status === 403) {
        appendError("Authentication failed. Please check the widget configuration.");
      } else if (xhr.status === 404) {
        appendError("Service not found. Please check the widget configuration.");
      } else if (xhr.status === 429) {
        appendError("Too many messages. Please wait a moment and try again.");
      } else {
        appendError("Something went wrong (error " + xhr.status + "). Please try again.");
      }

      textarea.focus();
    };

    xhr.onerror = function () {
      hideTyping();
      isSending = false;
      appendError("Could not reach the server. Please check your connection.");
      textarea.focus();
    };

    xhr.ontimeout = function () {
      hideTyping();
      isSending = false;
      appendError("The request timed out. Please try again.");
      textarea.focus();
    };

    xhr.send(
      JSON.stringify({
        sender_id: getSenderId(),
        message: text,
      })
    );
  }

  sendBtn.addEventListener("click", sendMessage);

  textarea.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // ---------------------------------------------------------------------------
  // Message rendering
  // ---------------------------------------------------------------------------
  function appendMessage(text, type) {
    var div = document.createElement("div");
    div.className = "cw-msg cw-msg-" + type;
    div.setAttribute("role", type === "bot" ? "status" : "log");
    div.textContent = text;
    messages.appendChild(div);
    scrollToBottom();
  }

  function appendError(text) {
    var div = document.createElement("div");
    div.className = "cw-error";
    div.setAttribute("role", "alert");
    div.textContent = text;
    messages.appendChild(div);
    scrollToBottom();
  }

  function showTyping() {
    if (typingIndicator) return;
    typingIndicator = document.createElement("div");
    typingIndicator.className = "cw-typing";
    typingIndicator.setAttribute("role", "status");
    typingIndicator.setAttribute("aria-label", "Typing");
    for (var i = 0; i < 3; i++) {
      var dot = document.createElement("span");
      dot.className = "cw-typing-dot";
      typingIndicator.appendChild(dot);
    }
    messages.appendChild(typingIndicator);
    scrollToBottom();
  }

  function hideTyping() {
    if (typingIndicator && typingIndicator.parentNode) {
      typingIndicator.parentNode.removeChild(typingIndicator);
    }
    typingIndicator = null;
  }

  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }
})();
