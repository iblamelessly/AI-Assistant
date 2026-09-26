// JARVIS AI Assistant - Autonomous Agent & Voice Controller

let currentSessionId = null;
let isStreaming = false;
let currentAssistantBubble = null;
let currentStreamBuffer = "";
let voiceEnabled = true;

let recognition = null;
let isRecording = false;

// Simple, robust offline markdown parser
function parseMarkdown(text) {
  if (!text) return "";

  // Escape HTML tags
  let escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Code blocks: ```lang ... ```
  escaped = escaped.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, function(match, lang, code) {
    const langLabel = lang || "code";
    return `
      <div class="code-block-wrapper">
        <div class="code-header">
          <span>${langLabel}</span>
          <button class="btn-copy-code" onclick="copyCode(this)">Copy</button>
        </div>
        <pre><code>${code.trim()}</code></pre>
      </div>
    `;
  });

  // Inline code: `code`
  escaped = escaped.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Bold: **text**
  escaped = escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

  // Headings: ### text
  escaped = escaped.replace(/^### (.*$)/gim, "<h3>$1</h3>");
  escaped = escaped.replace(/^## (.*$)/gim, "<h2>$1</h2>");
  escaped = escaped.replace(/^# (.*$)/gim, "<h1>$1</h1>");

  // Lists: - item or * item
  escaped = escaped.replace(/^\s*[-*]\s+(.*$)/gim, "<li>$1</li>");
  escaped = escaped.replace(/(<li>.*<\/li>)/s, "<ul>$1</ul>");

  // Newlines to <br> if not inside code or lists
  escaped = escaped.replace(/\n\n/g, "</p><p>");
  escaped = escaped.replace(/\n/g, "<br>");

  return `<p>${escaped}</p>`;
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// Render tool or terminal execution output into chat bubble
function renderToolHtml(toolInfo) {
  if (!toolInfo || !toolInfo.result) return "";

  const toolName = toolInfo.tool || "";
  const res = toolInfo.result;

  if (toolName === "run_command" || toolName === "run_shell_command") {
    const isSuccess = res.success;
    const exitCode = res.exit_code !== undefined ? res.exit_code : (isSuccess ? 0 : 1);
    const outputText = res.stdout || res.stderr || res.summary || "Command finished.";

    return `
      <div class="terminal-card">
        <div class="terminal-card-header">
          <span class="terminal-cmd">&gt; powershell ${escapeHtml(toolInfo.param || res.command)}</span>
          <span class="terminal-status ${isSuccess ? 'success' : 'error'}">exit code ${exitCode}</span>
        </div>
        <div class="terminal-output">${escapeHtml(outputText)}</div>
      </div>
    `;
  }

  if (toolName === "read_file") {
    return `
      <div class="terminal-card">
        <div class="terminal-card-header">
          <span class="terminal-cmd">📄 File: ${escapeHtml(toolInfo.param || res.path)}</span>
          <span class="terminal-status ${res.success ? 'success' : 'error'}">${res.success ? 'Read OK' : 'Error'}</span>
        </div>
        <div class="terminal-output">${escapeHtml(res.content || res.summary)}</div>
      </div>
    `;
  }

  if (toolName === "take_screenshot") {
    return `<div class="tool-badge">📸 Screenshot: ${escapeHtml(res.path || 'Saved to screenshots folder')}</div>`;
  }

  if (toolName === "set_volume") {
    return `<div class="tool-badge">🔊 ${escapeHtml(res.summary || res.action || 'Volume updated')}</div>`;
  }

  if (toolName === "open_file") {
    return `<div class="tool-badge">📄 ${escapeHtml(res.summary || 'Opened file')}</div>`;
  }

  if (toolName === "open_folder") {
    return `<div class="tool-badge">📂 ${escapeHtml(res.summary || 'Opened folder')}</div>`;
  }

  if (toolName === "search_files" || toolName === "search_folders") {
    return `<div class="tool-badge">🔍 ${escapeHtml(res.summary ? res.summary.split('\n')[0] : 'Search completed')}</div>`;
  }

  const actionDesc = res.summary || res.action || "Action executed";
  return `<div class="tool-badge">⚡ ${escapeHtml(actionDesc)}</div>`;
}

// Dynamic smart icons for suggestions
function getSuggestionIcon(text) {
  const t = text.toLowerCase();
  if (t === "cancel" || t.includes("cancel")) return "✕";
  if (t.includes(".py") || t.includes(".txt") || t.includes(".pdf") || t.includes(".json") || t.includes(".doc") || t.includes("file")) return "📄";
  if (t.includes("folder") || t.includes("/") || t.includes("\\")) return "📁";
  if (t.includes("browser") || t.includes("web") || t.includes("http")) return "🌐";
  return "⚡";
}

// Universal Clipboard Copy with Fallback
function copyToClipboard(text, button, successLabel = "✓ Copied") {
  if (!text) return;
  const originalHtml = button.innerHTML;

  const showSuccess = () => {
    button.innerHTML = successLabel;
    button.style.color = "var(--accent-primary)";
    setTimeout(() => {
      button.innerHTML = originalHtml;
      button.style.color = "";
    }, 2000);
  };

  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(showSuccess).catch(() => {
      fallbackCopy(text, showSuccess);
    });
  } else {
    fallbackCopy(text, showSuccess);
  }
}

function fallbackCopy(text, cb) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  ta.style.top = "-9999px";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    document.execCommand("copy");
    if (cb) cb();
  } catch (err) {
    console.error("Clipboard copy failed:", err);
  }
  document.body.removeChild(ta);
}

// Copy code button handler
window.copyCode = function(button) {
  const codeBlock = button.closest(".code-block-wrapper").querySelector("pre code");
  if (codeBlock) {
    copyToClipboard(codeBlock.innerText, button, "✓ Copied");
  }
};

// Copy message text handler
window.copyMessage = function(button) {
  const bubble = button.closest(".message-bubble");
  if (!bubble) return;
  const clone = bubble.cloneNode(true);
  clone.querySelectorAll(".btn-copy-message, .btn-copy-code, .permission-prompt-actions, .tool-badge, .terminal-card").forEach(el => el.remove());
  const text = clone.innerText.trim();
  copyToClipboard(text, button, "✓ Copied");
};

// UI Initialization
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();

  if (window.pywebview) {
    onAppReady();
  } else {
    window.addEventListener("pywebviewready", onAppReady);
  }
});

function onAppReady() {
  window.pywebview.api.init_app().then((data) => {
    // Populate models
    const modelSelect = document.getElementById("model-select");
    const settingModelSelect = document.getElementById("setting-model-select");
    modelSelect.innerHTML = "";
    settingModelSelect.innerHTML = "";

    data.models.forEach((m) => {
      const opt1 = document.createElement("option");
      opt1.value = m;
      opt1.textContent = m;
      if (m === data.current_model) opt1.selected = true;
      modelSelect.appendChild(opt1);

      const opt2 = document.createElement("option");
      opt2.value = m;
      opt2.textContent = m;
      if (m === data.current_model) opt2.selected = true;
      settingModelSelect.appendChild(opt2);
    });

    // Populate provider & settings
    if (data.config) {
      const cfg = data.config;
      const provSelect = document.getElementById("setting-provider-select");
      if (provSelect) provSelect.value = cfg.provider || "groq";

      const keyInput = document.getElementById("setting-groq-key");
      if (keyInput) keyInput.value = cfg.groq_api_key || "";

      const groqModelSelect = document.getElementById("setting-groq-model");
      if (groqModelSelect) groqModelSelect.value = cfg.groq_model || "llama-3.3-70b-versatile";

      const ollamaUrlInput = document.getElementById("setting-ollama-url");
      if (ollamaUrlInput) ollamaUrlInput.value = cfg.ollama_url || "http://localhost:11434";

      const confirmActions = document.getElementById("setting-confirm-actions");
      if (confirmActions) confirmActions.checked = cfg.confirm_sensitive_actions !== false;

      const confirmPrivacy = document.getElementById("setting-confirm-privacy");
      if (confirmPrivacy) confirmPrivacy.checked = cfg.confirm_personal_data_access !== false;

      toggleProviderSections(cfg.provider || "groq");
    }

    // Populate sessions
    renderSessionList(data.sessions, data.active_session_id);

    // Update greeting with user name if known
    if (data.memory && data.memory.user && data.memory.user.name) {
      const userName = data.memory.user.name;
      document.getElementById("welcome-greeting").textContent = `Hello ${userName}, I am Jarvis.`;
    }

    // Voice initial state
    if (data.voice_enabled !== undefined) {
      voiceEnabled = data.voice_enabled;
      updateVoiceButtonUI();
    }

    // Populate memory modal
    populateMemoryUI(data.memory);

    // Populate stats
    if (data.system_stats) {
      updateStatsPill(data.system_stats);
    }
  }).catch((err) => {
    console.error("Init app error:", err);
  });
}

function updateVoiceButtonUI() {
  const btn = document.getElementById("btn-toggle-voice");
  if (voiceEnabled) {
    btn.classList.add("active");
    btn.title = "Jarvis Voice: ON (Click to Mute)";
  } else {
    btn.classList.remove("active");
    btn.title = "Jarvis Voice: MUTED (Click to Enable)";
  }
}

// Render Sessions
function renderSessionList(sessions, activeId) {
  const listEl = document.getElementById("session-list");
  listEl.innerHTML = "";

  if (!sessions || sessions.length === 0) {
    listEl.innerHTML = '<div style="padding:10px; color:var(--text-dim); font-size:12px;">No past chats</div>';
    return;
  }

  sessions.forEach((s) => {
    const item = document.createElement("div");
    item.className = `session-item ${s.id === activeId ? "active" : ""}`;
    item.dataset.id = s.id;

    item.innerHTML = `
      <span class="session-title" title="${s.title}">${s.title}</span>
      <button class="btn-del-session" title="Delete conversation" onclick="deleteSession(event, '${s.id}')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"></polyline>
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
        </svg>
      </button>
    `;

    item.addEventListener("click", () => switchSession(s.id));
    listEl.appendChild(item);
  });

  currentSessionId = activeId;
}

// Switch Session
function switchSession(sessionId) {
  if (isStreaming) return;
  window.pywebview.api.load_session(sessionId).then((session) => {
    currentSessionId = session.id;
    document.getElementById("current-session-title").textContent = session.title || "Conversation";

    document.querySelectorAll(".session-item").forEach((el) => {
      el.classList.toggle("active", el.dataset.id === sessionId);
    });

    renderMessages(session.messages);
  });
}

// Render Messages
function renderMessages(messages) {
  const container = document.getElementById("messages-container");
  const welcomeCard = document.getElementById("welcome-card");

  container.innerHTML = "";

  if (!messages || messages.length === 0) {
    container.appendChild(welcomeCard);
    welcomeCard.style.display = "flex";
    return;
  }

  welcomeCard.style.display = "none";

  messages.forEach((msg) => {
    appendMessageBubble(msg.role, msg.content, msg.tool_info);
  });

  scrollToBottom();
}

// Append Message Bubble
function appendMessageBubble(role, content, toolInfo = null) {
  const container = document.getElementById("messages-container");
  const welcomeCard = document.getElementById("welcome-card");
  if (welcomeCard) welcomeCard.style.display = "none";

  const row = document.createElement("div");
  row.className = `message-row ${role}`;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = role === "user" ? "You" : "J";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  let htmlContent = '<button class="btn-copy-message" onclick="copyMessage(this)" title="Copy message text">📋 Copy</button>';
  if (toolInfo) {
    htmlContent += renderToolHtml(toolInfo);
  }

  const cleanContent = (role === "assistant") ? content.replace(/\[Suggestion:\s*.*?\]/gi, "").trim() : content;
  htmlContent += parseMarkdown(cleanContent);

  // If Jarvis asks a human confirmation question, add interactive Yes/No buttons
  if (role === "assistant" && (content.includes("[Yes / No]") || content.includes("[Yes/No]") || content.includes("[Overwrite / Cancel]") || content.includes("Proceed?"))) {
    htmlContent += `
      <div class="permission-prompt-actions" style="margin-top:10px;">
        <button class="btn-confirm-yes" onclick="replyConfirmation('Yes, proceed')">✓ Approve / Yes</button>
        <button class="btn-confirm-no" onclick="replyConfirmation('No, cancel')">✕ Cancel / No</button>
      </div>
    `;
  }

  // If Jarvis offers application, file, or multiple-choice suggestions
  const suggMatch = content.match(/\[Suggestion:\s*(.*?)\]/i);
  if (role === "assistant" && suggMatch) {
    const rawOptions = suggMatch[1].split("|").map(s => s.trim()).filter(Boolean);
    if (rawOptions.length > 0) {
      let suggHtml = `<div class="app-suggestion-actions" style="margin-top:10px;">`;
      rawOptions.forEach(opt => {
        const cleanArg = opt.replace(/'/g, "\\'");
        const icon = getSuggestionIcon(opt);
        suggHtml += `<button class="btn-app-suggestion" onclick="replyConfirmation('${cleanArg}')">${icon} ${escapeHtml(opt)}</button>`;
      });
      suggHtml += `</div>`;
      htmlContent += suggHtml;
    }
  }

  bubble.innerHTML = htmlContent;

  row.appendChild(avatar);
  row.appendChild(bubble);
  container.appendChild(row);

  scrollToBottom();
  return bubble;
}

// Live tool execution callback during stream
window.onToolExecuted = function(toolInfo) {
  if (currentAssistantBubble) {
    const toolHtml = renderToolHtml(toolInfo);
    currentAssistantBubble.insertAdjacentHTML("afterbegin", toolHtml);
    scrollToBottom();
  }
};

// Streaming chunk handler
window.onStreamChunk = function(chunk) {
  currentStreamBuffer += chunk;
  if (currentAssistantBubble) {
    currentAssistantBubble.innerHTML = parseMarkdown(currentStreamBuffer) + '<span class="typing-cursor"></span>';
    scrollToBottom();
  }
};

// Stream complete handler with audio speech response
window.onStreamComplete = function(fullResponse, toolInfo, audioB64) {
  isStreaming = false;
  document.getElementById("btn-send").disabled = false;

  if (currentAssistantBubble) {
    let finalHtml = '<button class="btn-copy-message" onclick="copyMessage(this)" title="Copy message text">📋 Copy</button>';
    if (toolInfo) {
      finalHtml += renderToolHtml(toolInfo);
    }
    const cleanFull = fullResponse.replace(/\[Suggestion:\s*.*?\]/gi, "").trim();
    finalHtml += parseMarkdown(cleanFull);

    if (fullResponse.includes("[Yes / No]") || fullResponse.includes("[Yes/No]") || fullResponse.includes("[Overwrite / Cancel]") || fullResponse.includes("Proceed?")) {
      finalHtml += `
        <div class="permission-prompt-actions" style="margin-top:10px;">
          <button class="btn-confirm-yes" onclick="replyConfirmation('Yes, proceed')">✓ Approve / Yes</button>
          <button class="btn-confirm-no" onclick="replyConfirmation('No, cancel')">✕ Cancel / No</button>
        </div>
      `;
    }

    const completeSuggMatch = fullResponse.match(/\[Suggestion:\s*(.*?)\]/i);
    if (completeSuggMatch) {
      const rawOptions = completeSuggMatch[1].split("|").map(s => s.trim()).filter(Boolean);
      if (rawOptions.length > 0) {
        let suggHtml = `<div class="app-suggestion-actions" style="margin-top:10px;">`;
        rawOptions.forEach(opt => {
          const cleanArg = opt.replace(/'/g, "\\'");
          const icon = getSuggestionIcon(opt);
          suggHtml += `<button class="btn-app-suggestion" onclick="replyConfirmation('${cleanArg}')">${icon} ${escapeHtml(opt)}</button>`;
        });
        suggHtml += `</div>`;
        finalHtml += suggHtml;
      }
    }

    currentAssistantBubble.innerHTML = finalHtml;
  }

  // Play Neural Audio Speech if enabled
  if (audioB64 && voiceEnabled) {
    try {
      const audioEl = document.getElementById("jarvis-audio");
      if (audioEl) {
        audioEl.src = "data:audio/mp3;base64," + audioB64;
        audioEl.play().catch(e => console.warn("Audio playback failed:", e));
      }
    } catch (err) {
      console.warn("Audio play error:", err);
    }
  }

  currentAssistantBubble = null;
  currentStreamBuffer = "";

  // Refresh session list to update titles if changed
  window.pywebview.api.get_sessions().then((sessions) => {
    renderSessionList(sessions, currentSessionId);
  });

  // Refresh memory in background
  window.pywebview.api.get_memory().then((mem) => {
    populateMemoryUI(mem);
  });
};

// Send Message
function sendMessage() {
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text || isStreaming) return;

  input.value = "";
  input.style.height = "auto";
  isStreaming = true;
  document.getElementById("btn-send").disabled = true;

  // Append user bubble
  appendMessageBubble("user", text);

  // Create empty assistant bubble with cursor
  const container = document.getElementById("messages-container");
  const row = document.createElement("div");
  row.className = "message-row assistant";

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = "J";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.innerHTML = '<span class="typing-cursor"></span>';

  row.appendChild(avatar);
  row.appendChild(bubble);
  container.appendChild(row);

  currentAssistantBubble = bubble;
  currentStreamBuffer = "";
  scrollToBottom();

  // Call Python API
  window.pywebview.api.send_message(text, currentSessionId).catch((err) => {
    console.error("Send message error:", err);
    bubble.innerHTML = `<p style="color:var(--danger)">Error: ${err}</p>`;
    isStreaming = false;
    document.getElementById("btn-send").disabled = false;
  });
}

// Hardware Microphone & Voice Input Controller (Groq Whisper Bridge)
let isNativeRecording = false;
let recordingAutoStopTimer = null;

function toggleRecording() {
  const micBtn = document.getElementById("btn-mic");
  const chatInput = document.getElementById("chat-input");

  if (!isNativeRecording) {
    // Start Recording from hardware microphone
    isNativeRecording = true;
    micBtn.classList.add("listening");
    chatInput.placeholder = "🎙️ Listening... Speak now (Click mic or press Enter to send)";

    window.pywebview.api.start_voice_recording().then((res) => {
      if (res && res.status === "error") {
        console.warn("Could not start recording:", res.message);
        stopRecordingUI();
      }
    }).catch(err => {
      console.warn("Voice recording start error:", err);
      stopRecordingUI();
    });

    // Auto-stop after 8 seconds if user forgets to click stop
    clearTimeout(recordingAutoStopTimer);
    recordingAutoStopTimer = setTimeout(() => {
      if (isNativeRecording) {
        toggleRecording();
      }
    }, 8000);

  } else {
    // Stop Recording & Transcribe with Groq Whisper
    clearTimeout(recordingAutoStopTimer);
    stopRecordingUI();
    chatInput.placeholder = "⚡ Transcribing your voice with Groq Whisper...";

    window.pywebview.api.stop_voice_recording().then((res) => {
      chatInput.placeholder = "Ask Jarvis, give a voice command, or run any laptop task... (Shift + Enter for new line)";
      if (res && res.text) {
        chatInput.value = res.text;
        chatInput.style.height = "auto";
        chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
        sendMessage();
      }
    }).catch(err => {
      console.error("Transcription error:", err);
      chatInput.placeholder = "Ask Jarvis, give a voice command, or run any laptop task... (Shift + Enter for new line)";
    });
  }
}

function stopRecordingUI() {
  isNativeRecording = false;
  const micBtn = document.getElementById("btn-mic");
  if (micBtn) micBtn.classList.remove("listening");
}

// Memory Center Functions
function populateMemoryUI(memory) {
  if (!memory || !memory.user) return;
  const u = memory.user;

  document.getElementById("mem-name").value = u.name || "";
  document.getElementById("mem-career").value = u.career_goal || "";
  document.getElementById("mem-education").value = u.education || "";

  renderTags("projects", u.projects || []);
  renderTags("skills", u.skills || []);
  renderTags("preferences", u.preferences || []);
  renderTags("other", u.other || []);
}

function renderTags(category, items) {
  const container = document.getElementById(`tags-${category}`);
  const countBadge = document.getElementById(`count-${category}`);
  container.innerHTML = "";
  countBadge.textContent = items.length;

  if (items.length === 0) {
    container.innerHTML = '<span style="color:var(--text-dim); font-size:12px; font-style:italic;">No items yet</span>';
    return;
  }

  items.forEach((item, idx) => {
    const tag = document.createElement("div");
    tag.className = "tag-item";
    tag.innerHTML = `
      <span>${escapeHtml(item)}</span>
      <span class="btn-remove-tag" title="Remove" onclick="removeMemoryItem('${category}', ${idx})">&times;</span>
    `;
    container.appendChild(tag);
  });
}

window.removeMemoryItem = function(category, index) {
  window.pywebview.api.remove_memory_item(category, index).then((updatedMem) => {
    populateMemoryUI(updatedMem);
  });
};

window.deleteSession = function(event, sessionId) {
  event.stopPropagation();
  if (confirm("Delete this conversation?")) {
    window.pywebview.api.delete_session(sessionId).then((sessions) => {
      renderSessionList(sessions, sessions.length > 0 ? sessions[0].id : null);
      if (sessions.length > 0) {
        switchSession(sessions[0].id);
      } else {
        renderMessages([]);
      }
    });
  }
};

function updateStatsPill(stats) {
  const summaryEl = document.getElementById("stats-summary-text");
  if (stats && stats.cpu && stats.ram) {
    summaryEl.textContent = `CPU: ${stats.cpu.split(' ')[0]} | RAM: ${stats.ram.split(' ')[0]}G`;
  }
}

function scrollToBottom() {
  const container = document.getElementById("messages-container");
  container.scrollTop = container.scrollHeight;
}

// Event Listeners Setup
function setupEventListeners() {
  const chatInput = document.getElementById("chat-input");

  // Auto resize textarea
  chatInput.addEventListener("input", function() {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 140) + "px";
  });

  // Enter to send, Shift+Enter for newline
  chatInput.addEventListener("keydown", function(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  document.getElementById("btn-send").addEventListener("click", sendMessage);

  // Microphone click
  document.getElementById("btn-mic").addEventListener("click", toggleRecording);

  // Voice toggle button
  document.getElementById("btn-toggle-voice").addEventListener("click", () => {
    voiceEnabled = !voiceEnabled;
    updateVoiceButtonUI();
    window.pywebview.api.toggle_voice(voiceEnabled);
  });

  // New Chat button
  document.getElementById("btn-new-chat").addEventListener("click", () => {
    if (isStreaming) return;
    window.pywebview.api.create_session().then((newSession) => {
      window.pywebview.api.get_sessions().then((sessions) => {
        renderSessionList(sessions, newSession.id);
        switchSession(newSession.id);
      });
    });
  });

  // Clear chat button
  document.getElementById("btn-clear-chat").addEventListener("click", () => {
    if (currentSessionId && confirm("Clear current chat?")) {
      window.pywebview.api.clear_session_messages(currentSessionId).then(() => {
        renderMessages([]);
      });
    }
  });

  // Quick prompt cards and chips
  document.querySelectorAll("[data-prompt]").forEach((el) => {
    el.addEventListener("click", function() {
      const prompt = this.getAttribute("data-prompt");
      chatInput.value = prompt;
      sendMessage();
    });
  });

  // Model select
  document.getElementById("model-select").addEventListener("change", function() {
    window.pywebview.api.set_model(this.value);
  });

  // Quick stats header icon
  document.getElementById("btn-quick-stats").addEventListener("click", () => {
    chatInput.value = "Show my system performance metrics";
    sendMessage();
  });

  // Stats pill click to refresh
  document.getElementById("stats-pill").addEventListener("click", () => {
    window.pywebview.api.get_system_stats().then((stats) => {
      updateStatsPill(stats);
    });
  });

  // Modal open/close: Memory Center
  const memModal = document.getElementById("memory-modal");
  document.getElementById("btn-open-memory").addEventListener("click", () => {
    window.pywebview.api.get_memory().then((mem) => {
      populateMemoryUI(mem);
      memModal.classList.add("active");
    });
  });
  document.getElementById("btn-close-memory").addEventListener("click", () => {
    memModal.classList.remove("active");
  });

  // Save profile button
  document.getElementById("btn-save-profile").addEventListener("click", () => {
    const name = document.getElementById("mem-name").value;
    const career = document.getElementById("mem-career").value;
    const edu = document.getElementById("mem-education").value;
    window.pywebview.api.update_profile(name, career, edu).then((updated) => {
      populateMemoryUI(updated);
      alert("Profile memories updated successfully!");
    });
  });

  // Add tag buttons
  document.querySelectorAll(".btn-add-tag").forEach((btn) => {
    btn.addEventListener("click", function() {
      const cat = this.getAttribute("data-cat");
      const inputId = this.getAttribute("data-input");
      const input = document.getElementById(inputId);
      const val = input.value.trim();
      if (val) {
        window.pywebview.api.add_memory_item(cat, val).then((updated) => {
          populateMemoryUI(updated);
          input.value = "";
        });
      }
    });
  });

function toggleProviderSections(provider) {
  const groqSection = document.getElementById("section-groq-settings");
  const ollamaSection = document.getElementById("section-ollama-settings");
  if (provider === "groq") {
    if (groqSection) groqSection.style.display = "block";
    if (ollamaSection) ollamaSection.style.display = "none";
  } else {
    if (groqSection) groqSection.style.display = "none";
    if (ollamaSection) ollamaSection.style.display = "block";
  }
}

window.replyConfirmation = function(choice) {
  const input = document.getElementById("chat-input");
  input.value = choice;
  sendMessage();
};

  const provSelect = document.getElementById("setting-provider-select");
  if (provSelect) {
    provSelect.addEventListener("change", function() {
      toggleProviderSections(this.value);
    });
  }

  // Modal open/close: Settings
  const settingsModal = document.getElementById("settings-modal");
  document.getElementById("btn-open-settings").addEventListener("click", () => {
    settingsModal.classList.add("active");
  });
  document.getElementById("btn-close-settings").addEventListener("click", () => {
    settingsModal.classList.remove("active");
  });

  document.getElementById("btn-save-settings").addEventListener("click", () => {
    const provider = document.getElementById("setting-provider-select").value;
    const groqKey = document.getElementById("setting-groq-key").value.trim();
    const groqModel = document.getElementById("setting-groq-model").value;
    const ollamaUrl = document.getElementById("setting-ollama-url").value.trim();
    const ollamaModel = document.getElementById("setting-model-select").value;
    const personaName = document.getElementById("setting-persona-name").value.trim();
    const confirmActions = document.getElementById("setting-confirm-actions").checked;
    const confirmPrivacy = document.getElementById("setting-confirm-privacy").checked;

    window.pywebview.api.save_settings({
      provider: provider,
      groq_api_key: groqKey,
      groq_model: groqModel,
      ollama_url: ollamaUrl,
      ollama_model: ollamaModel,
      persona_name: personaName,
      confirm_sensitive_actions: confirmActions,
      confirm_personal_data_access: confirmPrivacy
    }).then(() => {
      settingsModal.classList.remove("active");
      alert("Settings saved! Jarvis will now use " + (provider === 'groq' ? 'Groq Llama 3.3 70B' : 'Local Ollama') + ".");
      window.location.reload();
    });
  });
}
