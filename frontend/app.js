const API_BASE = ""; // same origin: FastAPI serves this page
const POLL_MS = 1000;
const MAX_POLLS = 300;
const STEP_MS = 600;
const LARGE_MAP = 12; // screens; bigger maps zoom out, so labels need a larger font

const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const state = {
  cy: null,
  map: null,
  mapId: null,
  startId: null,
  exploredMaps: [], // finished runs: /api/maps only lists sample and demo maps
  mapRun: 0, // each counter invalidates older async work of its kind
  routeRun: 0,
  locateRun: 0,
  previewUrl: null,
};

function showError(message) {
  $("banner-text").textContent = message;
  $("banner").hidden = false;
}

function clearError() {
  $("banner").hidden = true;
}

async function api(path, options) {
  let res;
  try {
    res = await fetch(API_BASE + path, options);
  } catch {
    throw new Error("Can't reach the Atlas API. Is the server running?");
  }
  const body = await res.text();
  let data = null;
  try {
    data = JSON.parse(body);
  } catch {
    // handled below: errors keep the status, success needs JSON
  }
  if (!res.ok) {
    const detail = data?.detail ?? data?.error;
    throw new Error(detail ? String(typeof detail === "string" ? detail : JSON.stringify(detail)) : `API error ${res.status}`);
  }
  if (data === null) throw new Error(`The API sent an unreadable reply for ${path}`);
  return data;
}

// Screenshots live under data/, but run maps store absolute paths to them.
function shotUrl(path) {
  if (!path) return "";
  const clean = path.replaceAll("\\", "/");
  const at = clean.lastIndexOf("/data/");
  if (at >= 0) return API_BASE + clean.slice(at);
  return `${API_BASE}/${clean.replace(/^\/+/, "")}`;
}

function screen(id) {
  return state.map?.screens.find((s) => s.id === id);
}

function homeScreen(map) {
  return map.screens.find((s) => s.url === map.app) ?? map.screens[0];
}

// The last screen a BFS reaches gives the demo the longest route to show.
function farthestScreen(map, startId) {
  const seen = new Set([startId]);
  const queue = [startId];
  for (const id of queue) {
    for (const edge of map.edges) {
      if (edge.from === id && !seen.has(edge.to)) {
        seen.add(edge.to);
        queue.push(edge.to);
      }
    }
  }
  return queue[queue.length - 1];
}

function shortAction(action) {
  const text = String(action ?? "").replace(/^click\s+/i, "").replace(/^['"]|['"]$/g, "");
  return text.length > 22 ? `${text.slice(0, 21)}…` : text;
}

function sentence(text) {
  const value = String(text ?? "");
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function graphStyle(screenCount) {
  const ink = cssVar("--ink");
  const paper = cssVar("--paper");
  const route = cssVar("--route");
  const here = cssVar("--here");
  return [
    {
      selector: "node",
      style: {
        shape: "round-rectangle",
        width: 176,
        height: 110,
        "background-color": "#fff",
        "border-width": 2,
        "border-color": ink,
        label: "data(label)",
        color: ink,
        "font-family": cssVar("--font"),
        "font-size": screenCount > LARGE_MAP ? 26 : 17,
        "font-weight": 700,
        "text-valign": "bottom",
        "text-margin-y": 6,
        "text-wrap": "wrap",
        "text-max-width": 190,
        "text-background-color": paper,
        "text-background-opacity": 0.9,
        "text-background-padding": 3,
      },
    },
    {
      selector: "node[img]",
      style: { "background-image": "data(img)", "background-fit": "cover", "background-clip": "node" },
    },
    {
      selector: "edge",
      style: {
        width: 2,
        "curve-style": "bezier",
        "line-color": cssVar("--edge"),
        "target-arrow-color": cssVar("--edge"),
        "target-arrow-shape": "triangle",
        label: "data(short)",
        color: cssVar("--ink-soft"),
        "font-family": cssVar("--font"),
        "font-size": 13,
        "text-rotation": "autorotate",
        "text-background-color": paper,
        "text-background-opacity": 1,
        "text-background-padding": 2,
        "min-zoomed-font-size": 8,
      },
    },
    { selector: ".dim", style: { opacity: 0.25 } },
    { selector: "node.on-route", style: { "border-width": 6, "border-color": route, "z-index": 10 } },
    {
      selector: "edge.on-route",
      style: {
        width: 6,
        "line-color": route,
        "target-arrow-color": route,
        color: route,
        "font-size": 16,
        "font-weight": 700,
        "z-index": 10,
      },
    },
    { selector: "node.here", style: { "border-width": 7, "border-color": here, "z-index": 11 } },
  ];
}

function renderGraph(map, homeId) {
  const known = new Set(map.screens.map((s) => s.id));
  const nodes = map.screens.map((s) => {
    const data = { id: s.id, label: s.label };
    const img = shotUrl(s.screenshot);
    if (img) data.img = img;
    return { data };
  });
  const edges = map.edges
    .filter((e) => known.has(e.from) && known.has(e.to))
    .map((e, i) => ({ data: { id: `e${i}`, source: e.from, target: e.to, short: shortAction(e.action) } }));

  state.cy?.destroy();
  const cy = cytoscape({
    container: $("graph"),
    elements: [...nodes, ...edges],
    style: graphStyle(map.screens.length),
    minZoom: 0.15,
    maxZoom: 1.3,
    layout: {
      name: "breadthfirst",
      directed: true,
      roots: [homeId],
      spacingFactor: 1.15,
      avoidOverlap: true,
      nodeDimensionsIncludeLabels: true,
      padding: 40,
    },
  });
  fillStage(cy);
  cy.on("tap", "node", (event) => openDetail(event.target.id()));
  cy.on("tap", (event) => {
    if (event.target === cy) closeDetail();
  });
  state.cy = cy;
}

// Long chains come out tall, but the stage is wide: run them left to right so
// the screens stay big. Nodes are wider than tall, hence the uneven scaling.
function fillStage(cy) {
  const box = cy.nodes().boundingBox();
  if (box.h / box.w <= cy.height() / cy.width()) return;
  cy.nodes().positions((node) => {
    const { x, y } = node.position();
    return { x: y * 1.6, y: x * 0.75 };
  });
  cy.fit(undefined, 40);
}

function clearRoute() {
  state.routeRun += 1;
  state.cy?.elements().removeClass("on-route dim");
  $("route-result").replaceChildren();
}

function setStart(id) {
  state.startId = id;
  $("start-label").textContent = screen(id)?.label ?? "—";
  clearRoute();
  state.cy?.nodes().removeClass("here");
  state.cy?.getElementById(id).addClass("here");
}

function openDetail(id) {
  const s = screen(id);
  if (!s) return;
  $("detail").dataset.id = id;
  $("detail-img").src = shotUrl(s.screenshot);
  $("detail-img").alt = `Screenshot of ${s.label}`;
  $("detail-label").textContent = s.label;
  $("detail-summary").textContent = s.summary ?? "";
  // Crawled pages decide this value, so only real web links become clickable.
  const link = $("detail-url");
  link.hidden = !/^https?:\/\//i.test(s.url ?? "");
  link.href = link.hidden ? "#" : s.url;
  link.textContent = s.url ?? "";
  $("detail").hidden = false;
}

function closeDetail() {
  $("detail").hidden = true;
}

function resetTools() {
  closeDetail();
  $("route-input").value = "";
  $("locate-result").replaceChildren();
  $("route-result").replaceChildren();
}

async function loadMap(id) {
  const run = ++state.mapRun;
  state.routeRun += 1;
  state.locateRun += 1;
  clearError();
  let map;
  try {
    map = await api(`/api/maps/${encodeURIComponent(id)}`);
  } catch (error) {
    if (run === state.mapRun) showError(error.message);
    return false;
  }
  if (run !== state.mapRun) return false;

  state.map = map;
  state.mapId = id;
  $("map-select").value = id;
  resetTools();
  if (!map.screens?.length) {
    state.cy?.destroy();
    state.cy = null;
    $("empty").textContent = "This map has no screens yet.";
    $("empty").hidden = false;
    $("start-label").textContent = "—";
    return false;
  }
  map.edges ??= [];
  $("empty").hidden = true;
  const home = homeScreen(map);
  renderGraph(map, home.id);
  setStart(home.id);
  return true;
}

function mapLabel(id) {
  return id === "sample" ? "Sample (placeholder)" : id;
}

async function loadMapList() {
  const ids = await api("/api/maps");
  const select = $("map-select");
  select.replaceChildren();
  for (const id of ids) select.add(new Option(mapLabel(id), id));
  for (const { id, label } of state.exploredMaps) select.add(new Option(label, id));
  return ids;
}

// Precomputed demo maps are real crawls, so they beat the placeholder sample.
function bestMap(ids) {
  return ids.find((id) => id !== "sample") ?? ids[0];
}

async function loadDemo() {
  try {
    const ids = await loadMapList();
    const id = bestMap(ids);
    if (!id) throw new Error("No demo maps yet. Add one to data/demo/.");
    if (!(await loadMap(id))) return;
    const target = screen(farthestScreen(state.map, state.startId));
    $("route-input").value = target.label;
    await findRoute(target.id);
  } catch (error) {
    showError(error.message);
  }
}

function destination(text) {
  const match = state.map.screens.find((s) => s.label.toLowerCase() === text.toLowerCase());
  return match?.id ?? text;
}

function note(text) {
  const p = document.createElement("p");
  p.className = "note";
  p.textContent = text;
  return p;
}

function headline(text) {
  const p = document.createElement("p");
  p.className = "headline";
  p.textContent = text;
  return p;
}

async function findRoute(query) {
  if (!state.map) return;
  const target = query.trim();
  const box = $("route-result");
  if (!target) {
    box.replaceChildren(note("Type a screen name, or click a screen and choose Route here."));
    return;
  }
  clearRoute();
  clearError();
  const run = state.routeRun;
  const startLabel = screen(state.startId)?.label ?? "here";
  box.replaceChildren(note("Finding a route…"));

  let result;
  try {
    const params = new URLSearchParams({ from: state.startId, to: target });
    result = await api(`/api/maps/${encodeURIComponent(state.mapId)}/path?${params}`);
  } catch (error) {
    if (run === state.routeRun) {
      box.replaceChildren();
      showError(error.message);
    }
    return;
  }
  if (run !== state.routeRun) return;

  const targetLabel = screen(result.target_id)?.label ?? target;
  if (!result.found) {
    const message = result.target_id
      ? `No path from ${startLabel} to ${targetLabel}.`
      : `No screen matches “${target}”.`;
    box.replaceChildren(headline(message));
    return;
  }
  if (!result.steps.length) {
    box.replaceChildren(headline(`You are already on ${targetLabel}.`));
    return;
  }
  await animateRoute(result.steps, targetLabel, run);
}

async function animateRoute(steps, targetLabel, run) {
  const clicks = steps.length === 1 ? "1 click" : `${steps.length} clicks`;
  const list = document.createElement("ol");
  list.className = "steps";
  const items = steps.map((step) => {
    const item = document.createElement("li");
    item.textContent = sentence(step.action);
    const lands = document.createElement("small");
    lands.textContent = `to ${screen(step.to)?.label ?? step.to}`;
    item.append(lands);
    return item;
  });
  list.append(...items);
  $("route-result").replaceChildren(headline(`${clicks} to ${targetLabel}`), list);

  closeDetail();
  const { cy } = state;
  cy.elements().addClass("dim");
  cy.getElementById(state.startId).removeClass("dim").addClass("on-route");

  for (const [i, step] of steps.entries()) {
    if (!reducedMotion.matches) await sleep(STEP_MS);
    if (run !== state.routeRun) return;
    const edge = cy.edges().filter((e) => e.source().id() === step.from && e.target().id() === step.to);
    edge.removeClass("dim").addClass("on-route");
    cy.getElementById(step.to).removeClass("dim").addClass("on-route");
    items[i].classList.add("done");
  }
}

function showPreview(file) {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = URL.createObjectURL(file);
  const img = document.createElement("img");
  img.src = state.previewUrl;
  img.alt = "Your screenshot";
  return img;
}

async function locate(file) {
  if (!state.map) {
    showError("Load a map before uploading a screenshot.");
    return;
  }
  if (!file.type.startsWith("image/")) {
    showError(`${file.name} is not an image. Upload a PNG or JPEG screenshot.`);
    return;
  }
  clearError();
  const run = ++state.locateRun;
  const mapId = state.mapId;
  const box = $("locate-result");
  const row = document.createElement("div");
  row.className = "located";
  const text = document.createElement("div");
  text.append(note("Recognizing the screen…"));
  row.append(showPreview(file), text);
  box.replaceChildren(row);

  const form = new FormData();
  form.append("file", file);
  let result;
  try {
    result = await api(`/api/maps/${encodeURIComponent(mapId)}/locate`, { method: "POST", body: form });
  } catch (error) {
    if (run === state.locateRun) {
      box.replaceChildren();
      showError(error.message);
    }
    return;
  }
  if (run !== state.locateRun) return;

  const match = screen(result.screen_id);
  if (!match) {
    box.replaceChildren();
    showError(`Atlas answered with a screen that isn't on this map: ${result.screen_id}`);
    return;
  }
  setStart(match.id);
  text.replaceChildren(headline(match.label), note(`${percent(result.confidence)} confident`));
  box.append(candidateList(result.candidates ?? []));
}

function percent(value) {
  return `${Math.round(Number(value) * 100)}%`;
}

function candidateList(candidates) {
  const list = document.createElement("ul");
  list.className = "candidates";
  for (const candidate of candidates) {
    const s = screen(candidate.screen_id);
    if (!s) continue;
    const button = document.createElement("button");
    button.type = "button";
    const name = document.createElement("span");
    name.textContent = s.label;
    const score = document.createElement("span");
    score.textContent = percent(candidate.score);
    button.append(name, score);
    button.addEventListener("click", () => openDetail(s.id));
    const item = document.createElement("li");
    item.append(button);
    list.append(item);
  }
  return list;
}

function normalizeUrl(text) {
  const value = text.trim();
  const url = new URL(/^[a-z][a-z0-9+.-]*:\/\//i.test(value) ? value : `https://${value}`);
  if (!/^https?:$/.test(url.protocol)) throw new Error("Atlas can only explore http and https URLs.");
  return url.href;
}

function setProgress(text) {
  $("progress").textContent = text;
  $("progress").hidden = !text;
}

async function explore(text) {
  let url;
  try {
    url = normalizeUrl(text);
  } catch (error) {
    showError(error instanceof TypeError ? `That doesn't look like a URL: ${text}` : error.message);
    return;
  }
  clearError();
  $("explore-btn").disabled = true;
  setProgress("Starting exploration…");
  try {
    const { job_id: jobId } = await api("/api/explore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    for (let poll = 0; poll < MAX_POLLS; poll += 1) {
      const job = await api(`/api/jobs/${encodeURIComponent(jobId)}`);
      if (job.status === "error") throw new Error(job.error ?? "Exploration failed.");
      if (job.status === "done") {
        state.exploredMaps.push({ id: job.map_id, label: new URL(url).hostname });
        await loadMapList();
        await loadMap(job.map_id);
        return;
      }
      setProgress(job.progress ?? "Exploring…");
      await sleep(POLL_MS);
    }
    throw new Error("Exploration is taking too long. Try a ready-made map.");
  } catch (error) {
    showError(error.message);
  } finally {
    setProgress("");
    $("explore-btn").disabled = false;
  }
}

function bindDropzone() {
  const zone = $("dropzone");
  // A file dropped outside the zone would otherwise navigate away from the demo.
  for (const type of ["dragover", "drop"]) {
    window.addEventListener(type, (event) => event.preventDefault());
  }
  zone.addEventListener("dragover", () => zone.classList.add("over"));
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (event) => {
    zone.classList.remove("over");
    const [file] = event.dataTransfer.files;
    if (file) locate(file);
  });
  $("file-input").addEventListener("change", (event) => {
    const [file] = event.target.files;
    event.target.value = "";
    if (file) locate(file);
  });
}

function bindEvents() {
  $("explore-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if ($("url-input").value.trim()) explore($("url-input").value);
    else showError("Paste a URL to explore.");
  });
  $("route-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (state.map) findRoute(destination($("route-input").value.trim()));
    else showError("Load a map first.");
  });
  $("map-select").addEventListener("change", (event) => loadMap(event.target.value));
  $("demo-btn").addEventListener("click", loadDemo);
  $("banner-close").addEventListener("click", clearError);
  $("detail-close").addEventListener("click", closeDetail);
  $("detail-start").addEventListener("click", () => {
    setStart($("detail").dataset.id);
    closeDetail();
  });
  $("detail-route").addEventListener("click", () => {
    const { id } = $("detail").dataset;
    $("route-input").value = screen(id)?.label ?? "";
    findRoute(id);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeDetail();
  });
  new ResizeObserver(() => {
    state.cy?.resize();
    state.cy?.fit(undefined, 40);
  }).observe($("graph"));
  bindDropzone();
}

async function init() {
  bindEvents();
  if (!window.cytoscape) {
    $("empty").textContent = "The map can't be drawn.";
    showError("Couldn't load the graph library from unpkg.com. Check the internet connection and reload.");
    return;
  }
  try {
    const ids = await loadMapList();
    if (ids.length) await loadMap(bestMap(ids));
    else $("empty").textContent = "No maps yet. Paste a URL above to explore an app.";
  } catch (error) {
    $("empty").textContent = "No map loaded.";
    showError(error.message);
  }
}

init();
