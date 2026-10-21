// QA2 r7 — D-01 평면도 측정 (DEF-QA2-501 · 502 · 503). 이름 · 키 · 숫자만 돌려준다 (본문 없음).
// 쓰는 법: 페이지에서 이 파일 내용을 실행 → await window.qa2r7.frame(390, "dark")
window.qa2r7 = (function () {
  function measure(win) {
    var doc = win.document, T = win.agentdashTwin, svg = doc.getElementById("twin-svg");
    var de = doc.documentElement, names = {};
    (T.last.lines || []).forEach(function (ln) { (ln.machines || []).forEach(function (m) { names[m.key] = m; }); });
    var ctm = svg.getScreenCTM(), sc = ctm ? ctm.a : null, out = [], ell = 0, over = 0;
    doc.querySelectorAll("#twin-svg g.machine").forEach(function (g) {
      var k = g.getAttribute("data-key"), m = names[k]; if (!m) return;
      var w = m.box.w, nm = g.querySelector(".m-name"), len = nm.getComputedTextLength();
      var right = 26 + len, has = nm.textContent.slice(-1) === "…";
      if (has) ell++;
      if (right > w - 26 + 0.5) over++;
      var st = g.querySelector('[data-role="state"]');
      var nr = nm.getBoundingClientRect(), wr = doc.getElementById("twin-svg").getBoundingClientRect();
      out.push({key: k.slice(0, 12), st: m.state, full: m.name.length, shown: nm.textContent.length, ell: has,
                right: Math.round(right * 10) / 10, limit: w - 26, stateText: st ? st.textContent : null,
                inCard: nr.left >= wr.left - 0.5 && nr.right <= wr.right + 0.5});
    });
    var fs = function (sel) { var e = doc.querySelector("#twin-svg " + sel); return e ? parseFloat(win.getComputedStyle(e).fontSize) : null; };
    return {w: win.innerWidth, theme: de.getAttribute("data-theme"), bg: win.getComputedStyle(doc.body).backgroundColor,
            sw: de.scrollWidth, cw: de.clientWidth, grid: T.last.grid, scale: T.scale, ctm: sc && Math.round(sc * 1000) / 1000,
            nameEff: sc && Math.round(fs(".m-name") * sc * 10) / 10, stEff: sc && Math.round(fs(".m-st") * sc * 10) / 10,
            kindEff: sc && Math.round(fs(".m-kind") * sc * 10) / 10,
            card: doc.getElementById("twin-svg").getBoundingClientRect().width, vb: T.vb, machines: out.length,
            ellipsis: ell, nameOverBadge: over, err: (doc.getElementById("twin-err") || {}).textContent || "",
            rows: out};
  }
  function frame(width, theme) {
    try { localStorage.setItem("agentdash-theme", theme); } catch (e) {}
    var f = document.createElement("iframe");
    f.style.cssText = "position:fixed;left:0;top:0;width:" + width + "px;height:844px;border:0;z-index:99999;background:#fff";
    f.src = "/";
    document.body.appendChild(f);
    window.qa2r7.cur = f;
    return new Promise(function (res) {
      var t0 = Date.now();
      (function poll() {
        var w = f.contentWindow, T = w && w.agentdashTwin;
        if (T && T.last && T.scale && w.document.querySelector("#twin-svg g.machine")) setTimeout(function () { res(measure(w)); }, 600);
        else if (Date.now() - t0 > 15000) res({timeout: true});
        else setTimeout(poll, 100);
      })();
    });
  }
  function close() { if (window.qa2r7.cur) { window.qa2r7.cur.remove(); window.qa2r7.cur = null; } }
  return {measure: measure, frame: frame, close: close};
})();
