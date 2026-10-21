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
      if (typeof renderBubble === "function") renderBubble();
      return chatOpen;
    };
    const chatButton = button("desktop-chat", "聊聊", "展開或收起對話", () => setChat(!chatOpen));
    chatButton.setAttribute("aria-expanded", "false");
    chatButton.setAttribute("aria-controls", "desktop-conversation");
    conversation.id = "desktop-conversation";
    conversation.inert = true;
    const forward = id => document.querySelector(id)?.click();
    const microphoneButton = button("desktop-microphone", "麥克風：關", "開啟或關閉麥克風；不會自動開始錄音", () => forward("#microphone-toggle"));
    const voiceButton = button("desktop-voice", "說話", "沿用對話的麥克風與語音輸入", () => {
      setChat(true);
      forward("#voice");
    });
    const handsFreeButton = button("desktop-voice-auto", "免手動：關", "偵測到說話自動錄音，停頓後自動送出；SIRO 說話時不收音", () => forward("#voice-auto"));
    button("desktop-stop", "停止", "停止回覆、工具與語音", () => forward("#cancel"));
    const output = document.querySelector("#voice-output");
    const speechButton = button("desktop-speech", "朗讀：關", "朗讀 SIRO 的回覆", () => {
      if (!output || output.disabled) return;
      output.checked = !output.checked;
      output.dispatchEvent(new Event("change", {bubbles: true}));
      updateStatus();
    });
    speechButton.setAttribute("aria-pressed", String(Boolean(output?.checked)));
    speechButton.disabled = !output || output.disabled;
    button("desktop-smaller", "－", "縮小角色", () => nativeCommand({type: "desktop.scale", step: -1}))
      .setAttribute("aria-label", "縮小角色");
    const scaleButton = button("desktop-scale", "100%", "還原角色大小", () => nativeCommand({type: "desktop.scale", step: 0}));
    button("desktop-larger", "＋", "放大角色", () => nativeCommand({type: "desktop.scale", step: 1}))
      .setAttribute("aria-label", "放大角色");
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
    let roleDocument, pressed, roleDragged = false;
    const roleDown = event => {
      roleDragged = false;
      pressed = event.button === 0 ? {x: event.screenX, y: event.screenY, id: event.pointerId} : null;
    };
    const roleMove = event => {
      if (typeof event.buttons === "number" && !(event.buttons & 1)) { pressed = null; return; }
      if (!pressed || event.pointerId !== pressed.id || Math.hypot(event.screenX - pressed.x, event.screenY - pressed.y) < 7) return;
      if (nativeCommand({type: "desktop.move", button: 1, screenX: event.screenX, screenY: event.screenY})) {
        roleDragged = true;
        pressed = null;
        event.preventDefault();
      }
    };
    const roleUp = () => { pressed = null; };
    const roleClick = event => {
      if (!roleDragged) return;
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    const roleEvents = {pointerdown: roleDown, pointermove: roleMove, pointerup: roleUp, pointercancel: roleUp, click: roleClick};
    const detachRole = () => {
      if (roleDocument) for (const [name, handler] of Object.entries(roleEvents)) roleDocument.removeEventListener(name, handler, true);
      roleDocument = null;
      pressed = null;
    };
    const attachRole = () => {
      let next;
      try { next = frame.contentDocument; } catch (_) { return; }
      if (!next || roleDocument === next) return;
      detachRole();
      roleDocument = next;
      for (const [name, handler] of Object.entries(roleEvents)) roleDocument.addEventListener(name, handler, true);
    };
    frame.addEventListener("load", attachRole);
    attachRole();
    let reportedControlsHeight;
    const setLayout = incoming => {
      const layout = incoming && {...incoming, paneX: incoming.paneX ?? incoming.petX, paneWidth: incoming.paneWidth ?? incoming.petWidth, controlsY: incoming.controlsY ?? incoming.petHeight + 10};
      const geometry = {petWidth: "pet-width", petHeight: "pet-height", petX: "pet-left", chatX: "chat-x", chatY: "chat-y", chatWidth: "chat-width", chatHeight: "chat-height", paneX: "pane-left", paneWidth: "pane-width", controlsY: "controls-y"};
      if (!layout || !Object.keys(geometry).every(key => Number.isSafeInteger(layout[key]) && layout[key] >= 0 && layout[key] <= 4096) ||
          !Number.isFinite(layout.scale) || layout.scale <= 0 || layout.scale > 1.5) return;
      for (const [key, name] of Object.entries(geometry)) document.documentElement.style?.setProperty(`--desktop-${name}`, `${layout[key]}px`);
      scaleButton.textContent = `${Math.round(layout.scale * 100)}%`;
      if (controls.getBoundingClientRect) {
        const height = Math.min(320, Math.max(64, Math.ceil(controls.getBoundingClientRect().height + 20)));
        if (height !== reportedControlsHeight) { reportedControlsHeight = height; nativeCommand({type: "desktop.controls", height}); }
      }
    };
    let detached = false;
    const updateStatus = () => {
      const source = id => document.querySelector(id)?.textContent?.trim() || "";
      const notices = ["#service-notice", "#runtime-notice"].map(id => document.querySelector(id));
      const notice = notices.find(node => node && !node.hidden && node.textContent?.trim());
      const activity = document.querySelector("#activity-notice");
      consoleButton.textContent = activity && !activity.hidden ? "控制台 · 有更新" : "控制台";
      voiceButton.textContent = source("#voice") || "說話";
      const microphone = document.querySelector("#microphone-toggle");
      microphoneButton.textContent = source("#microphone-toggle") || "麥克風：未提供";
      microphoneButton.disabled = !microphone || microphone.disabled;
      microphoneButton.setAttribute("aria-pressed", microphone?.getAttribute?.("aria-pressed") || "false");
      const handsFree = document.querySelector("#voice-auto");
      handsFreeButton.textContent = source("#voice-auto") || "免手動：未提供";
      handsFreeButton.disabled = !handsFree;
      handsFreeButton.setAttribute("aria-pressed", handsFree?.getAttribute?.("aria-pressed") || "false");
      speechButton.textContent = output?.checked ? "朗讀：開" : "朗讀：關";
      speechButton.setAttribute("aria-pressed", String(Boolean(output?.checked)));
      status.textContent = detached ? "角色顯示已交接；重新啟動桌寵可取回。" :
        notice ? notice.textContent.trim() :
          // Short states first, so a long recognised sentence cannot push them out of view.
          [source("#connection"), source("#tts-status"), source("#voice-status")].filter(Boolean).join(" · ");
      status.title = status.textContent;
    };
    const observer = new MutationObserver(updateStatus);
    output?.addEventListener("change", updateStatus);
    for (const id of ["#connection", "#voice", "#voice-auto", "#microphone-toggle", "#voice-status", "#tts-status", "#activity-notice", "#service-notice", "#runtime-notice"]) {
      const node = document.querySelector(id);
      if (node) observer.observe(node, {childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ["hidden", "disabled", "aria-pressed"]});
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
    window.addEventListener("pagehide", () => {
      observer.disconnect(); unreadObserver.disconnect(); detachRole(); unwatchActivity?.();
      frame.removeEventListener("load", attachRole);
      output?.removeEventListener("change", updateStatus);
    }, {once: true});
    // Bubble (CP-V05): one short line above her, only facts the activity journal already has.
    const bubble = document.createElement("div");
    bubble.id = "desktop-bubble";
    bubble.setAttribute("role", "status");
    bubble.hidden = true;
    const bubbleIcon = document.createElement("span");
    bubbleIcon.className = "desktop-bubble-icon";
    bubbleIcon.setAttribute("aria-hidden", "true");
    const bubbleLabel = document.createElement("span");
    bubbleLabel.className = "desktop-bubble-label";
    const bubbleAction = document.createElement("button");
    bubbleAction.type = "button";
    bubbleAction.hidden = true;
    bubble.appendChild(bubbleIcon);
    bubble.appendChild(bubbleLabel);
    bubble.appendChild(bubbleAction);
    document.body.appendChild(bubble);
    const LIVE = new Set(["proposed", "queued", "running", "paused", "cancelling"]);
    const TOOL_NAMES = {"browser.navigate+read": "開網頁", "computer.execute": "執行程式"};
    const openActivity = () => {
      if (!nativeCommand({type: "desktop.console", page: "activity"})) window.open("/?view=control#/activity", "siro-control");
    };
    const seenStates = new Map();
    let lastView, flash, hadLive = false, dismissed = "", bubbleRun;
    const subject = item => item.reason || TOOL_NAMES[item.tools?.[0]?.capability] || "工具操作";
    const toolName = tool => tool ? (tool.target?.program ? `執行 ${tool.target.program}` : TOOL_NAMES[tool.capability] || "使用工具") : "使用工具";
    const bubbleFor = view => {
      const items = [...view.items.values()].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
      const live = items.filter(item => LIVE.has(item.state) && item.tools?.length);
      if (view.status === "offline") return hadLive ? {icon: "⚠", text: "斷線了，狀態可能過時", tone: "warn"} : null;
      if (view.status !== "ok") return null;
      hadLive = live.length > 0;
      const proposed = live.find(item => item.state === "proposed");
      if (proposed) return {icon: "◔", text: `等你允許：${toolName(proposed.tools[0])}`, action: "查看", run: () => setChat(true)};
      if (live.some(item => item.state === "cancelling" || view.stopping?.has(item.activity_id))) return {icon: "◌", text: "停止中…", tone: "warn"};
      // Her motions are only a show: "正在" needs a tool the journal records as running.
      const working = live.find(item => item.tools.some(tool => tool.state === "running"));
      if (working) {
        const tool = working.tools.find(item => item.state === "running");
        return {icon: "●", text: `${tool.capability.startsWith("browser.") ? "正在查" : "正在執行"}：${subject(working)}`};
      }
      if (flash && Date.now() < flash.until) {
        const {item} = flash;
        if (item.state === "completed") return {icon: "✓", text: `做好了：${subject(item)}`, action: "看看", run: openActivity};
        if (item.state === "unknown") return {icon: "?", text: `結果沒確認：${subject(item)}`, action: "看看", run: openActivity, tone: "warn"};
        return {icon: "✕", text: `沒做成：${subject(item)}`, action: "看看", run: openActivity, tone: "bad"};
      }
      return null;
    };
    const renderBubble = () => {
      const quiet = chatOpen || window.siroSpeechBusy?.() || document.activeElement === document.querySelector("#text");
      const next = lastView && !quiet ? bubbleFor(lastView) : null;
      const show = next && next.text !== dismissed ? next : null;
      if (!next) dismissed = "";
      bubble.hidden = !show;
      if (!show) { bubbleRun = undefined; return; }
      bubble.setAttribute("data-tone", show.tone || "");
      bubbleIcon.textContent = show.icon;
      bubbleLabel.textContent = show.text;
      bubble.title = show.text;
      bubbleAction.hidden = !show.action;
      bubbleAction.textContent = show.action || "";
      bubbleRun = show.run;
    };
    bubbleAction.addEventListener("click", () => bubbleRun?.());
    bubble.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      // Esc here only folds the bubble; Esc elsewhere keeps its stop meaning.
      event.stopPropagation?.();
      dismissed = bubbleLabel.textContent;
      renderBubble();
    });
    const unwatchActivity = window.siroWatchActivity?.(view => {
      for (const item of view.items.values()) {
        const before = seenStates.get(item.activity_id);
        if (before && LIVE.has(before) && !LIVE.has(item.state) && item.state !== "cancelled" && item.tools?.length) flash = {item, until: Date.now() + 8000};
        seenStates.set(item.activity_id, item.state);
      }
      if (seenStates.size > 500) {
        seenStates.clear();
        for (const item of view.items.values()) seenStates.set(item.activity_id, item.state);
      }
      lastView = view;
      renderBubble();
    });
    const typing = document.querySelector("#text");
    typing?.addEventListener("focus", renderBubble);
    typing?.addEventListener("blur", renderBubble);
    // Walking: the character asks to walk; the native window travels and reports back to her.
    const toRole = update => {
      try { frame.contentWindow?.postMessage({...update, type: "siro.desktop.walk.state", v: 1}, location.origin); } catch (_) { /* renderer gone */ }
    };
    const walkUpdate = update => {
      const states = ["started", "stopping", "ended", "refused"];
      if (!update || typeof update.id !== "string" || !states.includes(update.state)) return;
      const numbers = ["direction", "distance", "ramp", "cruise", "delay", "remaining"].filter(key => key in update);
      if (!numbers.every(key => Number.isFinite(update[key]))) return;
      toRole(update);
    };
    const walkRequest = data => {
      if (typeof data.id !== "string" || data.id.length > 40) return;
      if (data.action === "stop") { nativeCommand({type: "desktop.walk.stop", id: data.id}); return; }
      const fields = ["distance", "speed", "ramp", "delay"];
      if (data.action !== "start" || ![-1, 0, 1].includes(data.direction) || !fields.every(key => Number.isFinite(data[key]))) return;
      const message = {type: "desktop.walk", id: data.id, direction: data.direction};
      for (const key of fields) message[key] = data[key];
      if (Number.isFinite(data.cycle)) message.cycle = data.cycle;
      if (chatOpen || !nativeCommand(message)) toRole({id: data.id, state: "refused", reason: chatOpen ? "chat" : "native"});
    };
    window.siroDesktopView = Object.freeze({toggleChat: () => setChat(!chatOpen), openChat: () => setChat(true), closeChat: () => setChat(false), setLayout, walkUpdate});
    window.addEventListener("message", event => {
      if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
      if (event.data?.type === "siro.renderer.ready") nativeCommand({type: "desktop.ready"});
      if (event.data?.type === "siro.renderer.interact" && !roleDragged) setChat(true);
      if (event.data?.type === "siro.desktop.walk" && event.data.v === 1) walkRequest(event.data);
    });
    updateStatus();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initializeDesktop, {once: true});
  else initializeDesktop();
})();
