/* Results page: animated gauge, count-up number and an SVG radar chart (no libraries) */
(function () {
  const fg = document.querySelector(".g-fg");
  if (fg) {
    const C = 2 * Math.PI * 86;
    const score = parseFloat(fg.dataset.score) || 0;
    requestAnimationFrame(() => setTimeout(() => (fg.style.strokeDashoffset = C * (1 - score / 100)), 100));
  }
  document.querySelectorAll("[data-count]").forEach((el) => {
    const target = parseFloat(el.dataset.count) || 0;
    const start = performance.now();
    (function tick(now) {
      const p = Math.min(1, (now - start) / 1500);
      el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(tick);
    })(start);
  });

  const host = document.getElementById("radar");
  if (!host) return;
  let dims;
  try { dims = JSON.parse(host.dataset.dims); } catch (e) { return; }
  const items = Object.values(dims).filter((d) => d.score !== null && d.score !== undefined);
  if (items.length < 3) { host.textContent = "Not enough data for a chart."; return; }

  const NS = "http://www.w3.org/2000/svg";
  const W = 420, H = 340, cx = W / 2, cy = H / 2 + 6, R = 110;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Radar chart of dimension scores");
  const el = (name, attrs, parent) => {
    const n = document.createElementNS(NS, name);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    (parent || svg).appendChild(n);
    return n;
  };
  const n = items.length;
  const pt = (i, f) => {
    const a = (2 * Math.PI * i) / n - Math.PI / 2;
    return [cx + R * f * Math.cos(a), cy + R * f * Math.sin(a)];
  };
  [0.25, 0.5, 0.75, 1].forEach((lv) => {
    const pts = items.map((_, i) => pt(i, lv).join(",")).join(" ");
    el("polygon", { points: pts, fill: "none", stroke: "#dfe3f3", "stroke-width": 1 });
  });
  items.forEach((d, i) => {
    const [x, y] = pt(i, 1);
    el("line", { x1: cx, y1: cy, x2: x, y2: y, stroke: "#e6e9f4" });
    const [lx, ly] = pt(i, 1.2);
    const c = Math.cos((2 * Math.PI * i) / n - Math.PI / 2);
    const t = el("text", {
      x: lx, y: ly + 4, "font-size": 11, "font-weight": 700, fill: "#334155",
      "text-anchor": Math.abs(c) < 0.3 ? "middle" : c > 0 ? "start" : "end",
    });
    t.textContent = d.label.replace("& ", "").split(" ").slice(0, 2).join(" ");
  });
  const area = el("polygon", {
    points: items.map((_, i) => pt(i, 0).join(",")).join(" "),
    fill: "rgba(79,70,229,.22)", stroke: "#4f46e5", "stroke-width": 2.5, "stroke-linejoin": "round",
  });
  const dots = items.map((d, i) => {
    const c = el("circle", { cx, cy, r: 5, fill: "#fff", stroke: "#4f46e5", "stroke-width": 2.5 });
    const title = document.createElementNS(NS, "title");
    title.textContent = d.label + ": " + Math.round(d.score);
    c.appendChild(title);
    return c;
  });
  host.appendChild(svg);

  const start = performance.now();
  (function animate(now) {
    const p = Math.min(1, (now - start) / 1200);
    const e = 1 - Math.pow(1 - p, 3);
    area.setAttribute("points", items.map((d, i) => pt(i, (d.score / 100) * e).join(",")).join(" "));
    dots.forEach((c, i) => {
      const [x, y] = pt(i, (items[i].score / 100) * e);
      c.setAttribute("cx", x); c.setAttribute("cy", y);
    });
    if (p < 1) requestAnimationFrame(animate);
  })(start);
})();
