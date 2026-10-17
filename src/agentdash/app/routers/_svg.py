"""서버 렌더 SVG 조각 — D-04 일별 추이 · D-05 간트 · 동시 실행 면적. 담당 개발1. 외부 스크립트 없음.

값 · 라벨은 이스케이프해서 넣는다. 색은 CSS 변수(var(--…))로만 — 다크 모드는 _dev1_style.html 이 바꾼다.
"""

from __future__ import annotations

from html import escape


def fmt_int(n: float | int | None) -> str:
    if n is None:
        return "—"
    n = float(n)
    for unit, d in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(n) >= d:
            return f"{n / d:.1f}{unit}"
    return f"{int(n)}"


def bars(points: list[tuple[str, float | None]], *, width: int = 720, height: int = 160, unit: str = "",
         fmt=fmt_int, title: str = "") -> str:
    """단일 계열 막대 (일자 → 값). 막대마다 <title> 툴팁. 값 None 은 빈 칸(0 이 아님)."""
    pad_l, pad_r, pad_t, pad_b = 44, 8, 10, 22
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    vals = [v for _, v in points if v is not None]
    vmax = max(vals) if vals else 0
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}" '
           f'preserveAspectRatio="none" width="100%" height="{height}">']
    out.append(f'<line class="axis" x1="{pad_l}" y1="{pad_t + h}" x2="{pad_l + w}" y2="{pad_t + h}"/>')
    if vmax > 0:
        for frac in (0.5, 1.0):
            y = pad_t + h - h * frac
            out.append(f'<line class="grid" x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + w}" y2="{y:.1f}"/>')
            out.append(f'<text class="tick" x="{pad_l - 4}" y="{y + 4:.1f}" text-anchor="end">{escape(fmt(vmax * frac))}</text>')
    n = len(points)
    if n:
        slot = w / n
        bw = max(1.0, min(28.0, slot - 2))
        for i, (label, v) in enumerate(points):
            x = pad_l + i * slot + (slot - bw) / 2
            if v is not None and vmax > 0:
                bh = max(1.0, h * v / vmax)
                y = pad_t + h - bh
                r = min(4.0, bw / 2, bh)
                out.append(f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="{r:.1f}">'
                           f'<title>{escape(label)} · {escape(fmt(v))}{escape(unit)}</title></rect>')
            if n <= 16 or i in (0, n - 1) or i % max(1, n // 6) == 0:
                out.append(f'<text class="tick" x="{x + bw / 2:.1f}" y="{height - 6}" text-anchor="middle">'
                           f'{escape(label[5:] if len(label) == 10 else label)}</text>')
    else:
        out.append(f'<text class="tick" x="{width / 2}" y="{height / 2}" text-anchor="middle">기간 안 기록 없음</text>')
    out.append("</svg>")
    return "".join(out)


def area(points: list[tuple[float, int]], t0: float, t1: float, *, width: int = 960, height: int = 70,
         left: int = 0, label_fmt=str) -> str:
    """동시 실행 수 면적 (계단). points = [(epoch, n)] 균등 칸."""
    pad_t, pad_b = 6, 14
    h = height - pad_t - pad_b
    w = width - left
    nmax = max((n for _, n in points), default=0)
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="동시 실행 수" '
           f'preserveAspectRatio="none" width="100%" height="{height}">']
    out.append(f'<line class="axis" x1="{left}" y1="{pad_t + h}" x2="{width}" y2="{pad_t + h}"/>')
    if points and nmax > 0 and t1 > t0:
        step = (t1 - t0) / len(points)
        d = [f"M{left},{pad_t + h}"]
        for t, n in points:
            xa = left + (t - t0) / (t1 - t0) * w
            xb = left + (t + step - t0) / (t1 - t0) * w
            y = pad_t + h - h * n / nmax
            d.append(f"L{xa:.1f},{y:.1f} L{xb:.1f},{y:.1f}")
        d.append(f"L{width},{pad_t + h} Z")
        out.append(f'<path class="area" d="{" ".join(d)}"/>')
        for t, n in points:
            xa = left + (t - t0) / (t1 - t0) * w
            xw = max(1.0, step / (t1 - t0) * w)
            out.append(f'<rect class="hit" x="{xa:.1f}" y="{pad_t}" width="{xw:.1f}" height="{h}">'
                       f'<title>{escape(label_fmt(t))} · 동시 {n}</title></rect>')
        out.append(f'<text class="tick" x="{left + 2}" y="{pad_t + 9}">최대 {nmax}</text>')
    else:
        out.append(f'<text class="tick" x="{width / 2}" y="{height / 2}" text-anchor="middle">기간 안 실행 없음</text>')
    out.append("</svg>")
    return "".join(out)
