"""Stylesheet shared by the app (taken from the approved mock)."""
CSS = r"""
:root { --tf-bg:#f4f5f7; --tf-panel:#ffffff; --tf-line:#e3e5ea; --tf-muted:#6b7280; }
body.body--dark { --tf-bg:#121417; --tf-panel:#1b1e23; --tf-line:#2b3038; --tf-muted:#9aa3ae; }
body { background:var(--tf-bg); }
.tf-layout { display:grid; gap:12px; grid-template-columns:1fr; width:100%; }
.tf-panel { background:var(--tf-panel); border:1px solid var(--tf-line); border-radius:14px;
            display:flex; flex-direction:column; min-width:0; overflow:hidden; }
.tf-scroll { overflow:auto; min-height:0; flex:1; padding:10px; }
.tf-grid { display:grid; gap:10px; grid-template-columns:repeat(auto-fill, minmax(92px, 1fr)); }
.tf-muted { color:var(--tf-muted); }
@media (min-width:1024px) {
  .tf-layout { grid-template-columns:minmax(0,1.1fr) minmax(0,1fr) 360px; height:calc(100dvh - 92px); }
  .tf-mobile-only { display:none !important; }
}
@media (max-width:1023px) {
  .tf-panel.tf-inactive, .tf-detail-panel { display:none !important; }
  .tf-panel { min-height:calc(100dvh - 160px); overflow:visible; }
  .tf-actions { position:sticky; bottom:56px; z-index:2; background:var(--tf-panel);
                border-radius:0 0 14px 14px; box-shadow:0 -6px 12px rgba(0,0,0,.18); }
  .tf-grid { grid-template-columns:repeat(auto-fill, minmax(76px, 1fr)); gap:8px; }
  .tf-desktop-only { display:none !important; }
  .tf-quick { display:none !important; }
}

/* grid tile */
.tf-card { position:relative; border-radius:7px; padding:4px; cursor:pointer; user-select:none;
           box-shadow:0 1px 3px rgba(0,0,0,.25); transition:transform .12s ease, box-shadow .12s ease; }
.tf-card:hover { transform:translateY(-2px); box-shadow:0 6px 14px rgba(0,0,0,.28); }
.tf-card.sel { outline:3px solid #3b82f6; outline-offset:1px; }
.tf-card.picked { outline:3px solid #f59e0b; outline-offset:1px; }
.tf-hit { display:flex; flex-direction:column; gap:3px; }
.tf-effect { background:linear-gradient(160deg,#d9925a,#b4682f); }
.tf-xyz { background:linear-gradient(160deg,#4b4f57,#25282d); }
.tf-xyz .tf-foot, .tf-xyz .tf-name { background:rgba(255,255,255,.92); }
.tf-pendulum { background:linear-gradient(180deg,#d9925a 0%,#d9925a 55%,#35b29c 100%); }
.tf-normal { background:linear-gradient(160deg,#e9cf7a,#c9a640); }
.tf-ritual { background:linear-gradient(160deg,#7aa6e0,#4775b8); }
.tf-token { background:linear-gradient(160deg,#b8bcc4,#8c919a); }
.tf-fusion { background:linear-gradient(160deg,#a477c9,#7a4ea3); }
.tf-synchro { background:linear-gradient(160deg,#f3f3f3,#cfd3d8); }
.tf-spell { background:linear-gradient(160deg,#35b29c,#1d8574); }
.tf-trap { background:linear-gradient(160deg,#cc6aa3,#9c3f77); }
.tf-name { background:rgba(255,255,255,.9); color:#16181c; border-radius:3px; font-size:10px; line-height:12px;
           padding:2px 3px; font-weight:600; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
           overflow:hidden; height:28px; }
.tf-artimg { width:100%; aspect-ratio:1; object-fit:cover; display:block; border-radius:2px;
             border:1px solid rgba(0,0,0,.35); background:#222; }
.tf-foot { font-size:9px; line-height:12px; color:#16181c; background:rgba(255,255,255,.8); border-radius:3px;
           padding:0 3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.tf-badge { position:absolute; font-size:10px; font-weight:700; border-radius:9px; padding:0 6px; line-height:17px; z-index:1; }
.tf-count { top:-7px; right:-7px; background:#2563eb; color:#fff; box-shadow:0 1px 3px rgba(0,0,0,.4); }
.tf-limit { top:36px; left:-5px; background:#dc2626; color:#fff; }
.tf-alt { top:36px; right:-5px; background:#111827; color:#fde68a; }
.tf-check { top:-7px; left:-7px; background:#f59e0b; color:#111; }
.tf-adot { position:absolute; top:36px; left:50%; transform:translateX(-50%); display:none; }
.tf-quick { position:absolute; left:4px; right:4px; bottom:18px; display:none; gap:4px; justify-content:center; z-index:2; }
.tf-card:hover .tf-quick { display:flex; }
.tf-qbtn { flex:1; height:30px; border-radius:6px; border:none; font-size:18px; font-weight:800; cursor:pointer;
           color:#fff; box-shadow:0 2px 6px rgba(0,0,0,.4); }
.tf-qbtn.minus { background:#dc2626; } .tf-qbtn.plus { background:#2563eb; }

/* full card in the detail view */
.tf-real { border-radius:10px; padding:10px; color:#16181c; box-shadow:0 4px 18px rgba(0,0,0,.35); }
.tf-real-name { display:flex; align-items:center; gap:6px; background:rgba(255,255,255,.9); border-radius:4px;
                padding:4px 6px; font-weight:800; font-size:16px; line-height:20px; }
.tf-real-name span:first-child { flex:1; }
.tf-adot2 { width:26px; height:26px; border-radius:50%; color:#fff; font-size:14px; font-weight:800; display:flex;
            align-items:center; justify-content:center; border:2px solid rgba(255,255,255,.8); flex:none; }
.tf-real-stars { text-align:right; color:#c0392b; font-size:15px; letter-spacing:1px; min-height:20px; padding:2px 4px;
                 text-shadow:0 0 2px #fff; }
.tf-real-art { width:86%; margin:2px auto 8px; aspect-ratio:1; display:block; border:2px solid rgba(0,0,0,.45);
               background:#222; image-rendering:auto; }
.tf-real-text { background:rgba(255,255,255,.92); border-radius:4px; padding:6px 8px; font-size:13px; line-height:19px;
                white-space:pre-wrap; max-height:220px; overflow:auto; }
.tf-real-type { font-weight:800; font-size:12px; margin-bottom:2px; }
.tf-real-atk { text-align:right; font-weight:800; font-size:13px; padding:4px 4px 0; }
.tf-big-btn { min-height:46px; font-size:15px !important; }

.tf-section-title { font-weight:700; font-size:13px; display:flex; align-items:center; gap:8px; margin:6px 2px; }
.tf-slot { border-radius:10px; padding:8px 10px; cursor:pointer; border:1px solid transparent; }
.tf-slot:hover { background:rgba(127,127,127,.08); }
.tf-slot.active { border-color:#3b82f6; background:rgba(59,130,246,.10); }
.tf-tab { border-top:3px solid transparent; }
.tf-tab-on { border-top-color:#fbbf24; background:rgba(251,191,36,.12); font-weight:700; }
.tf-pickbar { background:#f59e0b; color:#111; border-radius:12px; margin:6px 8px; padding:6px 8px; }
"""

EXTRA_CSS = r"""
.tf-noart { width:100%; aspect-ratio:1; display:flex; align-items:center; justify-content:center; border-radius:2px;
            font-size:28px; font-weight:800; color:rgba(255,255,255,.95); text-shadow:0 1px 3px rgba(0,0,0,.4); }
.tf-real .tf-noart { width:70%; margin:2px auto 8px; font-size:64px; }
.tf-card.locked { opacity:.45; filter:grayscale(.6); }
.tf-lock { bottom:22px; right:-5px; background:#374151; color:#fff; }
.tf-start { max-width:980px; margin:0 auto; }
.tf-box { background:var(--tf-panel); border:1px solid var(--tf-line); border-radius:14px; padding:16px; }
.tf-dirty { color:#f59e0b; }
.tf-darksynchro { background:linear-gradient(160deg,#3a3f47,#0b0d10); }
.tf-darksynchro .tf-foot, .tf-darksynchro .tf-name { background:rgba(255,255,255,.92); }
.tf-orig { bottom:22px; left:-5px; background:#0f766e; color:#fff; }
.tf-tuner1, .tf-tuner2 { top:56px; right:-5px; color:#fff; }
.tf-tuner1 { background:#15803d; } .tf-tuner2 { background:#4c1d95; }
.tf-fav { top:56px; left:-5px; background:#db2777; color:#fff; }
"""
