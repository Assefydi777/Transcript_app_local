const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function badge(status) {
  return `<span class="badge ${status}">${status}</span>`;
}

async function refreshJobs() {
  if (!$("#jobsTable")) return;
  const res = await fetch("/api/jobs?status=all");
  const data = await res.json();
  for (const [key, value] of Object.entries(data.counts || {})) {
    const target = document.querySelector(`[data-stat="${key}"]`);
    if (target) target.textContent = value;
  }
  $("#jobsTable").innerHTML = data.jobs.map((job) => `
    <tr>
      <td>${badge(job.status)}</td>
      <td><a href="/jobs/${job.id}">${job.filename}</a></td>
      <td>${Number(job.duration || 0).toFixed(1)}s</td>
      <td>${job.created_at || ""}</td>
    </tr>`).join("");
}

function upload(file) {
  const form = new FormData();
  form.append("file", file);
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/jobs/upload");
  xhr.upload.onprogress = (event) => {
    if (event.lengthComputable) $("#uploadProgress").value = (event.loaded / event.total) * 100;
  };
  xhr.onload = () => {
    const data = JSON.parse(xhr.responseText);
    window.location.href = `/jobs/${data.job_id}`;
  };
  xhr.send(form);
}

function setupUpload() {
  const zone = $("#dropZone");
  if (!zone) return;
  $("#chooseFile").onclick = () => $("#fileInput").click();
  $("#fileInput").onchange = (event) => upload(event.target.files[0]);
  ["dragenter", "dragover"].forEach((name) => zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.add("dragover");
  }));
  ["dragleave", "drop"].forEach((name) => zone.addEventListener(name, (event) => {
    event.preventDefault();
    zone.classList.remove("dragover");
  }));
  zone.addEventListener("drop", (event) => upload(event.dataTransfer.files[0]));
}

function renderJob(data) {
  $("#jobStatus").outerHTML = badge(data.status).replace("<span", '<span id="jobStatus"');
  $("#jobProgress").value = data.progress || 0;
  if (data.transcript) {
    $("#transcript").innerHTML = data.transcript.segments.map((s) => {
      const time = Number(s.start || 0).toFixed(1);
      return `<div><span class="segment-time" data-seek="${time}">[${time}s]</span>${s.text}</div>`;
    }).join("");
  }
  if (data.summary) {
    $("#summary").innerHTML = `
      <div class="summary-card"><strong>TL;DR</strong><p>${data.summary.tldr || ""}</p></div>
      <div class="summary-card"><strong>Bullets</strong><ul>${(data.summary.bullets || []).map((x) => `<li>${x}</li>`).join("")}</ul></div>
      <div class="summary-card"><strong>Action Items</strong>${(data.summary.action_items || []).map((x) => `<label><input type="checkbox"> ${x}</label><br>`).join("")}</div>
      <div class="summary-card">${(data.summary.keywords || []).map((x) => `<span class="pill">${x}</span>`).join("")}</div>`;
  }
}

async function pollJob(id) {
  const res = await fetch(`/api/jobs/${id}`);
  renderJob(await res.json());
}

function setupJob() {
  const head = $(".job-head");
  if (!head) return;
  const id = head.dataset.jobId;
  if (window.EventSource) {
    const events = new EventSource(`/api/jobs/${id}/stream`);
    events.addEventListener("progress", () => pollJob(id));
  }
  pollJob(id);
  setInterval(() => pollJob(id), 2000);
}

function debounce(fn, ms) {
  let handle;
  return (...args) => {
    clearTimeout(handle);
    handle = setTimeout(() => fn(...args), ms);
  };
}

function setupSearch() {
  const input = $("#searchInput");
  if (!input) return;
  input.addEventListener("input", debounce(async () => {
    const q = input.value.trim();
    if (!q) {
      $("#searchResults").innerHTML = "";
      return;
    }
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    $("#searchResults").innerHTML = data.results.map((item) => `
      <div class="result"><a href="/jobs/${item.job_id}">${item.job_id}</a><p>${item.snippet}</p></div>
    `).join("");
  }, 300));
}

setupUpload();
setupJob();
setupSearch();
refreshJobs();
setInterval(refreshJobs, 5000);

