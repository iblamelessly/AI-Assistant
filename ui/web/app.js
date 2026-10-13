// JARVIS AI Assistant - Autonomous Agent & Voice Controller

let currentSessionId = null;
let isStreaming = false;
let currentAssistantBubble = null;
let currentStreamBuffer = "";
let voiceEnabled = true;

let recognition = null;
let isRecording = false;

let pendingAttachments = [];
let voiceConversationMode = false;
let continuousListen = true;
let subtitleFadeTimer = null;
let pendingCommandQueue = [];

function showOrbSubtitle(text) {
  const card = document.getElementById("orb-subtitle-card");
  const textEl = document.getElementById("orb-subtitle-text");
  if (!card || !textEl) return;
  clearTimeout(subtitleFadeTimer);
  textEl.textContent = text;
  card.classList.remove("hidden");
}

function hideOrbSubtitle(delayMs = 0) {
  const card = document.getElementById("orb-subtitle-card");
  if (!card) return;
  clearTimeout(subtitleFadeTimer);
  if (delayMs > 0) {
    subtitleFadeTimer = setTimeout(() => {
      card.classList.add("hidden");
    }, delayMs);
  } else {
    card.classList.add("hidden");
  }
}

function updateVoiceModeUI() {
  const btn = document.getElementById("btn-toggle-voice-mode");
  if (btn) {
    btn.classList.toggle("active", voiceConversationMode);
  }
  document.body.classList.toggle("voice-mode", voiceConversationMode);
  if (voiceConversationMode) {
    showVoiceOrb("🎙️ JARVIS Voice Companion Active");
  }
}

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

function createMediaCardHtml(type, filePath, caption) {
  if (!filePath) return "";
  const cleanPath = filePath.trim();
  const fileName = cleanPath.split(/[\\/]/).pop();
  const cleanArg = cleanPath.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
  const typeLower = (type || "image").toLowerCase();
  const typeLabel = typeLower === 'image' ? '🖼️ Photo / Screenshot' : (typeLower === 'video' ? '🎬 Video' : '🎵 Audio');

  let mediaElem = "";
  if (typeLower === "image") {
    mediaElem = `<img class="chat-media-img" data-media-src="${escapeHtml(cleanPath)}" alt="${escapeHtml(fileName)}" onclick="openMediaLightbox('${cleanArg}', 'image')" />`;
  } else if (typeLower === "video") {
    mediaElem = `<video class="chat-media-vid" data-media-src="${escapeHtml(cleanPath)}" controls preload="metadata"></video>`;
  } else if (typeLower === "audio") {
    mediaElem = `<audio class="chat-media-aud" data-media-src="${escapeHtml(cleanPath)}" controls></audio>`;
  }

  const subLabel = caption ? `<div class="chat-media-caption" style="padding:4px 8px 6px 8px; font-size:11px; color:var(--text-muted);">${escapeHtml(caption)}</div>` : "";

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
      ${subLabel}
    </div>
  `;
}

function renderMediaTags(htmlText) {
  if (!htmlText) return "";
  const mediaRegex = /\[MEDIA:\s*(image|video|audio)\s*\|\s*([^\]]+)\]/gi;
  return htmlText.replace(mediaRegex, function(match, type, filePath) {
    return createMediaCardHtml(type, filePath);
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

  const mediaPath = res.output_path || res.path || "";

  if (toolName === "take_screenshot") {
    if (mediaPath && res.success !== false) {
      return createMediaCardHtml("image", mediaPath, res.summary || "Captured screenshot");
    }
    return `<div class="tool-badge">📸 Screenshot: ${escapeHtml(res.path || 'Saved to screenshots folder')}</div>`;
  }

  if (toolName === "generate_ai_image" || toolName === "alter_ai_image" || toolName === "generate_image" || toolName === "create_image") {
    if (mediaPath && res.success !== false) {
      return createMediaCardHtml("image", mediaPath, res.summary || "Generated AI Image");
    }
  }

  if (toolName === "generate_ai_video" || toolName === "generate_video") {
    if (mediaPath && res.success !== false) {
      return createMediaCardHtml("video", mediaPath, res.summary || "Generated AI Video");
    }
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
    if (mediaPath && res.success !== false) {
      return createMediaCardHtml("image", mediaPath, res.summary || "Image edited successfully");
    }
    const isSuccess = res.success !== false;
    const actionDesc = res.summary || (isSuccess ? "Image edited successfully" : ("Error: " + (res.error || "Failed")));
    return `<div class="tool-badge">🖼️ ${escapeHtml(actionDesc)}</div>`;
  }

  if (toolName === "edit_video" || toolName === "video_edit" || toolName === "trim_video" || toolName === "extract_audio" || toolName === "mute_video") {
    if (mediaPath && res.success !== false && (toolName === "edit_video" || toolName === "video_edit" || toolName === "trim_video")) {
      return createMediaCardHtml("video", mediaPath, res.summary || "Video edited successfully");
    }
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

  document.addEventListener("click", primeAudio, { once: true });
  document.addEventListener("keydown", primeAudio, { once: true });

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
      const modelId = typeof m === "object" ? m.id : m;
      const modelName = typeof m === "object" ? (m.name || m.id) : m;

      const opt1 = document.createElement("option");
      opt1.value = modelId;
      opt1.textContent = modelName;
      if (modelId === data.current_model) opt1.selected = true;
      modelSelect.appendChild(opt1);

      const opt2 = document.createElement("option");
      opt2.value = modelId;
      opt2.textContent = modelName;
      if (modelId === data.current_model) opt2.selected = true;
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

      const googleKeyInput = document.getElementById("setting-google-key");
      if (googleKeyInput) googleKeyInput.value = cfg.google_api_key || "";

      const voiceConvCheck = document.getElementById("setting-voice-conversation-mode");
      if (voiceConvCheck) {
        voiceConvCheck.checked = cfg.voice_conversation_mode === true;
        voiceConversationMode = cfg.voice_conversation_mode === true;
        updateVoiceModeUI();
      }

      const continuousCheck = document.getElementById("setting-continuous-listen");
      if (continuousCheck) {
        continuousCheck.checked = cfg.continuous_listen !== false;
        continuousListen = cfg.continuous_listen !== false;
      }

      const confirmActions = document.getElementById("setting-confirm-actions");
      if (confirmActions) confirmActions.checked = cfg.confirm_sensitive_actions !== false;

      const confirmPrivacy = document.getElementById("setting-confirm-privacy");
      if (confirmPrivacy) confirmPrivacy.checked = cfg.confirm_personal_data_access !== false;

      toggleProviderSections(cfg.provider || "groq");
    }

    // Populate sessions and restore active conversation history
    renderSessionList(data.sessions, data.active_session_id);
    if (data.active_session_id) {
      switchSession(data.active_session_id);
    }

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
    const voiceSelect = document.getElementById("setting-voice-select");
    if (voiceSelect && (data.voice_name || (data.config && data.config.voice_name))) {
      voiceSelect.value = data.voice_name || data.config.voice_name;
    }

    // Populate memory modal
    populateMemoryUI(data.memory);

    // Populate stats
    if (data.system_stats) {
      updateStatsPill(data.system_stats);
    }

    // Populate token & asset usage
    if (data.usage_stats && typeof window.renderUsageData === "function") {
      window.renderUsageData(data.usage_stats);
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

// Cached reference to the original welcome-card element so it is never permanently deleted
let cachedWelcomeCard = null;

// Render Messages
function renderMessages(messages) {
  const container = document.getElementById("messages-container");
  if (!container) return;

  if (!cachedWelcomeCard) {
    cachedWelcomeCard = document.getElementById("welcome-card");
  }

  // Clear container
  container.innerHTML = "";

  if (!messages || messages.length === 0) {
    if (cachedWelcomeCard) {
      container.appendChild(cachedWelcomeCard);
      cachedWelcomeCard.style.display = "flex";
    }
    return;
  }

  if (cachedWelcomeCard) {
    cachedWelcomeCard.style.display = "none";
  }

  messages.forEach((msg) => {
    if (msg && msg.content !== undefined && msg.content !== null) {
      appendMessageBubble(msg.role || "assistant", msg.content, msg.tool_info, msg.attachments);
    }
  });

  scrollToBottom();
}

// Append Message Bubble
function appendMessageBubble(role, content, toolInfo = null, attachments = null) {
  const container = document.getElementById("messages-container");
  if (!container) return;
  const welcomeCard = cachedWelcomeCard || document.getElementById("welcome-card");
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

// ── DYNAMIC ACTIVITY STATUS & ENGLISH VOICE SYSTEM ────────────────────
let currentStatusText = "Thinking...";
let currentStatusType = "thinking";
let currentStatusDetail = "Jarvis is processing your request...";

function getStatusIconHtml(stateType) {
  switch (stateType) {
    case "creating":
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"></path></svg>`;
    case "analyzing":
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>`;
    case "executing":
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>`;
    case "searching":
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>`;
    case "speaking":
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`;
    case "thinking":
    default:
      return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"></path><path d="M9 21h6"></path></svg>`;
  }
}

function renderActivityCardHtml(title, stateType, detail) {
  const iconSvg = getStatusIconHtml(stateType);
  return `
    <div class="assistant-activity-card state-${escapeHtml(stateType)}" id="current-activity-card">
      <div class="activity-orb">
        <span class="activity-orb-ring"></span>
        <span class="activity-orb-icon">${iconSvg}</span>
      </div>
      <div class="activity-content">
        <div class="activity-header">
          <span class="activity-title">${escapeHtml(title)}</span>
          <span class="activity-wave">
            <span></span><span></span><span></span>
          </span>
        </div>
        <div class="activity-subtitle">${escapeHtml(detail || "Jarvis is processing your request...")}</div>
      </div>
    </div>
  `;
}

function primeAudio() {
  try {
    const audioEl = document.getElementById("jarvis-audio");
    if (audioEl && audioEl.src) {
      const p = audioEl.play();
      if (p !== undefined) {
        p.then(() => audioEl.pause()).catch(() => {});
      }
    }
  } catch (e) {}
}

function speakWithBrowserSynthesis(text, onCompleteCallback) {
  if (!window.speechSynthesis || !text) {
    if (onCompleteCallback) onCompleteCallback();
    return;
  }
  try {
    window.speechSynthesis.cancel();
    const clean = text
      .replace(/```[\s\S]*?```/g, "")
      .replace(/\[(?:ACTION|TOOL|DOCUMENT|MEDIA|Suggestion):[\s\S]*?\]/g, "")
      .replace(/[#*_~`>]/g, "")
      .trim();

    if (!clean) {
      if (onCompleteCallback) onCompleteCallback();
      return;
    }

    const utterance = new SpeechSynthesisUtterance(clean.slice(0, 350));
    utterance.lang = "en-US";
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const enVoice = voices.find(v => (v.lang && (v.lang.startsWith("en-GB") || v.lang.startsWith("en-US") || v.lang.startsWith("en"))));
    if (enVoice) {
      utterance.voice = enVoice;
    }

    utterance.onend = () => {
      if (onCompleteCallback) onCompleteCallback();
    };
    utterance.onerror = () => {
      if (onCompleteCallback) onCompleteCallback();
    };

    window.speechSynthesis.speak(utterance);
  } catch (err) {
    console.warn("Browser speech synthesis error:", err);
    if (onCompleteCallback) onCompleteCallback();
  }
}

function playSpeech(audioB64, fallbackText, onCompleteCallback) {
  if (!voiceEnabled) {
    if (typeof onCompleteCallback === "function") onCompleteCallback();
    return;
  }

  const voiceBtn = document.getElementById("btn-toggle-voice");
  const orbLabel = document.getElementById("orb-status-text");
  const robotOrb = document.getElementById("jarvis-voice-orb");
  if (voiceBtn) voiceBtn.classList.add("speaking");
  if (robotOrb) robotOrb.classList.add("speaking");
  if (orbLabel) orbLabel.textContent = "🎙️ Speaking in English...";

  let finished = false;
  const finishSpeech = () => {
    if (!finished) {
      finished = true;
      if (voiceBtn) voiceBtn.classList.remove("speaking");
      if (robotOrb) robotOrb.classList.remove("speaking");
      if (orbLabel) orbLabel.textContent = "Tap robot to talk";
      if (typeof onCompleteCallback === "function") {
        onCompleteCallback();
      }
    }
  };

  const estSeconds = Math.max(2, Math.min(15, (fallbackText || "").split(" ").length * 0.35));

  if (audioB64) {
    try {
      const audioEl = document.getElementById("jarvis-audio");
      if (audioEl) {
        let mime = "audio/mp3";
        if (audioB64.startsWith("UklGR")) {
          mime = "audio/wav";
        }
        audioEl.src = `data:${mime};base64,${audioB64}`;

        audioEl.onended = finishSpeech;
        audioEl.onerror = () => {
          setTimeout(finishSpeech, estSeconds * 1000);
        };

        const playPromise = audioEl.play();
        if (playPromise !== undefined) {
          playPromise.catch(err => {
            console.warn("Audio play() handled or blocked by policy:", err);
            setTimeout(finishSpeech, estSeconds * 1000);
          });
        }
        return;
      }
    } catch (err) {
      console.warn("Audio playback error:", err);
    }
  }

  // Fallback to browser Web Speech API or timer
  speakWithBrowserSynthesis(fallbackText, finishSpeech);
  setTimeout(finishSpeech, estSeconds * 1000);
}

// Real-time status update from backend engine (Analyzing / Thinking / Creating / Executing / Speaking)
window.onStatusUpdate = function(statusText, statusType, detailText) {
  currentStatusText = statusText || "Thinking...";
  currentStatusType = statusType || "thinking";
  currentStatusDetail = detailText || "";

  const orbLabel = document.getElementById("orb-status-text");
  if (orbLabel) orbLabel.textContent = currentStatusText;

  if (currentAssistantBubble) {
    const existingCard = currentAssistantBubble.querySelector("#current-activity-card");
    if (existingCard) {
      existingCard.className = `assistant-activity-card state-${currentStatusType}`;
      const orbIcon = existingCard.querySelector(".activity-orb-icon");
      if (orbIcon) orbIcon.innerHTML = getStatusIconHtml(currentStatusType);
      const titleEl = existingCard.querySelector(".activity-title");
      if (titleEl) titleEl.textContent = currentStatusText;
      const subEl = existingCard.querySelector(".activity-subtitle");
      if (subEl) subEl.textContent = currentStatusDetail || "Jarvis is working on your request...";
    } else if (!currentStreamBuffer) {
      currentAssistantBubble.innerHTML = renderActivityCardHtml(currentStatusText, currentStatusType, currentStatusDetail);
    } else {
      const activePill = currentAssistantBubble.querySelector(".active-task-pill");
      if (activePill) {
        activePill.className = `active-task-pill state-${currentStatusType}`;
        const label = activePill.querySelector(".active-task-label");
        if (label) label.textContent = currentStatusText;
      }
    }
    scrollToBottom();
  }
};

// Live tool execution callback during stream
window.onToolExecuted = function(toolInfo) {
  if (currentAssistantBubble) {
    const toolHtml = renderToolHtml(toolInfo);
    currentAssistantBubble.insertAdjacentHTML("afterbegin", toolHtml);
    scrollToBottom();
  }
};

// Streaming chunk handler showing real-time task badge + streamed content
window.onStreamChunk = function(chunk) {
  currentStreamBuffer += chunk;
  if (voiceConversationMode || document.body.classList.contains("voice-mode") || document.body.classList.contains("mini-mode")) {
    showOrbSubtitle(currentStreamBuffer);
  }
  if (currentAssistantBubble) {
    const extracted = extractSuggestions(currentStreamBuffer);
    const pillHtml = `<div class="active-task-pill state-${currentStatusType}"><span class="active-task-dot"></span><span class="active-task-label">${escapeHtml(currentStatusText)}</span></div><br/>`;
    const contentHtml = renderDocumentTags(renderMediaTags(parseMarkdown(extracted.cleanText))) + '<span class="typing-cursor"></span>';
    currentAssistantBubble.innerHTML = pillHtml + contentHtml;
    loadAsyncMediaElements(currentAssistantBubble);
    scrollToBottom();
  }
};

// Stream complete handler with audio speech response
window.onStreamComplete = function(fullResponse, toolInfo, audioB64, modelUsed, isVoiceMode, activeSessionId) {
  isStreaming = false;
  document.getElementById("btn-send").disabled = false;

  if (activeSessionId && activeSessionId !== "ephemeral" && (!currentSessionId || currentSessionId !== activeSessionId)) {
    currentSessionId = activeSessionId;
  }

  const isVoice = Boolean(isVoiceMode || voiceConversationMode || document.body.classList.contains("voice-mode") || document.body.classList.contains("mini-mode"));

  if (isVoice) {
    showOrbSubtitle(fullResponse);
  }

  if (currentAssistantBubble) {
    let finalHtml = '<button class="btn-copy-message" onclick="copyMessage(this)" title="Copy message text">📋 Copy</button>';
    if (modelUsed) {
      let badgeLabel = modelUsed;
      if (modelUsed === "openai/gpt-oss-120b") badgeLabel = "⚡ Super AI [GPT-OSS 120B Reasoning]";
      else if (modelUsed === "qwen/qwen3.8-27b") badgeLabel = "⚡ Super AI [Qwen 3.8 27B Code Specialist]";
      else if (modelUsed === "openai/gpt-oss-20b") badgeLabel = "⚡ Super AI [GPT-OSS 20B Ultra-Fast]";
      else if (modelUsed === "allam-2-7b") badgeLabel = "⚡ Super AI [Allam 2 7B Multilingual]";
      else if (modelUsed === "gemini-3.8-flash") badgeLabel = "⚡ Super AI [Google Gemini 3.8 Flash]";
      else if (modelUsed === "gemini-3.5-flash") badgeLabel = "⚡ Super AI [Google Gemini 3.5 Flash]";
      else if (modelUsed === "gemini-3.5-flash-lite") badgeLabel = "⚡ Super AI [Google Gemini 3.5 Flash-Lite]";
      else if (modelUsed === "gemini-3.6-flash") badgeLabel = "⚡ Super AI [Google Gemini 3.6 Flash]";
      else if (modelUsed === "super-ai") badgeLabel = "⚡ Super AI Dynamic Ensemble";
      else badgeLabel = `⚡ ${modelUsed}`;
      finalHtml += `<div class="model-indicator-badge">${escapeHtml(badgeLabel)}</div>`;
    }
    if (toolInfo) {
      const toolOutPath = (toolInfo.result && (toolInfo.result.output_path || toolInfo.result.path)) || "";
      const textHasPreview = toolOutPath && fullResponse && fullResponse.includes(toolOutPath);
      if (!textHasPreview) {
        finalHtml += renderToolHtml(toolInfo);
      }
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

  // Speak back response ONLY when user interacted via voice or mini robot, keeping text chat 100% silent
  if (isVoice && audioB64) {
    playSpeech(audioB64, fullResponse, () => {
      hideOrbSubtitle(2500);
      if (continuousListen && voiceConversationMode) {
        setTimeout(() => {
          if (!isStreaming && !isNativeRecording && voiceConversationMode) {
            setOrbListening(true);
            toggleRecording();
          }
        }, 350);
      } else {
        const label = document.getElementById("orb-status-text");
        if (label) label.textContent = "Press Ctrl+J or tap robot to talk";
      }
    });
  } else if (isVoice) {
    hideOrbSubtitle(2000);
    if (continuousListen && voiceConversationMode) {
      setTimeout(() => {
        if (!isStreaming && !isNativeRecording && voiceConversationMode) {
          setOrbListening(true);
          toggleRecording();
        }
      }, 350);
    } else {
      const label = document.getElementById("orb-status-text");
      if (label) label.textContent = "Press Ctrl+J or tap robot to talk";
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

  // If a command was queued while Jarvis was processing, dispatch it immediately!
  if (pendingCommandQueue && pendingCommandQueue.length > 0) {
    const nextCmd = pendingCommandQueue.shift();
    console.log("Dispatching queued command:", nextCmd);
    const chatInput = document.getElementById("chat-input");
    if (chatInput) {
      chatInput.value = nextCmd;
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
    }
    setTimeout(() => {
      sendMessage();
    }, 150);
  }
};

// Send Message with dynamic activity status initialization
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

  // Prime audio on interaction so WebView2 never blocks speech
  primeAudio();

  const attachmentsToSend = [...pendingAttachments];
  pendingAttachments = [];
  renderAttachmentPreviews();

  const isVoice = Boolean(voiceConversationMode || document.body.classList.contains("voice-mode") || document.body.classList.contains("mini-mode"));

  // Append user message bubble to conversation history
  appendMessageBubble("user", userText, null, attachmentsToSend);

  // Create assistant bubble with dynamic activity widget in conversation
  const container = document.getElementById("messages-container");
  const row = document.createElement("div");
  row.className = "message-row assistant";

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = "J";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.innerHTML = renderActivityCardHtml(currentStatusText, currentStatusType, currentStatusDetail);

  row.appendChild(avatar);
  row.appendChild(bubble);
  container.appendChild(row);

  currentAssistantBubble = bubble;
  scrollToBottom();

  currentStreamBuffer = "";

  if (isVoice) {
    showVoiceOrb(currentStatusText);
    showOrbSubtitle("JARVIS is thinking...");
  }

  const orbLabel = document.getElementById("orb-status-text");
  if (orbLabel) orbLabel.textContent = currentStatusText;

  // Always save to conversation history so context persists and full tool outputs display
  const targetSessionId = currentSessionId || null;
  const saveHistory = true;

  // Call Python API
  window.pywebview.api.send_message(userText, targetSessionId, attachmentsToSend, isVoice, saveHistory).catch((err) => {
    console.error("Send message error:", err);
    if (currentAssistantBubble) {
      currentAssistantBubble.innerHTML = `<p style="color:var(--danger)">Error: ${err}</p>`;
    }
    isStreaming = false;
    document.getElementById("btn-send").disabled = false;
  });
}

// ── FLOATING MINI JARVIS VOICE ORB CONTROLLER ──────────────────────────
let isAlwaysOnTopPinned = false;
let isMiniModeActive = false;

function showVoiceOrb(statusText = "Tap robot to talk") {
  const orb = document.getElementById("jarvis-voice-orb");
  const label = document.getElementById("orb-status-text");
  if (!orb) return;
  voiceConversationMode = true;
  orb.classList.remove("hidden");
  orb.classList.add("visible");
  if (label) label.textContent = statusText;

  const toggleBtn = document.getElementById("btn-toggle-orb");
  if (toggleBtn) toggleBtn.classList.add("active");
}

function hideVoiceOrb() {
  voiceConversationMode = false;
  const orb = document.getElementById("jarvis-voice-orb");
  if (!orb) return;
  orb.classList.remove("visible", "listening", "speaking");
  orb.classList.add("hidden");
  const toggleBtn = document.getElementById("btn-toggle-orb");
  if (toggleBtn) toggleBtn.classList.remove("active");

  // Restore normal window if in mini mode
  if (isMiniModeActive) {
    toggleMiniMode(false);
  }

  if (isNativeRecording) {
    toggleRecording();
  }
}

window.setMiniModeUI = function(isMini) {
  isMiniModeActive = isMini;
  const toggleBtn = document.getElementById("btn-toggle-orb");
  if (isMini) {
    document.body.classList.add("mini-mode");
    if (toggleBtn) toggleBtn.classList.add("active");
    showVoiceOrb("Mini Robot ready — press Ctrl+J or tap to talk");
  } else {
    document.body.classList.remove("mini-mode");
    if (toggleBtn) toggleBtn.classList.remove("active");
  }
};

function toggleMiniMode(forceState) {
  const targetState = forceState !== undefined ? forceState : !isMiniModeActive;
  if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.toggle_mini_mode) {
    window.setMiniModeUI(targetState);
    return;
  }
  window.pywebview.api.toggle_mini_mode(targetState).then((isMini) => {
    window.setMiniModeUI(isMini);
  }).catch((err) => {
    console.warn("Toggle mini mode error:", err);
  });
}

function setOrbListening(active) {
  const orb = document.getElementById("jarvis-voice-orb");
  const label = document.getElementById("orb-status-text");
  if (!orb) return;
  if (active) {
    orb.classList.remove("speaking");
    orb.classList.add("listening");
    if (label) label.textContent = "🎙️ Listening to you...";
  } else {
    orb.classList.remove("listening");
    if (label) label.textContent = "Processing...";
  }
}

// Hardware Microphone & Voice Input Controller (Groq Whisper Bridge)
let isNativeRecording = false;
let recordingAutoStopTimer = null;
let transcriptionSafetyTimer = null;
let lastProcessedVoiceText = "";
let lastVoiceProcessedTime = 0;

// Asynchronous callback pushed when background recording thread finishes initialization
window.onVoiceRecordingStarted = function(status) {
  if (status === "error") {
    console.warn("Hardware microphone recording could not be started.");
    stopRecordingUI();
    const label = document.getElementById("orb-status-text");
    if (label) label.textContent = "Mic error. Check audio device.";
  }
};

// Asynchronous callback pushed from Python background worker thread
window.onVoiceTranscribed = function(transcribedText) {
  clearTimeout(transcriptionSafetyTimer);
  clearTimeout(recordingAutoStopTimer);
  isNativeRecording = false;
  stopRecordingUI();
  setOrbListening(false);

  const chatInput = document.getElementById("chat-input");
  const defaultPlaceholder = "Ask Jarvis, give a voice command, or run any laptop task... (Shift + Enter for new line)";
  if (chatInput) {
    chatInput.placeholder = defaultPlaceholder;
  }

  const cleanText = (transcribedText || "").trim();
  const now = Date.now();
  if (cleanText && cleanText.toLowerCase() === lastProcessedVoiceText.toLowerCase() && (now - lastVoiceProcessedTime) < 2500) {
    return; // Ignore duplicate from dual-engine pipeline
  }

  if (cleanText) {
    lastProcessedVoiceText = cleanText;
    lastVoiceProcessedTime = now;

    if (isStreaming) {
      // User spoke another command while Jarvis is still processing the previous one!
      console.log("Queuing command while processing:", cleanText);
      pendingCommandQueue.push(cleanText);
      showOrbSubtitle(`Queued next command: "${cleanText}"`);
      const label = document.getElementById("orb-status-text");
      if (label) label.textContent = `Queued (${pendingCommandQueue.length}): ${cleanText.substring(0, 20)}...`;
      return;
    }
    if (chatInput) {
      chatInput.value = cleanText;
      chatInput.style.height = "auto";
      chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + "px";
    }
    const label = document.getElementById("orb-status-text");
    if (label) label.textContent = "Processing command...";
    sendMessage();
  } else {
    // Silence or background noise filtered out — seamlessly continue listening if in hands-free live voice mode
    const isLiveVoice = Boolean(voiceConversationMode || document.body.classList.contains("voice-mode") || document.body.classList.contains("mini-mode"));
    if (isLiveVoice && continuousListen && !isStreaming) {
      stopRecordingUI();
      const label = document.getElementById("orb-status-text");
      if (label) label.textContent = "🎙️ Listening to you...";
      setTimeout(() => {
        if (!isStreaming && !isNativeRecording && (voiceConversationMode || document.body.classList.contains("voice-mode") || document.body.classList.contains("mini-mode"))) {
          toggleRecording();
        }
      }, 250);
    } else {
      const label = document.getElementById("orb-status-text");
      if (label) label.textContent = "Tap robot to talk";
      hideOrbSubtitle(1500);
      stopRecordingUI();
    }
  }
};

function toggleRecording() {
  const micBtn = document.getElementById("btn-mic");
  const chatInput = document.getElementById("chat-input");

  if (!isNativeRecording) {
    // Start Recording from hardware microphone
    isNativeRecording = true;
    if (micBtn) micBtn.classList.add("listening");
    setOrbListening(true);
    if (chatInput) {
      chatInput.placeholder = "🎙️ Listening... Speak now (Click mic or press Enter to send)";
    }

    if (window.pywebview && window.pywebview.api && window.pywebview.api.start_voice_recording) {
      window.pywebview.api.start_voice_recording().then((res) => {
        if (res && res.status === "error") {
          console.warn("Could not start recording:", res.message);
          stopRecordingUI();
        }
      }).catch(err => {
        console.warn("Voice recording start error:", err);
        stopRecordingUI();
      });
    }

    // Auto-stop after 10 seconds if user forgets to click stop
    clearTimeout(recordingAutoStopTimer);
    recordingAutoStopTimer = setTimeout(() => {
      if (isNativeRecording) {
        toggleRecording();
      }
    }, 10000);

  } else {
    // Stop Recording & Transcribe asynchronously on background thread
    clearTimeout(recordingAutoStopTimer);
    stopRecordingUI();
    setOrbListening(false);
    if (chatInput) {
      chatInput.placeholder = "⚡ Transcribing your voice with Groq Whisper...";
    }

    // Failsafe timer: restore placeholder if network drops or takes > 7s
    clearTimeout(transcriptionSafetyTimer);
    transcriptionSafetyTimer = setTimeout(() => {
      if (chatInput && chatInput.placeholder.includes("Transcribing")) {
        chatInput.placeholder = "Ask Jarvis, give a voice command, or run any laptop task... (Shift + Enter for new line)";
        const label = document.getElementById("orb-status-text");
        if (label) label.textContent = "Tap robot to talk";
      }
    }, 7000);

    if (window.pywebview && window.pywebview.api && window.pywebview.api.stop_voice_recording) {
      window.pywebview.api.stop_voice_recording().then((res) => {
        if (res && (res.status === "empty" || res.status === "error")) {
          clearTimeout(transcriptionSafetyTimer);
          if (chatInput) {
            chatInput.placeholder = "Ask Jarvis, give a voice command, or run any laptop task... (Shift + Enter for new line)";
          }
          const isLiveVoice = Boolean(voiceConversationMode || document.body.classList.contains("voice-mode") || document.body.classList.contains("mini-mode"));
          if (isLiveVoice && continuousListen && !isStreaming) {
            const label = document.getElementById("orb-status-text");
            if (label) label.textContent = "🎙️ Listening to you...";
            setTimeout(() => {
              if (!isStreaming && !isNativeRecording && (voiceConversationMode || document.body.classList.contains("voice-mode") || document.body.classList.contains("mini-mode"))) {
                toggleRecording();
              }
            }, 250);
          } else {
            const label = document.getElementById("orb-status-text");
            if (label) label.textContent = "Tap robot to talk";
          }
        }
      }).catch(err => {
        console.error("Stop recording API error:", err);
        clearTimeout(transcriptionSafetyTimer);
        if (chatInput) {
          chatInput.placeholder = "Ask Jarvis, give a voice command, or run any laptop task... (Shift + Enter for new line)";
        }
      });
    }
  }
}

function stopRecordingUI() {
  isNativeRecording = false;
  const micBtn = document.getElementById("btn-mic");
  if (micBtn) micBtn.classList.remove("listening");
  setOrbListening(false);
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
    if (!voiceEnabled) {
      hideVoiceOrb();
    }
  });

  // Siri / JARVIS Voice Conversation Mode Button
  const btnToggleVoiceMode = document.getElementById("btn-toggle-voice-mode");
  if (btnToggleVoiceMode) {
    btnToggleVoiceMode.addEventListener("click", () => {
      voiceConversationMode = !voiceConversationMode;
      updateVoiceModeUI();
      if (voiceConversationMode) {
        if (!isNativeRecording && !isStreaming) {
          setTimeout(() => {
            if (voiceConversationMode && !isNativeRecording && !isStreaming) {
              toggleRecording();
            }
          }, 50);
        }
      } else {
        if (isNativeRecording) {
          clearTimeout(recordingAutoStopTimer);
          clearTimeout(transcriptionSafetyTimer);
          stopRecordingUI();
          const chatInput = document.getElementById("chat-input");
          if (chatInput) {
            chatInput.placeholder = "Ask Jarvis, give a voice command, or run any laptop task... (Shift + Enter for new line)";
          }
          if (window.pywebview && window.pywebview.api && window.pywebview.api.stop_voice_recording) {
            window.pywebview.api.stop_voice_recording().catch(() => {});
          }
        }
        hideVoiceOrb();
      }
    });
  }

  // Always on Top Pin Button
  const pinBtn = document.getElementById("btn-pin-ontop");
  if (pinBtn) {
    pinBtn.addEventListener("click", () => {
      isAlwaysOnTopPinned = !isAlwaysOnTopPinned;
      pinBtn.classList.toggle("active", isAlwaysOnTopPinned);
      if (window.pywebview && window.pywebview.api && window.pywebview.api.set_window_on_top) {
        window.pywebview.api.set_window_on_top(isAlwaysOnTopPinned);
      }
    });
  }

  // Floating Mini JARVIS Voice Orb Listeners
  const orbDismissBtn = document.getElementById("orb-dismiss-btn");
  if (orbDismissBtn) {
    orbDismissBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (isMiniModeActive) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.minimize_window) {
          window.pywebview.api.minimize_window();
        } else {
          hideVoiceOrb();
        }
      } else {
        hideVoiceOrb();
      }
    });
  }

  const orbMiniBtn = document.getElementById("orb-mini-btn");
  if (orbMiniBtn) {
    orbMiniBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleMiniMode();
    });
  }

  const orbCore = document.getElementById("orb-core");
  if (orbCore) {
    orbCore.addEventListener("click", () => {
      const orb = document.getElementById("jarvis-voice-orb");
      if (orb && orb._preventClick) return;
      if (!isNativeRecording) {
        voiceConversationMode = true;
        setOrbListening(true);
        toggleRecording();
      } else {
        toggleRecording();
      }
    });
  }

  // Make Voice Orb Draggable on Screen
  (function initOrbDrag() {
    const orb = document.getElementById("jarvis-voice-orb");
    if (!orb) return;
    let isDragging = false;
    let startX = 0, startY = 0, origX = 0, origY = 0;
    let hasMoved = false;

    orb.addEventListener("mousedown", (e) => {
      if (e.target.closest("#orb-dismiss-btn") || e.target.closest("#orb-mini-btn")) return;
      if (isMiniModeActive) return;
      isDragging = true;
      hasMoved = false;
      startX = e.clientX;
      startY = e.clientY;
      const rect = orb.getBoundingClientRect();
      origX = rect.left;
      origY = rect.top;
      orb.style.transition = "none";
    });

    window.addEventListener("mousemove", (e) => {
      if (!isDragging || isMiniModeActive) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
        hasMoved = true;
      }
      const newX = Math.max(10, Math.min(window.innerWidth - 90, origX + dx));
      const newY = Math.max(10, Math.min(window.innerHeight - 90, origY + dy));
      orb.style.left = newX + "px";
      orb.style.top = newY + "px";
      orb.style.right = "auto";
      orb.style.bottom = "auto";
    });

    window.addEventListener("mouseup", () => {
      if (!isDragging) return;
      isDragging = false;
      orb.style.transition = "";
      if (hasMoved) {
        orb._preventClick = true;
        setTimeout(() => { orb._preventClick = false; }, 120);
      }
    });
  })();

  // Voice Orb & Always-On Mini Robot HUD Toggle Button
  const orbToggleBtn = document.getElementById("btn-toggle-orb");
  if (orbToggleBtn) {
    orbToggleBtn.addEventListener("click", () => {
      if (isMiniModeActive) {
        toggleMiniMode(false);
        hideVoiceOrb();
        orbToggleBtn.classList.remove("active");
      } else {
        toggleMiniMode(true);
        orbToggleBtn.classList.add("active");
      }
    });
  }

  // Emergency Stop / Cancel active autonomous task
  window.emergencyStop = function() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.emergency_stop) {
      window.pywebview.api.emergency_stop().then((res) => {
        console.log("Emergency stop acknowledged:", res);
        const label = document.getElementById("orb-status-text");
        if (label) label.textContent = "Halted by user";
        hideOrbSubtitle(2000);
        stopRecordingUI();
        isStreaming = false;
        const sendBtn = document.getElementById("btn-send");
        if (sendBtn) sendBtn.disabled = false;
      }).catch(err => console.warn("Emergency stop error:", err));
    }
  };

  // Keyboard shortcut: Ctrl+J for Voice Listening Toggle, Alt+J to toggle Always-On Mini Robot Desktop HUD & Escape for Emergency Stop
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && !e.altKey && (e.key === "j" || e.key === "J")) {
      e.preventDefault();
      toggleRecording();
    } else if (e.altKey && (e.key === "j" || e.key === "J")) {
      e.preventDefault();
      const toggleBtn = document.getElementById("btn-toggle-orb");
      if (isMiniModeActive) {
        toggleMiniMode(false);
        hideVoiceOrb();
        if (toggleBtn) toggleBtn.classList.remove("active");
      } else {
        toggleMiniMode(true);
        if (toggleBtn) toggleBtn.classList.add("active");
      }
    } else if (e.key === "Escape") {
      if (isStreaming) {
        window.emergencyStop();
      } else if (isMiniModeActive) {
        if (window.pywebview && window.pywebview.api && window.pywebview.api.minimize_window) {
          window.pywebview.api.minimize_window();
        }
      }
    }
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

  // Modal open/close: Usage & Limits Dashboard
  const usageModal = document.getElementById("usage-modal");
  function renderUsageData(stats) {
    if (!stats) return;
    const pTokens = document.getElementById("stat-prompt-tokens");
    const cTokens = document.getElementById("stat-completion-tokens");
    const tTokens = document.getElementById("stat-total-tokens");
    const tReqs = document.getElementById("stat-total-requests");
    const aiImgs = document.getElementById("stat-ai-images");
    const aiVids = document.getElementById("stat-ai-videos");
    const docs = document.getElementById("stat-documents");

    if (pTokens) pTokens.textContent = (stats.prompt_tokens || 0).toLocaleString();
    if (cTokens) cTokens.textContent = (stats.completion_tokens || 0).toLocaleString();
    if (tTokens) tTokens.textContent = (stats.total_tokens || 0).toLocaleString();
    if (tReqs) tReqs.textContent = (stats.total_requests || 0).toLocaleString();

    if (aiImgs) aiImgs.textContent = (stats.ai_images || 0).toLocaleString();
    if (aiVids) aiVids.textContent = (stats.ai_videos || 0).toLocaleString();
    if (docs) docs.textContent = (stats.documents || 0).toLocaleString();

    const rateTokensEl = document.getElementById("stat-rate-tokens");
    const barTokensEl = document.getElementById("bar-rate-tokens");
    if (rateTokensEl) {
      if (stats.rate_limit_remaining_tokens !== null && stats.rate_limit_limit_tokens) {
        const pct = Math.max(0, Math.min(100, Math.round((stats.rate_limit_remaining_tokens / stats.rate_limit_limit_tokens) * 100)));
        rateTokensEl.textContent = `${stats.rate_limit_remaining_tokens.toLocaleString()} / ${stats.rate_limit_limit_tokens.toLocaleString()} (${pct}%)`;
        if (barTokensEl) barTokensEl.style.width = pct + "%";
      } else {
        rateTokensEl.textContent = stats.rate_limit_remaining_tokens !== null ? stats.rate_limit_remaining_tokens.toLocaleString() : "Available (Standard Free Tier)";
      }
    }

    const rateReqsEl = document.getElementById("stat-rate-requests");
    const barReqsEl = document.getElementById("bar-rate-requests");
    if (rateReqsEl) {
      if (stats.rate_limit_remaining_requests !== null && stats.rate_limit_limit_requests) {
        const pct = Math.max(0, Math.min(100, Math.round((stats.rate_limit_remaining_requests / stats.rate_limit_limit_requests) * 100)));
        rateReqsEl.textContent = `${stats.rate_limit_remaining_requests.toLocaleString()} / ${stats.rate_limit_limit_requests.toLocaleString()} (${pct}%)`;
        if (barReqsEl) barReqsEl.style.width = pct + "%";
      } else {
        rateReqsEl.textContent = stats.rate_limit_remaining_requests !== null ? stats.rate_limit_remaining_requests.toLocaleString() : "Active (Optimal)";
      }
    }
  }

  window.renderUsageData = renderUsageData;

  function refreshUsageModalUI() {
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_usage_stats) return;
    window.pywebview.api.get_usage_stats().then((stats) => {
      renderUsageData(stats);
    }).catch((err) => console.warn("Failed to fetch usage stats:", err));
  }

  document.getElementById("btn-open-usage").addEventListener("click", () => {
    refreshUsageModalUI();
    if (usageModal) usageModal.classList.add("active");
  });
  document.getElementById("btn-close-usage").addEventListener("click", () => {
    if (usageModal) usageModal.classList.remove("active");
  });

  document.getElementById("btn-save-settings").addEventListener("click", () => {
    const provider = document.getElementById("setting-provider-select").value;
    const groqKey = document.getElementById("setting-groq-key").value.trim();
    const groqModel = document.getElementById("setting-groq-model").value;
    const googleKey = document.getElementById("setting-google-key") ? document.getElementById("setting-google-key").value.trim() : "";
    const voiceConvMode = document.getElementById("setting-voice-conversation-mode") ? document.getElementById("setting-voice-conversation-mode").checked : false;
    const contListen = document.getElementById("setting-continuous-listen") ? document.getElementById("setting-continuous-listen").checked : true;
    const ollamaUrl = document.getElementById("setting-ollama-url").value.trim();
    const ollamaModel = document.getElementById("setting-model-select").value;
    const personaName = document.getElementById("setting-persona-name").value.trim();
    const voiceSelect = document.getElementById("setting-voice-select");
    const voiceName = voiceSelect ? voiceSelect.value : "en-GB-RyanNeural";
    const confirmActions = document.getElementById("setting-confirm-actions").checked;
    const confirmPrivacy = document.getElementById("setting-confirm-privacy").checked;

    window.pywebview.api.save_settings({
      provider: provider,
      groq_api_key: groqKey,
      groq_model: groqModel,
      google_api_key: googleKey,
      voice_conversation_mode: voiceConvMode,
      continuous_listen: contListen,
      ollama_url: ollamaUrl,
      ollama_model: ollamaModel,
      persona_name: personaName,
      voice_name: voiceName,
      confirm_sensitive_actions: confirmActions,
      confirm_personal_data_access: confirmPrivacy
    }).then(() => {
      settingsModal.classList.remove("active");
      alert("Settings saved! JARVIS configuration updated.");
      window.location.reload();
    });
  });

  // Test Google Gemini Connection
  const btnTestGoogle = document.getElementById("btn-test-google");
  if (btnTestGoogle) {
    btnTestGoogle.addEventListener("click", () => {
      const keyInput = document.getElementById("setting-google-key");
      const badge = document.getElementById("google-status-badge");
      const key = keyInput ? keyInput.value.trim() : "";
      btnTestGoogle.textContent = "⚡ Testing...";
      btnTestGoogle.disabled = true;

      if (window.pywebview && window.pywebview.api && window.pywebview.api.test_google_connection) {
        window.pywebview.api.test_google_connection(key).then(res => {
          btnTestGoogle.textContent = "⚡ Test Key";
          btnTestGoogle.disabled = false;
          if (badge) {
            if (res && res.success) {
              badge.textContent = "✓ Connected (" + (res.models ? res.models.length : 3) + " models)";
              badge.style.color = "var(--success)";
            } else {
              badge.textContent = "✕ Failed: " + (res && res.error ? res.error : "Invalid API key");
              badge.style.color = "var(--danger)";
            }
          }
        }).catch(err => {
          btnTestGoogle.textContent = "⚡ Test Key";
          btnTestGoogle.disabled = false;
          if (badge) {
            badge.textContent = "✕ Test error: " + err;
            badge.style.color = "var(--danger)";
          }
        });
      } else {
        btnTestGoogle.textContent = "⚡ Test Key";
        btnTestGoogle.disabled = false;
      }
    });
  }

  // Test English Neural Voice Output
  const btnTestVoice = document.getElementById("btn-test-voice");
  if (btnTestVoice) {
    btnTestVoice.addEventListener("click", () => {
      const vSelect = document.getElementById("setting-voice-select");
      const chosenVoice = vSelect ? vSelect.value : "en-GB-RyanNeural";
      btnTestVoice.textContent = "🔊 Speaking...";
      btnTestVoice.disabled = true;
      primeAudio();

      if (window.pywebview && window.pywebview.api && window.pywebview.api.test_voice) {
        window.pywebview.api.test_voice(chosenVoice).then(res => {
          if (res && res.audio_b64) {
            playSpeech(res.audio_b64, res.text);
          } else {
            speakWithBrowserSynthesis(res ? res.text : "Good day, sir. JARVIS speech synthesis is online.");
          }
          btnTestVoice.textContent = "🔊 Test Voice";
          btnTestVoice.disabled = false;
        }).catch(err => {
          console.warn("Test voice error:", err);
          speakWithBrowserSynthesis("Good day, sir. JARVIS speech synthesis is online and speaking in English.");
          btnTestVoice.textContent = "🔊 Test Voice";
          btnTestVoice.disabled = false;
        });
      } else {
        speakWithBrowserSynthesis("Good day, sir. JARVIS speech synthesis is online and speaking in English.");
        btnTestVoice.textContent = "🔊 Test Voice";
        btnTestVoice.disabled = false;
      }
    });
  }

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
