// Engagement Inbox screen - Local browser Engagement adapter.
//
// This module mirrors the local SQLite engagement service for rendering. When
// the localhost bridge is active, mutations persist through the Python
// services. Direct-file mode remains a localStorage demo fallback. Replies are
// not sent automatically. A reply approval means approved locally only. Local
// status changes never call social platform APIs.

(function () {
  const ENGAGEMENT_ITEMS_KEY = "local-social-ai-manager.engagementItems";
  const REPLY_SUGGESTIONS_KEY = "local-social-ai-manager.replySuggestions";
  const REPLY_APPROVALS_KEY = "local-social-ai-manager.replyApprovals";
  const SETTINGS_KEY = "local-social-ai-manager.settings";
  const platformIds = ["facebook", "instagram", "threads", "youtube", "tiktok", "linkedin", "x"];
  const engagementStatuses = [
    "new",
    "needs_reply",
    "reply_suggested",
    "reply_approved",
    "replied_manually",
    "ignored",
    "archived",
    "spam",
    "escalated",
  ];
  let selectedEngagementId = null;
  let editingSuggestionId = null;

  function activeApiBridge() {
    return window.localApiBridge?.available ? window.localApiBridge : null;
  }

  function currentBrandProfileId() {
    return activeApiBridge()?.snapshot?.brandProfile?.id || "demo-brand-brightside-exterior-care";
  }

  async function syncBridge() {
    const bridge = activeApiBridge();
    if (bridge) await bridge.sync();
  }

  function getElement(id) {
    return document.getElementById(id);
  }

  function safeParse(raw, fallback) {
    if (!raw) return fallback;
    try {
      const parsed = JSON.parse(raw);
      return parsed == null ? fallback : parsed;
    } catch (error) {
      console.warn("engagement: failed to parse local demo data", error);
      return fallback;
    }
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatStatus(value) {
    return String(value || "-").replace(/_/g, " ");
  }

  function formatDateTime(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "-";
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  }

  function daysAgoIso(days, hour) {
    const date = new Date();
    date.setDate(date.getDate() - days);
    date.setHours(hour, 0, 0, 0);
    return date.toISOString();
  }

  function defaultMockEngagementItems() {
    return [
      {
        id: "browser-mock-engagement-praise-comment",
        platform: "instagram",
        itemType: "comment",
        authorName: "Demo Visitor A",
        authorHandle: "@demo_neighbor_a",
        content: "The refreshed walkway looks great. Nice work keeping the edges tidy.",
        receivedAt: daysAgoIso(0, 9),
        sentiment: "positive",
        intent: "praise",
        priority: "low",
        status: "new",
        requiresResponse: false,
        relatedPost: "Driveway refresh: before and after",
        threadContext: "Public demo comment on a mock transformation post.",
        notes: "Clearly fake local fixture.",
      },
      {
        id: "browser-mock-engagement-pricing-question",
        platform: "facebook",
        itemType: "comment",
        authorName: "Demo Visitor B",
        authorHandle: "@demo_homeowner_b",
        content: "Do you provide estimates for gutter cleaning? I am comparing options for later this month.",
        receivedAt: daysAgoIso(0, 10),
        sentiment: "neutral",
        intent: "price_request",
        priority: "normal",
        status: "needs_reply",
        requiresResponse: true,
        relatedPost: "When should gutters be checked?",
        threadContext: "Public demo comment on a mock FAQ post.",
        notes: "Do not invent pricing. Invite the person to request an estimate.",
      },
      {
        id: "browser-mock-engagement-booking-request",
        platform: "instagram",
        itemType: "direct_message",
        authorName: "Demo Visitor C",
        authorHandle: "@demo_neighbor_c",
        content: "I would like to ask about booking an exterior cleanup. What is the best way to get started?",
        receivedAt: daysAgoIso(1, 14),
        sentiment: "neutral",
        intent: "booking_request",
        priority: "high",
        status: "needs_reply",
        requiresResponse: true,
        relatedPost: "Driveway refresh: before and after",
        threadContext: "Private demo message. Keep any future response general and owner-reviewed.",
        notes: "Fake fixture with no customer contact details.",
      },
      {
        id: "browser-mock-engagement-complaint",
        platform: "facebook",
        itemType: "comment",
        authorName: "Demo Visitor D",
        authorHandle: "@demo_neighbor_d",
        content: "I expected a clearer explanation of what the seasonal service includes.",
        receivedAt: daysAgoIso(1, 16),
        sentiment: "negative",
        intent: "complaint",
        priority: "high",
        status: "escalated",
        requiresResponse: true,
        relatedPost: "Seasonal exterior care reminder",
        threadContext: "Public demo complaint. Human review is required before any response.",
        notes: "Escalated by default. Never auto-reply to complaints.",
      },
      {
        id: "browser-mock-engagement-spam",
        platform: "threads",
        itemType: "mention",
        authorName: "Demo Visitor E",
        authorHandle: "@demo_offer_e",
        content: "Promote your page instantly with our unrelated demo offer.",
        receivedAt: daysAgoIso(2, 11),
        sentiment: "unknown",
        intent: "spam",
        priority: "low",
        status: "spam",
        requiresResponse: false,
        relatedPost: "-",
        threadContext: "Mock spam mention.",
        notes: "Safe to mark as spam locally. No deletion occurs.",
      },
      {
        id: "browser-mock-engagement-review-like-comment",
        platform: "facebook",
        itemType: "review",
        authorName: "Demo Visitor F",
        authorHandle: "@demo_neighbor_f",
        content: "The process explanation was helpful and straightforward.",
        receivedAt: daysAgoIso(3, 13),
        sentiment: "positive",
        intent: "praise",
        priority: "normal",
        status: "new",
        requiresResponse: false,
        relatedPost: "Behind the scenes: careful setup",
        threadContext: "Clearly fake review-like comment for local UI testing.",
        notes: "Do not reuse this as a real testimonial.",
      },
      {
        id: "browser-mock-engagement-urgent-lead",
        platform: "instagram",
        itemType: "lead_message",
        authorName: "Demo Visitor G",
        authorHandle: "@demo_neighbor_g",
        content: "I need to understand whether you cover my area before I arrange a walkthrough.",
        receivedAt: daysAgoIso(0, 8),
        sentiment: "neutral",
        intent: "urgent",
        priority: "urgent",
        status: "escalated",
        requiresResponse: true,
        relatedPost: "Driveway refresh: before and after",
        threadContext: "Urgent demo lead. Owner follow-up is required.",
        notes: "Do not invent service-area coverage or availability.",
      },
      {
        id: "browser-mock-engagement-general-comment",
        platform: "linkedin",
        itemType: "comment",
        authorName: "Demo Visitor H",
        authorHandle: "@demo_local_h",
        content: "Thanks for showing the preparation steps behind the project.",
        receivedAt: daysAgoIso(4, 15),
        sentiment: "positive",
        intent: "general",
        priority: "normal",
        status: "new",
        requiresResponse: false,
        relatedPost: "Behind the scenes: careful setup",
        threadContext: "Public demo comment on a mock process post.",
        notes: "Clearly fake local fixture.",
      },
    ];
  }

  function normalizeEngagementItem(item) {
    const now = new Date().toISOString();
    return {
      id: item.id,
      platform: platformIds.includes(item.platform) ? item.platform : "facebook",
      itemType: item.itemType || "unknown",
      authorName: item.authorName || "",
      authorHandle: item.authorHandle || "",
      content: item.content || "",
      receivedAt: item.receivedAt || now,
      sentiment: item.sentiment || "unknown",
      intent: item.intent || "unknown",
      priority: item.priority || "normal",
      status: engagementStatuses.includes(item.status) ? item.status : "new",
      requiresResponse: item.requiresResponse === true,
      source: item.source || "manual",
      relatedPost: item.relatedPost || "-",
      threadContext: item.threadContext || "No additional local thread context.",
      notes: item.notes || "",
      createdAt: item.createdAt || now,
      updatedAt: item.updatedAt || now,
    };
  }

  function loadEngagementItems() {
    const stored = safeParse(window.localStorage.getItem(ENGAGEMENT_ITEMS_KEY), []);
    return Array.isArray(stored) ? stored.map(normalizeEngagementItem) : [];
  }

  function saveEngagementItems(items) {
    window.localStorage.setItem(
      ENGAGEMENT_ITEMS_KEY,
      JSON.stringify(items.map(normalizeEngagementItem)),
    );
  }

  function normalizeReplySuggestion(suggestion) {
    const now = new Date().toISOString();
    return {
      id: suggestion.id,
      engagementItemId: suggestion.engagementItemId,
      suggestedReply: suggestion.suggestedReply || "",
      tone: suggestion.tone || "helpful",
      confidence: suggestion.confidence || "high",
      safetyReview: Array.isArray(suggestion.safetyReview) ? suggestion.safetyReview : [],
      blockingFlags: Array.isArray(suggestion.blockingFlags) ? suggestion.blockingFlags : [],
      recommendedAction: suggestion.recommendedAction || "reply",
      needsHumanReview: suggestion.needsHumanReview !== false,
      reasonSummary: suggestion.reasonSummary || "Local mock suggestion for owner review.",
      provider: suggestion.provider || "mock",
      status: suggestion.status || "generated",
      createdAt: suggestion.createdAt || now,
      updatedAt: suggestion.updatedAt || now,
    };
  }

  function loadReplySuggestions() {
    const stored = safeParse(window.localStorage.getItem(REPLY_SUGGESTIONS_KEY), []);
    return Array.isArray(stored) ? stored.map(normalizeReplySuggestion) : [];
  }

  function saveReplySuggestions(suggestions) {
    window.localStorage.setItem(
      REPLY_SUGGESTIONS_KEY,
      JSON.stringify(suggestions.map(normalizeReplySuggestion)),
    );
  }

  function loadReplyApprovals() {
    const stored = safeParse(window.localStorage.getItem(REPLY_APPROVALS_KEY), []);
    return Array.isArray(stored) ? stored : [];
  }

  function saveReplyApprovals(approvals) {
    window.localStorage.setItem(REPLY_APPROVALS_KEY, JSON.stringify(approvals));
  }

  function appendReplyApproval(item, action, previousStatus, newStatus, reason, suggestionId) {
    const approvals = loadReplyApprovals();
    approvals.push({
      id: `browser-reply-approval-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      replySuggestionId: suggestionId || null,
      engagementItemId: item.id,
      action,
      previousStatus,
      newStatus,
      reason,
      actorType: action === "suggest" ? "ai" : "user",
      createdAt: new Date().toISOString(),
    });
    saveReplyApprovals(approvals);
  }

  function latestSuggestionFor(itemId) {
    return loadReplySuggestions()
      .filter((suggestion) => suggestion.engagementItemId === itemId)
      .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))[0] || null;
  }

  function browserSafetyReview(item, replyText, includeInboundRequestRisks) {
    const reply = String(replyText || "");
    const reviewText = includeInboundRequestRisks ? `${item.content}\n${reply}` : reply;
    const flags = [];
    const addFlag = (code, severity, message) => {
      if (!flags.some((flag) => flag.code === code)) flags.push({ code, severity, message });
    };
    if (/\$\s*\d|(?:price|cost|charge)\s+(?:is|will be)\s+\d/i.test(reply)) {
      addFlag("invented_price", "critical", "Remove any invented price before approval.");
    }
    if (/\b(?:available|appointment|scheduled|booked)\s+(?:today|tomorrow|on|for|at)\b/i.test(reply)) {
      addFlag("invented_availability", "critical", "Remove invented scheduling availability before approval.");
    }
    if (/\bguarantee(?:d|s)?\b/i.test(reviewText)) {
      addFlag("unsupported_guarantee", "critical", "Keep the reply supportable and remove guarantee language.");
    }
    if (/\b(?:idiot|stupid|shut up|go away|your fault)\b/i.test(reply)) {
      addFlag("aggressive_language", "critical", "Use calm, respectful language.");
    }
    if (item.intent === "complaint" && reply && !/\b(?:sorry|apolog|understand|thank you for letting us know)\b/i.test(reply)) {
      addFlag("complaint_mishandled", "critical", "Complaints need an empathetic acknowledgment and human escalation.");
    }
    if (item.intent === "spam") {
      addFlag("spam_no_reply_recommended", "info", "Spam should not receive an outward reply.");
    }
    return {
      flags,
      blockingFlags: flags.filter((flag) => flag.severity === "critical").map((flag) => flag.code),
    };
  }

  function browserMockReply(item) {
    const tone = "helpful";
    if (item.intent === "spam") {
      return { suggestedReply: "", tone, recommendedAction: "mark_spam", reasonSummary: "Spam should not receive an outward reply." };
    }
    if (item.intent === "praise") {
      return { suggestedReply: "Thank you for the kind words. We appreciate you taking the time to share them.", tone: "friendly", recommendedAction: "reply", reasonSummary: "Friendly thank-you draft for owner review." };
    }
    if (item.intent === "price_request") {
      return { suggestedReply: "Thanks for asking. Pricing depends on the project details. Please send us a message and we can help with an estimate.", tone, recommendedAction: "invite_to_message", reasonSummary: "Invites an estimate request without inventing a price." };
    }
    if (item.intent === "booking_request") {
      return { suggestedReply: "Thanks for reaching out. Please send the project details and the best way to contact you so the team can follow up about next steps.", tone, recommendedAction: "ask_for_more_info", reasonSummary: "Requests next-step details without inventing availability." };
    }
    if (item.intent === "complaint") {
      return { suggestedReply: "Thank you for letting us know. We are sorry this was frustrating. Please send us a message so a person can review the details and follow up.", tone: "empathetic", recommendedAction: "escalate", reasonSummary: "Uses an empathetic acknowledgment and routes the complaint to a person." };
    }
    if (item.intent === "urgent") {
      return { suggestedReply: "Thanks for reaching out. Please send the key details and the best contact method so a person can review this promptly.", tone, recommendedAction: "escalate", reasonSummary: "Provides a concise next step while keeping a person in the loop." };
    }
    return { suggestedReply: "Thanks for reaching out. Please send us a message and we will be glad to help.", tone, recommendedAction: "reply", reasonSummary: "Helpful general response for owner review." };
  }

  function generateReplySuggestion() {
    const items = loadEngagementItems();
    const item = items.find((entry) => entry.id === selectedEngagementId);
    if (!item) throw new Error("Select an engagement item before generating a reply.");
    const draft = browserMockReply(item);
    const safety = browserSafetyReview(item, draft.suggestedReply, true);
    const now = new Date().toISOString();
    const suggestion = normalizeReplySuggestion({
      ...draft,
      id: `browser-reply-suggestion-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      engagementItemId: item.id,
      confidence: "high",
      safetyReview: safety.flags,
      blockingFlags: safety.blockingFlags,
      needsHumanReview: true,
      provider: "mock",
      status: "generated",
      createdAt: now,
      updatedAt: now,
    });
    const suggestions = loadReplySuggestions();
    suggestions.push(suggestion);
    saveReplySuggestions(suggestions);
    const previousStatus = item.status;
    item.status = "reply_suggested";
    item.requiresResponse = true;
    item.updatedAt = now;
    saveEngagementItems(items);
    appendReplyApproval(item, "suggest", previousStatus, "reply_suggested", "Local mock AI suggestion generated for owner review only.", suggestion.id);
    editingSuggestionId = null;
    return suggestion;
  }

  function generateMockEngagement() {
    if (!mockEngagementAllowed()) {
      throw new Error("Mock engagement is available only in development, demo, or test mode.");
    }
    const existing = loadEngagementItems();
    const knownIds = new Set(existing.map((item) => item.id));
    const createdAt = new Date().toISOString();
    const created = defaultMockEngagementItems()
      .filter((item) => !knownIds.has(item.id))
      .map((item) => normalizeEngagementItem({
        ...item,
        source: "mock",
        createdAt,
        updatedAt: createdAt,
      }));
    if (created.length) saveEngagementItems(existing.concat(created));
    return created;
  }

  function updateEngagementStatus(itemId, status) {
    if (!engagementStatuses.includes(status)) {
      throw new Error("Choose a supported local engagement status.");
    }
    const items = loadEngagementItems();
    const item = items.find((entry) => entry.id === itemId);
    if (!item) throw new Error("Select an engagement item before recording an action.");
    item.status = status;
    item.requiresResponse = ["needs_reply", "reply_suggested", "reply_approved", "escalated"].includes(status);
    item.updatedAt = new Date().toISOString();
    saveEngagementItems(items);
    return item;
  }

  function mockEngagementAllowed() {
    const settings = safeParse(window.localStorage.getItem(SETTINGS_KEY), {});
    return ["development", "demo", "test"].includes(settings.appEnvironment || "development");
  }

  function dateRangeMatches(item, days) {
    if (days === "all") return true;
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - Number(days));
    return new Date(item.receivedAt) >= cutoff;
  }

  function filteredEngagementItems() {
    const platform = getElement("engagement-platform-filter")?.value || "all";
    const status = getElement("engagement-status-filter")?.value || "all";
    const sentiment = getElement("engagement-sentiment-filter")?.value || "all";
    const intent = getElement("engagement-intent-filter")?.value || "all";
    const priority = getElement("engagement-priority-filter")?.value || "all";
    const source = getElement("engagement-source-filter")?.value || "all";
    const range = getElement("engagement-date-filter")?.value || "all";
    const search = (getElement("engagement-search")?.value || "").trim().toLowerCase();
    return loadEngagementItems()
      .filter((item) => platform === "all" || item.platform === platform)
      .filter((item) => status === "all" || item.status === status)
      .filter((item) => sentiment === "all" || item.sentiment === sentiment)
      .filter((item) => intent === "all" || item.intent === intent)
      .filter((item) => priority === "all" || item.priority === priority)
      .filter((item) => source === "all" || item.source === source)
      .filter((item) => dateRangeMatches(item, range))
      .filter((item) => {
        if (!search) return true;
        return `${item.content} ${item.authorName} ${item.authorHandle} ${item.platform}`
          .toLowerCase()
          .includes(search);
      })
      .sort((a, b) => new Date(b.receivedAt) - new Date(a.receivedAt));
  }

  function count(items, predicate) {
    return items.filter(predicate).length;
  }

  function renderEngagementSummary(items) {
    getElement("engagement-summary-new").textContent = count(items, (item) => item.status === "new");
    getElement("engagement-summary-needs-reply").textContent = count(items, (item) => item.status === "needs_reply");
    getElement("engagement-summary-reply-suggested").textContent = count(items, (item) => item.status === "reply_suggested");
    getElement("engagement-summary-approved").textContent = count(items, (item) => item.status === "reply_approved");
    getElement("engagement-summary-urgent").textContent = count(items, (item) => item.priority === "urgent");
    getElement("engagement-summary-complaints").textContent = count(items, (item) => item.intent === "complaint");
    getElement("engagement-summary-leads").textContent = count(items, (item) => ["booking_request", "price_request", "urgent"].includes(item.intent));
    getElement("engagement-summary-spam").textContent = count(items, (item) => item.status === "spam" || item.intent === "spam");
  }

  function badgeClass(value) {
    if (["spam", "escalated", "negative", "urgent"].includes(value)) return "engagement-badge danger";
    if (["needs_reply", "complaint", "high"].includes(value)) return "engagement-badge warning";
    if (["positive", "replied_manually"].includes(value)) return "engagement-badge success";
    return "engagement-badge";
  }

  function engagementCardMarkup(item) {
    const author = item.authorHandle || item.authorName || "Unknown local author";
    return `
      <button class="engagement-card${item.id === selectedEngagementId ? " selected" : ""}" type="button" data-engagement-id="${escapeHtml(item.id)}">
        <div class="engagement-card-header">
          <span class="engagement-platform">${escapeHtml(formatStatus(item.platform))}</span>
          <span class="${badgeClass(item.source)}">${escapeHtml(formatStatus(item.source))}</span>
        </div>
        <h3>${escapeHtml(author)}</h3>
        <p>${escapeHtml(item.content)}</p>
        <div class="engagement-card-meta">
          <span>${escapeHtml(formatStatus(item.itemType))}</span>
          <span class="${badgeClass(item.sentiment)}">${escapeHtml(formatStatus(item.sentiment))}</span>
          <span class="${badgeClass(item.intent)}">${escapeHtml(formatStatus(item.intent))}</span>
          <span class="${badgeClass(item.priority)}">${escapeHtml(formatStatus(item.priority))}</span>
          <span class="${badgeClass(item.status)}">${escapeHtml(formatStatus(item.status))}</span>
        </div>
        <small>${escapeHtml(formatDateTime(item.receivedAt))}${item.relatedPost !== "-" ? ` · ${escapeHtml(item.relatedPost)}` : ""}</small>
      </button>
    `;
  }

  function renderEngagementList() {
    const items = filteredEngagementItems();
    const list = getElement("engagement-list");
    const empty = getElement("engagement-empty-state");
    empty.hidden = items.length > 0;
    list.innerHTML = items.map(engagementCardMarkup).join("");
    if (!items.some((item) => item.id === selectedEngagementId)) {
      selectedEngagementId = items[0]?.id || null;
    }
    renderEngagementDetail();
  }

  function setText(id, value) {
    getElement(id).textContent = value || "-";
  }

  function renderEngagementDetail() {
    const empty = getElement("engagement-detail-empty");
    const content = getElement("engagement-detail-content");
    const item = loadEngagementItems().find((entry) => entry.id === selectedEngagementId);
    empty.hidden = Boolean(item);
    content.hidden = !item;
    if (!item) return;
    setText("engagement-detail-full-content", item.content);
    setText("engagement-detail-platform", formatStatus(item.platform));
    setText("engagement-detail-author", item.authorHandle || item.authorName || "-");
    setText("engagement-detail-received", formatDateTime(item.receivedAt));
    setText("engagement-detail-sentiment", formatStatus(item.sentiment));
    setText("engagement-detail-intent", formatStatus(item.intent));
    setText("engagement-detail-priority", formatStatus(item.priority));
    setText("engagement-detail-status", formatStatus(item.status));
    setText("engagement-detail-related-post", item.relatedPost);
    setText("engagement-detail-thread", item.threadContext);
    setText("engagement-detail-notes", item.notes);
    renderReplySuggestion(item);
  }

  function clearReplySuggestionDisplay() {
    editingSuggestionId = null;
    const text = getElement("engagement-suggestion-text");
    text.value = "";
    text.disabled = true;
    setText("engagement-suggestion-tone", "-");
    setText("engagement-suggestion-confidence", "-");
    setText("engagement-suggestion-action", "-");
    setText("engagement-suggestion-status", "-");
    setText("engagement-suggestion-created", "-");
    setText("engagement-suggestion-reason", "-");
    getElement("engagement-suggestion-safety-flags").innerHTML = "";
    getElement("engagement-edit-suggestion").hidden = false;
    getElement("engagement-save-suggestion-edit").hidden = true;
    getElement("engagement-approve-suggestion").disabled = true;
    getElement("engagement-reject-suggestion").disabled = true;
  }

  function renderReplySuggestion(item) {
    const suggestion = latestSuggestionFor(item.id);
    const empty = getElement("engagement-suggestion-empty");
    const content = getElement("engagement-suggestion-content");
    empty.hidden = Boolean(suggestion);
    content.hidden = !suggestion;
    renderReplyApprovalHistory(item.id);
    if (!suggestion) {
      clearReplySuggestionDisplay();
      return;
    }
    const editing = editingSuggestionId === suggestion.id;
    const text = getElement("engagement-suggestion-text");
    text.value = suggestion.suggestedReply;
    text.disabled = !editing;
    setText("engagement-suggestion-tone", suggestion.tone);
    setText("engagement-suggestion-confidence", suggestion.confidence);
    setText("engagement-suggestion-action", formatStatus(suggestion.recommendedAction));
    setText("engagement-suggestion-status", formatStatus(suggestion.status));
    setText("engagement-suggestion-created", formatDateTime(suggestion.createdAt));
    setText("engagement-suggestion-reason", suggestion.reasonSummary);
    const flagList = getElement("engagement-suggestion-safety-flags");
    flagList.innerHTML = suggestion.safetyReview.length
      ? suggestion.safetyReview
        .map((flag) => `<li class="${flag.severity === "critical" ? "blocking" : ""}"><strong>${escapeHtml(formatStatus(flag.severity))}:</strong> ${escapeHtml(formatStatus(flag.code))} · ${escapeHtml(flag.message)}</li>`)
        .join("")
      : "<li>No safety flags. Owner approval is still required.</li>";
    getElement("engagement-edit-suggestion").hidden = editing;
    getElement("engagement-save-suggestion-edit").hidden = !editing;
    getElement("engagement-approve-suggestion").disabled = suggestion.status === "approved";
    getElement("engagement-reject-suggestion").disabled = suggestion.status === "rejected";
  }

  function renderReplyApprovalHistory(itemId) {
    const node = getElement("engagement-approval-history");
    const approvals = loadReplyApprovals().filter((entry) => entry.engagementItemId === itemId);
    node.innerHTML = approvals.length
      ? approvals
        .map((entry) => `
          <article>
            <strong>${escapeHtml(formatStatus(entry.action))}</strong>
            <span>${escapeHtml(formatStatus(entry.newStatus))} · ${escapeHtml(formatDateTime(entry.createdAt))}</span>
            <p>${escapeHtml(entry.reason || "Local audit entry.")}</p>
          </article>
        `)
        .join("")
      : "<p>No local reply actions recorded yet.</p>";
  }

  function saveSuggestionEdit() {
    const item = loadEngagementItems().find((entry) => entry.id === selectedEngagementId);
    const suggestions = loadReplySuggestions();
    const suggestion = suggestions.find((entry) => entry.id === editingSuggestionId);
    if (!item || !suggestion) throw new Error("Choose a suggestion before saving an edit.");
    const nextText = getElement("engagement-suggestion-text").value.trim();
    if (!nextText && !["ignore", "mark_spam", "escalate"].includes(suggestion.recommendedAction)) {
      throw new Error("Add reply text before saving this suggestion.");
    }
    const safety = browserSafetyReview(item, nextText, false);
    suggestion.suggestedReply = nextText;
    suggestion.safetyReview = safety.flags;
    suggestion.blockingFlags = safety.blockingFlags;
    suggestion.status = "edited";
    suggestion.updatedAt = new Date().toISOString();
    saveReplySuggestions(suggestions);
    appendReplyApproval(item, "edit", item.status, "reply_suggested", "Owner edited the local reply draft.", suggestion.id);
    editingSuggestionId = null;
    return suggestion;
  }

  function approveSuggestionLocally() {
    const items = loadEngagementItems();
    const item = items.find((entry) => entry.id === selectedEngagementId);
    const suggestions = loadReplySuggestions();
    const suggestion = suggestions.find((entry) => entry.id === latestSuggestionFor(selectedEngagementId)?.id);
    if (!item || !suggestion) throw new Error("Generate a local suggestion before approving.");
    if (item.status === "spam" || item.intent === "spam") {
      throw new Error("This item is marked spam. Reply approval is not recommended.");
    }
    if (suggestion.blockingFlags.length) {
      throw new Error("This suggestion has critical safety flags. Edit it before approving.");
    }
    const safety = browserSafetyReview(item, suggestion.suggestedReply, false);
    if (safety.blockingFlags.length) {
      throw new Error("This suggestion has critical safety flags. Edit it before approving.");
    }
    const previousStatus = item.status;
    suggestion.safetyReview = safety.flags;
    suggestion.blockingFlags = safety.blockingFlags;
    suggestion.status = "approved";
    suggestion.updatedAt = new Date().toISOString();
    item.status = "reply_approved";
    item.requiresResponse = true;
    item.updatedAt = suggestion.updatedAt;
    saveReplySuggestions(suggestions);
    saveEngagementItems(items);
    appendReplyApproval(item, "approve", previousStatus, "reply_approved", "Approved locally only. No external reply was sent.", suggestion.id);
    return suggestion;
  }

  function rejectSuggestion() {
    const items = loadEngagementItems();
    const item = items.find((entry) => entry.id === selectedEngagementId);
    const suggestions = loadReplySuggestions();
    const suggestion = suggestions.find((entry) => entry.id === latestSuggestionFor(selectedEngagementId)?.id);
    if (!item || !suggestion) throw new Error("Generate a local suggestion before rejecting.");
    const previousStatus = item.status;
    suggestion.status = "rejected";
    suggestion.updatedAt = new Date().toISOString();
    item.status = "needs_reply";
    item.requiresResponse = true;
    item.updatedAt = suggestion.updatedAt;
    saveReplySuggestions(suggestions);
    saveEngagementItems(items);
    appendReplyApproval(item, "reject", previousStatus, "needs_reply", "Owner rejected the local reply draft.", suggestion.id);
    return suggestion;
  }

  function setActionMessage(kind, message) {
    const success = getElement("engagement-action-message");
    const error = getElement("engagement-action-error");
    success.hidden = kind !== "success";
    error.hidden = kind !== "error";
    success.textContent = kind === "success" ? message : "";
    error.textContent = kind === "error" ? message : "";
  }

  async function handleStatusAction(status) {
    try {
      const items = loadEngagementItems();
      const item = items.find((entry) => entry.id === selectedEngagementId);
      if (!item) throw new Error("Select an engagement item before recording an action.");
      const previousStatus = item.status;
      const bridge = activeApiBridge();
      if (bridge) {
        await bridge.request(`/api/engagement/${encodeURIComponent(selectedEngagementId)}/status`, {
          method: "POST",
          body: {
            status,
            suggestion_id: latestSuggestionFor(item.id)?.id || null,
          },
        });
        await syncBridge();
      } else {
        updateEngagementStatus(selectedEngagementId, status);
      }
      const actionByStatus = {
        replied_manually: "mark_replied_manually",
        escalated: "escalate",
        spam: "mark_spam",
        archived: "archive",
      };
      if (!bridge && actionByStatus[status]) {
        appendReplyApproval(
          item,
          actionByStatus[status],
          previousStatus,
          status,
          status === "replied_manually"
            ? "Owner recorded a reply handled outside the app."
            : `Owner updated the local Inbox status to ${formatStatus(status)}.`,
          latestSuggestionFor(item.id)?.id,
        );
      }
      setActionMessage(
        "success",
        status === "replied_manually"
          ? "Marked replied manually. Manual reply tracking is local only."
          : `Local status updated to ${formatStatus(status)}. Replies are not sent automatically.`,
      );
      renderEngagement();
    } catch (error) {
      setActionMessage("error", error.message || "The local engagement action could not be recorded.");
    }
  }

  function renderEngagement() {
    const loading = getElement("engagement-loading-state");
    const error = getElement("engagement-error-state");
    if (!loading || !error) return;
    try {
      loading.hidden = true;
      error.hidden = true;
      const items = loadEngagementItems();
      renderEngagementSummary(items);
      renderEngagementList();
    } catch (renderError) {
      console.error("engagement: render failed", renderError);
      loading.hidden = true;
      error.hidden = false;
    }
  }

  function setupEngagement() {
    const view = getElement("engagement-view");
    if (!view) return;
    [
      "engagement-platform-filter",
      "engagement-status-filter",
      "engagement-sentiment-filter",
      "engagement-intent-filter",
      "engagement-priority-filter",
      "engagement-source-filter",
      "engagement-date-filter",
    ].forEach((id) => getElement(id).addEventListener("change", renderEngagement));
    getElement("engagement-search").addEventListener("input", renderEngagement);
    getElement("engagement-list").addEventListener("click", (event) => {
      const card = event.target.closest("[data-engagement-id]");
      if (!card) return;
      selectedEngagementId = card.dataset.engagementId;
      renderEngagementList();
    });
    const statusActions = {
      "engagement-mark-needs-reply": "needs_reply",
      "engagement-ignore": "ignored",
      "engagement-archive": "archived",
      "engagement-mark-spam": "spam",
      "engagement-escalate": "escalated",
      "engagement-mark-replied-manually": "replied_manually",
    };
    Object.entries(statusActions).forEach(([id, status]) => {
      getElement(id).addEventListener("click", () => handleStatusAction(status));
    });
    getElement("engagement-generate-suggestion").addEventListener("click", async () => {
      try {
        const bridge = activeApiBridge();
        if (bridge) {
          if (!selectedEngagementId) throw new Error("Select an engagement item before generating a reply.");
          await bridge.request(`/api/engagement/${encodeURIComponent(selectedEngagementId)}/suggestions`, {
            method: "POST",
            body: {},
          });
          await syncBridge();
        } else {
          generateReplySuggestion();
        }
        setActionMessage("success", "Local AI reply suggestion generated. Review and approve it locally before handling any reply outside the app.");
        renderEngagement();
      } catch (error) {
        setActionMessage("error", error.message || "The local reply suggestion could not be generated.");
      }
    });
    getElement("engagement-edit-suggestion").addEventListener("click", () => {
      const suggestion = latestSuggestionFor(selectedEngagementId);
      if (!suggestion) return;
      editingSuggestionId = suggestion.id;
      renderEngagementDetail();
      getElement("engagement-suggestion-text").focus();
    });
    getElement("engagement-save-suggestion-edit").addEventListener("click", async () => {
      try {
        const bridge = activeApiBridge();
        if (bridge) {
          const suggestion = latestSuggestionFor(selectedEngagementId);
          if (!suggestion) throw new Error("Choose a suggestion before saving an edit.");
          await bridge.request(`/api/reply-suggestions/${encodeURIComponent(suggestion.id)}`, {
            method: "PATCH",
            body: {
              suggested_reply: getElement("engagement-suggestion-text").value.trim(),
              tone: suggestion.tone,
            },
          });
          editingSuggestionId = null;
          await syncBridge();
        } else {
          saveSuggestionEdit();
        }
        setActionMessage("success", "Local reply edit saved. Safety review ran again. Nothing was sent.");
        renderEngagement();
      } catch (error) {
        setActionMessage("error", error.message || "The local reply edit could not be saved.");
      }
    });
    getElement("engagement-approve-suggestion").addEventListener("click", async () => {
      try {
        const bridge = activeApiBridge();
        if (bridge) {
          const suggestion = latestSuggestionFor(selectedEngagementId);
          if (!suggestion) throw new Error("Generate a local suggestion before approving.");
          await bridge.request(`/api/reply-suggestions/${encodeURIComponent(suggestion.id)}/approve`, {
            method: "POST",
            body: {},
          });
          await syncBridge();
        } else {
          approveSuggestionLocally();
        }
        setActionMessage("success", "Reply approved locally only. Nothing was sent automatically.");
        renderEngagement();
      } catch (error) {
        setActionMessage("error", error.message || "The local reply suggestion could not be approved.");
      }
    });
    getElement("engagement-reject-suggestion").addEventListener("click", async () => {
      try {
        const bridge = activeApiBridge();
        if (bridge) {
          const suggestion = latestSuggestionFor(selectedEngagementId);
          if (!suggestion) throw new Error("Generate a local suggestion before rejecting.");
          await bridge.request(`/api/reply-suggestions/${encodeURIComponent(suggestion.id)}/reject`, {
            method: "POST",
            body: {},
          });
          await syncBridge();
        } else {
          rejectSuggestion();
        }
        setActionMessage("success", "Local reply suggestion rejected. The Inbox item still needs review.");
        renderEngagement();
      } catch (error) {
        setActionMessage("error", error.message || "The local reply suggestion could not be rejected.");
      }
    });
    const mockButton = getElement("engagement-generate-mock");
    mockButton.hidden = !mockEngagementAllowed();
    mockButton.addEventListener("click", async () => {
      try {
        const bridge = activeApiBridge();
        const result = bridge
          ? await bridge.request("/api/engagement/mock", {
            method: "POST",
            body: { brand_profile_id: currentBrandProfileId() },
          })
          : null;
        if (bridge) await syncBridge();
        const created = bridge ? result.items : generateMockEngagement();
        const message = created.length
          ? `${created.length} clearly labeled mock engagement items generated locally. No comments were fetched and no replies were sent.`
          : "Mock engagement is already loaded. Existing stable demo records were kept without duplicates.";
        getElement("engagement-mock-message").textContent = message;
        getElement("engagement-mock-message").hidden = false;
        renderEngagement();
      } catch (error) {
        setActionMessage("error", error.message || "Mock engagement could not be generated.");
      }
    });
    renderEngagement();
    window.addEventListener("local-api-ready", renderEngagement);
    window.addEventListener("hashchange", () => {
      if (window.location.hash === "#engagement") renderEngagement();
    });
  }

  document.addEventListener("DOMContentLoaded", setupEngagement);
})();
