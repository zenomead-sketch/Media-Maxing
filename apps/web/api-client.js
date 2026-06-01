// Localhost SQLite bridge client.
//
// When the web shell is served by apps/api/local_server.py, this client
// hydrates the existing browser adapters from SQLite and exposes safe JSON
// request helpers. Opening index.html directly still falls back to the static
// localStorage demo without external calls.

(function () {
  const storageKeys = {
    settings: "local-social-ai-manager.settings",
    brandProfile: "local-social-ai-manager.brandBrain",
    mediaAssets: "local-social-ai-manager.mediaLibrary",
    drafts: "local-social-ai-manager.drafts",
    scheduledPosts: "local-social-ai-manager.scheduledPosts",
    publishQueueItems: "local-social-ai-manager.publishQueueItems",
    publishAttempts: "local-social-ai-manager.publishAttempts",
    approvalLogs: "local-social-ai-manager.approvalLogs",
    connectedAccounts: "local-social-ai-manager.connectedAccounts",
    connectorAudit: "local-social-ai-manager.connectorAudit",
    analyticsSnapshots: "local-social-ai-manager.analyticsSnapshots",
    analyticsInsights: "local-social-ai-manager.analyticsInsights",
    engagementItems: "local-social-ai-manager.engagementItems",
    replySuggestions: "local-social-ai-manager.replySuggestions",
    replyApprovals: "local-social-ai-manager.replyApprovals",
    aiMemory: "local-social-ai-manager.aiMemory",
    weeklyReports: "local-social-ai-manager.weeklyReports",
  };

  function apiUrl(path) {
    if (window.location.protocol === "http:" || window.location.protocol === "https:") {
      return `${window.location.origin}${path}`;
    }
    return `http://127.0.0.1:8000${path}`;
  }

  async function request(path, options = {}) {
    const response = await window.fetch(apiUrl(path), {
      method: options.method || "GET",
      headers: options.body ? { "Content-Type": "application/json" } : {},
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
    const payload = await response.json();
    if (!response.ok) {
      const error = new Error(payload.error || "The local SQLite bridge request failed.");
      error.errorCodes = payload.errorCodes || [];
      throw error;
    }
    return payload;
  }

  async function upload(path, file) {
    const response = await window.fetch(apiUrl(path), {
      method: "POST",
      headers: {
        "Content-Type": file.type || "application/octet-stream",
        "X-Local-Filename": encodeURIComponent(file.name),
      },
      body: file,
    });
    const payload = await response.json();
    if (!response.ok) {
      const error = new Error(payload.error || "The local media import failed.");
      error.errorCodes = payload.errorCodes || [];
      throw error;
    }
    return payload;
  }

  function storeSnapshot(snapshot) {
    Object.entries(storageKeys).forEach(([field, key]) => {
      if (Object.prototype.hasOwnProperty.call(snapshot, field)) {
        window.localStorage.setItem(key, JSON.stringify(snapshot[field]));
      }
    });
  }

  async function sync() {
    const snapshot = await request("/api/bootstrap");
    storeSnapshot(snapshot);
    bridge.available = true;
    bridge.snapshot = snapshot;
    window.dispatchEvent(new CustomEvent("local-api-ready", { detail: snapshot }));
    return snapshot;
  }

  async function start() {
    try {
      await sync();
    } catch (error) {
      bridge.available = false;
      console.info("local-api: SQLite bridge unavailable; using static local demo adapter.");
      window.dispatchEvent(new CustomEvent("local-api-unavailable", { detail: error }));
    }
  }

  const bridge = {
    available: false,
    snapshot: null,
    request,
    upload,
    sync,
    start,
  };

  window.localApiBridge = bridge;
  document.addEventListener("DOMContentLoaded", start);
})();
