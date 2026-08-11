/* Widgets for the Contact Patch article page.

   Two sources of truth, deliberately separated:
     - the tire curve is recomputed live from tire.js (which self-checks
       against the Python it was ported from);
     - every RESULT is read from data.js, exported verbatim from the
       experiments' own artefacts by tools/export_web_data.py.
   Nothing here re-derives a published number. */
(function () {
"use strict";
var T = window.CPTire, D = window.CPData;
if (!T || !D) return;
if (!T.ok) { var w = document.getElementById('warn'); if (w) w.style.display = 'block'; }

var NS = 'http://www.w3.org/2000/svg';
function el(tag, a) { var e = document.createElementNS(NS, tag);
  for (var k in a) if (a.hasOwnProperty(k)) e.setAttribute(k, a[k]); return e; }
function clear(s) { while (s.firstChild) s.removeChild(s.firstChild); }
function txt(svg, x, y, s, fill, size, anchor, weight) {
  var t = el('text', { x: x, y: y, fill: fill || '#6A6358', 'font-size': size || 11,
    'font-family': "'JetBrains Mono',monospace" });
  if (anchor) t.setAttribute('text-anchor', anchor);
  if (weight) t.setAttribute('font-weight', weight);
  t.textContent = s; svg.appendChild(t); return t;
}
function line(svg, x1, y1, x2, y2, stroke, w, dash) {
  var a = { x1: x1, y1: y1, x2: x2, y2: y2, stroke: stroke, 'stroke-width': w || 1 };
  if (dash) a['stroke-dasharray'] = dash;
  svg.appendChild(el('line', a));
}
/* Arrow with a proportional head, used by every force drawing here. */
function arrow(svg, x1, y1, x2, y2, colour, w) {
  var dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy);
  if (L < 0.7) return;
  var ux = dx / L, uy = dy / L, h = Math.min(9, L * 0.42);
  line(svg, x1, y1, x2 - ux * h * 0.7, y2 - uy * h * 0.7, colour, w || 2.2);
  svg.appendChild(el('polygon', { points:
    (x2) + ',' + (y2) + ' ' +
    (x2 - ux * h - uy * h * 0.42) + ',' + (y2 - uy * h + ux * h * 0.42) + ' ' +
    (x2 - ux * h + uy * h * 0.42) + ',' + (y2 - uy * h - ux * h * 0.42),
    fill: colour }));
}
var C = { amber: '#E8C068', amberDim: '#C49A3C', steel: '#9AAABB', sage: '#7D9A6A',
  coral: '#FF5E3A', terra: '#C47A5A', mauve: '#9A7AB0', text: '#C8C2B4',
  bright: '#EDE8DC', muted: '#6A6358', border: '#2a2820', raised: '#211e17' };

/* reveal + progress */
var prog = document.getElementById('progress');
addEventListener('scroll', function () { var h = document.documentElement;
  prog.style.width = (h.scrollTop / (h.scrollHeight - h.clientHeight) * 100) + '%'; }, { passive: true });
if ('IntersectionObserver' in window) {
  var io = new IntersectionObserver(function (es) { es.forEach(function (e) {
    if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }); },
    { rootMargin: '0px 0px -10% 0px', threshold: .1 });
  document.querySelectorAll('.reveal').forEach(function (n) { io.observe(n); });
} else document.querySelectorAll('.reveal').forEach(function (n) { n.classList.add('in'); });

/* ============ 1. ONE TIRE: the curve, drawn as a wheel + a graph ============ */
(function () {
  var svg = document.getElementById('t_svg'); if (!svg) return;
  var slider = document.getElementById('t_a'), FZ = 3600;
  var peak = T.peakLateral(FZ);
  function render() {
    var deg = slider.value / 10;
    document.getElementById('t_av').textContent = deg.toFixed(1) + '°';
    var f = Math.abs(T.fy0(deg * Math.PI / 180, FZ));
    document.getElementById('t_f').textContent = Math.round(f).toLocaleString() + ' N';
    document.getElementById('t_p').textContent = (100 * f / peak.force).toFixed(0) + '%';
    clear(svg);

    /* --- left: the wheel, rotated by the actual angle, to scale --- */
    var cx = 128, cy = 150;
    line(svg, cx, cy - 84, cx, cy + 84, C.muted, 1, '4 4');
    txt(svg, cx, cy + 104, 'direction of travel', C.muted, 10, 'middle');
    var g = el('g', { transform: 'rotate(' + (-deg) + ' ' + cx + ' ' + cy + ')' });
    g.appendChild(el('rect', { x: cx - 15, y: cy - 46, width: 30, height: 92, rx: 7,
      fill: C.raised, stroke: C.steel, 'stroke-width': 1.6 }));
    svg.appendChild(g);
    /* grip arrow: length proportional to force, pointing across the travel line */
    arrow(svg, cx, cy, cx + (f / peak.force) * 74, cy, C.coral, 3);

    /* --- right: the curve, with a marker where you are --- */
    var L = 268, R = 596, TP = 40, B = 244, MAXA = 20;
    line(svg, L, B, R, B, C.border, 1); line(svg, L, TP, L, B, C.border, 1);
    var pts = [], i, a, y;
    for (i = 0; i <= 120; i++) {
      a = MAXA * i / 120;
      y = B - Math.abs(T.fy0(a * Math.PI / 180, FZ)) / peak.force * (B - TP) * 0.92;
      pts.push((L + (R - L) * a / MAXA).toFixed(1) + ',' + y.toFixed(1));
    }
    /* Beyond 12 deg the tire file is extrapolating; show it, but greyed. */
    var xb = L + (R - L) * 12 / MAXA;
    svg.appendChild(el('rect', { x: xb, y: TP, width: R - xb, height: B - TP,
      fill: C.coral, opacity: .05 }));
    line(svg, xb, TP, xb, B, C.coral, 1, '3 3');
    txt(svg, xb + 5, TP + 12, 'past what the rig measured', C.coral, 9);
    svg.appendChild(el('polyline', { points: pts.join(' '), fill: 'none',
      stroke: C.amberDim, 'stroke-width': 2 }));
    var px = L + (R - L) * Math.min(deg, MAXA) / MAXA;
    var py = B - f / peak.force * (B - TP) * 0.92;
    line(svg, px, B, px, py, C.amber, 1, '3 3');
    svg.appendChild(el('circle', { cx: px, cy: py, r: 5, fill: C.amber }));
    var kx = L + (R - L) * peak.alphaDeg / MAXA;
    line(svg, L, B - (B - TP) * 0.92, R, B - (B - TP) * 0.92, C.sage, 1, '2 5');
    txt(svg, R, B - (B - TP) * 0.92 - 6, 'most it can ever make', C.sage, 9.5, 'end');
    txt(svg, kx, B + 15, 'peak ' + peak.alphaDeg.toFixed(1) + '°', C.sage, 9.5, 'middle');
    txt(svg, L, B + 15, '0°', C.muted, 10);
    txt(svg, R, B + 15, '20°', C.muted, 10, 'end');
    txt(svg, L, TP - 10, 'sideways force vs slip angle', C.muted, 10);

    document.getElementById('t_cap').innerHTML =
      'At <b>' + deg.toFixed(1) + '°</b> this tire makes <b>' + Math.round(f).toLocaleString() +
      ' N</b> sideways — ' + (100 * f / peak.force).toFixed(0) + '% of everything it has. ' +
      (deg < 0.3 ? 'Pointed exactly where it is going, it makes <b>nothing at all</b>.'
       : deg < 6 ? 'Most of the grip arrives in the first few degrees.'
       : deg < 12 ? 'Near the top the curve is nearly flat — this is where the feedback goes quiet.'
       : 'Past 12° the tire file is extrapolating: the curve is our fit, not measured rubber.');
  }
  slider.addEventListener('input', render); render();
})();

/* ============ 2. LOAD TRANSFER: two tires, fixed total ============ */
(function () {
  var svg = document.getElementById('l_svg'); if (!svg) return;
  var slider = document.getElementById('l_x'), TOT = 6000;
  var even = 2 * T.peakLateral(TOT / 2).force;
  function render() {
    var xfer = slider.value / 100 * 2000;
    var inner = TOT / 2 - xfer, outer = TOT / 2 + xfer;
    var pair = T.peakLateral(inner).force + T.peakLateral(outer).force;
    var loss = 100 * (even - pair) / even;
    document.getElementById('l_xv').textContent = Math.round(xfer) + ' N';
    document.getElementById('l_in').textContent = Math.round(inner) + ' N';
    document.getElementById('l_out').textContent = Math.round(outer) + ' N';
    document.getElementById('l_tot').textContent = Math.round(pair).toLocaleString() + ' N';
    document.getElementById('l_loss').textContent = '−' + loss.toFixed(1) + '%';
    var tag = document.getElementById('l_tag');
    tag.textContent = xfer < 40 ? 'even' : loss > 3 ? 'expensive' : 'sharing unevenly';
    tag.className = 'tag ' + (xfer < 40 ? 'ok' : loss > 3 ? 'no' : 'idle');
    clear(svg);

    /* two tires drawn as squashing blocks, width ~ load */
    [[168, inner, 'inside'], [392, outer, 'outside']].forEach(function (t) {
      var x = t[0], load = t[1], w = 26 + 54 * (load / 5000);
      var h = 96;
      svg.appendChild(el('rect', { x: x - w / 2, y: 60, width: w, height: h, rx: 7,
        fill: C.raised, stroke: load > 3000 ? C.terra : C.steel, 'stroke-width': 1.8 }));
      /* downward load arrow, length ~ load */
      arrow(svg, x, 34, x, 56, C.steel, 1.6 + 1.6 * (load / 5000));
      txt(svg, x, 26, Math.round(load) + ' N', C.text, 11, 'middle');
      txt(svg, x, 176, t[2], C.muted, 10.5, 'middle');
      var g = T.peakLateral(load).force;
      arrow(svg, x, 158, x + 52 * (g / 4200), 158, C.coral, 2.4);
      txt(svg, x, 196, Math.round(g) + ' N grip', C.coral, 10, 'middle');
      txt(svg, x, 212, 'μ ' + T.peakLateral(load).mu.toFixed(2), C.muted, 9.5, 'middle');
    });

    /* the pair total, as a bar against the even-split reference */
    var BX = 470, BW = 118, BY = 62, BH = 96;
    svg.appendChild(el('rect', { x: BX, y: BY, width: BW, height: BH, rx: 4,
      fill: 'none', stroke: C.border }));
    var fh = BH * (pair / even);
    svg.appendChild(el('rect', { x: BX, y: BY + (BH - fh), width: BW, height: fh, rx: 4,
      fill: loss > 3 ? C.coral : C.sage, opacity: .55 }));
    line(svg, BX - 6, BY, BX + BW + 6, BY, C.sage, 1, '3 3');
    txt(svg, BX + BW / 2, BY - 10, 'even split', C.sage, 9.5, 'middle');
    txt(svg, BX + BW / 2, BY + BH + 18, 'what the pair', C.muted, 10, 'middle');
    txt(svg, BX + BW / 2, BY + BH + 32, 'can now make', C.muted, 10, 'middle');
    txt(svg, BX + BW / 2, BY + BH / 2 + 4, '−' + loss.toFixed(1) + '%',
        loss > 3 ? C.coral : C.text, 15, 'middle', '600');
  }
  slider.addEventListener('input', render); render();
})();

/* ============ 3. FRICTION ELLIPSE: drag the demand ============ */
(function () {
  var svg = document.getElementById('e_svg'); if (!svg) return;
  var cx = 210, cy = 190, R = 132, ang = -Math.PI / 2, dragging = false;
  function render() {
    clear(svg);
    svg.appendChild(el('circle', { cx: cx, cy: cy, r: R, fill: C.coral, opacity: .06 }));
    svg.appendChild(el('circle', { cx: cx, cy: cy, r: R, fill: 'none',
      stroke: C.bright, 'stroke-width': 2.2 }));
    line(svg, cx - R - 14, cy, cx + R + 14, cy, C.border, 1);
    line(svg, cx, cy - R - 14, cx, cy + R + 14, C.border, 1);
    txt(svg, cx, cy - R - 22, 'accelerating', C.muted, 10, 'middle');
    txt(svg, cx, cy + R + 32, 'braking', C.muted, 10, 'middle');
    txt(svg, cx - R - 18, cy + 4, 'turning', C.muted, 10, 'end');
    txt(svg, cx + R + 18, cy + 4, 'turning', C.muted, 10);
    var tx = cx + R * Math.cos(ang), ty = cy + R * Math.sin(ang);
    arrow(svg, cx, cy, tx, ty, C.coral, 3);
    svg.appendChild(el('circle', { cx: tx, cy: ty, r: 8, fill: C.amber, opacity: .95 }));
    var bx = Math.abs(Math.sin(ang)), by = Math.abs(Math.cos(ang));
    document.getElementById('e_bx').textContent = Math.round(100 * bx) + '%';
    document.getElementById('e_by').textContent = Math.round(100 * by) + '%';
    var t = document.getElementById('e_tag');
    t.textContent = by > .97 ? 'all cornering' : bx > .97 ? 'all braking' : 'sharing it';
  }
  function toAng(ev) {
    var r = svg.getBoundingClientRect();
    var p = ev.touches ? ev.touches[0] : ev;
    var vb = 420 / r.width;
    var x = (p.clientX - r.left) * vb - cx, y = (p.clientY - r.top) * vb - cy;
    ang = Math.atan2(y, x); render();
  }
  svg.addEventListener('pointerdown', function (e) { dragging = true; svg.setPointerCapture(e.pointerId); toAng(e); });
  svg.addEventListener('pointermove', function (e) { if (dragging) toAng(e); });
  svg.addEventListener('pointerup', function () { dragging = false; });
  render();
})();

/* ============ 4. FOUR TIRES THROUGH THE CORNER (the centrepiece) ======== */
(function () {
  var svg = document.getElementById('c_svg'); if (!svg) return;
  var drv = 'rwd', i = 20, playing = null;
  var slider = document.getElementById('c_s');
  var W = D.wheels, geo = D.corner;
  var N = W.rwd.s.length;
  slider.max = N - 1;
  slider.step = 1;
  /* One scale for every wheel and both drivetrains, so rings are comparable. */
  var maxLoad = 0;
  ['rwd', 'fwd'].forEach(function (d) { ['fl', 'fr', 'rl', 'rr'].forEach(function (c) {
    W[d][c].load.forEach(function (v) { if (v > maxLoad) maxLoad = v; }); }); });

  function capOf(load) { return T.peakLateral(Math.max(load, 1)).force; }

  function render() {
    var w = W[drv], s = w.s[i];
    var phase = s < geo.entry ? 'approach'
              : s < geo.entry + geo.arc ? 'in the corner'
              : 'exit';
    document.getElementById('c_sv').textContent =
      Math.round(s) + ' m · ' + phase;
    clear(svg);

    /* --- road map along the top, with the car's position --- */
    var MX = 24, MY = 30, MW = 572, MH = 60;
    txt(svg, MX, MY - 12, 'where the car is', C.muted, 10);
    var eFrac = geo.entry / geo.length, aFrac = (geo.entry + geo.arc) / geo.length;
    svg.appendChild(el('rect', { x: MX, y: MY, width: MW, height: MH, rx: 4,
      fill: C.raised, stroke: C.border }));
    svg.appendChild(el('rect', { x: MX + MW * eFrac, y: MY, width: MW * (aFrac - eFrac),
      height: MH, fill: C.amber, opacity: .13 }));
    txt(svg, MX + MW * (eFrac + aFrac) / 2, MY + MH / 2 + 4, 'the corner', C.amberDim, 10, 'middle');
    txt(svg, MX + 8, MY + MH / 2 + 4, 'approach', C.muted, 9.5);
    txt(svg, MX + MW - 8, MY + MH / 2 + 4, 'exit straight', C.muted, 9.5, 'end');
    var px = MX + MW * (s / geo.length);
    line(svg, px, MY - 5, px, MY + MH + 5, C.amber, 2);

    /* --- four wheels in plan, each a ring (capacity) + arrow (spend) --- */
    var POS = { fl: [206, 178], fr: [412, 178], rl: [206, 278], rr: [412, 278] };
    var NAME = { fl: 'front left', fr: 'front right', rl: 'rear left', rr: 'rear right' };
    /* car body outline behind the wheels, for orientation */
    svg.appendChild(el('rect', { x: 258, y: 150, width: 102, height: 156, rx: 16,
      fill: 'none', stroke: C.border, 'stroke-width': 1.4 }));
    txt(svg, 309, 232, 'front', C.muted, 9, 'middle');
    line(svg, 288, 240, 330, 240, C.border, 1);

    var worst = 0, worstName = '';
    ['fl', 'fr', 'rl', 'rr'].forEach(function (c) {
      var p = POS[c], x = p[0], y = p[1];
      var load = w[c].load[i], fx = w[c].fx[i], fy = w[c].fy[i];
      var cap = capOf(load);
      /* ring radius tracks how much this tire HAS */
      var r = 15 + 26 * Math.sqrt(load / maxLoad);
      var used = Math.min(Math.hypot(fx, fy) / cap, 1.3);
      if (used > worst) { worst = used; worstName = NAME[c]; }
      svg.appendChild(el('circle', { cx: x, cy: y, r: r, fill: C.coral,
        opacity: .05 + .22 * Math.min(used, 1) }));
      svg.appendChild(el('circle', { cx: x, cy: y, r: r, fill: 'none',
        stroke: used > .92 ? C.coral : C.steel, 'stroke-width': used > .92 ? 2.2 : 1.4 }));
      /* arrow: +fx forward (up on screen), +fy is ISO-left so screen-left */
      arrow(svg, x, y, x - (fy / cap) * r, y - (fx / cap) * r,
            used > .92 ? C.coral : C.amber, 2.4);
      txt(svg, x, y + r + 15, NAME[c], C.muted, 9.5, 'middle');
      txt(svg, x, y + r + 29, Math.round(load) + ' N · ' + Math.round(100 * used) + '%',
          used > .92 ? C.coral : C.text, 10, 'middle');
    });
    txt(svg, 24, 132, 'ring = what that tire is carrying · arrow = what it is spending',
        C.muted, 10);

    var pct = Math.round(100 * worst);
    /* On the exit straight the DRIVEN pair's total is pinned by the engine but
       the left/right split is not — with a free differential and two wheels of
       equal capability, any split summing to the cap is equally good. The
       solver lands on an arbitrary one, so the two can read very differently
       for no physical reason. Say so rather than let it look like a finding. */
    var dp = drv === 'rwd' ? ['rl', 'rr'] : ['fl', 'fr'];
    var d0 = Math.abs(w[dp[0]].fx[i]), d1 = Math.abs(w[dp[1]].fx[i]);
    var lop = (d0 + d1) > 500 && Math.abs(d0 - d1) / (d0 + d1) > 0.35 &&
              Math.abs(w[dp[0]].load[i] - w[dp[1]].load[i]) < 300;
    document.getElementById('c_cap').innerHTML =
      '<b>' + (drv === 'rwd' ? 'Rear-wheel drive' : 'Front-wheel drive') + '</b> at ' +
      Math.round(s) + ' m. Busiest tire: <b>' + worstName + '</b> at ' + pct + '% of what it has left. ' +
      (s < geo.entry ? 'Still on the approach — braking, weight moving forward.'
       : s < geo.entry + geo.arc ? 'In the corner: the outside tires are carrying the car and both drivetrains look the same.'
       : (drv === 'fwd'
          ? 'Past the exit, and the front tires are <b>still working</b> — they are accelerating the car as well as having steered it.'
          : 'Past the exit, and the front tires have gone quiet. The rears are doing the accelerating.')) +
      (lop ? ' <span style="color:#6A6358">(The two driven wheels read very differently here even though they carry almost the same load. Their <i>total</i> is pinned by the engine; how it splits left to right is not, so the solver picks arbitrarily among equally good answers. Nothing physical distinguishes them.)</span>' : '');
  }
  function go(n) { i = Math.max(0, Math.min(N - 1, n)); slider.value = i; render(); }
  slider.addEventListener('input', function () { go(+slider.value); });
  document.getElementById('c_back').addEventListener('click', function () { go(i - 1); });
  document.getElementById('c_fwd').addEventListener('click', function () { go(i + 1); });
  /* Arrow keys once the widget has been touched — stepping one solver node at
     a time is the point, and a slider drag cannot do it. */
  slider.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') { go(i - 1); e.preventDefault(); }
    if (e.key === 'ArrowRight') { go(i + 1); e.preventDefault(); }
  });
  /* Jump straight to the phases worth comparing, so nobody has to hunt. */
  var arcEnd = geo.entry + geo.arc;
  function nearest(target) {
    var best = 0;
    for (var k = 0; k < N; k++)
      if (Math.abs(W[drv].s[k] - target) < Math.abs(W[drv].s[best] - target)) best = k;
    return best;
  }
  var JUMPS = { brake: function () { return nearest(geo.entry - 22); },
                turnin: function () { return nearest(geo.entry + 4); },
                apex: function () { return nearest(geo.entry + geo.arc * 0.55); },
                exit: function () { return nearest(arcEnd + 3); },
                straight: function () { return nearest(arcEnd + 80); } };
  document.querySelectorAll('[data-jump]').forEach(function (b) {
    b.addEventListener('click', function () { go(JUMPS[b.getAttribute('data-jump')]()); });
  });
  document.querySelectorAll('.toggle[data-drv]').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('.toggle[data-drv]').forEach(function (o) { o.classList.remove('active'); });
      b.classList.add('active'); drv = b.getAttribute('data-drv'); render();
    });
  });
  var playBtn = document.getElementById('c_play');
  playBtn.addEventListener('click', function () {
    if (playing) { clearInterval(playing); playing = null; playBtn.textContent = 'Play';
      playBtn.classList.remove('on'); return; }
    playBtn.textContent = 'Pause'; playBtn.classList.add('on');
    if (i >= N - 1) go(0);
    playing = setInterval(function () {
      if (i >= N - 1) {                    /* stop at the end, don't loop */
        clearInterval(playing); playing = null;
        playBtn.textContent = 'Play'; playBtn.classList.remove('on'); return;
      }
      go(i + 1);
    }, 340);
  });
  render();
})();

/* ============ 5. FWD vs RWD ACROSS POWER ============ */
(function () {
  var svg = document.getElementById('p_svg'); if (!svg) return;
  /* Four discrete solves, so four buttons. A slider would imply we measured
     the range in between, and we didn't. */
  var rows = D.drivetrain.power, k = 1;
  function render() {
    var r = rows[k];
    clear(svg);
    var diff = r.fwd - r.rwd;                 /* + means FWD slower */
    var L = 150, TOP = 46, BH = 34, GAP = 22;
    var lo = Math.min(r.rwd, r.fwd), span = 0.42;
    function w(t) { return Math.max(6, (1 - (t - lo) / span) * 300 + 60); }
    [['rear drive', r.rwd, C.steel], ['front drive', r.fwd, C.amberDim]].forEach(function (b, n) {
      var y = TOP + n * (BH + GAP);
      svg.appendChild(el('rect', { x: L, y: y, width: w(b[1]), height: BH, rx: 3,
        fill: b[2], opacity: .85 }));
      txt(svg, L - 12, y + 22, b[0], C.text, 12, 'end');
      txt(svg, L + w(b[1]) + 10, y + 22, b[1].toFixed(3) + ' s', C.bright, 12);
    });
    var winner = diff > 0 ? 'rear' : 'front';
    var mag = Math.abs(diff);
    txt(svg, L, 160, (mag < 0.006 ? 'dead even' :
      winner + ' drive quicker by ' + mag.toFixed(3) + ' s'),
      mag < 0.006 ? C.muted : (winner === 'rear' ? C.steel : C.amber), 15, 'start', '600');

    /* the whole curve underneath, so the crossover is visible at once */
    var GX = 150, GY = 196, GW = 300, GH = 44;
    line(svg, GX, GY + GH / 2, GX + GW, GY + GH / 2, C.border, 1);
    txt(svg, GX, GY + GH + 22, rows[0].hp + ' hp', C.muted, 9.5);
    txt(svg, GX + GW, GY + GH + 22, rows[rows.length - 1].hp + ' hp', C.muted, 9.5, 'end');
    txt(svg, GX, GY - 8, 'front drive advantage across the range', C.muted, 9.5);
    var maxd = 0.30;
    rows.forEach(function (rr, n) {
      var x = GX + GW * n / (rows.length - 1);
      var d = rr.fwd - rr.rwd;
      var y = GY + GH / 2 - Math.max(-1, Math.min(1, -d / maxd)) * (GH / 2);
      svg.appendChild(el('circle', { cx: x, cy: y, r: n === k ? 6 : 4,
        fill: d > 0.006 ? C.steel : d < -0.006 ? C.amber : C.muted }));
      if (n === k) svg.appendChild(el('circle', { cx: x, cy: y, r: 10, fill: 'none',
        stroke: C.amber, 'stroke-width': 1.5 }));
    });
    txt(svg, GX + GW + 12, GY + 8, 'front', C.amber, 9.5);
    txt(svg, GX + GW + 12, GY + GH + 2, 'rear', C.steel, 9.5);

    document.getElementById('p_cap').innerHTML =
      'At <b>' + r.hp + ' hp</b>' + (k === 1 ? ' (the car being modelled)' : '') +
      ': rear drive ' + r.rwd.toFixed(3) + ' s, front drive ' +
      r.fwd.toFixed(3) + ' s. ' + (mag < 0.006
        ? 'Level — neither layout has an advantage worth the name here.'
        : (winner === 'front'
          ? 'Front drive is ahead, because at this power the exit is limited by the <b>engine</b>, not by grip.'
          : 'Rear drive is ahead, and the gap grows fast — the front tires are saturating and being asked to steer as well.'));
  }
  document.querySelectorAll('[data-pow]').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('[data-pow]').forEach(function (o) { o.classList.remove('active'); });
      b.classList.add('active'); k = +b.getAttribute('data-pow'); render();
    });
  });
  render();
})();

/* ============ 6. BALANCE -> UNDERSTEER ============ */
(function () {
  var svg = document.getElementById('b_svg'); if (!svg) return;
  var B = D.balance, sl = document.getElementById('b_i');
  function render() {
    var k = +sl.value, frac = B.frac[k], K = B.K[k];
    document.getElementById('b_v').textContent = Math.round(frac * 100) + '%';
    document.getElementById('b_tag').textContent = Math.round(frac * 100) + '% front';
    clear(svg);

    /* car in plan, mass blob sliding along it */
    var CX = 150, CY = 118, CL = 200, CW = 74;
    svg.appendChild(el('rect', { x: CX - CW / 2, y: CY - CL / 2, width: CW, height: CL, rx: 18,
      fill: 'none', stroke: C.border, 'stroke-width': 1.5 }));
    txt(svg, CX, CY - CL / 2 - 10, 'front', C.muted, 9.5, 'middle');
    var my = CY - CL / 2 + CL * (1 - frac);
    svg.appendChild(el('circle', { cx: CX, cy: my, r: 26, fill: C.amber, opacity: .3 }));
    svg.appendChild(el('circle', { cx: CX, cy: my, r: 26, fill: 'none', stroke: C.amber, 'stroke-width': 2 }));
    txt(svg, CX, my + 5, 'mass', '#0d0c07', 11, 'middle', '600');
    /* which end gives up first */
    var overs = K < -0.02, unders = K > 0.02;
    txt(svg, CX, CY + CL / 2 + 26,
        overs ? 'the back steps out' : unders ? 'the front pushes wide' : 'neutral',
        overs ? C.coral : unders ? C.steel : C.sage, 12, 'middle', '600');

    /* the gradient scale */
    var GX = 320, GY = 60, GW = 250, GH = 140;
    txt(svg, GX, GY - 18, 'understeer gradient (deg/g)', C.muted, 10);
    line(svg, GX, GY, GX, GY + GH, C.border, 1);
    var lo = -0.5, hi = 0.8;
    function ypos(v) { return GY + GH * (hi - v) / (hi - lo); }
    line(svg, GX - 6, ypos(0), GX + GW, ypos(0), C.sage, 1, '3 3');
    txt(svg, GX + GW, ypos(0) - 5, 'neutral', C.sage, 9.5, 'end');
    B.K.forEach(function (v, n) {
      var y = ypos(v), on = n === k;
      svg.appendChild(el('circle', { cx: GX + 34 + n * 44, cy: y, r: on ? 7 : 4,
        fill: v < 0 ? C.coral : v > 0 ? C.steel : C.sage, opacity: on ? 1 : .5 }));
      txt(svg, GX + 34 + n * 44, GY + GH + 18, Math.round(B.frac[n] * 100) + '%',
          on ? C.bright : C.muted, 9.5, 'middle');
    });
    txt(svg, GX - 10, ypos(0.8) + 4, 'understeer', C.steel, 9.5, 'end');
    txt(svg, GX - 10, ypos(-0.5) + 4, 'oversteer', C.coral, 9.5, 'end');
    txt(svg, GX + 34 + k * 44 + 14, ypos(K) + 4, (K > 0 ? '+' : '') + K.toFixed(2),
        C.bright, 13, 'start', '600');

    document.getElementById('b_cap').innerHTML =
      'At <b>' + Math.round(frac * 100) + '% front</b> the understeer gradient is <b>' +
      (K > 0 ? '+' : '') + K.toFixed(2) + ' deg/g</b>, and the lap takes ' +
      B.rwd[k].toFixed(2) + ' s with rear drive, ' + B.fwd[k].toFixed(2) + ' s with front. ' +
      'Across the whole sweep the character swings by <b>1.05 deg/g</b> — oversteer to understeer — ' +
      'while the lap time moves about <b>0.2 s</b>.';
  }
  sl.addEventListener('input', render); render();
})();

/* ============ 7. LAYOUT: the two axes ============ */
(function () {
  var svg = document.getElementById('y_svg'); if (!svg) return;
  var L = D.layout;
  var KEYS = ['front_fwd', 'front_rwd', 'front_mid_rwd', 'mid_rwd', 'rear_rwd'];
  var LAB = { front_fwd: 'front engine, FWD', front_rwd: 'front engine, RWD',
    front_mid_rwd: 'front-mid, RWD', mid_rwd: 'mid engine', rear_rwd: 'rear engine' };
  var sel = 'mid_rwd';
  function render() {
    clear(svg);
    var X0 = 96, X1 = 470, Y0 = 54, Y1 = 232;
    function px(f) { return X0 + (X1 - X0) * (f - 0.34) / (0.68 - 0.34); }
    function py(i) { return Y1 - (Y1 - Y0) * (i - 0.72) / (1.32 - 0.72); }
    line(svg, X0 - 16, Y1, X1 + 20, Y1, C.border, 1);
    line(svg, X0 - 16, Y0 - 14, X0 - 16, Y1, C.border, 1);
    txt(svg, (X0 + X1) / 2, Y1 + 34, 'mass further back  ←   where the weight sits   →  further forward', C.muted, 10, 'middle');
    txt(svg, X0 - 26, Y0 - 20, 'mass flung out toward the ends', C.muted, 10);
    txt(svg, X0 - 26, Y1 + 4, 'gathered near the middle', C.muted, 10);

    KEYS.forEach(function (k) {
      var d = L[k], x = px(d.front), y = py(d.izz), on = k === sel;
      var g = el('g', { style: 'cursor:pointer' });
      g.appendChild(el('circle', { cx: x, cy: y, r: on ? 13 : 9,
        fill: on ? C.amber : C.steel, opacity: on ? .95 : .55 }));
      if (on) g.appendChild(el('circle', { cx: x, cy: y, r: 19, fill: 'none',
        stroke: C.amber, 'stroke-width': 1.5 }));
      g.addEventListener('click', function () { sel = k; render(); });
      svg.appendChild(g);
      txt(svg, x, y - (on ? 26 : 17), LAB[k], on ? C.bright : C.muted, on ? 11 : 10, 'middle');
    });

    /* readout for the selected layout */
    var d = L[sel], RX = 500;
    txt(svg, RX, 76, LAB[sel], C.bright, 12, 'start', '600');
    [['weight on front', Math.round(d.front * 100) + '%'],
     ['polar moment', d.izz.toFixed(2) + '×'],
     ['response time', Math.round(d.rise * 1000) + ' ms'],
     ['understeer', (d.K > 0 ? '+' : '') + d.K.toFixed(2)],
     ['lap time', d.lap.toFixed(2) + ' s']].forEach(function (r, n) {
      txt(svg, RX, 104 + n * 22, r[0], C.muted, 9.5);
      txt(svg, RX, 116 + n * 22, r[1], C.amber, 12);
    });
    document.getElementById('y_tag').textContent = LAB[sel];

    /* lap times all five, to make the flatness undeniable */
    var BY = 274, BX = 96, BW = 374;
    var laps = KEYS.map(function (k) { return L[k].lap; });
    var lo = Math.min.apply(null, laps), hi = Math.max.apply(null, laps);
    txt(svg, BX, BY - 12, 'lap time, all five — a span of ' +
        ((hi - lo)).toFixed(3) + ' s', C.muted, 10);
    line(svg, BX, BY + 12, BX + BW, BY + 12, C.border, 1);
    KEYS.forEach(function (k) {
      var x = BX + BW * (L[k].lap - lo) / Math.max(hi - lo, 1e-6);
      svg.appendChild(el('circle', { cx: x, cy: BY + 12, r: k === sel ? 7 : 5,
        fill: k === sel ? C.amber : C.steel, opacity: k === sel ? 1 : .6 }));
    });
    txt(svg, BX, BY + 34, lo.toFixed(2) + ' s', C.muted, 9.5);
    txt(svg, BX + BW, BY + 34, hi.toFixed(2) + ' s', C.muted, 9.5, 'end');

    document.getElementById('y_cap').innerHTML =
      '<b>' + LAB[sel] + '</b> · ' + Math.round(d.front * 100) + '% front, polar moment ' +
      d.izz.toFixed(2) + '×, settles in ' + Math.round(d.rise * 1000) +
      ' ms. Click the others: the front-engined saloon and the rear-engined 911 sit at ' +
      '<b>opposite ends of the balance axis and the same height on the inertia one</b> — ' +
      'and every one of these laps within a few hundredths of the rest.';
  }
  render();
})();

/* ====== 7b. RACING LINES UNDER DISTURBANCE, PER DESIGN ====== */
(function () {
  var svg = document.getElementById('ln_svg'); if (!svg || !window.CPLines) return;
  var L = window.CPLines, cond = 'nominal', design = '047';
  var geo = D.corner, HW = geo.halfWidth;

  var cbar = document.getElementById('ln_conds');
  Object.keys(L.conds).forEach(function (c) {
    var b = document.createElement('button');
    b.className = 'toggle' + (c === cond ? ' active' : '');
    b.textContent = L.conds[c]; b.setAttribute('data-cond', c);
    b.addEventListener('click', function () {
      cbar.querySelectorAll('.toggle').forEach(function (o) { o.classList.remove('active'); });
      b.classList.add('active'); cond = c; render();
    });
    cbar.appendChild(b);
  });
  var dbar = document.getElementById('ln_designs');
  L.designs.forEach(function (d) {
    var b = document.createElement('button');
    b.className = 'btn' + (d === design ? ' on' : '');
    b.textContent = parseInt(d, 10) + '%'; b.setAttribute('data-design', d);
    b.addEventListener('click', function () {
      dbar.querySelectorAll('.btn').forEach(function (o) { o.classList.remove('on'); });
      b.classList.add('on'); design = d; render();
    });
    dbar.appendChild(b);
  });

  function render() {
    clear(svg);
    var laps = L.cells[cond + '|' + design] || [];
    var X0 = 30, X1 = 592, Y = 128, H = 74;
    function px(s) { return X0 + (X1 - X0) * s / geo.length; }
    function py(n) { return Y - (n / HW) * H; }

    /* the road: edges are where a lap ends */
    svg.appendChild(el('rect', { x: X0, y: py(HW), width: X1 - X0, height: 2 * H,
      fill: C.raised, opacity: .55 }));
    var e0 = px(geo.entry), e1 = px(geo.entry + geo.arc);
    svg.appendChild(el('rect', { x: e0, y: py(HW), width: e1 - e0, height: 2 * H,
      fill: C.amber, opacity: .07 }));
    txt(svg, (e0 + e1) / 2, py(HW) - 8, 'the corner', C.amberDim, 9.5, 'middle');
    [HW, -HW].forEach(function (v) { line(svg, X0, py(v), X1, py(v), C.coral, 1.4); });
    line(svg, X0, py(0), X1, py(0), C.border, 1, '4 5');
    txt(svg, X0 - 4, py(HW) - 6, 'edge of the road', C.coral, 9, 'start');

    /* The same car with nothing going wrong, underneath. Without it the reader
       has to toggle back and forth to see what the disturbance actually moved. */
    if (cond !== 'nominal') {
      (L.cells['nominal|' + design] || []).forEach(function (lp) {
        var g = lp.n.map(function (n, k) { return px(L.grid[k]).toFixed(1) + ',' + py(n).toFixed(1); });
        svg.appendChild(el('polyline', { points: g.join(' '), fill: 'none',
          stroke: C.steel, 'stroke-width': 1, opacity: .16 }));
      });
      txt(svg, X1, 232, 'faint = same car, undisturbed', '#6A6358', 10, 'end');
    }

    var fails = 0;
    laps.forEach(function (lp) {
      var pts = lp.n.map(function (n, k) { return px(L.grid[k]).toFixed(1) + ',' + py(n).toFixed(1); });
      svg.appendChild(el('polyline', { points: pts.join(' '), fill: 'none',
        stroke: lp.ok ? C.steel : C.coral,
        'stroke-width': lp.ok ? 1.2 : 2, opacity: lp.ok ? .55 : .95 }));
      if (!lp.ok) {
        fails++;
        var k = lp.n.length - 1;
        svg.appendChild(el('circle', { cx: px(L.grid[k]), cy: py(lp.n[k]), r: 4.5, fill: C.coral }));
      }
    });

    txt(svg, X0, 232, laps.length + ' laps drawn · ' +
        (fails ? fails + ' left the road (marked)' : 'all stayed on'),
        fails ? C.coral : C.sage, 11);

    /* the measured rate, which is NOT the rate among these sampled laps */
    var r = L.rates[(cond === 'nominal' ? 'nominal' : cond) + '|' + design];
    var rateTxt = r && r.rate != null
      ? 'Measured over the full run: <b>' + r.fails + ' of ' + r.n + '</b> laps lost (' +
        (100 * r.rate).toFixed(1) + '%).'
      : '';
    document.getElementById('ln_cap').innerHTML =
      '<b>' + parseInt(design, 10) + '% of the weight on the front</b>, ' + L.conds[cond] +
      '. ' + (design === '040'
        ? 'This car fails whatever you do to it — the driver cannot hold it even undisturbed.'
        : fails
          ? 'Some laps run out of road.'
          : 'Every lap holds its line.') +
      ' ' + rateTxt +
      ' <span style="color:#6A6358">The lines are a sample of the laps driven, chosen to include the failures; the percentage comes from all of them.</span>';
  }
  render();
})();

/* ====== 8. WHICH WHEEL PAYS: open differential vs torque vectoring ====== */
(function () {
  var svg = document.getElementById('w_svg'); if (!svg || !window.CPTv) return;
  var TV = window.CPTv, OPEN = TV.configs.open, TVC = TV.configs.tv4;
  var N = Math.min(OPEN.s.length, TVC.s.length), i = 20, playing = null;
  var slider = document.getElementById('w_s');
  slider.max = N - 1; slider.step = 1;
  var geo = D.corner, arcEnd = geo.entry + geo.arc;
  /* One scale for both cars so the two panels are directly comparable. */
  var maxF = 0;
  [OPEN, TVC].forEach(function (cfg) { ['fl','fr','rl','rr'].forEach(function (c) {
    cfg[c].fx.forEach(function (v) { if (Math.abs(v) > maxF) maxF = Math.abs(v); }); }); });

  function panel(cfg, ox, title, sub) {
    var s = cfg.s[i];
    txt(svg, ox + 96, 30, title, C.bright, 12.5, 'middle', '600');
    txt(svg, ox + 96, 46, sub, C.muted, 10, 'middle');
    var POS = { fl: [ox + 46, 96], fr: [ox + 146, 96], rl: [ox + 46, 196], rr: [ox + 146, 196] };
    svg.appendChild(el('rect', { x: ox + 72, y: 74, width: 48, height: 144, rx: 12,
      fill: 'none', stroke: C.border, 'stroke-width': 1.2 }));
    txt(svg, ox + 96, 70, 'front', C.muted, 8.5, 'middle');
    var left = 0, right = 0;
    ['fl','fr','rl','rr'].forEach(function (c) {
      var pt = POS[c], x = pt[0], y = pt[1];
      var fx = cfg[c].fx[i], fz = cfg[c].fz[i];
      if (c === 'fl' || c === 'rl') left += fx; else right += fx;
      /* ring = load carried, arrow = drive (up) or brake (down) */
      var r = 13 + 18 * Math.sqrt(Math.max(fz, 0) / 6200);
      svg.appendChild(el('circle', { cx: x, cy: y, r: r, fill: 'none',
        stroke: C.border, 'stroke-width': 1.2 }));
      var len = (fx / maxF) * 40;
      var col = fx > 30 ? C.sage : fx < -30 ? C.coral : C.muted;
      if (Math.abs(len) > 1.5) arrow(svg, x, y, x, y - len, col, 2.6);
      else svg.appendChild(el('circle', { cx: x, cy: y, r: 2, fill: C.muted }));
      txt(svg, x, y + r + 13, Math.round(fx) + ' N', col, 9.5, 'middle');
    });
    return left - right;
  }

  function render() {
    clear(svg);
    var s = OPEN.s[i];
    var phase = s < geo.entry ? 'approach' : s < arcEnd ? 'in the corner' : 'exit';
    document.getElementById('w_sv').textContent = Math.round(s) + ' m · ' + phase;
    var leanO = panel(OPEN, 20, 'open differential', 'one fixed rule');
    var leanV = panel(TVC, 330, 'torque vectoring', 'deciding, every instant');
    line(svg, 310, 24, 310, 268, C.border, 1);
    /* the asymmetry each one is creating, which is the whole comparison */
    txt(svg, 116, 262, 'left minus right: ' + Math.round(leanO) + ' N',
        Math.abs(leanO) > 60 ? C.amber : C.muted, 11, 'middle');
    txt(svg, 426, 262, 'left minus right: ' + Math.round(leanV) + ' N',
        Math.abs(leanV) > 60 ? C.amber : C.muted, 11, 'middle');
    txt(svg, 310, 288, 'green = pushing that wheel forward · red = braking it', C.muted, 9.5, 'middle');
    var tag = document.getElementById('w_tag');
    tag.textContent = Math.abs(leanV) > 60 ? 'controller is twisting the car' : 'nothing to correct';
    tag.className = 'tag ' + (Math.abs(leanV) > 60 ? 'ok' : 'idle');

    document.getElementById('w_cap').innerHTML =
      'At <b>' + Math.round(s) + ' m</b>. The differential\'s two sides are ' +
      (Math.abs(leanO) < 1 ? '<b>exactly equal</b>' : 'within ' + Math.round(Math.abs(leanO)) + ' N') +
      ' — it has no way to be anything else. The controller is running a ' +
      Math.round(Math.abs(leanV)) + ' N difference across the car' +
      (Math.abs(leanV) < 60 ? ', which is to say it has decided this moment needs nothing.'
        : (leanV < 0 ? ', pushing harder on the outside to rotate the car <b>into</b> the corner.'
                     : ', pushing harder on the inside to take rotation <b>away</b>.'));
  }

  function go(n) { i = Math.max(0, Math.min(N - 1, n)); slider.value = i; render(); }
  slider.addEventListener('input', function () { go(+slider.value); });
  document.getElementById('w_back').addEventListener('click', function () { go(i - 1); });
  document.getElementById('w_fwd').addEventListener('click', function () { go(i + 1); });
  function nearest(target) { var b = 0;
    for (var k = 0; k < N; k++) if (Math.abs(OPEN.s[k] - target) < Math.abs(OPEN.s[b] - target)) b = k;
    return b; }
  var J = { brake: geo.entry - 22, turnin: geo.entry + 6, apex: geo.entry + geo.arc * 0.55,
            exit: arcEnd + 4, straight: arcEnd + 80 };
  document.querySelectorAll('[data-wjump]').forEach(function (b) {
    b.addEventListener('click', function () { go(nearest(J[b.getAttribute('data-wjump')])); });
  });
  var pb = document.getElementById('w_play');
  pb.addEventListener('click', function () {
    if (playing) { clearInterval(playing); playing = null; pb.textContent = 'Play'; pb.classList.remove('on'); return; }
    pb.textContent = 'Pause'; pb.classList.add('on');
    if (i >= N - 1) go(0);
    playing = setInterval(function () {
      if (i >= N - 1) { clearInterval(playing); playing = null;
        pb.textContent = 'Play'; pb.classList.remove('on'); return; }
      go(i + 1);
    }, 300);
  });
  render();
})();

/* ====== 9. WHAT IT IS WORTH: the cornering ceiling, per layout ====== */
(function () {
  var svg = document.getElementById('v_svg'); if (!svg || !D.limits) return;
  var pw = '1x';
  var KEYS = ['front_fwd', 'front_rwd', 'front_mid_rwd', 'mid_rwd', 'rear_rwd'];
  var LAB = { front_fwd: 'front engine, FWD', front_rwd: 'front engine, RWD',
    front_mid_rwd: 'front-mid, RWD', mid_rwd: 'mid engine', rear_rwd: 'rear engine' };
  function render() {
    clear(svg);
    var L = D.limits[pw];
    var X0 = 168, X1 = 560, lo = 0.30, hi = 1.16;
    function px(v) { return X0 + (X1 - X0) * (v - lo) / (hi - lo); }
    txt(svg, 20, 24, 'the most cornering each layout survives before it fails', C.muted, 10.5);
    KEYS.forEach(function (k, n) {
      var y = 58 + n * 42, o = L[k].off, v = L[k].on;
      txt(svg, X0 - 12, y + 4, LAB[k], C.text, 11, 'end');
      line(svg, px(lo), y, X1, y, C.border, 1);
      /* the gain, drawn as the distance between the two */
      if (Math.abs(v - o) > 0.004)
        line(svg, px(Math.min(o, v)), y, px(Math.max(o, v)), y,
             v > o ? C.sage : C.coral, 5);
      svg.appendChild(el('circle', { cx: px(o), cy: y, r: 6, fill: C.steel }));
      svg.appendChild(el('circle', { cx: px(v), cy: y, r: 6, fill: C.amber }));
      var d = 100 * (v / o - 1);
      txt(svg, X1 + 12, y + 4, (d > 0 ? '+' : '') + d.toFixed(0) + '%',
          Math.abs(d) < 3 ? C.muted : d > 0 ? C.sage : C.coral, 10.5);
    });
    var offs = KEYS.map(function (k) { return L[k].off; });
    var ons = KEYS.map(function (k) { return L[k].on; });
    function spread(a) { return Math.max.apply(null, a) - Math.min.apply(null, a); }
    txt(svg, X0 - 12, 274, 'spread across the five', C.muted, 10, 'end');
    txt(svg, X0 + 4, 274, 'open ' + spread(offs).toFixed(3), C.steel, 11);
    txt(svg, X0 + 104, 274, '→  with the controller ' + spread(ons).toFixed(3), C.amber, 11);
    svg.appendChild(el('circle', { cx: X0 + 4, cy: 246, r: 5, fill: C.steel }));
    txt(svg, X0 + 16, 250, 'open differential', C.muted, 10);
    svg.appendChild(el('circle', { cx: X0 + 150, cy: 246, r: 5, fill: C.amber }));
    txt(svg, X0 + 162, 250, 'torque vectoring', C.muted, 10);

    document.getElementById('v_cap').innerHTML =
      'Every layout lands in the same narrow band once the controller is on — spread falls from <b>' +
      spread(offs).toFixed(3) + '</b> to <b>' + spread(ons).toFixed(3) + '</b>' +
      (pw === '2x' ? ' at double power, where the passive cars fall apart entirely.' : '.') +
      ' <b>The rear-engined car gains most</b> because it had the most to fix. ' +
      'And the front-driven one <span class="coral">gets marginally worse</span> — its limit is the front tires ' +
      'running out of slip angle, not torque going to the wrong place, and moving torque around cannot help with that.';
  }
  document.querySelectorAll('[data-vpow]').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('[data-vpow]').forEach(function (o) { o.classList.remove('active'); });
      b.classList.add('active'); pw = b.getAttribute('data-vpow'); render();
    });
  });
  render();
})();

})();
