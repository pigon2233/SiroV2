/* Desktop pet. Talks to the gateway itself; the console page is not loaded.
   The VRM iframe owns /ws/body. This page owns /ws/control, turns, and audio. */
(() => {
  "use strict";
  let socket, currentTurn, assistantBubble, microphoneEnabled = false, authorizationMode = "full";
  let controlAttempt, controlDispose, controlEpoch = 0, controlAuthenticated = false;
  let reconnectTimer, reconnectAttempts = 0, pageClosing = false, online = false, detached = false;
  let submissionGeneration = 0, pendingSubmission, recorder, ttsAudio, ttsController;
  let ttsGeneration = 0, speechCancelled = false, liveSpeech, lastSpeech, speechStream = false;
  let speechEnabled = true, listening = false, recognizing = false, speaking = false, lastError = "";
  let replyGlanced = false;
  const researchTools = new Set();
  let phase = "connecting", stops = 0, chatOpen = false, roleDragged = false, hotTimer, reply, replyTimer;
  const runningTools = new Map();
  const startedAt = Date.now();
  const headers = () => ({"Content-Type": "application/json"});
  const $ = selector => document.querySelector(selector);
  const preview = () => typeof WebSocket !== "function" || location.protocol === "file:";

  function makeStatus(onText) {
    const node = {className: ""};
    let text = "";
    Object.defineProperty(node, "textContent", {
      get() { return text; },
      set(value) { text = String(value ?? ""); onText(text); },
    });
    return node;
  }
  const ttsStatus = makeStatus(text => {
    if (/正在說話/.test(text)) speaking = true;
    if (/朗讀完成|朗讀已停止|TTS 待命|朗讀失敗|時限|不一致/.test(text)) speaking = false;
    if (/朗讀失敗|沒有收到語音|不一致|已達朗讀時限/.test(text)) lastError = text;
    else if (/朗讀完成|朗讀已停止|TTS 待命|正在說話|準備|語音準備/.test(text) && /朗讀|語音/.test(lastError)) lastError = "";
    publishState();
  });
  const voiceStatus = makeStatus(text => {
    listening = /正在聆聽|免手動聆聽/.test(text);
    recognizing = /辨識中/.test(text);
    if (/無法使用麥克風|語音失敗|沒有辨識到|麥克風開關未確認|請先|沒聽清楚/.test(text)) lastError = text;
    else if (/辨識：|麥克風待命|麥克風已關閉|錄音與辨識已停止|免手動已關閉|直接說話/.test(text) && /麥克風|語音|辨識|聽清楚/.test(lastError)) lastError = "";
    publishState();
  });

  function publishState() {
    let state, label;
    if (detached) { state = "error"; label = "角色已交接"; }
    else if (!online) {
      state = lastError ? "error" : (preview() ? "offline" : "connecting");
      label = lastError ? "需要看一下" : (preview() ? "尚未連線" : "連線中");
    } else if (speaking) { state = "speaking"; label = "正在說"; }
    else if (listening) { state = "listening"; label = "正在聽"; }
    else if (recognizing || currentTurn || pendingSubmission || runningTools.size) { state = "thinking"; label = "正在想"; }
    else if (lastError) { state = "error"; label = "需要看一下"; }
    else { state = "ready"; label = "在"; }
    phase = state;
    $("#pet-state")?.setAttribute("data-state", state);
    const name = $("#pet-state-label");
    if (name) name.textContent = label;
    const err = $("#pet-error");
    if (err) { err.hidden = !lastError; err.textContent = lastError || ""; }
    const stop = $("#desktop-stop");
    if (stop) stop.hidden = !(listening || speaking || recognizing || currentTurn || pendingSubmission || runningTools.size);
    postAttention(attentionMode());
  }
  function attentionMode() {
    if (listening) return "listening";
    if (researchTools.size) return "research";
    if (recognizing || currentTurn || pendingSubmission || runningTools.size) return "thinking";
    return "idle";
  }
  function screenSide() {
    const width = window.screen?.width;
    if (!width) return 0;
    const mid = (window.screenX || 0) + (window.outerWidth || window.innerWidth || 0) / 2;
    return Math.max(-1, Math.min(1, (mid / width) * 2 - 1));
  }
  function postToRenderer(message) {
    const frame = $("#companion");
    if (!frame?.contentWindow || typeof frame.contentWindow.postMessage !== "function") return;
    try { frame.contentWindow.postMessage(message, location.origin); } catch { /* renderer gone */ }
  }
  function postAttention(mode) {
    postToRenderer({type: "siro.attention", v: 1, mode, side: screenSide()});
  }
  function glanceAt(node) {
    const frame = $("#companion");
    if (!frame || typeof frame.getBoundingClientRect !== "function" || typeof node?.getBoundingClientRect !== "function") return false;
    const a = frame.getBoundingClientRect();
    const b = node.getBoundingClientRect();
    if (!a.width || !a.height || b.width < 8 || b.height < 8) return false;
    const x = (b.left + b.width / 2 - a.left - a.width / 2) / a.width;
    const y = (b.top + b.height / 2 - a.top - a.height / 2) / a.height;
    postToRenderer({type: "siro.view.focus", v: 1, x, y});
    return true;
  }
  function glanceAtReply() {
    const chat = $("#pet-chat");
    if (chat && !chat.hidden && glanceAt(chat)) return;
    postAttention("reply");
  }
  function isResearchTool(name) {
    return typeof name === "string" && (name.startsWith("browser.") || name === "claude.ask");
  }
  function setNotice(text) {
    const bad = /未確認|沒有送出|中斷|無法|失敗|停用|尚未完成/.test(text);
    lastError = bad ? text : "";
    if (!bad && text) {
      reply = {text, until: Date.now() + 6000};
      clearTimeout(replyTimer);
      replyTimer = setTimeout(() => renderBubble(), 6050);
      replyTimer.unref?.();
    }
    publishState();
    renderBubble();
  }

  function createSessionAccess({fetcher = fetch, now = () => performance.now(), origin = location.origin} = {}) {
    let session, pending, retryAfter = 0, closed = false, bootstrap;
    async function getToken() {
      if (closed) throw new Error("頁面已關閉");
      if (session && now() < session.renewAt) return session.token;
      if (pending) return pending;
      if (now() < retryAfter) throw new Error("連線暫時無法恢復，請稍後再試。");
      pending = (async () => {
        bootstrap = new AbortController();
        const timeout = setTimeout(() => bootstrap.abort(), 5000);
        try {
          const response = await fetcher("/v1/session", {method: "POST", redirect: "error", headers: {Origin: origin}, signal: bootstrap.signal});
          if (!response.ok) throw new Error("無法建立連線，請稍後再試。");
          const data = await response.json(), ttl = data.expires_in_seconds * 1000;
          if (typeof data.token !== "string" || !data.token || !Number.isFinite(ttl) || ttl <= 0) throw new Error("連線資料無效，請重新連線。");
          if (closed) throw new Error("頁面已關閉");
          session = {token: data.token, renewAt: now() + ttl - Math.min(ttl * 0.1, 15000)};
          retryAfter = 0;
          return session.token;
        } catch (error) {
          retryAfter = now() + 3000;
          throw error;
        } finally { clearTimeout(timeout); bootstrap = undefined; }
      })().finally(() => { pending = undefined; });
      return pending;
    }
    async function request(url, options = {}) {
      if (typeof url !== "string" || !url.startsWith("/v1/")) throw new Error("不允許的連線目標");
      const target = new URL(url, origin);
      if (target.origin !== origin || !target.pathname.startsWith("/v1/")) throw new Error("不允許的連線目標");
      const check = () => {
        if (closed) throw new Error("頁面已關閉");
        if (options.signal?.aborted) throw new DOMException("已取消", "AbortError");
      };
      const send = token => {
        check();
        const requestHeaders = new Headers(options.headers);
        requestHeaders.set("Authorization", `Bearer ${token}`);
        const {onDispatch, onRejected, ...wireOptions} = options;
        onDispatch?.();
        return fetcher(url, {...wireOptions, redirect: "error", headers: requestHeaders});
      };
      check();
      const usedToken = await getToken();
      const response = await send(usedToken);
      if (response.url && new URL(response.url, origin).origin !== origin) throw new Error("不允許的連線回應");
      if (response.status !== 401) return response;
      const body = await response.clone().json().catch(() => null);
      if (body?.detail !== "session token is invalid or expired") return response;
      options.onRejected?.();
      check();
      if (session?.token === usedToken) session = undefined;
      return send(await getToken());
    }
    const invalidate = token => { if (session?.token === token) session = undefined; };
    return {getToken, request, invalidate, dispose: () => { closed = true; session = undefined; bootstrap?.abort(); }};
  }
  const sessionAccess = createSessionAccess();
  const authorizedFetch = (url, options) => sessionAccess.request(url, options);

  function createTerminalFence(limit = 1024) {
    const ended = new Set(), order = [];
    const progress = new Set(["assistant_started", "assistant_delta", "assistant_retry_wait", "assistant_route_notice", "affect_state", "agent_step", "tool_proposal", "tool_started", "tool_result"]);
    return data => {
      if (typeof data.stream_id !== "string") return true;
      if (ended.has(data.stream_id) && (progress.has(data.type) || data.type === "assistant_terminal")) return false;
      if (data.type === "assistant_terminal") {
        ended.add(data.stream_id); order.push(data.stream_id);
        if (order.length > limit) ended.delete(order.shift());
      }
      return true;
    };
  }
  const acceptRunEvent = createTerminalFence();

  function appendMessage(role, text) {
    const node = document.createElement("p");
    node.className = `message ${role}`;
    node.textContent = text || "";
    $("#messages")?.appendChild(node);
    const box = $("#messages");
    if (box) box.scrollTop = box.scrollHeight;
    return node;
  }
  function rememberReply(text) {
    if (!text || chatOpen || Date.now() - startedAt < 3000) return;
    reply = {text, until: Date.now() + Math.min(25000, 6000 + text.length * 90)};
    clearTimeout(replyTimer);
    replyTimer = setTimeout(() => renderBubble(), Math.max(0, reply.until - Date.now() + 50));
    $("#desktop-chat")?.classList.add("desktop-unread");
    renderBubble();
  }
  async function submitText(value, inputMode = "text") {
    if (foregroundControl.blocked()) return false;
    const submission = ++submissionGeneration;
    pendingSubmission?.abort(); pendingSubmission = undefined;
    stopTts(); speechCancelled = false;
    try { await connectControl(); }
    catch { appendMessage("assistant", "連線尚未完成，這則訊息沒有送出。"); return false; }
    if (pageClosing || submission !== submissionGeneration) return false;
    const controller = new AbortController(); pendingSubmission = controller;
    const dispatch = foregroundControl.begin(controller);
    appendMessage("user", value);
    publishState();
    try {
      const response = await authorizedFetch("/v1/conversations/browser/turns", {method: "POST", headers: headers(), signal: controller.signal, body: JSON.stringify({text: value, input_mode: inputMode}), onDispatch: () => foregroundControl.dispatch(dispatch), onRejected: () => { dispatch.dispatched = false; }});
      if (response.ok) foregroundControl.accepted(dispatch, (await response.json()).turn_id);
      if (!response.ok) appendMessage("assistant", response.status === 403 ? "對話目前被停用。請到控制台確認雲端對話設定。" : `訊息結果未確認（${response.status}），沒有自動重送；請先確認工作結果。`);
    } catch (error) {
      if (!controller.signal.aborted) appendMessage("assistant", "連線中斷，訊息結果未確認。我沒有自動重送，請先確認工作結果。");
    } finally {
      foregroundControl.settled(dispatch);
      if (pendingSubmission === controller) pendingSubmission = undefined;
      publishState();
    }
    return true;
  }
  function createForegroundControl() {
    let stopping = false, blocked = false, uncertain = false, observed = false, pending, turn, stream, deadline, stopEpoch = 0;
    const cancelled = new Set(), retired = new Set(), requests = new Set();
    const remember = (set, value) => {
      if (typeof value !== "string") return;
      set.add(value); if (set.size > 1024) set.delete(set.values().next().value);
    };
    const confirm = () => {
      if (stopping && !uncertain && observed && (!pending || pending.settled)) {
        blocked = false; clearTimeout(deadline); deadline = undefined;
        setNotice("已停止這次回覆，可以輸入下一則訊息。");
      }
    };
    const unconfirmed = (epoch = stopEpoch) => {
      if (epoch !== stopEpoch || !stopping || pageClosing) return;
      uncertain = true; blocked = true;
      setNotice("停止尚未確認，沒有重送操作；請先確認服務狀態。");
    };
    const cancelTurn = id => {
      if (typeof id !== "string" || cancelled.has(id) || pageClosing) return;
      remember(cancelled, id);
      const epoch = stopEpoch;
      const controller = new AbortController();
      const timer = setTimeout(() => { controller.abort(); unconfirmed(epoch); }, 5000);
      const owned = {controller, timer}; requests.add(owned);
      (async () => {
        try {
          const response = await authorizedFetch(`/v1/turns/${encodeURIComponent(id)}/cancel`, {method: "POST", headers: headers(), body: JSON.stringify({reason: "user"}), signal: controller.signal});
          if (!response.ok) throw new Error("cancel unavailable");
          if (epoch !== stopEpoch || uncertain || pageClosing) return;
          const check = await authorizedFetch("/v1/snapshot", {signal: controller.signal});
          if (!check.ok) throw new Error("readback unavailable");
          const snapshot = await check.json(), active = snapshot.active_turns?.browser;
          if (epoch !== stopEpoch) return;
          if (!active || active.turn_id !== id || !["responding", "awaiting_approval"].includes(active.state)) { observed = true; confirm(); }
        } catch { unconfirmed(epoch); }
        finally { clearTimeout(timer); requests.delete(owned); }
      })();
    };
    return {
      blocked: () => blocked,
      begin(controller) {
        stopEpoch++; clearTimeout(deadline);
        for (const owned of requests) { clearTimeout(owned.timer); owned.controller.abort(); }
        stopping = false; uncertain = false; observed = false;
        pending = {controller, dispatched: false, settled: false}; return pending;
      },
      dispatch(record) {
        if (stopping || record !== pending) throw new DOMException("已取消", "AbortError");
        record.dispatched = true;
      },
      accepted(record, id) { record.id = id; if (stopping) cancelTurn(id); },
      settled(record) {
        record.settled = true;
        if (stopping && record === pending) {
          if (!record.dispatched && !turn) observed = true;
          confirm();
        }
      },
      stop() {
        if (stopping) return;
        stopping = true; blocked = true; uncertain = false; observed = false;
        setNotice("正在停止回覆與語音…");
        deadline = setTimeout(() => {
          pending?.controller.abort();
          for (const owned of requests) owned.controller.abort();
          unconfirmed();
        }, 5000);
        if (pending && !pending.dispatched) pending.controller.abort();
        if (turn || currentTurn) cancelTurn(turn || currentTurn);
        else if (!pending || pending.settled) { observed = true; confirm(); }
        remember(retired, stream); currentTurn = undefined; assistantBubble = undefined;
      },
      event(data) {
        if (data.type === "turn_started") {
          if (turn !== data.turn_id) remember(retired, stream);
          turn = data.turn_id; stream = undefined;
          if (stopping) { cancelTurn(turn); return false; }
        }
        if (data.type === "assistant_started") {
          if (stopping) { stream = data.stream_id; remember(retired, data.stream_id); return false; }
          stream = data.stream_id;
        }
        if (data.type === "assistant_terminal" && stopping) {
          if (data.stream_id && retired.has(data.stream_id) && data.stream_id !== stream) return false;
          observed = true; remember(retired, data.stream_id); currentTurn = undefined; assistantBubble = undefined; confirm(); return false;
        }
        if (typeof data.stream_id === "string" && retired.has(data.stream_id)) return false;
        if (stopping && ["assistant_delta", "assistant_retry_wait", "assistant_route_notice", "affect_state"].includes(data.type)) return false;
        if (data.type === "assistant_terminal") {
          if (stream && data.stream_id && stream !== data.stream_id) return false;
          remember(retired, stream); turn = undefined; stream = undefined;
        }
        return true;
      },
      dispose() {
        clearTimeout(deadline); pending?.controller.abort();
        for (const owned of requests) { clearTimeout(owned.timer); owned.controller.abort(); }
        requests.clear();
      },
    };
  }
  const foregroundControl = createForegroundControl();

  function updateToolProposal(id, status) {
    const card = $(`#tool-${id}`); if (!card) return;
    let node = [...card.children].find(child => child.className === "tool-status");
    if (!node) { node = document.createElement("p"); node.className = "tool-status"; card.appendChild(node); }
    node.textContent = status;
  }
  function renderToolProposal(data) {
    const root = $("#messages");
    if (!root || $(`#tool-${data.proposal_id}`)) return;
    const card = document.createElement("div");
    card.className = "proposal"; card.id = `tool-${data.proposal_id}`;
    const description = document.createElement("p");
    const operation = data.capability === "process.start" ? "啟動應用程式" : data.capability === "browser.navigate+read" ? "開啟並讀取頁面" : data.capability;
    description.textContent = `操作：${operation}\n目標：${typeof data.target === "string" ? data.target : JSON.stringify(data.target ?? "")}`;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = data.automatic_approval_blocked === "prior_outcome_unknown" ? "確認結果後，授權這一次" : "授權這一次";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await connectControl();
        const response = await authorizedFetch(`/v1/tool-proposals/${data.proposal_id}/approve`, {method: "POST", headers: headers(), body: JSON.stringify({approved: true})});
        if (!response.ok) updateToolProposal(data.proposal_id, `授權結果未確認：${(await response.json()).detail}。沒有自動重送。`);
      } catch { updateToolProposal(data.proposal_id, "連線未完成，操作結果未確認。沒有自動重送。"); }
    });
    card.appendChild(description);
    if (authorizationMode !== "full" || data.automatic_approval_blocked === "prior_outcome_unknown") card.appendChild(button);
    root.appendChild(card);
    updateToolProposal(data.proposal_id, data.automatic_approval_blocked === "prior_outcome_unknown" ? "先前操作的結果未確認。請先確認實際結果，再決定是否授權。" : authorizationMode === "full" ? "已自動授權，等待執行…" : "等你允許這一次。");
  }
  function settleRunningTools(data) {
    for (const [id, stream] of runningTools) {
      if (typeof data.stream_id === "string" && stream !== data.stream_id) continue;
      runningTools.delete(id);
      researchTools.delete(id);
      updateToolProposal(id, data.state === "cancelled" ? "已停止：這次工作已取消，沒有自動重送。" : `未完成：沒有收到這個操作的結果${data.error ? `（${data.error}）` : ""}，不會自動重送。`);
    }
  }
  async function loadRuntime() {
    try {
      const response = await authorizedFetch("/v1/runtime");
      if (!response?.ok) return;
      speechStream = Boolean((await response.json()).speech_stream);
    } catch { /* snapshot already describes the switches */ }
  }
  function handleControlMessage(data) {
    if (!data || typeof data.type !== "string") return;
    if (!acceptRunEvent(data)) return;
    if (data.type === "assistant_terminal" && data.state !== "completed") settleRunningTools(data);
    if (!foregroundControl.event(data)) return;
    if (data.type === "snapshot") {
      online = true; controlAuthenticated = true; lastError = "";
      if (typeof data.authorization_mode === "string") authorizationMode = data.authorization_mode;
      if (typeof data.kill_switches?.microphone === "boolean") {
        microphoneEnabled = data.kill_switches.microphone;
        if (!microphoneEnabled) { cancelRecording(); stopHandsFree(); }
        updateMicrophoneControls();
      }
      publishState();
      loadRuntime();
      if (typeof window.siroWatchActivity !== "function") startActivityPoll();
    }
    if (data.type === "kill_switch" && data.name === "microphone" && typeof data.enabled === "boolean") {
      microphoneEnabled = data.enabled;
      if (!microphoneEnabled) { cancelRecording(); stopHandsFree(); }
      updateMicrophoneControls();
    }
    if (data.type === "turn_started") { currentTurn = data.turn_id; speechCancelled = false; stopTts(); publishState(); }
    if (data.type === "turn_cancelled") {
      if (!data.turn_id || data.turn_id === currentTurn) { currentTurn = undefined; speechCancelled = true; stopTts(); publishState(); }
    }
    if (data.type === "sensor_listen" && microphoneEnabled && recorder?.state !== "recording") onVoice();
    if (data.type === "assistant_retry_wait") {
      const seconds = Math.max(0, Math.min(60, Number(data.retry_after_seconds) || 0));
      setNotice(`對話服務暫時限流，約 ${Math.ceil(seconds)} 秒後重試這段回覆。可以隨時停止。`);
    }
    if (data.type === "assistant_route_notice" && typeof data.text === "string" && data.text) setNotice(data.text);
    if (data.type === "assistant_started") {
      assistantBubble = appendMessage("assistant", "");
      liveSpeech = beginLiveSpeech();
      replyGlanced = false;
    }
    if (data.type === "assistant_delta") {
      if (lastError && /限流/.test(lastError)) lastError = "";
      if (!assistantBubble) assistantBubble = appendMessage("assistant", "");
      assistantBubble.textContent += data.text || "";
      liveSpeech?.push(data.text || "");
      rememberReply(assistantBubble.textContent.trim());
      const box = $("#messages");
      if (box) box.scrollTop = box.scrollHeight;
      if (!replyGlanced) { replyGlanced = true; glanceAtReply(); }
    }
    if (data.type === "assistant_terminal") {
      const canonicalText = assistantBubble?.textContent || "";
      if (data.state !== "completed") {
        if (!assistantBubble) assistantBubble = appendMessage("assistant", "");
        const reasons = {
          ProviderOutputTruncated: "這次回覆未完成，文字生成已達上限。已收到的內容保留，沒有自動重送。",
          ProviderOutputFiltered: "這次回覆未完成，對話服務停止了這段輸出。",
          ProviderOutputIncomplete: "這次回覆未完成，沒有收到完整結束資訊。已收到的內容保留，沒有自動重送。",
        };
        const line = data.state === "cancelled" ? "已停止這次回覆。" : reasons[data.error] || "這次回覆未完成。請確認後再試。";
        assistantBubble.textContent += `${assistantBubble.textContent ? "\n" : ""}${line}${data.error && !reasons[data.error] && data.state !== "cancelled" ? `（${data.error}）` : ""}`;
        stopTts();
      }
      if (data.state === "completed" && canonicalText) {
        lastSpeech = {text: canonicalText, prosody: data.prosody || {}};
        const replay = $("#desktop-replay");
        if (replay) replay.disabled = false;
        if (liveSpeech?.started) { if (liveSpeech.current()) liveSpeech.finish(canonicalText, lastSpeech.prosody); }
        else if (!speechCancelled) playTts(canonicalText, lastSpeech.prosody);
        rememberReply(canonicalText);
      }
      assistantBubble = undefined; currentTurn = undefined; liveSpeech = undefined; publishState();
    }
    if (data.type === "tool_proposal") renderToolProposal(data);
    if (data.type === "tool_started") {
      runningTools.set(data.proposal_id, data.stream_id);
      if (isResearchTool(data.capability)) researchTools.add(data.proposal_id);
      updateToolProposal(data.proposal_id, "執行中…");
      publishState();
    }
    if (data.type === "tool_result") {
      runningTools.delete(data.proposal_id);
      researchTools.delete(data.proposal_id);
      updateToolProposal(data.proposal_id, "完成");
      publishState();
    }
  }
  function connectControl() {
    if (pageClosing) return Promise.reject(new Error("頁面已關閉"));
    if (controlAuthenticated && socket?.readyState === 1) return Promise.resolve();
    if (controlAttempt) return controlAttempt;
    const epoch = ++controlEpoch;
    controlAttempt = (async () => {
      const token = await sessionAccess.getToken();
      if (pageClosing || epoch !== controlEpoch) throw new Error("頁面已關閉或連線已交接");
      const ready = {};
      const authenticated = new Promise((resolve, reject) => { ready.resolve = resolve; ready.reject = reject; });
      const owner = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/control`);
      socket = owner; controlAuthenticated = false; online = false;
      let retired = false;
      const abandon = message => { retired = true; clearTimeout(timeout); controlAuthenticated = false; online = false; ready.reject(new Error(message)); };
      controlDispose = abandon;
      const timeout = setTimeout(() => { abandon("連線尚未完成，請再試一次。"); owner.close(); }, 5000);
      owner.onopen = () => { if (!retired && socket === owner && epoch === controlEpoch) owner.send(JSON.stringify({type: "authenticate", token})); };
      owner.onmessage = event => {
        if (retired || owner.readyState !== 1 || socket !== owner || epoch !== controlEpoch) return;
        let data; try { data = JSON.parse(event.data); } catch { return; }
        const wasOnline = controlAuthenticated;
        handleControlMessage(data);
        if (!wasOnline && controlAuthenticated) { clearTimeout(timeout); reconnectAttempts = 0; ready.resolve(); }
      };
      owner.onclose = event => {
        if (socket !== owner || epoch !== controlEpoch) return;
        if (!controlAuthenticated && event?.code === 1008 && event.reason === "invalid session token") sessionAccess.invalidate(token);
        abandon("連線中斷，已送出的工作不會自動重送。");
        stopTts();
        lastError = "連線中斷了。已送出的工作不會自動重送。";
        publishState();
        if (!pageClosing && reconnectAttempts < 3 && !reconnectTimer) {
          reconnectAttempts += 1;
          reconnectTimer = setTimeout(() => { reconnectTimer = undefined; connectControl().catch(() => {}); }, 250 * 2 ** reconnectAttempts);
        }
      };
      try { await authenticated; } finally { clearTimeout(timeout); }
    })().finally(() => { controlAttempt = undefined; });
    return controlAttempt;
  }

      function stopTts() {
        const active = Boolean(ttsController || ttsAudio);
        ttsGeneration++;
        ttsController?.abort(); ttsController = undefined;
        if (ttsAudio) {
          ttsAudio.onplay = null; ttsAudio.onended = null; ttsAudio.onerror = null;
          ttsAudio.pause(); URL.revokeObjectURL(ttsAudio.src);
          ttsAudio.removeAttribute?.("src"); ttsAudio.load?.(); ttsAudio = undefined;
        }
        const status = ttsStatus;
        status.textContent = active ? "朗讀已停止" : "TTS 待命"; status.className = "warn";
      }
      // Mouth sync: the audio path owns the mouth. Each TTS segment is decoded once into a
      // loudness/tone envelope and sampled on the playback clock, so the character's mouth
      // follows what is actually heard. Best effort only; playback never waits on it.
      const MOUTH_RATE = 60;
      function speechEnvelope(blob) {
        const Offline = globalThis.OfflineAudioContext;
        if (typeof Offline !== "function" || typeof blob?.arrayBuffer !== "function") return Promise.resolve(null);
        return blob.arrayBuffer().then(bytes => new Offline(1, 1, 16000).decodeAudioData(bytes)).then(buffer => {
          const data = buffer.getChannelData(0), step = buffer.sampleRate / MOUTH_RATE;
          const frames = Math.ceil(data.length / step);
          const loud = new Float32Array(frames), bright = new Float32Array(frames);
          for (let i = 0; i < frames; i++) {
            const a = Math.floor(i * step), b = Math.min(data.length, Math.floor((i + 1) * step));
            let sum = 0, crossings = 0;
            for (let j = a; j < b; j++) { sum += data[j] * data[j]; if (j > a && (data[j] >= 0) !== (data[j - 1] >= 0)) crossings++; }
            loud[i] = Math.sqrt(sum / Math.max(1, b - a)); bright[i] = crossings / Math.max(1, b - a);
          }
          const sorted = Float32Array.from(loud).sort(), voiced = Array.from(bright).filter((_, i) => loud[i] > sorted[Math.floor(frames * 0.5)]).sort((x, y) => x - y);
          const top = sorted[Math.floor(frames * 0.95)] || 1, low = voiced[Math.floor(voiced.length * 0.2)] ?? 0, high = voiced[Math.floor(voiced.length * 0.8)] ?? 1;
          const clamp = x => Math.max(0, Math.min(1, x));
          return Array.from(loud, (value, i) => [clamp((value / top - 0.1) / 0.8), clamp((bright[i] - low) / Math.max(1e-6, high - low))]);
        }).catch(() => null);
      }
      function syncMouth(audio, blob, current) {
        const target = document.querySelector("#companion")?.contentWindow, frame = globalThis.requestAnimationFrame;
        if (!target || typeof frame !== "function") return;
        let envelope = null, sent = -1, quiet = 0;
        const send = (level, tone) => {
          // skip near-duplicates, but refresh every few frames: the renderer closes a stale mouth
          if (Math.abs(level - sent) < 0.02 && (level !== 0 || sent === 0) && ++quiet < 6) return;
          sent = level; quiet = 0;
          try { target.postMessage({type: "siro.speech.mouth", v: 1, level, tone}, location.origin); } catch (_) { /* renderer gone */ }
        };
        if (Array.isArray(blob?.envelope)) envelope = blob.envelope; // streaming: grows as chunks arrive
        else speechEnvelope(blob).then(value => { envelope = value; });
        const step = () => {
          if (ttsAudio !== audio || !current()) { send(0, 0.5); return; }
          const sample = envelope && !audio.paused ? envelope[Math.floor(audio.currentTime * MOUTH_RATE)] : null;
          send(sample?.[0] ?? 0, sample?.[1] ?? 0.5);
          frame(step);
        };
        frame(step);
      }
      const validSpeechPlan = plan => Array.isArray(plan.segments) && plan.segments.length > 0 && plan.segments.length <= 128 &&
        plan.max_chars === 80 && plan.max_segments === 128 && plan.max_total_chars === 8000 &&
        typeof plan.version === "string" && Boolean(plan.version) && typeof plan.spoken_text === "string" &&
        Boolean(plan.spoken_text.trim()) && Array.from(plan.spoken_text).length <= 8000 &&
        !plan.segments.some(segment => typeof segment !== "string" || !segment.trim() || Array.from(segment).length > 80) &&
        plan.segments.reduce((sum, segment) => sum + Array.from(segment).length, 0) <= 8000 &&
        plan.segments.join("") === plan.spoken_text &&
        Number.isFinite(plan.deadline_seconds) && plan.deadline_seconds > 0 && plan.deadline_seconds <= 1200;
      // Text that can be read now: up to the last finished sentence, never inside an open code fence.
      function speakablePrefix(raw) {
        let head = raw;
        for (;;) {
          if ((head.split("```").length - 1) % 2) head = head.slice(0, head.lastIndexOf("```"));
          let end = -1;
          for (const match of head.matchAll(/[。！？!?\n]|\.(?=\s)/g)) end = match.index + match[0].length;
          const prefix = end > 0 ? head.slice(0, end) : "";
          // Cutting at a sentence end can land inside a fenced block that closes later.
          if ((prefix.split("```").length - 1) % 2 === 0) return prefix;
          head = prefix;
        }
      }
      // Live narration: start reading finished sentences while the reply is still streaming.
      // The completed reply is planned once more at the end, so the full text is still covered.
      function beginLiveSpeech() {
        if (speechCancelled || speechEnabled === false) return undefined;
        const live = {raw: "", final: undefined, prosody: {}, started: false, wake: undefined, current: () => false};
        live.push = text => {
          live.raw += text;
          if (!live.started && speakablePrefix(live.raw)) { live.started = true; playTts(undefined, {}, live); }
          live.wake?.();
        };
        live.finish = (text, prosody) => { live.final = text; live.prosody = prosody || {}; live.wake?.(); };
        return live;
      }
      async function playTts(text, prosody, live) {
        stopTts();
        if (speechEnabled === false) return;
        const generation = ttsGeneration;
        const controller = new AbortController(); ttsController = controller;
        const current = () => generation === ttsGeneration && !controller.signal.aborted;
        if (live) live.current = current;
        const status = ttsStatus; status.textContent = "準備全文朗讀…";
        const started = performance.now();
        let played = 0, total = 0, deadlineReached = false;
        let timer = setTimeout(() => { deadlineReached = true; controller.abort(); }, 1200000);
        const aborted = () => new DOMException("朗讀已停止", "AbortError");
        const assertCurrent = () => { if (!current()) throw aborted(); };
        const waitFor = promise => new Promise((resolve, reject) => {
          const cancel = () => reject(aborted());
          controller.signal.addEventListener("abort", cancel, {once: true});
          Promise.resolve(promise).then(resolve, reject).finally(() => controller.signal.removeEventListener("abort", cancel));
          if (!current()) cancel();
        });
        const request = async (url, body) => {
          assertCurrent();
          const response = await waitFor(authorizedFetch(url, {method: "POST", headers: headers(), signal: controller.signal, body: JSON.stringify(body)}));
          assertCurrent();
          if (!response.ok) throw new Error((await waitFor(response.json())).detail || `HTTP ${response.status}`);
          return response;
        };
        // Segments arrive all at once (planned text) or sentence by sentence (live narration).
        const segments = [];
        let closed = false, planError, waiters = [];
        const progress = () => closed ? `${played}/${total}` : `${played}`;
        const notify = () => { const pending = waiters; waiters = []; pending.forEach(resolve => resolve()); };
        const segmentAt = async index => {
          while (index >= segments.length && !closed) await waitFor(new Promise(resolve => waiters.push(resolve)));
          assertCurrent();
          if (index >= segments.length && planError) throw planError;
          return segments[index];
        };
        const loadSegment = async index => {
          try {
            const segment = await segmentAt(index);
            if (segment === undefined) return {done: true};
            if (index === 0 && speechStream) {
              // Only the first segment streams: later ones are prefetched while earlier ones play.
              // Any failure before audio exists falls back to the whole-sentence request below.
              try {
                const response = await request("/v1/audio/speech/stream", {text: segment, ...(live ? live.prosody : prosody)});
                const rate = Number(/rate=(\d+)/.exec(response.headers?.get?.("content-type") || "")?.[1]);
                if (typeof response.body?.getReader === "function" && rate >= 8000 && rate <= 96000) return {stream: {response, rate}};
                response.body?.cancel?.();
              } catch (error) { assertCurrent(); }
            }
            const response = await request("/v1/audio/speech", {text: segment, ...(live ? live.prosody : prosody)});
            const blob = await waitFor(response.blob()); assertCurrent();
            return {blob};
          } catch (error) { return {error}; } // A prefetched rejection always has an owner.
        };
        const plan = async body => {
          const response = await request("/v1/audio/speech/plan", body);
          const value = await waitFor(response.json()); assertCurrent();
          if (!validSpeechPlan(value)) throw new Error("朗讀計畫超出上限或內容無效，沒有截短播放");
          return value;
        };
        const accept = value => {
          total = value.segments.length;
          clearTimeout(timer);
          const remaining = value.deadline_seconds * 1000 - (performance.now() - started);
          if (remaining <= 0) { deadlineReached = true; controller.abort(); throw aborted(); }
          timer = setTimeout(() => { deadlineReached = true; controller.abort(); }, remaining);
        };
        // Planning a prefix closes it as a sentence (an extra "。", a line break read as a pause),
        // so queued text is matched to the full text ignoring punctuation and spacing.
        const unheardRest = (spoken, heard) => {
          const pause = /[\s。．.，,！!？?；;：:、…~～—-]/;
          const need = Array.from(heard).filter(c => !pause.test(c)).join("");
          const chars = Array.from(spoken);
          let index = 0, matched = 0;
          while (index < chars.length && matched < need.length) {
            if (!pause.test(chars[index])) { if (chars[index] !== need[matched]) return undefined; matched++; }
            index++;
          }
          if (matched < need.length) return undefined;
          while (index < chars.length && pause.test(chars[index])) index++;
          return chars.slice(index).join("");
        };
        // Where already-read text first stops matching the full plan, so a failure says what differed.
        const divergence = (spoken, heard) => {
          const pause = /[\s。．.，,！!？?；;：:、…~～—-]/;
          const need = Array.from(heard).filter(c => !pause.test(c)), chars = Array.from(spoken);
          let index = 0, matched = 0;
          while (index < chars.length && matched < need.length) {
            if (!pause.test(chars[index])) { if (chars[index] !== need[matched]) break; matched++; }
            index++;
          }
          return `已讀「${need.slice(Math.max(0, matched - 4), matched + 4).join("")}」與全文「${chars.slice(Math.max(0, index - 4), index + 4).join("")}」`;
        };
        const followLive = async () => {
          let planned = 0, deadlineSet = false;
          for (;;) {
            assertCurrent();
            const final = live.final;
            if (final === undefined) {
              const prefix = speakablePrefix(live.raw);
              if (prefix.length <= planned) { await waitFor(new Promise(resolve => { live.wake = resolve; })); continue; }
              planned = prefix.length;
              let value;
              try { value = await plan({text: prefix}); } catch (error) { assertCurrent(); continue; } // retried with more text
              if (!deadlineSet) { accept(value); deadlineSet = true; }
              // Only text not yet queued is new. A longer prefix can move earlier segment
              // boundaries (the short first segment grows), so then just the rest is planned.
              const heard = segments.join("");
              let fresh = value.segments;
              if (heard) {
                if (segments.every((segment, i) => segment === value.segments[i])) fresh = value.segments.slice(segments.length);
                else {
                  const rest = unheardRest(value.spoken_text, heard);
                  if (!rest?.trim()) continue; // nothing new yet, or the final plan settles it
                  try { fresh = (await plan({text: rest})).segments; } catch (error) { assertCurrent(); continue; }
                }
              }
              // Every segment but the last is final: later text only extends the last one.
              // A finished first sentence is read at once; that is what the short first segment is for.
              const stable = !heard && fresh.length === 1 && /[。！？!?]$/.test(fresh[0]) ? fresh : fresh.slice(0, -1);
              if (stable.length) { segments.push(...stable); notify(); }
              continue;
            }
            const value = await plan({text: final});
            accept(value);
            if (segments.every((segment, i) => segment === value.segments[i])) segments.push(...value.segments.slice(segments.length));
            else {
              // Already-read text no longer lines up with the full plan: read only what is left.
              const heard = segments.join("");
              const rest = unheardRest(value.spoken_text, heard);
              if (rest === undefined) {
                const detail = divergence(value.spoken_text, heard);
                console.error("speech mismatch", {heard, spoken: value.spoken_text});
                throw new Error(`朗讀內容與完整回覆不一致，沒有續播（${detail}）`);
              }
              if (rest.trim()) segments.push(...(await plan({text: rest})).segments);
            }
            total = segments.length; closed = true; notify(); return;
          }
        };
        // Plays PCM16 chunks on a WebAudio clock as they arrive. It stands in for the Audio
        // element (paused / currentTime / pause) so stopTts and the mouth sync need no changes.
        const playStream = async ({response, rate}) => {
          assertCurrent();
          const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
          if (!Context) throw new Error("瀏覽器不支援串流播放");
          let context;
          try { context = new Context({sampleRate: rate}); } catch (_) { context = new Context(); }
          const reader = response.body.getReader(), sources = [], envelope = [];
          let startedAt, nextAt = 0, carry = new Uint8Array(0), peak = 0.02, low = 1, high = 0;
          const player = {
            src: "", paused: false, envelope,
            get currentTime() { return startedAt === undefined ? 0 : Math.max(0, context.currentTime - startedAt); },
            pause() {
              player.paused = true;
              for (const source of sources) { try { source.stop(); } catch (_) { /* already ended */ } }
              reader.cancel().catch(() => {}); context.close?.().catch?.(() => {});
            },
          };
          ttsAudio = player;
          const cancel = () => player.pause();
          controller.signal.addEventListener("abort", cancel, {once: true});
          try {
            await waitFor(context.resume?.());
            for (;;) {
              const {done, value} = await waitFor(reader.read()); assertCurrent();
              if (done) break;
              const bytes = carry.length ? Uint8Array.from([...carry, ...value]) : value;
              const usable = bytes.length - (bytes.length % 2);
              carry = bytes.slice(usable);
              if (!usable) continue;
              const view = new DataView(bytes.buffer, bytes.byteOffset, usable), count = usable / 2;
              const buffer = context.createBuffer(1, count, rate), samples = buffer.getChannelData(0);
              for (let i = 0; i < count; i++) samples[i] = view.getInt16(i * 2, true) / 32768;
              // Best-effort mouth envelope with running normalisation (no whole-segment pass).
              const step = rate / MOUTH_RATE;
              for (let a = 0; a < count; a += step) {
                const end = Math.min(count, Math.floor(a + step));
                let sum = 0, crossings = 0;
                for (let j = Math.floor(a); j < end; j++) { sum += samples[j] * samples[j]; if (j > a && (samples[j] >= 0) !== (samples[j - 1] >= 0)) crossings++; }
                const loud = Math.sqrt(sum / Math.max(1, end - Math.floor(a))), bright = crossings / Math.max(1, end - Math.floor(a));
                peak = Math.max(peak, loud); if (loud > peak * 0.3) { low = Math.min(low, bright); high = Math.max(high, bright); }
                const clamp = x => Math.max(0, Math.min(1, x));
                envelope.push([clamp((loud / peak - 0.1) / 0.8), clamp((bright - low) / Math.max(1e-6, high - low))]);
              }
              const source = context.createBufferSource();
              source.buffer = buffer; source.connect(context.destination);
              if (startedAt === undefined) {
                nextAt = context.currentTime + 0.05; startedAt = nextAt;
                syncMouth(player, player, current);
                if (current()) { status.textContent = `SIRO 正在說話（已播 ${progress()} 段）`; status.className = "ok"; }
              } else if (nextAt < context.currentTime) nextAt = context.currentTime + 0.02; // late chunk: audible gap, not a stall
              source.start(nextAt); nextAt += buffer.duration; sources.push(source);
            }
            if (startedAt === undefined) throw new Error("沒有收到語音");
            await waitFor(new Promise(resolve => setTimeout(resolve, Math.max(0, (nextAt - context.currentTime) * 1000) + 30)));
            assertCurrent();
          } finally {
            controller.signal.removeEventListener("abort", cancel);
            player.pause();
            if (ttsAudio === player) ttsAudio = undefined;
          }
        };
        const playSegment = async blob => {
          assertCurrent();
          const url = URL.createObjectURL(blob);
          let audio;
          try { audio = new Audio(url); } catch (error) { URL.revokeObjectURL(url); throw error; }
          ttsAudio = audio;
          syncMouth(audio, blob, current);
          let cancel;
          try {
            await new Promise((resolve, reject) => {
              cancel = () => reject(aborted());
              controller.signal.addEventListener("abort", cancel, {once: true});
              audio.onplay = () => {
                if (current()) { status.textContent = `SIRO 正在說話（已播 ${progress()} 段）`; status.className = "ok"; }
              };
              audio.onended = () => { if (current()) resolve(); else reject(aborted()); };
              audio.onerror = () => reject(new Error("音訊播放失敗"));
              try {
                Promise.resolve(audio.play()).then(() => { if (!current()) audio.pause(); }, reject);
              } catch (error) { reject(error); }
            });
            assertCurrent();
          } finally {
            controller.signal.removeEventListener("abort", cancel);
            audio.onplay = null; audio.onended = null; audio.onerror = null; audio.pause();
            if (ttsAudio === audio) {
              URL.revokeObjectURL(audio.src); audio.removeAttribute?.("src"); audio.load?.(); ttsAudio = undefined;
            }
          }
        };
        try {
          if (live) {
            followLive().catch(error => { planError = error; closed = true; notify(); });
          } else {
            const value = await plan({text});
            accept(value);
            segments.push(...value.segments); closed = true;
          }
          let next = loadSegment(0);
          for (let index = 0; ; index++) {
            status.textContent = `語音準備中（已播 ${progress()} 段）`; status.className = "warn";
            const result = await next; assertCurrent();
            if (result.error) throw result.error;
            if (result.done) break;
            const playback = result.stream ? playStream(result.stream) : playSegment(result.blob);
            next = !closed || index + 1 < total ? loadSegment(index + 1) : undefined;
            await playback; assertCurrent();
            played++;
            if (!next) break;
          }
          if (planError) throw planError;
          status.textContent = `全文朗讀完成（${played}/${total} 段）`; status.className = "ok";
        } catch (error) {
          if (generation === ttsGeneration && (deadlineReached || !controller.signal.aborted)) {
            status.textContent = deadlineReached ? `已達朗讀時限（已播 ${progress()} 段），全文未完成。`
              : `朗讀失敗（已播 ${progress()} 段）：${error.message}。全文未完成。`;
            status.className = "warn";
          }
        } finally {
          clearTimeout(timer); controller.abort();
          if (ttsController === controller) ttsController = undefined;
        }
      }
      function wavFromBuffer(buffer) {
        const samples = buffer.getChannelData(0).subarray(0, Math.floor(buffer.sampleRate * 30)), data = new ArrayBuffer(44 + samples.length * 2);
        const view = new DataView(data), write = (offset, text) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
        write(0, "RIFF"); view.setUint32(4, 36 + samples.length * 2, true); write(8, "WAVE"); write(12, "fmt ");
        view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
        view.setUint32(24, buffer.sampleRate, true); view.setUint32(28, buffer.sampleRate * 2, true);
        view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, samples.length * 2, true);
        samples.forEach((sample, i) => view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, sample)) * (sample < 0 ? 32768 : 32767), true));
        return new Blob([data], {type: "audio/wav"});
      }
      async function openMicrophone(constraints) {
        // Some WebKit builds reject the processing hints; fall back to the plain device.
        try { return await navigator.mediaDevices.getUserMedia({audio: constraints}); }
        catch (error) { if (error?.name === "NotAllowedError" || error?.name === "NotFoundError") throw error; return await navigator.mediaDevices.getUserMedia({audio: true}); }
      }
      let microphoneEpoch = 0, microphoneCapture, transcriptionController, permissionPending = false;
      function updateMicrophoneControls() {
        const toggle = document.querySelector("#desktop-microphone");
        if (!toggle) return;
        toggle.textContent = microphoneEnabled ? "麥克風：開" : "麥克風：關";
        toggle.setAttribute?.("aria-pressed", String(microphoneEnabled));
        voiceStatus.textContent = microphoneEnabled ? "麥克風待命，按「說話」錄音" : "麥克風已關閉";
      }
      function cancelRecording() {
        microphoneEpoch++; permissionPending = false;
        transcriptionController?.abort(); transcriptionController = undefined;
        if (microphoneCapture) {
          const capture = microphoneCapture; microphoneCapture = undefined;
          clearTimeout(capture.timer);
          capture.recorder.onstop = null; capture.recorder.ondataavailable = null;
          if (capture.recorder.state === "recording") capture.recorder.stop();
          capture.stream.getTracks().forEach(track => track.stop());
        }
        recorder = undefined;
        const button = document.querySelector("#desktop-voice");
        button.disabled = false; button.textContent = "說話";
        voiceStatus.textContent = "錄音與辨識已停止";
      }
      async function transcribeRecording(chunks, epoch) {
        const current = () => epoch === microphoneEpoch && !pageClosing && microphoneEnabled;
        if (!current()) return;
        const controller = new AbortController(); transcriptionController = controller;
        const deadline = setTimeout(() => controller.abort(), 45000);
        const status = voiceStatus; status.textContent = "辨識中…";
        let context;
        try {
          const encoded = await new Blob(chunks).arrayBuffer();
          context = new AudioContext();
          const decoded = await context.decodeAudioData(encoded);
          if (!current() || controller.signal.aborted) return;
          const response = await authorizedFetch("/v1/audio/transcriptions?language=zh", {method: "POST", headers: {"Content-Type": "audio/wav"}, signal: controller.signal, body: wavFromBuffer(decoded)});
          if (!current() || controller.signal.aborted) return;
          if (!response.ok) throw new Error((await response.json()).detail || `HTTP ${response.status}`);
          const result = await response.json();
          if (!current() || controller.signal.aborted) return;
          if (!result.text) throw new Error("沒有辨識到語音");
          document.querySelector("#text").value = result.text;
          status.textContent = `辨識：${result.text}`; status.className = "ok";
          await submitText(result.text, "speech");
        } finally {
          clearTimeout(deadline); await context?.close();
          if (transcriptionController === controller) transcriptionController = undefined;
        }
      }

      // Hands-free listening: an energy detector starts capture when the owner speaks and
      // submits after a short pause. It never listens while SIRO is answering or speaking,
      // so her own voice is not captured; the microphone kill switch still owns the device.
      const handsFree = {on: false, stream: undefined, context: undefined, node: undefined, timer: undefined};
      const HANDS_FREE = {frameMs: 30, startMs: 150, endSilenceMs: 800, prerollMs: 300, tailHoldMs: 1500, minVoicedMs: 350, maxFloor: 0.05, maxMs: 29000, rate: 16000};
      function handsFreeBusy() {
        return Boolean(currentTurn || ttsController || ttsAudio || transcriptionController || microphoneCapture || permissionPending);
      }
      function downsampledWav(chunks, sourceRate) {
        const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0), ratio = sourceRate / HANDS_FREE.rate;
        const joined = new Float32Array(length);
        let offset = 0;
        for (const chunk of chunks) { joined.set(chunk, offset); offset += chunk.length; }
        const samples = new Float32Array(Math.floor(length / ratio));
        for (let i = 0; i < samples.length; i++) {
          const start = Math.floor(i * ratio), end = Math.min(length, Math.floor((i + 1) * ratio));
          let sum = 0;
          for (let j = start; j < end; j++) sum += joined[j];
          samples[i] = sum / Math.max(1, end - start);
        }
        return wavFromBuffer({sampleRate: HANDS_FREE.rate, getChannelData: () => samples});
      }
      async function submitUtterance(wav, epoch) {
        const status = voiceStatus;
        const current = () => epoch === microphoneEpoch && handsFree.on && !pageClosing && microphoneEnabled;
        const controller = new AbortController(); transcriptionController = controller;
        const deadline = setTimeout(() => controller.abort(), 45000);
        status.textContent = "辨識中…"; status.className = "warn";
        try {
          const response = await authorizedFetch("/v1/audio/transcriptions?language=zh", {method: "POST", headers: {"Content-Type": "audio/wav"}, signal: controller.signal, body: wav});
          if (!current()) return;
          if (!response.ok) throw new Error((await response.json()).detail || `HTTP ${response.status}`);
          const result = await response.json();
          if (!current()) return;
          if (!result.text) { status.textContent = "沒聽清楚，請再說一次"; return; }
          status.textContent = `辨識：${result.text}`; status.className = "ok";
          await submitText(result.text, "speech");
        } catch (error) {
          if (current()) { status.textContent = `語音失敗：${error.message}`; status.className = "warn"; }
        } finally {
          clearTimeout(deadline);
          if (transcriptionController === controller) transcriptionController = undefined;
        }
      }
      function stopHandsFree(message) {
        handsFree.on = false;
        clearInterval(handsFree.timer); handsFree.timer = undefined;
        if (handsFree.node) handsFree.node.onaudioprocess = null;
        handsFree.node?.disconnect(); handsFree.node = undefined;
        handsFree.stream?.getTracks().forEach(track => track.stop()); handsFree.stream = undefined;
        handsFree.context?.close().catch(() => {}); handsFree.context = undefined;
        const button = document.querySelector("#desktop-voice-auto");
        if (button) { button.textContent = "免手動：關"; button.setAttribute?.("aria-pressed", "false"); }
        if (message) voiceStatus.textContent = message;
      }
      async function startHandsFree() {
        const status = voiceStatus, button = document.querySelector("#desktop-voice-auto");
        if (!microphoneEnabled) { status.textContent = "請先按「麥克風：關」開啟，再使用免手動"; return; }
        cancelRecording();
        handsFree.on = true; button.textContent = "免手動：開"; button.setAttribute?.("aria-pressed", "true");
        status.textContent = "正在請求麥克風權限…";
        try {
          const stream = await openMicrophone({echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1});
          if (!handsFree.on || !microphoneEnabled || pageClosing) { stream.getTracks().forEach(track => track.stop()); return; }
          const context = new AudioContext(), source = context.createMediaStreamSource(stream);
          const node = context.createScriptProcessor(1024, 1, 1);
          Object.assign(handsFree, {stream, context, node});
          const frames = [], preroll = [], prerollLimit = Math.ceil(HANDS_FREE.prerollMs / 1000 * context.sampleRate / 1024);
          let speaking = false, loudMs = 0, quietMs = 0, spokenMs = 0, floor = 0.01, holdUntil = 0, epoch = microphoneEpoch;
          const idle = () => { status.textContent = "免手動聆聽中，直接說話即可"; status.className = "ok"; };
          idle();
          node.onaudioprocess = event => {
            const input = event.inputBuffer.getChannelData(0), chunk = Float32Array.from(input);
            event.outputBuffer?.getChannelData(0).fill(0);
            if (!microphoneEnabled || pageClosing) { stopHandsFree("麥克風已關閉"); return; }
            // Her voice keeps ringing in the room after playback ends, so stay deaf a moment longer.
            if (handsFreeBusy()) holdUntil = performance.now() + HANDS_FREE.tailHoldMs;
            if (!speaking && performance.now() < holdUntil) { preroll.length = 0; loudMs = 0; return; }
            let sum = 0;
            for (const value of chunk) sum += value * value;
            const level = Math.sqrt(sum / chunk.length), ms = chunk.length / context.sampleRate * 1000;
            const threshold = Math.max(0.012, floor * 3);
            if (!speaking) {
              preroll.push(chunk); if (preroll.length > prerollLimit) preroll.shift();
              if (level > threshold) { loudMs += ms; floor = Math.min(HANDS_FREE.maxFloor, floor * 0.995 + level * 0.005); } // steady video/game sound slowly becomes the floor
              else { loudMs = 0; floor = floor * 0.95 + level * 0.05; }
              if (loudMs >= HANDS_FREE.startMs) {
                speaking = true; quietMs = 0; spokenMs = 0; epoch = microphoneEpoch;
                frames.push(...preroll); preroll.length = 0;
                status.textContent = "正在聆聽…（停頓後自動送出）"; status.className = "ok";
              }
              return;
            }
            frames.push(chunk); spokenMs += ms;
            quietMs = level > threshold * 0.7 ? 0 : quietMs + ms;
            if (quietMs >= HANDS_FREE.endSilenceMs || spokenMs >= HANDS_FREE.maxMs) {
              speaking = false; loudMs = 0;
              const voicedMs = spokenMs - quietMs, wav = downsampledWav(frames.splice(0), context.sampleRate);
              if (voicedMs < HANDS_FREE.minVoicedMs) { idle(); return; } // a click or blip is not an utterance
              if (epoch === microphoneEpoch) submitUtterance(wav, epoch).finally(() => { if (handsFree.on && !handsFreeBusy()) idle(); });
            }
          };
          source.connect(node); node.connect(context.destination);
          // Show that listening resumed once SIRO has finished answering.
          let wasBusy = false;
          handsFree.timer = setInterval(() => {
            const busy = handsFreeBusy();
            if (wasBusy && !busy && !speaking) idle();
            wasBusy = busy;
          }, 250);
          handsFree.timer.unref?.();
        } catch (error) {
          stopHandsFree(`無法使用麥克風：${error.message}`);
        }
      }


  function nativeCommand(message) {
    const bridge = window.webkit?.messageHandlers?.siroDesktop;
    if (!bridge) return false;
    bridge.postMessage(JSON.stringify(message));
    return true;
  }
  function openControl(page) {
    const message = page ? {type: "desktop.console", page} : {type: "desktop.console"};
    if (nativeCommand(message)) return;
    const hash = page === "activity" ? "#/activity" : "#/chat";
    window.open(`/?view=control${hash}`, "siro-control");
  }
  function setChat(open) {
    chatOpen = Boolean(open);
    document.body.classList.toggle("desktop-chat-open", chatOpen);
    const chat = $("#pet-chat");
    if (chat) chat.hidden = !chatOpen;
    const chatButton = $("#desktop-chat");
    chatButton?.setAttribute("aria-expanded", String(chatOpen));
    chatButton?.classList.remove("desktop-unread");
    nativeCommand({type: "desktop.chat", open: chatOpen});
    if (chatOpen) $("#text")?.focus();
    renderBubble();
    return chatOpen;
  }
  function setMenu(open) {
    document.body.classList.toggle("pet-menu", open);
    document.body.classList.toggle("pet-hot", open || document.body.classList.contains("pet-hot"));
    const more = $("#pet-more");
    if (more) more.hidden = !open;
    $("#desktop-more")?.setAttribute("aria-expanded", String(open));
    if (!open && !document.body.classList.contains("pet-hot")) document.body.classList.remove("pet-hot");
  }
  function armHot() {
    clearTimeout(hotTimer);
    document.body.classList.add("pet-hot");
  }
  function disarmHot() {
    clearTimeout(hotTimer);
    hotTimer = setTimeout(() => { if (!document.body.classList.contains("pet-menu")) document.body.classList.remove("pet-hot"); }, 500);
  }
  function stopAll() {
    stops += 1;
    speechCancelled = true;
    submissionGeneration += 1;
    pendingSubmission?.abort();
    cancelRecording();
    stopHandsFree();
    stopTts();
    foregroundControl.stop();
    publishState();
  }
  const scaleButton = () => $("#desktop-scale");
  function setLayout(incoming) {
    const layout = incoming && {...incoming, paneX: incoming.paneX ?? incoming.petX, paneWidth: incoming.paneWidth ?? incoming.petWidth, controlsY: incoming.controlsY ?? incoming.petHeight + 10};
    const geometry = {petWidth: "pet-width", petHeight: "pet-height", petX: "pet-left", chatX: "chat-x", chatY: "chat-y", chatWidth: "chat-width", chatHeight: "chat-height", paneX: "pane-left", paneWidth: "pane-width", controlsY: "controls-y"};
    if (!layout || !Object.keys(geometry).every(key => Number.isSafeInteger(layout[key]) && layout[key] >= 0 && layout[key] <= 4096) || !Number.isFinite(layout.scale) || layout.scale <= 0 || layout.scale > 1.5) return;
    for (const [key, name] of Object.entries(geometry)) document.documentElement.style?.setProperty(`--desktop-${name}`, `${layout[key]}px`);
    const label = scaleButton();
    if (label) label.textContent = `${Math.round(layout.scale * 100)}%`;
  }
  const LIVE = new Set(["proposed", "queued", "running", "paused", "cancelling"]);
  const TOOL_NAMES = {"browser.navigate+read": "開網頁", "computer.execute": "執行程式"};
  let lastView, flash, hadLive = false, dismissed = "", bubbleRun, bubbleNote;
  const subject = item => item.reason || TOOL_NAMES[item.tools?.[0]?.capability] || "工具操作";
  const toolName = tool => tool ? (tool.target?.program ? `執行 ${tool.target.program}` : TOOL_NAMES[tool.capability] || "使用工具") : "使用工具";
  function bubbleFor(view) {
    const items = [...view.items.values()].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
    const live = items.filter(item => LIVE.has(item.state) && item.tools?.length);
    if (view.status === "offline") return hadLive ? {icon: "⚠", text: "斷線了，狀態可能過時", tone: "warn"} : null;
    if (view.status !== "ok") return null;
    hadLive = live.length > 0;
    const proposed = live.find(item => item.state === "proposed");
    if (proposed) return {icon: "◔", text: `等你允許：${toolName(proposed.tools[0])}`, action: "查看", run: () => setChat(true)};
    if (live.some(item => item.state === "cancelling" || view.stopping?.has(item.activity_id))) return {icon: "◌", text: "停止中…", tone: "warn"};
    const calm = Boolean(view.selfActivity?.quiet);
    const working = calm ? undefined : live.find(item => item.tools.some(tool => tool.state === "running"));
    if (working) {
      const tool = working.tools.find(item => item.state === "running");
      if (working.origin === "self_interest") {
        const id = working.activity_id;
        return {icon: "●", text: `自己在讀：${subject(working)}`, action: "停", run: () => window.siroStopActivity?.(id)};
      }
      return {icon: "●", text: `${tool.capability.startsWith("browser.") ? "正在查" : "正在執行"}：${subject(working)}`};
    }
    const note = calm ? undefined : view.selfActivity?.unshared?.[0];
    if (note) return {icon: "✓", text: "查好了，要聽嗎？", action: "聽", run: () => window.siroShareNote?.(note), note};
    if (flash && Date.now() < flash.until) {
      const {item} = flash;
      if (calm && item.state === "completed") return null;
      if (item.state === "completed") return {icon: "✓", text: `做好了：${subject(item)}`, action: "看看", run: () => openControl("activity")};
      if (item.state === "unknown") return {icon: "?", text: `結果沒確認：${subject(item)}`, action: "看看", run: () => openControl("activity"), tone: "warn"};
      return {icon: "✕", text: `沒做成：${subject(item)}`, action: "看看", run: () => openControl("activity"), tone: "bad"};
    }
    return null;
  }
  function renderBubble() {
    const bubble = $("#desktop-bubble");
    if (!bubble) return;
    const quiet = chatOpen || window.siroSpeechBusy?.() || document.activeElement === $("#text");
    if (reply && (chatOpen || Date.now() >= reply.until)) reply = undefined;
    const next = reply ? {icon: "", text: reply.text, kind: "reply"} : lastView && !quiet ? bubbleFor(lastView) : null;
    const show = next && next.text !== dismissed ? next : null;
    if (!next) dismissed = "";
    bubble.hidden = !show;
    if (!show) { bubbleRun = bubbleNote = undefined; return; }
    bubble.setAttribute("data-tone", show.tone || "");
    bubble.setAttribute("data-kind", show.kind || "");
    bubble.children[0].textContent = show.icon;
    bubble.children[1].textContent = show.text;
    bubble.title = show.text;
    bubble.children[2].hidden = !show.action;
    bubble.children[2].textContent = show.action || "";
    bubbleRun = show.run;
    bubbleNote = show.note;
  }
  function onActivity(view) {
    const seen = onActivity.seen || (onActivity.seen = new Map());
    for (const item of view.items.values()) {
      const before = seen.get(item.activity_id);
      if (before && LIVE.has(before) && !LIVE.has(item.state) && item.state !== "cancelled" && item.tools?.length) flash = {item, until: Date.now() + 8000};
      seen.set(item.activity_id, item.state);
    }
    if (seen.size > 500) { seen.clear(); for (const item of view.items.values()) seen.set(item.activity_id, item.state); }
    lastView = view;
    renderBubble();
  }
  function startActivityPoll() {
    if (startActivityPoll.started) return;
    startActivityPoll.started = true;
    const view = {items: new Map(), cursor: null, status: "idle", stopping: new Set(), selfActivity: null, epoch: 0, timer: 0};
    const apply = () => onActivity(view);
    async function read(url) {
      const response = await authorizedFetch(url, {headers: {Accept: "application/json"}});
      if (!response.ok && response.status !== 503) return null;
      const data = await response.json().catch(() => null);
      return data && data.status === "ok" ? data : null;
    }
    async function refresh() {
      try {
        const data = await read("/v1/activities?limit=50");
        if (!data) { view.status = "offline"; apply(); return; }
        view.items = new Map(data.activities.map(item => [item.activity_id, item]));
        view.cursor = data.cursor; view.status = "ok"; view.selfActivity = data.self_activity || null;
      } catch { view.status = "offline"; }
      apply();
      schedule(3000);
    }
    async function poll() {
      try {
        const data = await read(`/v1/activities/changes?after=${view.cursor}&limit=100`);
        if (!data) { view.status = "offline"; apply(); return; }
        if (data.gap) return refresh();
        for (const [id, item] of Object.entries(data.activities || {})) view.items.set(id, item);
        view.cursor = data.cursor; view.status = "ok";
        if (data.self_activity) view.selfActivity = data.self_activity;
        apply();
        schedule(data.has_more ? 0 : 3000);
      } catch { view.status = "offline"; apply(); schedule(3000); }
    }
    function schedule(delay) {
      clearTimeout(view.timer);
      if (pageClosing || !controlAuthenticated) return;
      view.timer = setTimeout(() => poll(), delay);
      view.timer.unref?.();
    }
    async function stopActivity(id) {
      if (view.status !== "ok" || view.stopping.has(id)) return;
      view.stopping.add(id); apply();
      try {
        const response = await authorizedFetch(`/v1/activities/${encodeURIComponent(id)}/stop`, {method: "POST"});
        if (!response.ok && response.status !== 409 && response.status !== 404) throw new Error("stop failed");
      } catch { view.stopping.delete(id); setNotice("停止沒有送出，請再按一次。"); }
      refresh();
    }
    async function noteAction(id, action) {
      try { await authorizedFetch(`/v1/self-notes/${encodeURIComponent(id)}/${action}`, {method: "POST"}); }
      catch { setNotice(action === "share" ? "這則沒有送出，請再按一次。" : "先沒能標成已讀，請再按一次。"); }
    }
    window.siroStopActivity ??= id => stopActivity(id);
    window.siroShareNote ??= id => noteAction(id, "share");
    window.siroDismissNote ??= id => noteAction(id, "dismiss");
    refresh();
    return () => { clearTimeout(view.timer); pageClosing = pageClosing; };
  }
  function toRole(update) {
    try { $("#companion")?.contentWindow?.postMessage({...update, type: "siro.desktop.walk.state", v: 1}, location.origin); } catch { /* renderer gone */ }
  }
  function walkUpdate(update) {
    const states = ["started", "stopping", "ended", "refused"];
    if (!update || typeof update.id !== "string" || !states.includes(update.state)) return;
    const numbers = ["direction", "distance", "ramp", "cruise", "delay", "remaining"].filter(key => key in update);
    if (!numbers.every(key => Number.isFinite(update[key]))) return;
    toRole(update);
  }
  function pointerUpdate(x, y) {
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    const frame = $("#companion");
    const box = frame?.getBoundingClientRect?.() || {left: 0, top: 0};
    try { frame?.contentWindow?.postMessage({type: "siro.desktop.pointer", v: 1, x: x - box.left, y: y - box.top}, location.origin); } catch { /* renderer gone */ }
  }
  function walkRequest(data) {
    if (typeof data.id !== "string" || data.id.length > 40) return;
    if (data.action === "stop") { nativeCommand({type: "desktop.walk.stop", id: data.id}); return; }
    const fields = ["distance", "speed", "ramp", "delay"];
    if (data.action !== "start" || ![-1, 0, 1].includes(data.direction) || !fields.every(key => Number.isFinite(data[key]))) return;
    const message = {type: "desktop.walk", id: data.id, direction: data.direction};
    for (const key of fields) message[key] = data[key];
    if (Number.isFinite(data.cycle)) message.cycle = data.cycle;
    if (chatOpen || !nativeCommand(message)) toRole({id: data.id, state: "refused", reason: chatOpen ? "chat" : "native"});
  }
  async function onVoice() {
    const button = $("#desktop-voice");
    if (!microphoneEnabled) { voiceStatus.textContent = "請先開啟麥克風，再開始說話"; voiceStatus.className = "warn"; return; }
    if (recorder?.state === "recording") { recorder.stop(); if (button) button.textContent = "說話"; return; }
    if (permissionPending) return;
    cancelRecording();
    const epoch = microphoneEpoch;
    permissionPending = true;
    if (button) button.disabled = true;
    voiceStatus.textContent = "正在請求麥克風權限…";
    try {
      const stream = await openMicrophone({echoCancellation: true, noiseSuppression: true, channelCount: 1});
      if (epoch !== microphoneEpoch || pageClosing || !microphoneEnabled) { stream.getTracks().forEach(track => track.stop()); return; }
      const chunks = [];
      let next;
      try {
        const mime = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find(type => MediaRecorder.isTypeSupported?.(type));
        next = mime ? new MediaRecorder(stream, {mimeType: mime}) : new MediaRecorder(stream);
      } catch (error) { stream.getTracks().forEach(track => track.stop()); throw error; }
      recorder = next;
      const capture = {recorder, stream, timer: undefined}; microphoneCapture = capture;
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      recorder.onstop = async () => {
        clearTimeout(capture.timer); stream.getTracks().forEach(track => track.stop());
        if (microphoneCapture === capture) microphoneCapture = undefined;
        if (button) button.textContent = "說話";
        listening = false; publishState();
        try { await transcribeRecording(chunks, epoch); }
        catch (error) { if (epoch === microphoneEpoch && !pageClosing) { voiceStatus.textContent = `語音失敗：${error.message}`; voiceStatus.className = "warn"; } }
      };
      recorder.start();
      capture.timer = setTimeout(() => { if (capture.recorder.state === "recording") capture.recorder.stop(); }, 30000);
      if (button) button.textContent = "停止並送出";
      voiceStatus.textContent = "正在聆聽（最長30秒）…"; voiceStatus.className = "ok";
    } catch (error) {
      if (epoch === microphoneEpoch) { cancelRecording(); voiceStatus.textContent = `無法使用麥克風：${error.message}`; voiceStatus.className = "warn"; }
    } finally {
      if (epoch === microphoneEpoch) { permissionPending = false; if (button) button.disabled = false; }
    }
  }
  async function onMicrophone() {
    const toggle = $("#desktop-microphone"), enabled = !microphoneEnabled;
    if (!enabled) { cancelRecording(); stopHandsFree(); }
    if (toggle) toggle.disabled = true;
    try {
      const response = await authorizedFetch("/v1/kill-switches/microphone", {method: "PUT", headers: headers(), body: JSON.stringify({enabled})});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      microphoneEnabled = enabled; updateMicrophoneControls();
    } catch (error) { voiceStatus.textContent = `麥克風開關未確認：${error.message}`; }
    finally { if (toggle) toggle.disabled = false; }
  }
  function bind(id, action) { $(id)?.addEventListener("click", action); }
  function init() {
    const frame = $("#companion");
    if (!frame || window.siroDesktopView) return;
    window.siroSpeechBusy ??= () => Boolean(ttsController || ttsAudio || speaking);
    const hide = $("#desktop-hide");
    if (hide) hide.title = window.siroDesktopHost === "electron" ? "先藏起來；可從系統匣恢復" : "最小化；可從工作列恢復";
    bind("#desktop-voice", () => { if (handsFree.on) stopHandsFree(); onVoice(); });
    bind("#desktop-stop", () => stopAll());
    bind("#desktop-more", () => setMenu(!document.body.classList.contains("pet-menu")));
    bind("#desktop-chat", () => setChat(!chatOpen));
    bind("#desktop-microphone", () => { if (microphoneEnabled && handsFree.on) stopHandsFree(); onMicrophone(); });
    bind("#desktop-voice-auto", () => handsFree.on ? stopHandsFree("免手動已關閉") : startHandsFree());
    bind("#desktop-speech", () => {
      speechEnabled = !speechEnabled;
      $("#desktop-speech")?.setAttribute("aria-pressed", String(speechEnabled));
      const node = $("#desktop-speech");
      if (node) node.textContent = speechEnabled ? "朗讀：開" : "朗讀：關";
      if (!speechEnabled) stopTts();
    });
    bind("#desktop-replay", async () => {
      if (!lastSpeech || pageClosing) return;
      speechEnabled = true;
      $("#desktop-speech")?.setAttribute("aria-pressed", "true");
      const node = $("#desktop-speech");
      if (node) node.textContent = "朗讀：開";
      speechCancelled = false;
      await playTts(lastSpeech.text, lastSpeech.prosody);
    });
    bind("#desktop-smaller", () => nativeCommand({type: "desktop.scale", step: -1}));
    bind("#desktop-scale", () => nativeCommand({type: "desktop.scale", step: 0}));
    bind("#desktop-larger", () => nativeCommand({type: "desktop.scale", step: 1}));
    bind("#desktop-console", () => openControl());
    bind("#desktop-hide", () => nativeCommand({type: "desktop.hide"}));
    bind("#desktop-quit", () => nativeCommand({type: "desktop.quit"}));
    $("#desktop-move")?.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      event.preventDefault();
      nativeCommand({type: "desktop.move", button: 1, screenX: event.screenX, screenY: event.screenY});
    });
    const chatForm = $("#chat");
    if (chatForm) chatForm.onsubmit = async event => {
      event.preventDefault();
      const input = $("#text");
      const value = input?.value || "";
      if (!value.trim()) return;
      if (input) input.value = "";
      if (await submitText(value) === false && input && !input.value) input.value = value;
    };
    const chatInput = $("#text");
    let composing = false;
    chatInput?.addEventListener("compositionstart", () => { composing = true; });
    chatInput?.addEventListener("compositionend", () => { composing = false; });
    chatInput?.addEventListener("keydown", event => {
      const ime = composing || event.isComposing || event.keyCode === 229 || event.which === 229;
      if (event.key === "Enter" && !event.shiftKey && !ime) { event.preventDefault(); chatForm?.requestSubmit?.(); }
    });
    let focusSentAt = -Infinity;
    const shareFocus = () => {
      const now = performance.now();
      if (!frame.contentWindow || frame.hidden || now - focusSentAt < 400 || !chatInput) return;
      const a = frame.getBoundingClientRect?.(), b = chatInput.getBoundingClientRect?.();
      if (!a?.width || !a.height || !b?.width) return;
      focusSentAt = now;
      const x = (b.left + b.width / 2 - a.left - a.width / 2) / a.width;
      const y = (b.top + b.height / 2 - a.top - a.height / 2) / a.height;
      try { frame.contentWindow.postMessage({type: "siro.view.focus", v: 1, x, y}, location.origin); } catch { /* renderer gone */ }
    };
    chatInput?.addEventListener("input", shareFocus);
    chatInput?.addEventListener("focus", () => { shareFocus(); renderBubble(); });
    chatInput?.addEventListener("blur", () => { composing = false; renderBubble(); });
    const bubble = $("#desktop-bubble");
    bubble?.children[2]?.addEventListener("click", () => bubbleRun?.());
    bubble?.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      event.stopPropagation?.();
      if (bubbleNote) { window.siroDismissNote?.(bubbleNote); bubble.hidden = true; return; }
      dismissed = bubble.children[1].textContent;
      renderBubble();
    });
    let pressed;
    const roleEvents = {
      pointerdown: event => { roleDragged = false; pressed = event.button === 0 ? {x: event.screenX, y: event.screenY, id: event.pointerId} : null; armHot(); },
      pointermove: event => {
        armHot();
        if (typeof event.buttons === "number" && !(event.buttons & 1)) { pressed = null; return; }
        if (!pressed || event.pointerId !== pressed.id || Math.hypot(event.screenX - pressed.x, event.screenY - pressed.y) < 7) return;
        if (nativeCommand({type: "desktop.move", button: 1, screenX: event.screenX, screenY: event.screenY})) { roleDragged = true; pressed = null; event.preventDefault(); }
      },
      pointerup: () => { pressed = null; },
      pointercancel: () => { pressed = null; },
      pointerleave: () => disarmHot(),
      click: event => { if (!roleDragged) return; event.preventDefault(); event.stopImmediatePropagation(); },
      dblclick: event => { if (!roleDragged) { event.preventDefault?.(); setChat(!chatOpen); } },
      contextmenu: event => { event.preventDefault?.(); setMenu(true); },
    };
    let roleDocument;
    const detachRole = () => {
      if (roleDocument) for (const [name, handler] of Object.entries(roleEvents)) roleDocument.removeEventListener(name, handler, true);
      roleDocument = null; pressed = null;
    };
    const attachRole = () => {
      let next; try { next = frame.contentDocument; } catch { return; }
      if (!next || roleDocument === next) return;
      detachRole(); roleDocument = next;
      for (const [name, handler] of Object.entries(roleEvents)) roleDocument.addEventListener(name, handler, true);
    };
    frame.addEventListener("load", attachRole);
    attachRole();
    $("#pet-stage")?.addEventListener("pointerenter", armHot);
    $("#pet-stage")?.addEventListener("pointerleave", disarmHot);
    $("#pet-controls")?.addEventListener("pointerenter", armHot);
    $("#pet-controls")?.addEventListener("pointerleave", disarmHot);
    $("#pet-stage")?.addEventListener("contextmenu", event => { event.preventDefault?.(); setMenu(true); });
    const unreadObserver = new MutationObserver(() => {
      if (!chatOpen) $("#desktop-chat")?.classList.add("desktop-unread");
    });
    const messages = $("#messages");
    if (messages) unreadObserver.observe(messages, {childList: true, characterData: true, subtree: true});
    const audioBusy = setInterval(() => {
      if (!frame.contentWindow || !(ttsAudio || ttsController || microphoneCapture || transcriptionController || handsFree.on)) return;
      try { frame.contentWindow.postMessage({type: "siro.audio.busy", v: 1, busy: true}, location.origin); } catch { /* renderer gone */ }
    }, 1000);
    const attentionPulse = setInterval(() => postAttention(attentionMode()), 2000);
    audioBusy?.unref?.();
    attentionPulse?.unref?.();
    window.addEventListener("message", event => {
      if (event.origin !== location.origin || event.source !== frame.contentWindow) return;
      const data = event.data;
      if (data?.type === "siro.renderer.detached") {
        detached = true; speechEnabled = false; stopTts();
        frame.hidden = true;
        lastError = "角色顯示已交給別的視窗。重新開啟桌寵可以拿回來。";
        publishState();
      }
      if (data?.type === "siro.renderer.ready") nativeCommand({type: "desktop.ready"});
      if (data?.type === "siro.desktop.walk" && data.v === 1) walkRequest(data);
    });
    window.addEventListener("keydown", event => {
      if (event.key === "F2") { event.preventDefault?.(); setChat(!chatOpen); return; }
      if (event.key !== "Escape") return;
      const bubbleNode = $("#desktop-bubble");
      if (event.target === bubbleNode || bubbleNode?.contains?.(event.target)) return;
      setMenu(false);
      stopAll();
      setChat(false);
    });
    window.addEventListener("pagehide", () => {
      observerStop?.(); unreadObserver.disconnect(); detachRole(); clearInterval(audioBusy); clearInterval(attentionPulse); clearTimeout(hotTimer); clearTimeout(replyTimer);
    }, {once: true});
    window.addEventListener("beforeunload", () => {
      pageClosing = true; controlDispose?.("頁面已關閉"); controlEpoch += 1;
      submissionGeneration += 1; pendingSubmission?.abort();
      clearTimeout(reconnectTimer); sessionAccess.dispose(); stopTts(); cancelRecording(); stopHandsFree(); socket?.close();
      foregroundControl.dispose();
    });
    const unwatch = typeof window.siroWatchActivity === "function" ? window.siroWatchActivity(onActivity) : null;
    const observerStop = () => unwatch?.();
    window.siroDesktopView = Object.freeze({toggleChat: () => setChat(!chatOpen), openChat: () => setChat(true), closeChat: () => setChat(false), setLayout, walkUpdate, pointerUpdate});
    window.siroPet = Object.freeze({
      applyControl: handleControlMessage,
      get state() { return phase; },
      get stops() { return stops; },
      speakablePrefix, validSpeechPlan,
    });
    updateMicrophoneControls();
    const speechButton = $("#desktop-speech");
    speechButton?.setAttribute("aria-pressed", "true");
    if (speechButton) speechButton.textContent = "朗讀：開";
    if (preview()) {
      lastError = "這是介面預覽，尚未連接 SIRO。請從桌寵啟動，才能對話。";
      publishState();
      return;
    }
    publishState();
    connectControl().catch(() => { lastError = "目前無法連接 SIRO。請確認服務已啟動；已送出的工作不會自動重送。"; publishState(); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, {once: true});
  else init();
})();
