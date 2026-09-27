// JARVIS AI Assistant - Autonomous Agent & Voice Controller

let currentSessionId = null;
let isStreaming = false;
let currentAssistantBubble = null;
let currentStreamBuffer = "";
let voiceEnabled = true;

let recognition = null;
let isRecording = false;

let pendingAttachments = [];

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function renderAttachmentPreviews() {
  const container = document.getElementById("attachment-preview-container");
  if (!container) return;
  container.innerHTML = "";

  if (pendingAttachments.length === 0) {
    container.style.display = "none";
    return;
  }

  container.style.display = "flex";

  pendingAttachments.forEach((att, idx) => {
    const chip = document.createElement("div");
    chip.className = "attachment-chip";

    const icon = att.type === "image" ? "🖼️" : (att.type === "video" ? "🎬" : "📄");

    chip.innerHTML = `
      <div class="attachment-thumb" id="att-thumb-${idx}">${icon}</div>
      <div class="attachment-info">
        <span class="attachment-name" title="${escapeHtml(att.name)}">${escapeHtml(att.name)}</span>
        <span class="attachment-size">${formatFileSize(att.size)}</span>
      </div>
      <button class="btn-remove-attachment" title="Remove attachment" onclick="removeAttachment(${idx})">&times;</button>
    `;

    container.appendChild(chip);

    if (att.dataUrl && att.type === "image") {
      const thumb = chip.querySelector(`#att-thumb-${idx}`);
      if (thumb) thumb.innerHTML = `<img src="${att.dataUrl}" style="width:100%; height:100%; object-fit:cover; border-radius:4px;" />`;
    } else if (att.path && att.type === "image" && window.pywebview && window.pywebview.api) {
      window.pywebview.api.get_media_data_url(att.path).then((dataUrl) => {
        if (dataUrl) {
          const thumb = chip.querySelector(`#att-thumb-${idx}`);
          if (thumb) thumb.innerHTML = `<img src="${dataUrl}" style="width:100%; height:100%; object-fit:cover; border-radius:4px;" />`;
        }
      });
    }
  });
}

window.removeAttachment = function(idx) {
  pendingAttachments.splice(idx, 1);
  renderAttachmentPreviews();
};

function renderMediaTags(htmlText) {
  if (!htmlText) return "";
  const mediaRegex = /\[MEDIA:\s*(image|video|audio)\s*\|\s*([^\]]+)\]/gi;
  return htmlText.replace(mediaRegex, function(match, type, filePath) {
    const cleanPath = filePath.trim();
    const fileName = cleanPath.split(/[\\/]/).pop();
    const cleanArg = cleanPath.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    const typeLower = type.toLowerCase();
    const typeLabel = typeLower === 'image' ? '🖼️ Photo' : (typeLower === 'video' ? '🎬 Video' : '🎵 Audio');

    let mediaElem = "";
    if (typeLower === "image") {
      mediaElem = `<img class="chat-media-img" data-media-src="${cleanArg}" alt="${escapeHtml(fileName)}" onclick="openMediaLightbox('${cleanArg}', 'image')" />`;
    } else if (typeLower === "video") {
      mediaElem = `<video class="chat-media-vid" data-media-src="${cleanArg}" controls preload="metadata"></video>`;
    } else if (typeLower === "audio") {
      mediaElem = `<audio class="chat-media-aud" data-media-src="${cleanArg}" controls></audio>`;
    }

    return `
      <div class="chat-media-card">
        <div class="chat-media-header">
          <span class="chat-media-badge">${typeLabel}</span>
          <span class="chat-media-filename" title="${escapeHtml(cleanPath)}">${escapeHtml(fileName)}</span>
          <button class="chat-media-btn-reveal" onclick="revealMediaFile('${cleanArg}')" title="Show in File Explorer">📂 Open Folder</button>
        </div>
        <div class="chat-media-content">
          ${mediaElem}
        </div>
      </div>
    `;
  });
}

function loadAsyncMediaElements(container) {
  if (!container || !window.pywebview || !window.pywebview.api) return;
  const elements = container.querySelectorAll("[data-media-src]:not([data-media-loaded])");
  elements.forEach((el) => {
    const rawPath = el.getAttribute("data-media-src");
    if (!rawPath) return;
    el.setAttribute("data-media-loaded", "pending");

    window.pywebview.api.get_media_data_url(rawPath).then((dataUrl) => {
      if (dataUrl) {
        el.src = dataUrl;
        el.setAttribute("data-media-loaded", "true");
      }
    }).catch(err => {
      console.warn("Could not load media:", rawPath, err);
    });
  });
}

function renderUserAttachments(attachments) {
  if (!attachments || attachments.length === 0) return "";
  let html = `<div class="user-attachment-gallery">`;
  attachments.forEach((att) => {
    const cleanPath = (att.path || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    if (att.type === "image") {
      html += `<img class="user-attachment-thumb" data-media-src="${cleanPath}" title="${escapeHtml(att.name)}" onclick="openMediaLightbox('${cleanPath}', 'image')" />`;
    } else if (att.type === "video") {
      html += `<video class="user-attachment-thumb" data-media-src="${cleanPath}" title="${escapeHtml(att.name)}" onclick="openMediaLightbox('${cleanPath}', 'video')"></video>`;
    } else {
      html += `<span class="attachment-chip" title="${escapeHtml(att.path)}">📄 ${escapeHtml(att.name)}</span>`;
    }
  });
  html += `</div>`;
  return html;
}

window.openMediaLightbox = function(filePath, mediaType) {
  const modal = document.getElementById("lightbox-modal");
  if (!modal) return;
  const titleEl = document.getElementById("lightbox-filename");
  const pathEl = document.getElementById("lightbox-filepath");
  const iconEl = document.getElementById("lightbox-type-icon");
  const bodyEl = document.getElementById("lightbox-body");
  const btnReveal = document.getElementById("btn-lightbox-reveal");

  const fileName = filePath.split(/[\\/]/).pop();
  if (titleEl) titleEl.textContent = fileName;
  if (pathEl) pathEl.textContent = filePath;
  if (iconEl) iconEl.textContent = mediaType === "video" ? "🎬" : "🖼️";
  if (bodyEl) bodyEl.innerHTML = `<span style="color:var(--text-muted); font-size:12px;">Loading media preview...</span>`;

  if (btnReveal) btnReveal.onclick = () => revealMediaFile(filePath);

  modal.classList.add("active");

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.get_media_data_url(filePath).then((dataUrl) => {
      if (!dataUrl) {
        bodyEl.innerHTML = `<p style="color:var(--danger)">Failed to load media preview for ${escapeHtml(fileName)}</p>`;
        return;
      }
      if (mediaType === "video") {
        bodyEl.innerHTML = `<video controls autoplay style="max-width:82vw; max-height:72vh; border-radius:8px;"><source src="${dataUrl}" type="video/mp4"></video>`;
      } else {
        bodyEl.innerHTML = `<img src="${dataUrl}" alt="${escapeHtml(fileName)}" style="max-width:82vw; max-height:72vh; border-radius:8px; object-fit:contain;" />`;
      }
    }).catch(err => {
      bodyEl.innerHTML = `<p style="color:var(--danger)">Error: ${err}</p>`;
    });
  }
};

window.revealMediaFile = function(filePath) {
  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.reveal_in_explorer(filePath);
  }
};

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

  if (toolName === "edit_image" || toolName === "image_edit" || toolName === "resize_image" || toolName === "crop_image" || toolName === "filter_image") {
    const isSuccess = res.success !== false;
    const actionDesc = res.summary || (isSuccess ? "Image edited successfully" : ("Error: " + (res.error || "Failed")));
    return `<div class="tool-badge">🖼️ ${escapeHtml(actionDesc)}</div>`;
  }

  if (toolName === "edit_video" || toolName === "video_edit" || toolName === "trim_video" || toolName === "extract_audio" || toolName === "mute_video") {
    const isSuccess = res.success !== false;
    const actionDesc = res.summary || (isSuccess ? "Video edited successfully" : ("Error: " + (res.error || "Failed")));
    return `<div class="tool-badge">🎬 ${escapeHtml(actionDesc)}</div>`;
  }

  if (toolName === "inspect_media") {
    return `<div class="tool-badge">📊 ${escapeHtml(res.summary || 'Media inspected')}</div>`;
  }

  if (toolName === "create_presentation" || toolName === "create_document" || toolName === "create_pdf") {
    const isSuccess = res.success !== false;
    const actionDesc = res.summary || (isSuccess ? "Document generated successfully" : ("Error: " + (res.error || "Failed")));
    const icon = toolName === "create_presentation" ? "📊" : (toolName === "create_document" ? "📝" : "📑");
    return `<div class="tool-badge">${icon} ${escapeHtml(actionDesc)}</div>`;
  }

  const actionDesc = res.summary || res.action || "Action executed";
  return `<div class="tool-badge">⚡ ${escapeHtml(actionDesc)}</div>`;
}

// Dynamic smart icons for suggestions
function getSuggestionIcon(text) {
  const t = text.toLowerCase();
  if (t === "cancel" || t.includes("cancel")) return "✕";
  if (t.includes("open document") || t.includes("view document")) return "📖";
  if (t.includes("reveal") || t.includes("folder")) return "📂";
  if (t.includes("ppt") || t.includes("presentation") || t.includes("slides")) return "📊";
  if (t.includes("word") || t.includes("docx")) return "📝";
  if (t.includes("pdf")) return "📑";
  if (t.includes("channel") || t.includes("youtube") || t.includes("video")) return "▶️";
  if (t.includes("browser") || t.includes("web") || t.includes("official") || t.includes("page") || t.includes("site") || t.includes("http")) return "🌐";
  if (t.includes(".py") || t.includes(".txt") || t.includes(".json") || t.includes(".doc") || t.includes("file")) return "📄";
  return "⚡";
}

// Extract suggestions from [Suggestion: ...] or bracketed choices [Opt 1] [Opt 2] [Cancel]
function extractSuggestions(content) {
  if (!content) return { cleanText: "", suggestions: [] };

  let text = content;
  let suggestions = [];

  // 1. Explicit [Suggestion: Option 1 | Option 2 | Cancel]
  const suggMatch = text.match(/\[Suggestion:\s*(.*?)\]/i);
  if (suggMatch) {
    const rawOptions = suggMatch[1].split("|").map(s => s.trim()).filter(Boolean);
    suggestions.push(...rawOptions);
    text = text.replace(/\[Suggestion:\s*.*?\]/gi, "").trim();
  }

  // 2. Trailing bracketed buttons [Opt 1] [Opt 2] [Cancel], separated by em-space (\u2003), spaces, tabs, or |
  if (suggestions.length === 0) {
    const trailingPattern = /(?:(?:\*{0,2})\[([^[\]\n]{2,60})\](?:\*{0,2})[\s\u2000-\u200B|]{0,8}){2,}\s*$/;
    const trailingMatch = text.match(trailingPattern);
    if (trailingMatch) {
      const chunk = trailingMatch[0];
      const singleItemRegex = /\[([^[\]\n]{2,60})\]/g;
      let m;
      const found = [];
      while ((m = singleItemRegex.exec(chunk)) !== null) {
        const item = m[1].trim();
        if (!item.startsWith("ACTION:") && !item.startsWith("MEDIA:") && !item.startsWith("DOCUMENT:") && !item.startsWith("http")) {
          found.push(item);
        }
      }
      if (found.length >= 2) {
        suggestions.push(...found);
        text = text.substring(0, trailingMatch.index).trim();
      }
    }
  }

  return { cleanText: text, suggestions };
}

// Render generated presentation, word, or pdf document card
function renderDocumentTags(htmlText) {
  if (!htmlText) return "";
  const docRegex = /\[DOCUMENT:\s*(pptx|docx|pdf)\s*\|\s*([^\]]+)\]/gi;
  return htmlText.replace(docRegex, function(match, format, filePath) {
    const cleanPath = filePath.trim();
    const fileName = cleanPath.split(/[\\/]/).pop();
    const cleanArg = cleanPath.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
    const fmt = format.toLowerCase();

    let icon = "📊";
    let badgeLabel = "PowerPoint Presentation";
    let badgeClass = "badge-pptx";

    if (fmt === "docx") {
      icon = "📝";
      badgeLabel = "Word Document";
      badgeClass = "badge-docx";
    } else if (fmt === "pdf") {
      icon = "📑";
      badgeLabel = "PDF Document";
      badgeClass = "badge-pdf";
    }

    return `
      <div class="chat-document-card">
        <div class="chat-doc-icon-box ${badgeClass}">
          <span class="chat-doc-big-icon">${icon}</span>
          <span class="chat-doc-format-label">${fmt.toUpperCase()}</span>
        </div>
        <div class="chat-doc-details">
          <div class="chat-doc-header">
            <span class="chat-doc-badge ${badgeClass}">${badgeLabel}</span>
          </div>
          <div class="chat-doc-filename" title="${escapeHtml(cleanPath)}">${escapeHtml(fileName)}</div>
          <div class="chat-doc-actions">
            <button class="btn-doc-action primary" onclick="openDocumentFile('${cleanArg}')" title="Open in default viewer">
              <span>▶ Open Document</span>
            </button>
            <button class="btn-doc-action" onclick="revealMediaFile('${cleanArg}')" title="Reveal in File Explorer">
              <span>📂 Open Folder</span>
            </button>
          </div>
        </div>
      </div>
    `;
  });
}

window.openDocumentFile = function(filePath) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.open_document_file) {
    window.pywebview.api.open_document_file(filePath);
  } else if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.reveal_in_explorer(filePath);
  }
};

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
    appendMessageBubble(msg.role, msg.content, msg.tool_info, msg.attachments);
  });

  scrollToBottom();
}

// Append Message Bubble
function appendMessageBubble(role, content, toolInfo = null, attachments = null) {
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

  if (role === "user" && attachments && attachments.length > 0) {
    htmlContent += renderUserAttachments(attachments);
  }

  let cleanContent = content;
  let suggestions = [];
  if (role === "assistant") {
    const extracted = extractSuggestions(content);
    cleanContent = extracted.cleanText;
    suggestions = extracted.suggestions;
  }
  htmlContent += renderDocumentTags(renderMediaTags(parseMarkdown(cleanContent)));

  // If Jarvis asks a human confirmation question, add interactive Yes/No buttons
  if (role === "assistant" && (content.includes("[Yes / No]") || content.includes("[Yes/No]") || content.includes("[Overwrite / Cancel]") || content.includes("Proceed?"))) {
    htmlContent += `
      <div class="permission-prompt-actions" style="margin-top:10px;">
        <button class="btn-confirm-yes" onclick="replyConfirmation('Yes, proceed')">✓ Approve / Yes</button>
        <button class="btn-confirm-no" onclick="replyConfirmation('No, cancel')">✕ Cancel / No</button>
      </div>
    `;
  }

  // If Jarvis offers application, file, document, or multiple-choice suggestions
  if (role === "assistant" && suggestions.length > 0) {
    let suggHtml = `<div class="app-suggestion-actions" style="margin-top:10px;">`;
    suggestions.forEach(opt => {
      const cleanArg = opt.replace(/'/g, "\\'");
      const icon = getSuggestionIcon(opt);
      suggHtml += `<button class="btn-app-suggestion" onclick="replyConfirmation('${cleanArg}')">${icon} ${escapeHtml(opt)}</button>`;
    });
    suggHtml += `</div>`;
    htmlContent += suggHtml;
  }

  bubble.innerHTML = htmlContent;

  row.appendChild(avatar);
  row.appendChild(bubble);
  container.appendChild(row);

  loadAsyncMediaElements(bubble);

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
    const extracted = extractSuggestions(currentStreamBuffer);
    currentAssistantBubble.innerHTML = renderDocumentTags(renderMediaTags(parseMarkdown(extracted.cleanText))) + '<span class="typing-cursor"></span>';
    loadAsyncMediaElements(currentAssistantBubble);
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
    const extracted = extractSuggestions(fullResponse);
    finalHtml += renderDocumentTags(renderMediaTags(parseMarkdown(extracted.cleanText)));

    if (fullResponse.includes("[Yes / No]") || fullResponse.includes("[Yes/No]") || fullResponse.includes("[Overwrite / Cancel]") || fullResponse.includes("Proceed?")) {
      finalHtml += `
        <div class="permission-prompt-actions" style="margin-top:10px;">
          <button class="btn-confirm-yes" onclick="replyConfirmation('Yes, proceed')">✓ Approve / Yes</button>
          <button class="btn-confirm-no" onclick="replyConfirmation('No, cancel')">✕ Cancel / No</button>
        </div>
      `;
    }

    if (extracted.suggestions.length > 0) {
      let suggHtml = `<div class="app-suggestion-actions" style="margin-top:10px;">`;
      extracted.suggestions.forEach(opt => {
        const cleanArg = opt.replace(/'/g, "\\'");
        const icon = getSuggestionIcon(opt);
        suggHtml += `<button class="btn-app-suggestion" onclick="replyConfirmation('${cleanArg}')">${icon} ${escapeHtml(opt)}</button>`;
      });
      suggHtml += `</div>`;
      finalHtml += suggHtml;
    }

    currentAssistantBubble.innerHTML = finalHtml;
    loadAsyncMediaElements(currentAssistantBubble);
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
  const hasAttachments = pendingAttachments.length > 0;
  if ((!text && !hasAttachments) || isStreaming) return;

  const userText = text || (hasAttachments ? (pendingAttachments[0].type === "image" ? "Please inspect and display this image." : "Please inspect and display this video.") : "");
  input.value = "";
  input.style.height = "auto";
  isStreaming = true;
  document.getElementById("btn-send").disabled = true;

  const attachmentsToSend = [...pendingAttachments];
  pendingAttachments = [];
  renderAttachmentPreviews();

  // Append user bubble
  appendMessageBubble("user", userText, null, attachmentsToSend);

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
  window.pywebview.api.send_message(userText, currentSessionId, attachmentsToSend).catch((err) => {
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

  // Media Attachment button & file picker
  const btnAttach = document.getElementById("btn-attach");
  const mediaInput = document.getElementById("media-file-input");

  if (btnAttach) {
    btnAttach.addEventListener("click", () => {
      if (window.pywebview && window.pywebview.api && window.pywebview.api.select_media_files) {
        window.pywebview.api.select_media_files().then((files) => {
          if (files && files.length > 0) {
            files.forEach(f => {
              if (!pendingAttachments.some(a => a.path === f.path)) {
                pendingAttachments.push(f);
              }
            });
            renderAttachmentPreviews();
          }
        }).catch(err => {
          console.warn("Native file dialog error:", err);
          if (mediaInput) mediaInput.click();
        });
      } else if (mediaInput) {
        mediaInput.click();
      }
    });
  }

  if (mediaInput) {
    mediaInput.addEventListener("change", function(e) {
      const files = Array.from(e.target.files || []);
      files.forEach(file => {
        const reader = new FileReader();
        reader.onload = function(evt) {
          const b64Data = evt.target.result;
          if (window.pywebview && window.pywebview.api && window.pywebview.api.upload_media_file) {
            window.pywebview.api.upload_media_file(file.name, b64Data).then(res => {
              if (res && res.success) {
                res.dataUrl = b64Data;
                pendingAttachments.push(res);
                renderAttachmentPreviews();
              }
            });
          }
        };
        reader.readAsDataURL(file);
      });
      mediaInput.value = "";
    });
  }

  // Drag and Drop media files onto chat
  const chatMain = document.querySelector(".chat-main");
  if (chatMain) {
    ["dragenter", "dragover"].forEach(eventName => {
      chatMain.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      }, false);
    });

    ["dragleave", "drop"].forEach(eventName => {
      chatMain.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      }, false);
    });

    chatMain.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      if (!dt) return;
      const files = Array.from(dt.files || []);
      files.forEach(file => {
        const reader = new FileReader();
        reader.onload = function(evt) {
          const b64Data = evt.target.result;
          if (window.pywebview && window.pywebview.api && window.pywebview.api.upload_media_file) {
            window.pywebview.api.upload_media_file(file.name, b64Data).then(res => {
              if (res && res.success) {
                res.dataUrl = b64Data;
                pendingAttachments.push(res);
                renderAttachmentPreviews();
              }
            });
          }
        };
        reader.readAsDataURL(file);
      });
    });
  }

  // Clipboard Paste (Ctrl+V) for images
  document.addEventListener("paste", (e) => {
    const items = (e.clipboardData || window.clipboardData)?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.kind === 'file') {
        const blob = item.getAsFile();
        if (blob) {
          const reader = new FileReader();
          reader.onload = function(evt) {
            const b64Data = evt.target.result;
            const ext = blob.type.split("/")[1] || "png";
            const fileName = "pasted_" + Date.now() + "." + ext;
            if (window.pywebview && window.pywebview.api && window.pywebview.api.upload_media_file) {
              window.pywebview.api.upload_media_file(fileName, b64Data).then(res => {
                if (res && res.success) {
                  res.dataUrl = b64Data;
                  pendingAttachments.push(res);
                  renderAttachmentPreviews();
                }
              });
            }
          };
          reader.readAsDataURL(blob);
        }
      }
    }
  });

  // Lightbox Modal Close
  const lightboxModal = document.getElementById("lightbox-modal");
  const btnCloseLightbox = document.getElementById("btn-close-lightbox");
  if (btnCloseLightbox) {
    btnCloseLightbox.addEventListener("click", () => {
      if (lightboxModal) lightboxModal.classList.remove("active");
    });
  }
  if (lightboxModal) {
    lightboxModal.addEventListener("click", (e) => {
      if (e.target === lightboxModal) {
        lightboxModal.classList.remove("active");
      }
    });
  }
}
