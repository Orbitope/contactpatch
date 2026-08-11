/* Magic Formula 2002 pure-slip lateral force — a JavaScript port of
   physics/tire.py's MF02Tire.fy0, for the widgets on this page.

   Coefficients are Project Chrono's Sedan_Pac02Tire.tir with the conicity and
   ply-steer offsets zeroed, which is the tire every result in the series runs
   on. This is a THIRD implementation from the same coefficients (numpy and
   CasADi are the other two); KNOWN_ANSWERS below is checked at load so the
   page says so loudly rather than drawing plausible-looking wrong curves. */
(function (global) {
  "use strict";

  var P = {
    PCY1: 1.3507, PDY1: 1.0489, PDY2: -0.18033, PDY3: -2.8821,
    PEY1: -0.0074722, PEY2: -0.0063208, PEY3: -9.9935, PEY4: -760.14,
    PKY1: -21.92, PKY2: 2.0012, PKY3: -0.024778,
    FZ0: 3928.5000000000005
  };

  function dfz(fz) { return (fz - P.FZ0) / P.FZ0; }

  /* Pure-slip lateral force, N. alpha in radians, fz in newtons.
     Negative for positive alpha, matching the project's sign convention.
     Camber is zero throughout the series, so the gamma terms drop out. */
  function fy0(alpha, fz) {
    var d = dfz(fz);
    var Cy = P.PCY1;
    var muy = P.PDY1 + P.PDY2 * d;
    var Dy = muy * fz;
    // Ey is capped at 1 (Pacejka 4.E21); the sign(alpha) asymmetry is active.
    var Ey = Math.min((P.PEY1 + P.PEY2 * d) * (1.0 - P.PEY3 * Math.sign(alpha)), 1.0);
    var Ky = P.PKY1 * P.FZ0 * Math.sin(2.0 * Math.atan(fz / (P.PKY2 * P.FZ0)));
    var By = Ky / (Cy * Dy);
    var x = By * alpha;
    return Dy * Math.sin(Cy * Math.atan(x - Ey * (x - Math.atan(x))));
  }

  /* Peak |Fy| and the slip angle it happens at, by golden-section search over
     0..20 deg. The Python side solves this the same way. */
  function peakLateral(fz) {
    var lo = 0.0, hi = 20 * Math.PI / 180, gr = (Math.sqrt(5) - 1) / 2;
    var a = hi - gr * (hi - lo), b = lo + gr * (hi - lo);
    var fa = -Math.abs(fy0(a, fz)), fb = -Math.abs(fy0(b, fz));
    for (var i = 0; i < 80; i++) {
      if (fa < fb) { hi = b; b = a; fb = fa; a = hi - gr * (hi - lo); fa = -Math.abs(fy0(a, fz)); }
      else { lo = a; a = b; fa = fb; b = lo + gr * (hi - lo); fb = -Math.abs(fy0(b, fz)); }
    }
    var alpha = 0.5 * (lo + hi), force = Math.abs(fy0(alpha, fz));
    return { alphaDeg: alpha * 180 / Math.PI, force: force, mu: force / fz };
  }

  /* Checked against physics/tire.py at load. If this page's port ever drifts
     from the Python the series is written from, fail visibly. */
  var KNOWN = [
    { fz: 3600, alphaDeg: 5.0, fy: -3476.4 },
    { fz: 3600, peakDeg: 10.148, peakN: 3831.2 },
    { fz: 1000, mu: 1.1833 },
    { fz: 9000, mu: 0.8161 }
  ];
  function selfCheck() {
    var ok = true, tol = 2.0;
    var f = fy0(KNOWN[0].alphaDeg * Math.PI / 180, KNOWN[0].fz);
    if (Math.abs(f - KNOWN[0].fy) > tol) ok = false;
    var pk = peakLateral(KNOWN[1].fz);
    if (Math.abs(pk.alphaDeg - KNOWN[1].peakDeg) > 0.02) ok = false;
    if (Math.abs(pk.force - KNOWN[1].peakN) > tol) ok = false;
    if (Math.abs(peakLateral(KNOWN[2].fz).mu - KNOWN[2].mu) > 0.002) ok = false;
    if (Math.abs(peakLateral(KNOWN[3].fz).mu - KNOWN[3].mu) > 0.002) ok = false;
    return ok;
  }

  global.CPTire = { fy0: fy0, peakLateral: peakLateral, ok: selfCheck(), FZ0: P.FZ0 };
})(window);
