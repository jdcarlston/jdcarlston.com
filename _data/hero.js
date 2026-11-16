// Draws the homepage hero at build time: a plain-weave lattice on the left
// that frays into loose fiberglass strands on the right, with two Lissajous
// curves running through it. From "Trust is a Jenky State Machine": meaning
// structured "more like fiberglass and less like a crystal lattice."

function curve(a, b, delta, cx, cy, rx, ry) {
  const pts = [];
  const n = 720;
  for (let i = 0; i <= n; i++) {
    const t = (i / n) * Math.PI * 2;
    pts.push((i ? "L" : "M") + (cx + rx * Math.sin(a * t + delta)).toFixed(1) + " " + (cy + ry * Math.sin(b * t)).toFixed(1));
  }
  return pts.join(" ");
}

// Plain weave: at each crossing one thread passes over and the other breaks
// around it, alternating like a checkerboard.
function weave() {
  const step = 48, gap = 7, W = 912, H = 760;
  const h = [], v = [];
  for (let j = 0; j * step + 24 <= H; j++) {
    const y = j * step + 24;
    let start = 0;
    for (let i = 0; i * step + 24 <= W; i++) {
      const x = i * step + 24;
      if ((i + j) % 2 === 0) { h.push(`M${start} ${y} H${x - gap}`); start = x + gap; }
    }
    h.push(`M${start} ${y} H${W}`);
  }
  for (let i = 0; i * step + 24 <= W; i++) {
    const x = i * step + 24;
    let start = 0;
    for (let j = 0; j * step + 24 <= H; j++) {
      const y = j * step + 24;
      if ((i + j) % 2 === 1) { v.push(`M${x} ${start} V${y - gap}`); start = y + gap; }
    }
    v.push(`M${x} ${start} V${H}`);
  }
  return { h: h.join(" "), v: v.join(" ") };
}

// Loose strands, denser near the edge of the grid and thinning to the right.
// Seeded so the picture is the same on every build.
function fibers() {
  let seed = 93;
  const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
  const dim = [], warm = [];
  for (let k = 0; k < 260; k++) {
    const x = 900 + Math.pow(rnd(), 1.6) * 540;
    const y = rnd() * 760;
    const len = 30 + rnd() * 110;
    const ang = (rnd() - 0.5) * Math.PI * (0.25 + (x - 900) / 540);
    const x2 = x + Math.cos(ang) * len, y2 = y + Math.sin(ang) * len;
    const cx = (x + x2) / 2 + (rnd() - 0.5) * 30, cy = (y + y2) / 2 + (rnd() - 0.5) * 30;
    const d = `M${x.toFixed(1)} ${y.toFixed(1)} Q${cx.toFixed(1)} ${cy.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`;
    (k % 3 === 0 ? warm : dim).push(d);
  }
  return { dim: dim.join(" "), warm: warm.join(" ") };
}

module.exports = () => {
  const w = weave();
  const f = fibers();
  const t = 0.62;
  return {
    weaveH: w.h,
    weaveV: w.v,
    fibersDim: f.dim,
    fibersWarm: f.warm,
    curveA: curve(3, 4, Math.PI / 2, 1080, 380, 300, 300),
    curveB: curve(5, 4, Math.PI / 3, 1080, 380, 230, 230),
    node: {
      x: (1080 + 230 * Math.sin(5 * t + Math.PI / 3)).toFixed(1),
      y: (380 + 230 * Math.sin(4 * t)).toFixed(1),
    },
  };
};
