/* Native commands only control this window. All SIRO work uses the existing page. */
(() => {
  "use strict";
  function initializeDesktop() {
    if (!document.body.classList.contains("siro-desktop") || window.siroDesktopView) return;
    document.documentElement.classList.add("siro-desktop-root");
    const conversation = document.querySelector(".conversation");
    const frame = document.querySelector("#companion");
    if (!conversation || !frame) return;
    const controls = document.createElement("nav");
    controls.className = "desktop-controls";
    controls.setAttribute("aria-label", "桌寵控制");
    const nativeCommand = message => {
      const bridge = window.webkit?.messageHandlers?.siroDesktop;
      if (!bridge) return false;
      bridge.postMessage(JSON.stringify(message));
      return true;
    };
    const button = (id, text, title, action) => {
      const node = document.createElement("button");
      node.type = "button";
      node.id = id;
      node.textContent = text;
      node.title = title;
      node.addEventListener("click", action);
      controls.appendChild(node);
      return node;
    };
    let chatOpen = false;
    const setChat = open => {
      chatOpen = Boolean(open);
      document.body.classList.toggle("desktop-chat-open", chatOpen);
      conversation.inert = !chatOpen;
      chatButton.setAttribute("aria-expanded", String(chatOpen));
      chatButton.classList.remove("desktop-unread");
      nativeCommand({type: "desktop.chat", open: chatOpen});
      if (chatOpen) document.querySelector("#text")?.focus();
      return chatOpen;
    };
    const chatButton = button("desktop-chat", "聊聊", "展開或收起對話", () => setChat(!chatOpen));
    chatButton.setAttribute("aria-expanded", "false");
    chatButton.setAttribute("aria-controls", "desktop-conversation");
    conversation.id = "desktop-conversation";
    conversation.inert = true;
    const forward = id => document.querySelector(id)?.click();
    const voiceButton = button("desktop-voice", "說話", "沿用對話的麥克風與語音輸入", () => {
      setChat(true);
      forward("#voice");
    });
    button("desktop-stop", "停止", "停止回覆、工具與語音", () => forward("#cancel"));
    const moveButton = button("desktop-move", "移動", "按住這裡拖曳桌寵視窗", () => {});
    moveButton.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      event.preventDefault();
      nativeCommand({type: "desktop.move", button: 1, screenX: event.screenX, screenY: event.screenY});
    });
    const consoleButton = button("desktop-console", "控制台", "開啟任務、記憶與設定", () => {
      if (!nativeCommand({type: "desktop.console"})) window.open("/?view=control#/chat", "siro-control");
    });
    button("desktop-hide", "暫藏", "最小化；可從工作列恢復", () => nativeCommand({type: "desktop.hide"}));
    button("desktop-quit", "退出", "關閉桌寵視窗，SIRO 服務繼續執行", () => nativeCommand({type: "desktop.quit"}));
    const status = document.createElement("p");
    status.id = "desktop-status";
    status.setAttribute("role", "status");
    controls.appendChild(status);
    document.body.appendChild(controls);
    let detached = false;
    const updateStatus = () => {
      const source = id => document.querySelector(id)?.textContent?.trim() || "";
      const notices = ["#service-notice", "#runtime-notice"].map(id => document.querySelector(id));
      const notice = notices.find(node => node && !node.hidden && node.textContent?.trim());
      const activity = document.querySelector("#activity-notice");
      consoleButton.textContent = activity && !activity.hidden ? "控制台 · 有更新" : "控制台";
      voiceButton.textContent = source("#voice") || "說話";
      status.textContent = detached ? "角色顯示已交接；重新啟動桌寵可取回。" :
        notice ? notice.textContent.trim() :
          [source("#connection"), source("#voice-status"), source("#tts-status")].filter(Boolean).join(" · ");
    };
    const observer = new MutationObserver(updateStatus);
    for (const id of ["#connection", "#voice", "#voice-status", "#tts-status", "#activity-notice", "#service-notice", "#runtime-notice"]) {
      const node = document.querySelector(id);
      if (node) observer.observe(node, {childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ["hidden"]});
    }
    const messages = document.querySelector("#messages");
    const unreadObserver = new MutationObserver(() => {
      if (!chatOpen) chatButton.classList.add("desktop-unread");
    });
    if (messages) unreadObserver.observe(messages, {childList: true, characterData: true, subtree: true});
    window.addEventListener("message", event => {
      if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
      if (event.data?.type === "siro.renderer.detached") {
        detached = true;
        updateStatus();
      }
    });
    window.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      forward("#cancel");
      setChat(false);
    });
    window.addEventListener("pagehide", () => { observer.disconnect(); unreadObserver.disconnect(); }, {once: true});
    window.siroDesktopView = Object.freeze({toggleChat: () => setChat(!chatOpen), openChat: () => setChat(true), closeChat: () => setChat(false)});
    window.addEventListener("message", event => {
      if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
      if (event.data?.type === "siro.renderer.ready") nativeCommand({type: "desktop.ready"});
      if (event.data?.type === "siro.renderer.interact") setChat(true);
    });
    updateStatus();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initializeDesktop, {once: true});
  else initializeDesktop();
})();
