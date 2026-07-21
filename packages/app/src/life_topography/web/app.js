"use strict";

const state = { topology: null, preview: null, path: "", ownerEmail: "" };
const $ = (selector) => document.querySelector(selector);
const svgNS = "http://www.w3.org/2000/svg";

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}

function svgElement(tag, attributes = {}) {
  const node = document.createElementNS(svgNS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    let message = "Something went wrong.";
    try { message = (await response.json()).detail || message; } catch (_) { /* bounded fallback */ }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function showOnly(view) {
  for (const id of ["loading-view", "onboarding-view", "dashboard-view"]) {
    $(`#${id}`).classList.toggle("hidden", id !== view);
  }
}

function setStep(step) {
  $("#setup-step").classList.toggle("hidden", step !== 1);
  $("#consent-step").classList.toggle("hidden", step !== 2);
  $("#progress-step").classList.toggle("hidden", step !== 3);
  document.querySelectorAll(".step-indicator span").forEach((item, index) => {
    item.classList.toggle("active", index < step);
  });
}

function showError(target, message) {
  target.textContent = message;
  target.classList.remove("hidden");
}

function clearError(target) {
  target.textContent = "";
  target.classList.add("hidden");
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value || 0);
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function formatDate(value) {
  if (!value) return "Unknown";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown" : new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function renderPreview(preview) {
  const host = $("#preview-stats");
  host.replaceChildren();
  const values = [
    [formatNumber(preview.message_count), "Messages"],
    [formatNumber(preview.unique_address_count), "Addresses"],
    [formatBytes(preview.file_size_bytes), "Local file"],
    [formatDate(preview.earliest), "From"],
    [formatDate(preview.latest), "Through"],
    [formatNumber(preview.invalid_date_count), "Invalid dates"],
  ];
  for (const [value, label] of values) {
    const card = element("div", "preview-stat");
    card.append(element("strong", "", value), element("span", "", label));
    host.append(card);
  }
}

async function previewImport(event) {
  event.preventDefault();
  const error = $("#setup-error");
  clearError(error);
  const button = event.submitter;
  button.disabled = true;
  state.path = $("#mbox-path").value.trim();
  state.ownerEmail = $("#owner-email").value.trim();
  try {
    state.preview = await api("/api/onboarding/preview", {
      method: "POST",
      body: JSON.stringify({ path: state.path, owner_email: state.ownerEmail }),
    });
    renderPreview(state.preview);
    setStep(2);
  } catch (requestError) {
    showError(error, requestError.message);
  } finally {
    button.disabled = false;
  }
}

async function startDemo() {
  const error = $("#setup-error");
  const button = $("#start-demo");
  clearError(error);
  button.disabled = true;
  state.preview = { message_count: 30 };
  try {
    const response = await api("/api/demo", { method: "POST" });
    setStep(3);
    await pollJob(response.job_id);
  } catch (requestError) {
    showError(error, requestError.message);
    button.disabled = false;
  }
}

async function startImport() {
  const error = $("#consent-error");
  clearError(error);
  if (!$("#consent").checked) {
    showError(error, "Confirm metadata-only processing to continue.");
    return;
  }
  const button = $("#start-import");
  button.disabled = true;
  try {
    const response = await api("/api/onboarding/import", {
      method: "POST",
      body: JSON.stringify({
        path: state.path,
        owner_email: state.ownerEmail,
        metadata_only_consent: true,
      }),
    });
    setStep(3);
    await pollJob(response.job_id);
  } catch (requestError) {
    showError(error, requestError.message);
    button.disabled = false;
  }
}

async function pollJob(jobId) {
  const error = $("#progress-error");
  clearError(error);
  while (true) {
    let job;
    try {
      job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
    } catch (requestError) {
      showError(error, requestError.message);
      return;
    }
    const total = job.total || state.preview?.message_count || 0;
    const percent = total ? Math.min(100, Math.round((job.current / total) * 100)) : 0;
    $("#progress-bar").style.width = `${percent}%`;
    $("#progress-count").textContent = `${formatNumber(job.current)} / ${formatNumber(total)}`;
    $("#progress-phase").textContent = phaseLabel(job.phase);
    $("#progress-copy").textContent = phaseCopy(job.phase);
    if (job.status === "completed") {
      $("#progress-bar").style.width = "100%";
      await loadTopology();
      return;
    }
    if (job.status === "failed") {
      showError(error, job.error || "Import failed.");
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
}

function phaseLabel(phase) {
  return ({ queued: "Queued", starting: "Starting", importing: "Importing evidence", projecting: "Projecting map", completed: "Complete" })[phase] || "Working";
}

function phaseCopy(phase) {
  return ({ importing: "Persisting metadata-only evidence…", projecting: "Resolving people, organizations, and threads…", completed: "Your initial map is ready." })[phase] || "Preparing your local vault…";
}

async function loadTopology() {
  try {
    state.topology = await api("/api/topography");
    if (state.topology.nodes.length) {
      renderDashboard(state.topology);
      showOnly("dashboard-view");
    } else {
      setStep(1);
      showOnly("onboarding-view");
    }
  } catch (requestError) {
    showOnly("onboarding-view");
    showError($("#setup-error"), requestError.message);
  }
}

function renderDashboard(topology) {
  renderSummary(topology.summary);
  renderHighlights(topology);
  renderRankedList("#people-list", topology.nodes.filter((node) => node.kind === "person"));
  renderRankedList("#org-list", topology.nodes.filter((node) => node.kind === "organization"));
  renderRankedList("#thread-list", topology.nodes.filter((node) => node.kind === "thread"));
  renderGraph(topology);
  $("#detail-empty").classList.remove("hidden");
  $("#detail-content").classList.add("hidden");
}

function renderSummary(summary) {
  const host = $("#summary-grid");
  host.replaceChildren();
  for (const [key, label] of [["people", "People"], ["organizations", "Organizations"], ["threads", "Threads"], ["relationships", "Relationships"], ["evidence", "Evidence records"]]) {
    const card = element("div", "summary-card");
    card.append(element("span", "", label), element("strong", "", formatNumber(summary[key])));
    host.append(card);
  }
}

function renderHighlights(topology) {
  const host = $("#highlights");
  host.replaceChildren(element("p", "section-label", "What stands out"));
  const items = element("div", "highlight-items");
  for (const [kind, label] of [["person", "Strongest contact"], ["organization", "Dominant domain"], ["thread", "Most active context"]]) {
    const node = topology.nodes
      .filter((item) => item.kind === kind)
      .sort((a, b) => b.activity_count - a.activity_count || a.label.localeCompare(b.label))[0];
    const item = element("div", "highlight-item");
    item.append(element("span", "", label), element("strong", "", node ? node.label : "Not enough evidence"));
    if (node) item.append(element("small", "", `${formatNumber(node.activity_count)} linked records`));
    items.append(item);
  }
  host.append(items);
}

function renderRankedList(selector, nodes) {
  const host = $(selector);
  host.replaceChildren();
  const ranked = [...nodes].sort((a, b) => b.activity_count - a.activity_count || a.label.localeCompare(b.label)).slice(0, 8);
  if (!ranked.length) {
    host.append(element("p", "muted", "No objects in this category yet."));
    return;
  }
  for (const node of ranked) {
    const row = element("button", "rank-row");
    row.type = "button";
    const avatar = element("span", "rank-avatar", initials(node.label));
    const copy = element("span", "rank-copy");
    copy.append(element("strong", "", node.label), element("span", "", node.detail || node.kind));
    row.append(avatar, copy, element("span", "rank-count", formatNumber(node.activity_count)));
    row.addEventListener("click", () => selectNode(node));
    host.append(row);
  }
}

function initials(label) {
  return label.split(/\s+/).filter(Boolean).slice(0, 2).map((word) => word[0]).join("").toUpperCase() || "·";
}

function renderGraph(topology) {
  const svg = $("#topology-canvas");
  svg.replaceChildren();
  const top = (kind, count) => topology.nodes.filter((node) => node.kind === kind).sort((a, b) => b.activity_count - a.activity_count).slice(0, count);
  const visible = [...top("self", 1), ...top("person", 14), ...top("organization", 7), ...top("thread", 8)];
  $("#map-scope").textContent = visible.length < topology.nodes.length
    ? `Showing ${visible.length} of ${topology.nodes.length} objects, ranked by activity.`
    : `Showing all ${visible.length} mapped objects.`;
  const positions = layoutNodes(visible);
  const positionById = new Map(positions.map((item) => [item.node.id, item]));

  for (const edge of topology.edges) {
    const source = positionById.get(edge.source_id);
    const target = positionById.get(edge.target_id);
    if (!source || !target) continue;
    svg.append(svgElement("line", {
      x1: source.x, y1: source.y, x2: target.x, y2: target.y,
      class: "graph-edge", "stroke-width": Math.min(5, 0.7 + Math.log2(edge.weight + 1)),
    }));
  }

  for (const item of positions) {
    const radius = Math.min(19, 8 + Math.sqrt(item.node.activity_count) * 1.25);
    const group = svgElement("g", { class: "node-group", tabindex: "0", role: "button", "aria-pressed": "false", "data-node-id": item.node.id, "aria-label": `${item.node.kind}: ${item.node.label}` });
    group.append(svgElement("circle", { cx: item.x, cy: item.y, r: radius, class: `node-${item.node.kind}` }));
    const right = item.x >= 450;
    const label = svgElement("text", { x: item.x + (right ? radius + 7 : -radius - 7), y: item.y + 2, class: "node-label", "text-anchor": right ? "start" : "end" });
    label.textContent = truncate(item.node.label, 24);
    const sublabel = svgElement("text", { x: item.x + (right ? radius + 7 : -radius - 7), y: item.y + 14, class: "node-sublabel", "text-anchor": right ? "start" : "end" });
    sublabel.textContent = `${formatNumber(item.node.activity_count)} records`;
    group.append(label, sublabel);
    group.addEventListener("click", () => selectNode(item.node));
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectNode(item.node);
      }
    });
    svg.append(group);
  }
}

function layoutNodes(nodes) {
  const center = { x: 450, y: 300 };
  const result = [];
  const self = nodes.find((node) => node.kind === "self");
  if (self) result.push({ node: self, ...center });
  const rings = [
    [nodes.filter((node) => node.kind === "person"), 165, -Math.PI / 2],
    [nodes.filter((node) => node.kind === "organization" || node.kind === "thread"), 265, -Math.PI / 2 + 0.18],
  ];
  for (const [ringNodes, radius, offset] of rings) {
    ringNodes.forEach((node, index) => {
      const angle = offset + (index / Math.max(ringNodes.length, 1)) * Math.PI * 2;
      result.push({ node, x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius });
    });
  }
  return result;
}

function truncate(value, max) {
  return value.length <= max ? value : `${value.slice(0, max - 1)}…`;
}

function selectNode(node) {
  document.querySelectorAll(".node-group").forEach((group) => {
    group.setAttribute("aria-pressed", String(group.dataset.nodeId === node.id));
  });
  $("#detail-empty").classList.add("hidden");
  const host = $("#detail-content");
  host.replaceChildren();
  host.classList.remove("hidden");
  host.append(element("span", "detail-kind", node.kind), element("h2", "", node.label));
  if (node.detail) host.append(element("p", "muted", node.detail));
  const metrics = element("div", "detail-metrics");
  const activity = element("div"); activity.append(element("span", "", "Activity"), element("strong", "", formatNumber(node.activity_count)));
  const span = element("div"); span.append(element("span", "", "Observed"), element("strong", "", node.first_seen ? `${formatDate(node.first_seen)} – ${formatDate(node.last_seen)}` : "Unknown"));
  metrics.append(activity, span);
  host.append(metrics);

  const related = (state.topology?.edges || [])
    .filter((edge) => edge.source_id === node.id || edge.target_id === node.id)
    .sort((a, b) => b.weight - a.weight || a.id.localeCompare(b.id));
  if (related.length) {
    host.append(element("p", "section-label", "Relationships"));
    const connections = element("div", "connection-list");
    for (const edge of related.slice(0, 8)) {
      const otherId = edge.source_id === node.id ? edge.target_id : edge.source_id;
      const other = state.topology.nodes.find((item) => item.id === otherId);
      const details = element("details", "connection-row");
      const summary = element("summary", "connection-summary");
      const copy = element("span", "");
      copy.append(
        element("strong", "", other?.label || "Unknown object"),
        element("small", "", `${edge.kind.replaceAll("_", " ")} · ${formatNumber(edge.weight)} records`),
      );
      summary.append(copy, element("span", "connection-arrow", "›"));
      details.append(summary);
      const evidence = element("div", "evidence-list compact");
      edge.evidence_ids.slice(0, 4).forEach((identity, index) => {
        evidence.append(evidenceButton(identity, `Connection evidence ${index + 1}`));
      });
      details.append(
        evidence,
        element("p", "muted", `${formatNumber(edge.evidence_ids.length)} linked records · ${edge.derivation}`),
      );
      connections.append(details);
    }
    host.append(connections);
    if (related.length > 8) {
      host.append(element("p", "muted", `Showing 8 of ${related.length} relationships, ranked by activity.`));
    }
  }

  host.append(element("p", "section-label", "Object evidence"));
  const list = element("div", "evidence-list");
  node.evidence_ids.slice(0, 8).forEach((identity, index) => {
    list.append(evidenceButton(identity, `Header record ${index + 1}`));
  });
  host.append(list, element("p", "muted", `${formatNumber(node.evidence_ids.length)} linked header record${node.evidence_ids.length === 1 ? "" : "s"}. Deterministic derivation: ${node.derivation}.`));
}

function evidenceButton(identity, label) {
  const button = element("button", "evidence-button", label);
  button.type = "button";
  button.title = identity;
  button.addEventListener("click", () => showEvidence(identity));
  return button;
}

async function showEvidence(identity) {
  try {
    const record = await api(`/api/evidence/${encodeURIComponent(identity)}`);
    const body = $("#evidence-body");
    body.replaceChildren();
    const grid = element("dl", "evidence-grid");
    const payload = record.payload || {};
    const sender = payload.sender?.address || "Unknown";
    const recipients = (payload.recipients || []).map((item) => item.address).filter(Boolean).join(", ") || "None";
    const rows = [
      ["Subject", payload.subject || "(no subject)"], ["Sender", sender], ["Recipients", recipients],
      ["Sent", formatDate(payload.sent_at)], ["Message ID", payload.message_id || "Unavailable"],
      ["Evidence ID", record.identity], ["Stored content", "Headers only — no body or attachment"],
    ];
    for (const [term, value] of rows) grid.append(element("dt", "", term), element("dd", "", value));
    body.append(grid);
    $("#evidence-dialog").showModal();
  } catch (requestError) {
    window.alert(requestError.message);
  }
}

async function eraseVault() {
  const error = $("#reset-error");
  clearError(error);
  try {
    await api("/api/vault", { method: "DELETE", body: JSON.stringify({ confirmation: $("#reset-confirmation").value }) });
    $("#reset-dialog").close();
    state.topology = null;
    state.preview = null;
    $("#reset-confirmation").value = "";
    $("#consent").checked = false;
    setStep(1);
    showOnly("onboarding-view");
  } catch (requestError) {
    showError(error, requestError.message);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("#preview-form").addEventListener("submit", previewImport);
  $("#start-demo").addEventListener("click", startDemo);
  $("#back-to-setup").addEventListener("click", () => setStep(1));
  $("#consent").addEventListener("change", (event) => { $("#start-import").disabled = !event.target.checked; });
  $("#start-import").addEventListener("click", startImport);
  $("#refresh-map").addEventListener("click", loadTopology);
  document.querySelectorAll("[data-source-nav]").forEach((button) => button.addEventListener("click", () => { setStep(1); showOnly("onboarding-view"); }));
  document.querySelectorAll("[data-reset-open]").forEach((button) => button.addEventListener("click", () => $("#reset-dialog").showModal()));
  $("#reset-submit").addEventListener("click", eraseVault);
  document.querySelectorAll("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
  loadTopology();
});
