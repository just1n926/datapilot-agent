const state = { datasets: [], dataset: null, table: null, run: null, pollToken: 0 };
const datasetSelect = document.querySelector("#dataset-select");
const tableSelect = document.querySelector("#table-select");
const metaNode = document.querySelector("#dataset-meta");
const columnsNode = document.querySelector("#columns");
const resultNode = document.querySelector("#result");
const emptyNode = document.querySelector("#empty-state");
const statusNode = document.querySelector("#status");
const form = document.querySelector("#analysis-form");
const analyzeButton = document.querySelector("#analyze-button");
const uploadInput = document.querySelector("#file-input");
const uploadZone = document.querySelector(".upload-zone");

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  return payload;
}

function setStatus(status) {
  const labels = { idle: "待命", running: "分析中", completed: "已完成", failed: "失败" };
  statusNode.innerHTML = `<i></i>${escapeHtml(labels[status] || status)}`;
  statusNode.className = `status ${status}`;
}

function selectedTableMeta() {
  return state.dataset?.tables.find((table) => table.name === state.table);
}

function renderDataset() {
  const table = selectedTableMeta();
  if (!state.dataset || !table) return;
  metaNode.innerHTML = `
    <span class="meta-chip">${table.row_count.toLocaleString()} 行</span>
    <span class="meta-chip">${table.column_count} 列</span>
    <span class="meta-chip">${escapeHtml(table.source_name)}</span>`;
  columnsNode.innerHTML = table.columns.map((column) =>
    `<span class="column" title="${escapeHtml(column.dtype)} · 空值 ${column.null_count}">${escapeHtml(column.name)}</span>`
  ).join("");
}

function chooseDataset(datasetId) {
  state.dataset = state.datasets.find((dataset) => dataset.id === datasetId) || null;
  if (!state.dataset) return;
  state.table = state.dataset.primary_table;
  tableSelect.innerHTML = state.dataset.tables.map((table) =>
    `<option value="${escapeHtml(table.name)}">${escapeHtml(table.source_name)} · ${table.row_count} 行</option>`
  ).join("");
  tableSelect.value = state.table;
  renderDataset();
}

async function loadDatasets(preferredId = null) {
  state.datasets = await api("/api/datasets");
  datasetSelect.innerHTML = state.datasets.map((dataset) =>
    `<option value="${dataset.id}">${escapeHtml(dataset.filename)}</option>`
  ).join("");
  if (!state.datasets.length) return;
  const selected = preferredId || state.dataset?.id || state.datasets[0].id;
  datasetSelect.value = selected;
  chooseDataset(selected);
}

function numberLabel(value) {
  if (typeof value !== "number") return String(value ?? "");
  return Math.abs(value) >= 1000
    ? new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(value)
    : new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
}

function renderBarChart(run) {
  const xIndex = run.columns.indexOf(run.chart.x);
  const yName = run.chart.y[0];
  const yIndex = run.columns.indexOf(yName);
  const data = run.rows.slice(0, 16).filter((row) => typeof row[yIndex] === "number");
  if (!data.length) return "";
  const width = 760, height = 300, left = 55, bottom = 45, top = 20;
  const chartHeight = height - top - bottom;
  const max = Math.max(...data.map((row) => Math.abs(row[yIndex])), 1);
  const slot = (width - left - 20) / data.length;
  const bars = data.map((row, index) => {
    const value = row[yIndex];
    const barHeight = Math.abs(value) / max * chartHeight;
    const x = left + index * slot + slot * .18;
    const y = top + chartHeight - barHeight;
    return `<g><rect x="${x}" y="${y}" width="${slot * .64}" height="${barHeight}" rx="5" fill="url(#barGradient)" />
      <text x="${x + slot * .32}" y="${height - 22}" text-anchor="middle" fill="#86868b" font-size="10">${escapeHtml(String(row[xIndex]).slice(0, 12))}</text>
      <text x="${x + slot * .32}" y="${Math.max(y - 6, 12)}" text-anchor="middle" fill="#3a3a3c" font-size="9">${numberLabel(value)}</text></g>`;
  }).join("");
  return `<div class="chart-wrap"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(yName)} bar chart">
    <defs><linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#64d2ff"/><stop offset="100%" stop-color="#0071e3"/></linearGradient></defs>
    <line x1="${left}" y1="${top + chartHeight}" x2="${width - 10}" y2="${top + chartHeight}" stroke="#e5e5e7" />${bars}</svg></div>`;
}

function renderLineChart(run) {
  const xIndex = run.columns.indexOf(run.chart.x);
  const series = run.chart.y.map((name) => ({ name, index: run.columns.indexOf(name) }))
    .filter((item) => item.index >= 0);
  if (!series.length || run.rows.length < 2) return "";
  const width = 760, height = 300, left = 55, bottom = 45, top = 20;
  const chartWidth = width - left - 25, chartHeight = height - top - bottom;
  const values = run.rows.flatMap((row) => series.map((item) => row[item.index]))
    .filter((value) => typeof value === "number");
  const max = Math.max(...values, 1), colors = ["#0071e3", "#5e5ce6", "#f56300"];
  const lines = series.map((item, seriesIndex) => {
    const points = run.rows.map((row, index) => {
      const x = left + index * chartWidth / Math.max(run.rows.length - 1, 1);
      const y = top + chartHeight - Number(row[item.index] || 0) / max * chartHeight;
      return `${x},${y}`;
    }).join(" ");
    return `<polyline points="${points}" fill="none" stroke="${colors[seriesIndex]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />`;
  }).join("");
  const labels = run.rows.map((row, index) => {
    const x = left + index * chartWidth / Math.max(run.rows.length - 1, 1);
    return `<text x="${x}" y="${height - 20}" text-anchor="middle" fill="#86868b" font-size="10">${escapeHtml(String(row[xIndex]).slice(0, 10))}</text>`;
  }).join("");
  const legend = series.map((item, index) =>
    `<text x="${left + index * 110}" y="12" fill="${colors[index]}" font-size="10">● ${escapeHtml(item.name)}</text>`
  ).join("");
  return `<div class="chart-wrap"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="trend chart">${legend}
    <line x1="${left}" y1="${top + chartHeight}" x2="${width - 10}" y2="${top + chartHeight}" stroke="#e5e5e7" />${lines}${labels}</svg></div>`;
}

function renderTable(run) {
  const head = run.columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("");
  const body = run.rows.map((row) => `<tr>${row.map((value) =>
    `<td>${escapeHtml(typeof value === "number" ? numberLabel(value) : value)}</td>`
  ).join("")}</tr>`).join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function render(run) {
  state.run = run;
  emptyNode.classList.add("hidden");
  resultNode.classList.remove("hidden");
  setStatus(run.status);
  const events = run.events.map((event) =>
    `<li><strong>${escapeHtml(event.kind)}</strong><span>${escapeHtml(event.message)}</span></li>`
  ).join("");
  if (run.status === "running") {
    resultNode.innerHTML = `<div class="live"><span class="spinner"></span>Agent 正在理解字段并生成只读 SQL</div>
      <h3>执行轨迹</h3><ul class="events">${events}</ul>`;
    return;
  }
  if (run.status === "failed") {
    resultNode.innerHTML = `<p class="error">${escapeHtml(run.error)}</p><h3>执行轨迹</h3><ul class="events">${events}</ul>`;
    return;
  }
  const chart = run.chart.type === "bar" ? renderBarChart(run)
    : run.chart.type === "line" ? renderLineChart(run) : "";
  resultNode.innerHTML = `
    <h2 class="result-title">${escapeHtml(run.title)}</h2>
    <p class="summary">${escapeHtml(run.summary)}</p>
    <h3>关键发现</h3>
    <div class="insights">${run.insights.map((item) => `<div class="insight">${escapeHtml(item)}</div>`).join("")}</div>
    ${chart ? `<h3>可视化</h3>${chart}` : ""}
    <h3>结果数据 · ${run.rows.length} 行</h3>${renderTable(run)}
    <details><summary>查看只读 SQL</summary><pre>${escapeHtml(run.sql)}</pre></details>
    <details><summary>查看 Agent 执行轨迹</summary><ul class="events">${events}</ul></details>`;
}

async function poll(runId) {
  const token = ++state.pollToken;
  for (let attempt = 0; attempt < 400; attempt += 1) {
    await delay(600);
    if (token !== state.pollToken) return;
    const run = await api(`/api/analyses/${runId}`);
    render(run);
    if (run.status !== "running") return;
  }
  throw new Error("分析等待超时");
}

datasetSelect.addEventListener("change", () => chooseDataset(datasetSelect.value));
tableSelect.addEventListener("change", () => { state.table = tableSelect.value; renderDataset(); });

uploadInput.addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const message = document.querySelector("#upload-message");
  message.textContent = "上传并解析中…";
  try {
    const body = new FormData();
    body.append("file", file);
    const dataset = await api("/api/datasets", { method: "POST", body });
    await loadDatasets(dataset.id);
    message.textContent = `已加载 ${dataset.filename}`;
  } catch (error) {
    message.textContent = error.message;
  } finally {
    event.target.value = "";
  }
});

document.querySelectorAll("[data-question]").forEach((target) => {
  target.addEventListener("click", () => { document.querySelector("#question").value = target.dataset.question; });
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.dataset || !state.table) return;
  analyzeButton.disabled = true;
  analyzeButton.querySelector("span").textContent = "分析中…";
  try {
    const run = await api("/api/analyses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_id: state.dataset.id,
        table: state.table,
        question: document.querySelector("#question").value,
      }),
    });
    render(run);
    await poll(run.id);
  } catch (error) {
    setStatus("failed");
    emptyNode.classList.add("hidden");
    resultNode.classList.remove("hidden");
    resultNode.innerHTML = `<p class="error">${escapeHtml(error.message)}</p>`;
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.querySelector("span").textContent = "开始分析";
  }
});

Promise.all([loadDatasets(), api("/health")]).then(([, health]) => {
  document.querySelector("#engine").textContent = `${health.engine} · ${health.model}`;
  document.querySelector("#health-dot").classList.add("online");
  if (!health.uploads_enabled) {
    uploadInput.disabled = true;
    uploadZone.classList.add("disabled");
    uploadZone.querySelector("strong").textContent = "在线演示使用内置样例";
    uploadZone.querySelector("small").textContent = "公开环境已关闭文件上传";
  }
}).catch((error) => {
  document.querySelector("#engine").textContent = `offline · ${error.message}`;
});
