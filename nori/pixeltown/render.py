"""Render a self-contained pixelated Tiny Town HTML player."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def write_pixeltown(path: str, timeline: Dict[str, Any]) -> None:
    """Write the pixel sim HTML to the exact ``path``."""
    Path(path).write_text(render_html(timeline), encoding="utf-8")


def render_html(timeline: Dict[str, Any]) -> str:
    """Embed ``timeline`` JSON and return one self-contained HTML document."""
    payload = json.dumps(timeline, separators=(",", ":"), ensure_ascii=True)
    # Escape </script> so embedded JSON cannot break out of the script tag.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    return _HTML_HEAD + payload + _HTML_TAIL


_HTML_HEAD = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<title>Tiny Town · Pixel Sim</title>
<style>
:root {
  --bg: #1a1c2c;
  --panel: #262b44;
  --ink: #f4f0e8;
  --muted: #a0a8c0;
  --accent: #3cbcfc;
  --good: #38b764;
  --bad: #e43b44;
  --sun: #ffe66d;
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0; background: var(--bg); color: var(--ink);
  font-family: "Courier New", Courier, monospace;
  min-height: 100%;
}
body {
  display: flex; flex-direction: column; align-items: stretch;
  max-width: 720px; margin: 0 auto; padding: 8px;
  padding-bottom: calc(8px + env(safe-area-inset-bottom, 0px));
}
header {
  display: flex; justify-content: space-between; align-items: baseline;
  gap: 8px; flex-wrap: wrap; margin-bottom: 6px;
}
header h1 {
  font-size: 14px; letter-spacing: 0.08em; text-transform: uppercase;
  margin: 0; color: var(--accent);
}
header .meta { font-size: 11px; color: var(--muted); }
#stage-wrap {
  position: relative; width: 100%;
  background: #000; border: 2px solid #3a4466; border-radius: 4px;
  overflow: hidden; line-height: 0;
}
#stage {
  width: 100%; height: auto; display: block;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  background: #2d6a4f;
}
#hud {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px; margin-top: 8px;
}
@media (min-width: 520px) {
  #hud { grid-template-columns: 1.2fr 1fr 1fr; }
}
.card {
  background: var(--panel); border: 1px solid #3a4466; border-radius: 4px;
  padding: 8px; font-size: 12px; min-height: 64px;
}
.card h2 {
  margin: 0 0 4px; font-size: 10px; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.06em;
}
.card .big { font-size: 16px; color: var(--sun); }
#board { grid-column: 1 / -1; }
#board ol { margin: 0; padding-left: 18px; }
#board li { margin: 2px 0; }
#board .broke { color: var(--bad); }
#board .ok { color: var(--good); }
#controls {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin-top: 8px; background: var(--panel); border: 1px solid #3a4466;
  border-radius: 4px; padding: 8px;
}
button, select {
  font: inherit; font-size: 12px; background: #3a4466; color: var(--ink);
  border: 1px solid #5a6488; border-radius: 3px; padding: 6px 10px;
  min-height: 36px; touch-action: manipulation;
}
button:active { background: #4a5478; }
#day-slider {
  flex: 1 1 140px; min-width: 120px; accent-color: var(--accent);
}
#day-label { font-size: 12px; color: var(--muted); min-width: 4.5em; }
footer {
  margin-top: 8px; font-size: 10px; color: var(--muted); text-align: center;
}
</style>
</head>
<body>
<header>
  <h1>Tiny Town · Pixel Sim</h1>
  <div class="meta" id="seed-meta"></div>
</header>
<div id="stage-wrap"><canvas id="stage" width="320" height="240"></canvas></div>
<section id="hud">
  <div class="card"><h2>Day / Weather</h2><div class="big" id="hud-day">—</div><div id="hud-weather">—</div></div>
  <div class="card"><h2>Treasury</h2><div class="big" id="hud-treasury">—</div></div>
  <div class="card"><h2>Avg wallet</h2><div class="big" id="hud-wallet">—</div></div>
  <div class="card" id="board"><h2>Shop leaderboard</h2><ol id="hud-board"></ol></div>
</section>
<div id="controls">
  <button type="button" id="btn-play" aria-label="Play or pause">Play</button>
  <label>Speed
    <select id="speed" aria-label="Playback speed">
      <option value="0.5">0.5×</option>
      <option value="1" selected>1×</option>
      <option value="2">2×</option>
      <option value="4">4×</option>
    </select>
  </label>
  <input type="range" id="day-slider" min="0" max="0" value="0" aria-label="Day"/>
  <span id="day-label">day 1</span>
</div>
<footer>Read-only playback · sprites drawn in code · no external assets · Nori</footer>
<script>
const TIMELINE = """

_HTML_TAIL = r"""
;

(function () {
  "use strict";

  const MAP_W = 40;
  const MAP_H = 30;
  const TILE = 8;
  const canvas = document.getElementById("stage");
  const ctx = canvas.getContext("2d");
  canvas.width = MAP_W * TILE;
  canvas.height = MAP_H * TILE;
  ctx.imageSmoothingEnabled = false;

  const daily = Array.isArray(TIMELINE.daily) ? TIMELINE.daily : [];
  const seed = (TIMELINE.seed | 0) || 42;
  document.getElementById("seed-meta").textContent =
    "seed " + seed + " · " + daily.length + " days";

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rng = mulberry32(seed ^ 0x9e3779b9);

  function dollars(cents) {
    const n = Number(cents);
    if (!Number.isFinite(n)) return "$?";
    const sign = n < 0 ? "-" : "";
    const v = Math.abs(Math.trunc(n));
    return sign + "$" + Math.floor(v / 100) + "." + String(v % 100).padStart(2, "0");
  }

  function fmtTreasury(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return "$?";
    return "$" + n.toFixed(2);
  }

  function titleShop(id) {
    return String(id).split(/[-_]/).map(function (w) {
      return w ? w.charAt(0).toUpperCase() + w.slice(1) : "";
    }).join(" ");
  }

  const GRASS = 0, ROAD = 1, HOME = 2, SHOP = 3;
  const tiles = new Uint8Array(MAP_W * MAP_H);
  function setT(x, y, v) {
    if (x >= 0 && y >= 0 && x < MAP_W && y < MAP_H) tiles[y * MAP_W + x] = v;
  }
  function getT(x, y) {
    if (x < 0 || y < 0 || x >= MAP_W || y >= MAP_H) return -1;
    return tiles[y * MAP_W + x];
  }

  for (let i = 0; i < tiles.length; i++) tiles[i] = GRASS;
  for (let x = 0; x < MAP_W; x++) { setT(x, 14, ROAD); setT(x, 15, ROAD); }
  for (let y = 0; y < MAP_H; y++) { setT(19, y, ROAD); setT(20, y, ROAD); }
  for (let x = 4; x < MAP_W - 4; x++) { setT(x, 5, ROAD); setT(x, 24, ROAD); }
  for (let y = 5; y <= 24; y++) { setT(4, y, ROAD); setT(MAP_W - 5, y, ROAD); }

  const homeTiles = [];
  for (let x = 6; x < MAP_W - 6; x += 2) {
    if (getT(x, 3) === GRASS) { setT(x, 3, HOME); homeTiles.push([x, 3]); }
    if (getT(x, 26) === GRASS) { setT(x, 26, HOME); homeTiles.push([x, 26]); }
  }

  const shopIds = [];
  const seen = Object.create(null);
  for (let d = 0; d < daily.length; d++) {
    const biz = daily[d].businesses || {};
    for (const id in biz) {
      if (!seen[id]) { seen[id] = 1; shopIds.push(id); }
    }
  }

  const shopSlots = [
    [10, 10], [14, 10], [24, 10], [28, 10],
    [10, 18], [14, 18], [24, 18], [28, 18],
    [8, 12], [30, 12], [8, 16], [30, 16],
  ];
  const shopAt = Object.create(null);
  for (let i = 0; i < shopIds.length; i++) {
    const slot = shopSlots[i % shopSlots.length];
    const ox = (i >= shopSlots.length) ? (i % 3) : 0;
    const x = Math.min(MAP_W - 3, slot[0] + ox);
    const y = slot[1];
    setT(x, y, SHOP); setT(x + 1, y, SHOP);
    setT(x, y + 1, SHOP); setT(x + 1, y + 1, SHOP);
    shopAt[shopIds[i]] = { x: x, y: y, label: titleShop(shopIds[i]) };
  }

  const roadCells = [];
  for (let y = 0; y < MAP_H; y++) {
    for (let x = 0; x < MAP_W; x++) {
      if (getT(x, y) === ROAD) roadCells.push([x, y]);
    }
  }

  function nearestRoad(tx, ty) {
    let best = roadCells[0] || [19, 14], bestD = 1e9;
    for (let i = 0; i < roadCells.length; i++) {
      const c = roadCells[i];
      const d = Math.abs(c[0] - tx) + Math.abs(c[1] - ty);
      if (d < bestD) { bestD = d; best = c; }
    }
    return best;
  }

  const MAX_SPRITES = 36;
  const sprites = [];
  function rebuildSprites(entry) {
    sprites.length = 0;
    const residents = entry && entry.residents ? entry.residents : {};
    const count = Math.min(MAX_SPRITES, Math.max(4, Number(residents.count) || 12));
    const shopKeys = Object.keys(shopAt);
    for (let i = 0; i < count; i++) {
      const home = homeTiles[i % Math.max(1, homeTiles.length)] || [6, 3];
      const targetShop = shopKeys.length
        ? shopAt[shopKeys[i % shopKeys.length]]
        : { x: 19, y: 14 };
      const start = nearestRoad(home[0], home[1]);
      const goal = nearestRoad(targetShop.x, targetShop.y);
      sprites.push({
        x: start[0] + rng(),
        y: start[1] + rng(),
        tx: goal[0] + 0.5,
        ty: goal[1] + 0.5,
        homeX: start[0] + 0.5,
        homeY: start[1] + 0.5,
        color: (i * 47) % 360,
        toShop: true,
      });
    }
  }

  function fillTile(x, y, color) {
    ctx.fillStyle = color;
    ctx.fillRect(x * TILE, y * TILE, TILE, TILE);
  }

  function drawHome(x, y) {
    fillTile(x, y, "#6b4f3a");
    ctx.fillStyle = "#c45c26";
    ctx.fillRect(x * TILE, y * TILE, TILE, 3);
    ctx.fillStyle = "#ffe66d";
    ctx.fillRect(x * TILE + 3, y * TILE + 4, 2, 2);
  }

  function drawShopBuilding(x, y, boarded, name) {
    const wall = boarded ? "#3a3a44" : "#d4a373";
    const roof = boarded ? "#2a2a33" : "#9b2226";
    ctx.fillStyle = wall;
    ctx.fillRect(x * TILE, y * TILE, TILE * 2, TILE * 2);
    ctx.fillStyle = roof;
    ctx.fillRect(x * TILE, y * TILE, TILE * 2, 4);
    if (boarded) {
      ctx.fillStyle = "#1a1a22";
      ctx.fillRect(x * TILE + 3, y * TILE + 7, 10, 6);
      ctx.strokeStyle = "#555";
      ctx.beginPath();
      ctx.moveTo(x * TILE + 3, y * TILE + 7);
      ctx.lineTo(x * TILE + 13, y * TILE + 13);
      ctx.moveTo(x * TILE + 13, y * TILE + 7);
      ctx.lineTo(x * TILE + 3, y * TILE + 13);
      ctx.stroke();
    } else {
      ctx.fillStyle = "#89c2d9";
      ctx.fillRect(x * TILE + 3, y * TILE + 7, 4, 4);
      ctx.fillRect(x * TILE + 9, y * TILE + 7, 4, 4);
      ctx.fillStyle = "#432818";
      ctx.fillRect(x * TILE + 6, y * TILE + 12, 4, 4);
    }
    ctx.fillStyle = boarded ? "#888" : "#1a1c2c";
    ctx.font = "5px monospace";
    ctx.textBaseline = "top";
    const label = name.length > 10 ? name.slice(0, 9) + "\u2026" : name;
    ctx.fillText(label, x * TILE, y * TILE + TILE * 2 - 1);
  }

  function drawResident(s) {
    const px = Math.floor(s.x * TILE);
    const py = Math.floor(s.y * TILE);
    ctx.fillStyle = "hsl(" + s.color + " 70% 55%)";
    ctx.fillRect(px + 2, py + 1, 4, 3);
    ctx.fillStyle = "#243447";
    ctx.fillRect(px + 2, py + 4, 4, 4);
  }

  function weatherTint(cond) {
    switch (cond) {
      case "sun": return "rgba(255, 220, 100, 0.12)";
      case "rain": return "rgba(40, 80, 140, 0.22)";
      case "snow": return "rgba(220, 230, 255, 0.20)";
      case "storm": return "rgba(40, 20, 70, 0.35)";
      case "cloud": return "rgba(80, 90, 110, 0.18)";
      default: return "rgba(0,0,0,0)";
    }
  }

  let particles = [];
  function resetWeatherParticles(cond) {
    particles = [];
    const n = cond === "storm" ? 50 : cond === "rain" ? 40 : cond === "snow" ? 30 : 0;
    for (let i = 0; i < n; i++) {
      particles.push({
        x: rng() * canvas.width,
        y: rng() * canvas.height,
        v: 1 + rng() * 2.5,
        w: rng() * 1.5,
      });
    }
  }

  function drawWeatherOverlay(cond) {
    ctx.fillStyle = weatherTint(cond);
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    if (cond === "rain" || cond === "storm") {
      ctx.strokeStyle = cond === "storm" ? "#b8c0ff" : "#a0c4ff";
      ctx.lineWidth = 1;
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(p.x - 1, p.y + 4);
        ctx.stroke();
        p.y += p.v * (cond === "storm" ? 1.6 : 1);
        p.x -= 0.4;
        if (p.y > canvas.height) { p.y = -4; p.x = rng() * canvas.width; }
      }
    } else if (cond === "snow") {
      ctx.fillStyle = "#f8f9ff";
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        ctx.fillRect(p.x | 0, p.y | 0, 2, 2);
        p.y += p.v * 0.5;
        p.x += Math.sin(p.y * 0.05) * p.w;
        if (p.y > canvas.height) { p.y = -2; p.x = rng() * canvas.width; }
      }
    }
  }

  let dayIndex = 0;
  let lastCond = "";

  function currentEntry() {
    return daily[dayIndex] || daily[0] || { day: 1 };
  }

  function updateHud(entry) {
    const weather = entry.weather || {};
    const economy = entry.economy || {};
    const residents = entry.residents || {};
    const cond = weather.condition || "n/a";
    document.getElementById("hud-day").textContent = "Day " + (entry.day || (dayIndex + 1));
    document.getElementById("hud-weather").textContent =
      cond + (weather.temp_c != null ? " · " + weather.temp_c + "°C" : "");
    document.getElementById("hud-treasury").textContent = fmtTreasury(economy.treasury);
    document.getElementById("hud-wallet").textContent = dollars(residents.avg_wallet_cents);

    const biz = entry.businesses || {};
    const rows = Object.keys(biz).map(function (id) {
      return { id: id, bal: Number(biz[id].balance_cents) || 0, open: !!biz[id].open };
    }).sort(function (a, b) { return b.bal - a.bal; });
    const ol = document.getElementById("hud-board");
    ol.innerHTML = "";
    rows.slice(0, 6).forEach(function (r) {
      const li = document.createElement("li");
      const broke = r.bal <= 0;
      li.className = broke ? "broke" : "ok";
      li.textContent = titleShop(r.id) + " · " + dollars(r.bal) +
        (broke ? " · boarded" : (r.open ? "" : " · closed"));
      ol.appendChild(li);
    });
    document.getElementById("day-label").textContent = "day " + (entry.day || dayIndex + 1);
  }

  function drawMap(entry) {
    const biz = entry.businesses || {};
    const weather = entry.weather || {};
    const cond = weather.condition || "n/a";
    if (cond !== lastCond) {
      resetWeatherParticles(cond);
      lastCond = cond;
    }

    for (let y = 0; y < MAP_H; y++) {
      for (let x = 0; x < MAP_W; x++) {
        const t = getT(x, y);
        if (t === ROAD) {
          fillTile(x, y, "#5c6778");
          ctx.fillStyle = "#7d8597";
          if ((x + y) % 2 === 0) ctx.fillRect(x * TILE + 3, y * TILE + 3, 2, 2);
        } else if (t === GRASS || t === HOME || t === SHOP) {
          const g = ((x * 13 + y * 7) & 1) ? "#40916c" : "#52b788";
          fillTile(x, y, g);
        }
      }
    }

    for (let i = 0; i < homeTiles.length; i++) {
      drawHome(homeTiles[i][0], homeTiles[i][1]);
    }

    for (const id in shopAt) {
      const s = shopAt[id];
      const info = biz[id] || {};
      const bal = Number(info.balance_cents);
      const boarded = Number.isFinite(bal) && bal <= 0;
      drawShopBuilding(s.x, s.y, boarded, s.label);
    }

    for (let i = 0; i < sprites.length; i++) drawResident(sprites[i]);
    drawWeatherOverlay(cond);
  }

  function stepSprites(dt) {
    const speed = 0.015 * dt;
    for (let i = 0; i < sprites.length; i++) {
      const s = sprites[i];
      const dx = s.tx - s.x;
      const dy = s.ty - s.y;
      const dist = Math.hypot(dx, dy) || 1;
      if (dist < 0.15) {
        if (s.toShop) {
          s.tx = s.homeX; s.ty = s.homeY; s.toShop = false;
        } else {
          const keys = Object.keys(shopAt);
          if (keys.length) {
            const pick = keys[(rng() * keys.length) | 0];
            const sp = shopAt[pick];
            const road = nearestRoad(sp.x, sp.y);
            s.tx = road[0] + 0.5; s.ty = road[1] + 0.5;
          }
          s.toShop = true;
        }
      } else {
        s.x += (dx / dist) * speed;
        s.y += (dy / dist) * speed;
        const rx = Math.round(s.x), ry = Math.round(s.y);
        if (getT(rx, ry) !== ROAD && getT(rx, ry) !== SHOP) {
          const nr = nearestRoad(rx, ry);
          s.x += (nr[0] - s.x) * 0.05;
          s.y += (nr[1] - s.y) * 0.05;
        }
      }
    }
  }

  let playing = false;
  let acc = 0;
  let lastTs = 0;
  const slider = document.getElementById("day-slider");
  const btn = document.getElementById("btn-play");
  const speedSel = document.getElementById("speed");
  slider.max = Math.max(0, daily.length - 1);
  slider.value = 0;

  function setDay(i, rebuild) {
    dayIndex = Math.max(0, Math.min(daily.length - 1, i | 0));
    slider.value = String(dayIndex);
    const entry = currentEntry();
    if (rebuild) rebuildSprites(entry);
    updateHud(entry);
    drawMap(entry);
  }

  btn.addEventListener("click", function () {
    playing = !playing;
    btn.textContent = playing ? "Pause" : "Play";
    lastTs = 0;
  });
  slider.addEventListener("input", function () {
    playing = false;
    btn.textContent = "Play";
    setDay(Number(slider.value), true);
  });

  function frame(ts) {
    if (!lastTs) lastTs = ts;
    const dt = Math.min(50, ts - lastTs);
    lastTs = ts;
    const spd = Number(speedSel.value) || 1;
    if (playing && daily.length) {
      acc += dt * spd;
      const dayMs = 900;
      while (acc >= dayMs) {
        acc -= dayMs;
        if (dayIndex >= daily.length - 1) {
          playing = false;
          btn.textContent = "Play";
          break;
        }
        setDay(dayIndex + 1, true);
      }
    }
    stepSprites(dt * spd);
    drawMap(currentEntry());
    requestAnimationFrame(frame);
  }

  if (daily.length) {
    setDay(0, true);
  } else {
    updateHud({ day: 0, weather: { condition: "n/a" }, economy: {}, residents: {}, businesses: {} });
    drawMap({ businesses: {}, weather: { condition: "n/a" } });
  }
  requestAnimationFrame(frame);
})();
</script>
</body>
</html>
"""
