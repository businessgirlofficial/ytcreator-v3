"""
YTCreator Studio v3 — Pipeline completo YouTube
Flujo: Guión → Audio → Kaggle → Subtítulos → Ensamblar
Estado en sidebar derecho fijo
"""
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import os, json, asyncio, requests, zipfile
from html import escape as _html_escape
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="YTCreator Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

_REFRESH_INTERVALS = {"Off": 0, "15s": 15000, "30s": 30000, "60s": 60000}
if "autorefresh_interval" not in st.session_state:
    st.session_state["autorefresh_interval"] = "Off"

GROQ_KEY    = os.getenv("GROQ_API_KEY", "")
KAGGLE_USER = os.getenv("KAGGLE_USERNAME", "")
KAGGLE_KEY  = os.getenv("KAGGLE_KEY", "")
PIXABAY_KEY = os.getenv("PIXABAY_KEY", "") or os.getenv("PIXABAY_API_KEY", "")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Bebas+Neue&family=JetBrains+Mono:wght@400;500&display=swap');

*,*::before,*::after{box-sizing:border-box}
:root{
  --red:#FF0000;--red-dim:rgba(255,0,0,0.08);--red-mid:rgba(255,0,0,0.18);
  --dark:#0A0A0A;--dark2:#111111;--dark3:#1A1A1A;--dark4:#222222;--dark5:#2A2A2A;
  --border:#252525;--border2:#303030;--border3:#3A3A3A;
  --text:#F2F2F2;--text2:#999;--text3:#5A5A5A;--text4:#3A3A3A;
  --green:#1DB954;--green-dim:rgba(29,185,84,0.08);
  --blue:#3EA6FF;--blue-dim:rgba(62,166,255,0.08);
  --orange:#FF9500;--orange-dim:rgba(255,149,0,0.08);
  --purple:#A855F7;--purple-dim:rgba(168,85,247,0.08);
}

html,body{background:var(--dark)!important}
.stApp{background:var(--dark)!important;font-family:'Inter',sans-serif!important;color:var(--text)!important}
#MainMenu,footer,header{visibility:hidden!important;display:none!important}
.block-container{padding:0!important;max-width:100%!important}

/* ── Sidebar (Estado) ── */
section[data-testid="stSidebar"]{
  background:var(--dark2)!important;
  border-right:1px solid var(--border)!important;
  min-width:260px!important;
  max-width:300px!important;
}
section[data-testid="stSidebar"] .block-container{padding:0!important}
[data-testid="collapsedControl"]{display:none!important}

/* ── Header ── */
.hdr{
  background:var(--dark2);
  border-bottom:1px solid var(--border);
  padding:0 32px;height:56px;
  display:flex;align-items:center;justify-content:space-between;
}
.hdr-brand{display:flex;align-items:center;gap:10px}
.hdr-logo{font-family:'Bebas Neue',sans-serif;font-size:1.4rem;letter-spacing:3px;color:var(--text)}
.hdr-logo em{color:var(--red);font-style:normal}
.hdr-badge{background:var(--red);color:#fff;font-size:.52rem;font-weight:700;
  padding:2px 5px;border-radius:3px;letter-spacing:1px;vertical-align:middle}
.hdr-st{font-size:.7rem;color:var(--text3);display:flex;align-items:center;gap:5px;
  font-family:'JetBrains Mono',monospace}
.dot{width:5px;height:5px;border-radius:50%;display:inline-block;flex-shrink:0}
.on{background:var(--green)}.off{background:var(--red)}

/* ── Pipeline ── */
.pip{
  background:var(--dark2);border-bottom:1px solid var(--border);
  padding:0 32px;display:flex;align-items:center;height:44px;overflow-x:auto;
}
.ps{
  display:flex;align-items:center;gap:7px;padding:0 12px;height:100%;
  font-size:.74rem;font-weight:500;color:var(--text3);
  border-bottom:2px solid transparent;white-space:nowrap;letter-spacing:.2px;
}
.ps.done{color:var(--green);border-bottom-color:var(--green)}
.ps.active{color:var(--text);border-bottom-color:var(--red)}
.psn{
  width:17px;height:17px;border-radius:50%;
  background:var(--dark5);border:1px solid var(--border3);
  display:inline-flex;align-items:center;justify-content:center;
  font-size:.58rem;font-weight:700;font-family:'JetBrains Mono',monospace;flex-shrink:0;
}
.ps.done .psn{background:var(--green-dim);border-color:var(--green);color:var(--green)}
.ps.active .psn{background:var(--red-dim);border-color:var(--red);color:var(--red)}
.pa{color:var(--border3);font-size:.65rem;padding:0 1px}

/* ── Project bar ── */
.pbar-wrap{
  background:var(--dark3);border-bottom:1px solid var(--border);
  padding:8px 32px;display:flex;align-items:flex-end;gap:14px;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"]{
  background:var(--dark2)!important;border-bottom:1px solid var(--border)!important;
  padding:0 32px!important;gap:0!important;
}
.stTabs [data-baseweb="tab"]{
  background:transparent!important;color:var(--text3)!important;
  border:none!important;border-bottom:2px solid transparent!important;
  padding:12px 16px!important;font-size:.8rem!important;font-weight:500!important;
  border-radius:0!important;letter-spacing:.25px!important;
}
.stTabs [aria-selected="true"]{color:var(--text)!important;border-bottom-color:var(--red)!important}
.stTabs [data-baseweb="tab-panel"]{background:var(--dark)!important;padding:28px 32px!important}

/* ── Buttons ── */
.stButton>button{
  background:var(--red)!important;color:#fff!important;border:none!important;
  border-radius:6px!important;font-family:'Inter',sans-serif!important;
  font-weight:600!important;font-size:.82rem!important;padding:9px 20px!important;
  letter-spacing:.25px!important;transition:all .15s!important;width:100%!important;
}
.stButton>button:hover{background:#D90000!important;transform:translateY(-1px)!important;
  box-shadow:0 4px 14px rgba(255,0,0,.22)!important}

/* ── Inputs ── */
.stTextArea textarea,.stTextInput input{
  background:var(--dark3)!important;border:1px solid var(--border2)!important;
  color:var(--text)!important;border-radius:8px!important;
  font-family:'Inter',sans-serif!important;font-size:.84rem!important;
  transition:border-color .2s!important;
}
.stTextArea textarea::placeholder,.stTextInput input::placeholder{
  color:var(--text3)!important;opacity:1!important;
}
.stTextArea textarea:focus,.stTextInput input:focus{
  border-color:var(--red)!important;box-shadow:0 0 0 3px rgba(255,0,0,.07)!important;
}
.stSelectbox>div>div{
  background:var(--dark3)!important;border:1px solid var(--border2)!important;
  color:var(--text)!important;border-radius:8px!important;
}
/* Labels — más legibles */
label{color:var(--text2)!important;font-size:.8rem!important;font-weight:500!important;letter-spacing:.15px!important}
.stSlider label{color:var(--text2)!important;font-size:.8rem!important;font-weight:500!important}
.stSlider>div>div>div{background:var(--red)!important}
.stSlider>div>div>div>div{background:var(--red)!important;border-color:var(--red)!important}
.stSelectSlider>div>div{background:var(--dark3)!important}
.stCheckbox label{color:var(--text2)!important;font-size:.8rem!important}

/* ── Typography ── */
.step-title{
  font-size:1.35rem;font-weight:800;color:var(--text);
  letter-spacing:-.4px;margin-bottom:6px;line-height:1.2;
}
.step-sub{
  font-size:.83rem;color:var(--text3);margin-bottom:28px;
  line-height:1.65;font-weight:400;max-width:600px;
}
.section-label{
  font-size:.7rem;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:1.2px;margin-bottom:12px;
  font-family:'JetBrains Mono',monospace;
}

/* ── Cards ── */
.card{
  background:var(--dark2);border:1px solid var(--border);
  border-radius:12px;padding:20px 22px;transition:border-color .2s;
  margin-bottom:0;
}
.card:hover{border-color:var(--border3)}
.card.primary{border-color:rgba(255,0,0,.2);background:linear-gradient(160deg,rgba(255,0,0,.04) 0%,var(--dark2) 100%)}
.card-title{font-size:.92rem;font-weight:700;color:var(--text);margin-bottom:5px;display:flex;align-items:center;gap:8px}
.card-sub{font-size:.76rem;color:var(--text3);margin-bottom:16px;line-height:1.6}

/* ── Messages ── */
.stSuccess{background:var(--green-dim)!important;border:1px solid rgba(29,185,84,.25)!important;border-radius:8px!important}
.stError{background:var(--red-dim)!important;border:1px solid rgba(255,0,0,.25)!important;border-radius:8px!important}
.stInfo{background:var(--blue-dim)!important;border:1px solid rgba(62,166,255,.25)!important;border-radius:8px!important}
.stWarning{background:var(--orange-dim)!important;border:1px solid rgba(255,149,0,.25)!important;border-radius:8px!important}
.stSuccess p,.stError p,.stInfo p,.stWarning p{color:var(--text)!important;font-size:.83rem!important}

/* ── Metrics ── */
[data-testid="metric-container"]{
  background:var(--dark2)!important;border:1px solid var(--border)!important;
  border-radius:10px!important;padding:14px 16px!important;
}
[data-testid="metric-container"] label{
  color:var(--text3)!important;font-size:.68rem!important;
  text-transform:uppercase!important;letter-spacing:.9px!important;
  font-family:'JetBrains Mono',monospace!important;
}
[data-testid="stMetricValue"]{color:var(--text)!important;font-size:1.4rem!important;font-weight:700!important}

/* ── Progress ── */
.stProgress>div>div{background:var(--red)!important;border-radius:3px!important}
.stProgress>div{background:var(--dark4)!important;border-radius:3px!important;height:4px!important}

/* ── GPU bar ── */
.gpu-w{background:var(--dark3);border:1px solid var(--border);border-radius:9px;padding:12px 14px;margin-bottom:4px}
.gpu-lbl{font-size:.67rem;color:var(--text3);text-transform:uppercase;letter-spacing:.9px;
  font-weight:700;margin-bottom:8px;font-family:'JetBrains Mono',monospace}
.gpu-bg{background:var(--dark5);border-radius:3px;height:4px;overflow:hidden;margin-bottom:7px}
.gpu-f{height:100%;border-radius:3px;transition:width .4s}
.gpu-row{display:flex;justify-content:space-between;font-size:.7rem;color:var(--text3);
  font-family:'JetBrains Mono',monospace}
.gpu-row b{color:var(--text)}

/* ── Sidebar estado ── */
.sb-head{
  background:var(--dark2);border-bottom:1px solid var(--border);
  padding:14px 16px;
}
.sb-title{font-size:.72rem;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:1.2px;font-family:'JetBrains Mono',monospace}
.sb-proj{font-size:.9rem;font-weight:700;color:var(--text);margin-top:4px}

.sstep{
  display:flex;align-items:center;gap:10px;
  padding:10px 14px;border-left:2px solid transparent;
  transition:all .15s;
}
.sstep.done{border-left-color:var(--green)}
.sstep.active{border-left-color:var(--red);background:var(--red-dim)}
.sstep.pending{opacity:.5}
.si-wrap{width:28px;height:28px;border-radius:7px;display:flex;align-items:center;
  justify-content:center;font-size:.9rem;flex-shrink:0;background:var(--dark4)}
.sstep.done .si-wrap{background:var(--green-dim)}
.sstep.active .si-wrap{background:var(--red-dim)}
.sname{font-size:.78rem;font-weight:600;color:var(--text);line-height:1.2}
.sdesc{font-size:.67rem;color:var(--text3);margin-top:1px;font-family:'JetBrains Mono',monospace}
.sbadge{font-size:.6rem;font-weight:700;padding:1px 6px;border-radius:10px;
  margin-left:auto;flex-shrink:0;font-family:'JetBrains Mono',monospace}
.b-ok{background:var(--green-dim);color:var(--green);border:1px solid rgba(29,185,84,.2)}
.b-pend{background:var(--dark5);color:var(--text4);border:1px solid var(--border)}
.b-run{background:var(--orange-dim);color:var(--orange);border:1px solid rgba(255,149,0,.2)}

/* ── Expander ── */
.streamlit-expanderHeader{background:var(--dark3)!important;border:1px solid var(--border)!important;
  border-radius:8px!important;color:var(--text2)!important;font-size:.79rem!important;font-weight:600!important}
.streamlit-expanderContent{background:var(--dark3)!important;border:1px solid var(--border)!important;
  border-top:none!important;border-radius:0 0 8px 8px!important}

/* ── File uploader ── */
[data-testid="stFileUploader"]{background:var(--dark2)!important;
  border:2px dashed var(--border2)!important;border-radius:10px!important}
[data-testid="stFileUploader"]:hover{border-color:var(--red)!important}

/* ── Kaggle monitor ── */
.mon{background:#070B10;border:1px solid #151E2E;border-radius:8px;
  padding:10px 12px;font-family:'JetBrains Mono',monospace;font-size:.7rem;
  color:#5A8AB0;max-height:140px;overflow-y:auto;line-height:1.9}
.lok{color:var(--green)}.lerr{color:var(--red)}.linf{color:var(--blue)}

hr{border-color:var(--border)!important;margin:18px 0!important}

/* ── Monitor Dashboard ── */
.mon-score{
  text-align:center;padding:28px 20px;border-radius:14px;
  border:1px solid var(--border);position:relative;overflow:hidden;
}
.mon-score-num{font-size:3.2rem;font-weight:800;line-height:1;margin-bottom:2px;
  font-family:'Bebas Neue',sans-serif;letter-spacing:2px}
.mon-score-label{font-size:.72rem;color:var(--text3);text-transform:uppercase;
  letter-spacing:1.2px;font-family:'JetBrains Mono',monospace;font-weight:700}
.mon-healthy{background:linear-gradient(160deg,rgba(29,185,84,.08) 0%,var(--dark2) 100%);
  border-color:rgba(29,185,84,.25)}
.mon-healthy .mon-score-num{color:var(--green)}
.mon-degraded{background:linear-gradient(160deg,rgba(255,149,0,.08) 0%,var(--dark2) 100%);
  border-color:rgba(255,149,0,.25)}
.mon-degraded .mon-score-num{color:var(--orange)}
.mon-critical{background:linear-gradient(160deg,rgba(255,0,0,.08) 0%,var(--dark2) 100%);
  border-color:rgba(255,0,0,.25)}
.mon-critical .mon-score-num{color:var(--red)}

.mon-depto{
  background:var(--dark2);border:1px solid var(--border);border-radius:10px;
  padding:14px 16px;transition:border-color .2s;
}
.mon-depto:hover{border-color:var(--border3)}
.mon-depto-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.mon-depto-name{font-size:.82rem;font-weight:700;color:var(--text)}
.mon-depto-badge{font-size:.65rem;font-weight:700;padding:2px 8px;border-radius:10px;
  font-family:'JetBrains Mono',monospace}
.mon-depto-ok .mon-depto-badge{background:var(--green-dim);color:var(--green);border:1px solid rgba(29,185,84,.2)}
.mon-depto-warn .mon-depto-badge{background:var(--orange-dim);color:var(--orange);border:1px solid rgba(255,149,0,.2)}
.mon-depto-down .mon-depto-badge{background:var(--red-dim);color:var(--red);border:1px solid rgba(255,0,0,.2)}
.mon-depto-bar{background:var(--dark5);border-radius:3px;height:4px;overflow:hidden;margin-bottom:8px}
.mon-depto-fill{height:100%;border-radius:3px;transition:width .4s}

.mon-srv{display:flex;align-items:center;gap:8px;padding:4px 0;
  font-size:.73rem;font-family:'JetBrains Mono',monospace}
.mon-srv-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.mon-srv-name{color:var(--text2);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mon-srv-info{color:var(--text3);font-size:.67rem}

.mon-proj{
  background:var(--dark2);border:1px solid var(--border);border-radius:10px;
  padding:14px 16px;margin-bottom:8px;cursor:pointer;transition:all .15s;
}
.mon-proj:hover{border-color:var(--border3);transform:translateX(2px)}
.mon-proj-head{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.mon-proj-id{font-size:.85rem;font-weight:700;color:var(--text)}
.mon-proj-fase{font-size:.62rem;font-weight:700;padding:2px 8px;border-radius:10px;
  font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:.5px}
.mon-proj-bar{display:flex;gap:3px;margin-top:8px}
.mon-proj-seg{flex:1;height:4px;border-radius:2px;background:var(--dark5)}

.mon-agent-row{
  display:flex;align-items:center;gap:10px;padding:8px 12px;
  border-left:2px solid var(--border);margin-left:6px;
  font-size:.78rem;transition:all .15s;
}
.mon-agent-row:hover{background:var(--dark3);border-radius:0 6px 6px 0}
.mon-agent-row.a-ok{border-left-color:var(--green)}
.mon-agent-row.a-err{border-left-color:var(--red)}
.mon-agent-row.a-run{border-left-color:var(--orange)}
.mon-agent-icon{width:22px;height:22px;border-radius:6px;display:flex;align-items:center;
  justify-content:center;font-size:.7rem;flex-shrink:0}
.a-ok .mon-agent-icon{background:var(--green-dim);color:var(--green)}
.a-err .mon-agent-icon{background:var(--red-dim);color:var(--red)}
.a-run .mon-agent-icon{background:var(--orange-dim);color:var(--orange)}
.mon-agent-name{font-weight:600;color:var(--text);flex:1}
.mon-agent-meta{color:var(--text3);font-size:.7rem;font-family:'JetBrains Mono',monospace;
  display:flex;gap:12px}

.mon-log{
  background:#070B10;border:1px solid #151E2E;border-radius:10px;
  padding:14px 16px;font-family:'JetBrains Mono',monospace;font-size:.7rem;
  color:#5A8AB0;max-height:420px;overflow-y:auto;line-height:1.85;
  scrollbar-width:thin;scrollbar-color:#1A2535 #070B10;
}
.mon-log .l-time{color:#3A5068}
.mon-log .l-name{color:var(--blue)}
.mon-log .l-info{color:#5A8AB0}
.mon-log .l-warn{color:var(--orange)}
.mon-log .l-err{color:var(--red)}

/* ── Sidebar Health Widget ── */
.sb-health{padding:12px 14px}
.sb-health-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.sb-health-title{font-size:.68rem;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace}
.sb-health-score{font-size:.72rem;font-weight:800;padding:2px 8px;border-radius:8px;
  font-family:'JetBrains Mono',monospace;letter-spacing:.5px}
.sb-h-ok{background:var(--green-dim);color:var(--green);border:1px solid rgba(29,185,84,.2)}
.sb-h-warn{background:var(--orange-dim);color:var(--orange);border:1px solid rgba(255,149,0,.2)}
.sb-h-crit{background:var(--red-dim);color:var(--red);border:1px solid rgba(255,0,0,.2)}
.sb-h-off{background:var(--dark5);color:var(--text4);border:1px solid var(--border)}

.sb-deptos{display:flex;flex-direction:column;gap:4px}
.sb-depto-row{display:flex;align-items:center;gap:8px;padding:3px 0}
.sb-depto-dots{display:flex;gap:3px;flex-shrink:0}
.sb-depto-dot{width:6px;height:6px;border-radius:50%}
.sb-depto-label{font-size:.7rem;color:var(--text3);flex:1;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.sb-depto-count{font-size:.65rem;color:var(--text3);font-family:'JetBrains Mono',monospace}

.sb-health-bar{background:var(--dark5);border-radius:3px;height:5px;
  overflow:hidden;margin:8px 0 6px}
.sb-health-fill{height:100%;border-radius:3px;transition:width .4s}

.sb-pipeline-ready{display:flex;align-items:center;gap:6px;margin-top:8px;
  font-size:.7rem;font-family:'JetBrains Mono',monospace}

/* ── Header enhanced ── */
.hdr-health{display:flex;align-items:center;gap:12px}
.hdr-health-item{display:flex;align-items:center;gap:5px;font-size:.68rem;
  color:var(--text3);font-family:'JetBrains Mono',monospace}
.hdr-health-num{font-weight:700;color:var(--text2)}

/* ── Timeline / Gantt ── */
.tl-wrap{background:var(--dark2);border:1px solid var(--border);border-radius:12px;
  padding:18px 20px;overflow-x:auto}
.tl-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.tl-title{font-size:.82rem;font-weight:700;color:var(--text)}
.tl-duration{font-size:.72rem;color:var(--text3);font-family:'JetBrains Mono',monospace}

.tl-axis{position:relative;height:18px;margin-bottom:4px;border-bottom:1px solid var(--border)}
.tl-tick{position:absolute;bottom:0;font-size:.58rem;color:var(--text4);
  font-family:'JetBrains Mono',monospace;transform:translateX(-50%);padding-bottom:3px}
.tl-tick::before{content:'';position:absolute;bottom:-1px;left:50%;
  width:1px;height:6px;background:var(--border2)}

.tl-row{display:flex;align-items:center;gap:0;height:30px;position:relative}
.tl-label{width:140px;flex-shrink:0;font-size:.7rem;font-weight:600;
  color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  padding-right:8px;text-align:right;font-family:'JetBrains Mono',monospace}
.tl-track{flex:1;height:20px;position:relative;min-width:0}
.tl-bar{position:absolute;height:16px;top:2px;border-radius:4px;
  display:flex;align-items:center;justify-content:center;
  font-size:.58rem;font-weight:700;color:#fff;
  font-family:'JetBrains Mono',monospace;letter-spacing:.3px;
  min-width:2px;transition:opacity .15s;cursor:default;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:0 4px}
.tl-bar:hover{opacity:.85;z-index:2;box-shadow:0 2px 8px rgba(0,0,0,.4)}

.tl-bar.b-0{background:linear-gradient(90deg,#3EA6FF,#2196F3)}
.tl-bar.b-1{background:linear-gradient(90deg,#A855F7,#7C3AED)}
.tl-bar.b-2{background:linear-gradient(90deg,#FF9500,#F59E0B)}
.tl-bar.b-3{background:linear-gradient(90deg,#1DB954,#16A34A)}
.tl-bar.b-4{background:linear-gradient(90deg,#FF6B9D,#EC4899)}
.tl-bar.b-5{background:linear-gradient(90deg,#6366F1,#4F46E5)}
.tl-bar.b-err{background:linear-gradient(90deg,#FF0000,#DC2626)}

.tl-phase-sep{position:absolute;top:0;bottom:0;width:1px;
  background:var(--border);opacity:.4}

.tl-legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:12px;padding-top:10px;
  border-top:1px solid var(--border)}
.tl-legend-item{display:flex;align-items:center;gap:5px;font-size:.65rem;
  color:var(--text3);font-family:'JetBrains Mono',monospace}
.tl-legend-dot{width:10px;height:10px;border-radius:3px;flex-shrink:0}

/* ── API Reference ── */
.api-group{margin-bottom:14px}
.api-group-title{font-size:.72rem;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:.8px;padding:6px 0 6px;
  font-family:'JetBrains Mono',monospace;border-bottom:1px solid var(--border);
  margin-bottom:6px;display:flex;align-items:center;gap:8px}
.api-row{display:flex;align-items:center;gap:8px;padding:5px 8px;
  border-radius:6px;transition:background .12s;font-family:'JetBrains Mono',monospace}
.api-row:hover{background:var(--dark3)}
.api-method{font-size:.6rem;font-weight:800;padding:2px 6px;border-radius:4px;
  min-width:38px;text-align:center;letter-spacing:.5px;flex-shrink:0}
.api-get{background:rgba(29,185,84,.12);color:var(--green);border:1px solid rgba(29,185,84,.2)}
.api-post{background:rgba(62,166,255,.12);color:var(--blue);border:1px solid rgba(62,166,255,.2)}
.api-delete{background:rgba(255,0,0,.1);color:var(--red);border:1px solid rgba(255,0,0,.2)}
.api-path{font-size:.73rem;color:var(--text);font-weight:500;flex:1;min-width:0;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.api-desc{font-size:.65rem;color:var(--text3);flex-shrink:0;max-width:280px;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.api-auth{font-size:.55rem;color:var(--text4);padding:1px 4px;border-radius:3px;
  border:1px solid var(--border);flex-shrink:0}

/* ── Logs enhanced ── */
.mon-log-stats{display:flex;gap:16px;padding:8px 0}
.mon-log-stat{display:flex;align-items:center;gap:5px;font-size:.72rem;
  font-family:'JetBrains Mono',monospace}
.mon-log-stat-num{font-weight:700}
.mon-log-toolbar{display:flex;align-items:center;gap:6px;flex-wrap:wrap}

/* ── Cola de publicación ── */
.sb-queue{padding:12px 14px}
.sb-queue-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.sb-queue-title{font-size:.68rem;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace}
.sb-queue-buf{font-size:.68rem;font-weight:700;padding:2px 8px;border-radius:8px;
  font-family:'JetBrains Mono',monospace}
.sb-q-ok{background:var(--green-dim);color:var(--green);border:1px solid rgba(29,185,84,.2)}
.sb-q-full{background:var(--orange-dim);color:var(--orange);border:1px solid rgba(255,149,0,.2)}

.sb-q-item{
  display:flex;align-items:center;gap:8px;padding:6px 8px;
  border-radius:6px;margin-bottom:4px;transition:background .15s;
}
.sb-q-item:hover{background:var(--dark4)}
.sb-q-icon{width:20px;height:20px;border-radius:5px;display:flex;align-items:center;
  justify-content:center;font-size:.65rem;flex-shrink:0}
.sb-q-info{flex:1;min-width:0;overflow:hidden}
.sb-q-title{font-size:.73rem;font-weight:600;color:var(--text);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.sb-q-meta{font-size:.62rem;color:var(--text3);font-family:'JetBrains Mono',monospace}
.sb-q-badge{font-size:.58rem;font-weight:700;padding:1px 6px;border-radius:8px;
  font-family:'JetBrains Mono',monospace;flex-shrink:0}

.q-item-ready .sb-q-icon{background:var(--green-dim);color:var(--green)}
.q-item-ready .sb-q-badge{background:var(--green-dim);color:var(--green);border:1px solid rgba(29,185,84,.2)}
.q-item-process .sb-q-icon{background:var(--orange-dim);color:var(--orange)}
.q-item-process .sb-q-badge{background:var(--orange-dim);color:var(--orange);border:1px solid rgba(255,149,0,.2)}
.q-item-pub .sb-q-icon{background:var(--blue-dim);color:var(--blue)}
.q-item-pub .sb-q-badge{background:var(--blue-dim);color:var(--blue);border:1px solid rgba(62,166,255,.2)}
.q-item-err .sb-q-icon{background:var(--red-dim);color:var(--red)}
.q-item-err .sb-q-badge{background:var(--red-dim);color:var(--red);border:1px solid rgba(255,0,0,.2)}

.q-section-label{font-size:.62rem;font-weight:700;color:var(--text4);
  text-transform:uppercase;letter-spacing:.8px;padding:6px 8px 2px;
  font-family:'JetBrains Mono',monospace}

.q-empty{font-size:.7rem;color:var(--text4);padding:4px 8px;font-style:italic}

/* ── Eventos de automatización ── */
.sb-events{padding:12px 14px}
.sb-events-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.sb-events-title{font-size:.68rem;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace}
.sb-events-count{font-size:.65rem;color:var(--text3);font-family:'JetBrains Mono',monospace}

.sb-ev{display:flex;align-items:flex-start;gap:8px;padding:5px 4px;
  border-left:2px solid var(--border);margin-left:2px;transition:all .12s}
.sb-ev:hover{background:var(--dark4);border-radius:0 4px 4px 0}
.sb-ev.ev-success{border-left-color:var(--green)}
.sb-ev.ev-error{border-left-color:var(--red)}
.sb-ev.ev-warning{border-left-color:var(--orange)}

.sb-ev-icon{width:18px;height:18px;border-radius:5px;display:flex;align-items:center;
  justify-content:center;font-size:.6rem;flex-shrink:0;margin-top:1px}
.ev-success .sb-ev-icon{background:var(--green-dim);color:var(--green)}
.ev-error .sb-ev-icon{background:var(--red-dim);color:var(--red)}
.ev-warning .sb-ev-icon{background:var(--orange-dim);color:var(--orange)}

.sb-ev-body{flex:1;min-width:0;overflow:hidden}
.sb-ev-msg{font-size:.7rem;font-weight:600;color:var(--text);line-height:1.3;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sb-ev-time{font-size:.6rem;color:var(--text4);font-family:'JetBrains Mono',monospace;
  margin-top:1px}

.mon-events-table{width:100%;border-collapse:separate;border-spacing:0;font-size:.75rem;
  font-family:'JetBrains Mono',monospace}
.mon-events-table th{text-align:left;padding:8px 10px;color:var(--text3);font-weight:700;
  text-transform:uppercase;letter-spacing:.8px;font-size:.65rem;
  border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--dark2)}
.mon-events-table td{padding:6px 10px;border-bottom:1px solid var(--border);color:var(--text2)}
.mon-events-table tr:hover td{background:var(--dark3)}
.mon-ev-type{padding:2px 6px;border-radius:4px;font-size:.65rem;font-weight:700}
.met-pipeline{background:var(--blue-dim);color:var(--blue);border:1px solid rgba(62,166,255,.2)}
.met-agent{background:var(--purple-dim);color:var(--purple);border:1px solid rgba(168,85,247,.2)}
.met-system{background:var(--orange-dim);color:var(--orange);border:1px solid rgba(255,149,0,.2)}
.mon-ev-status{padding:1px 6px;border-radius:8px;font-size:.62rem;font-weight:700}
.mes-success{background:var(--green-dim);color:var(--green);border:1px solid rgba(29,185,84,.2)}
.mes-error{background:var(--red-dim);color:var(--red);border:1px solid rgba(255,0,0,.2)}

/* ── Scheduler ── */
.sb-sched{padding:12px 14px}
.sb-sched-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.sb-sched-title{font-size:.68rem;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace}
.sb-sched-count{font-size:.65rem;color:var(--text3);font-family:'JetBrains Mono',monospace}
.sb-sched-next{display:flex;align-items:center;gap:6px;margin-bottom:10px;
  padding:6px 8px;background:var(--dark3);border-radius:6px;border:1px solid var(--border)}
.sb-sched-next-icon{font-size:.85rem}
.sb-sched-next-info{flex:1}
.sb-sched-next-label{font-size:.68rem;color:var(--text3);font-family:'JetBrains Mono',monospace}
.sb-sched-next-time{font-size:.78rem;font-weight:700;color:var(--text)}

.sb-task{display:flex;align-items:center;gap:8px;padding:5px 4px;
  border-radius:4px;transition:background .12s}
.sb-task:hover{background:var(--dark4)}
.sb-task-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.sb-task-info{flex:1;min-width:0;overflow:hidden}
.sb-task-name{font-size:.7rem;font-weight:600;color:var(--text);white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.sb-task-meta{font-size:.6rem;color:var(--text4);font-family:'JetBrains Mono',monospace}

.mon-sched-card{background:var(--dark2);border:1px solid var(--border);border-radius:10px;
  padding:16px 18px;transition:border-color .2s}
.mon-sched-card:hover{border-color:var(--border3)}
.mon-sched-card-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.mon-sched-card-name{font-size:.85rem;font-weight:700;color:var(--text);display:flex;align-items:center;gap:8px}
.mon-sched-card-cron{font-size:.68rem;color:var(--text3);font-family:'JetBrains Mono',monospace;
  padding:2px 6px;background:var(--dark4);border-radius:4px}
.mon-sched-card-desc{font-size:.75rem;color:var(--text3);margin-bottom:10px;line-height:1.5}
.mon-sched-card-meta{display:flex;gap:16px;flex-wrap:wrap}
.mon-sched-meta-item{font-size:.7rem;color:var(--text3);font-family:'JetBrains Mono',monospace;
  display:flex;align-items:center;gap:4px}
.mon-sched-meta-item strong{color:var(--text2)}

/* ── Pausa global ── */
.pause-banner{
  background:linear-gradient(135deg,rgba(255,149,0,.12) 0%,rgba(255,0,0,.08) 100%);
  border:1px solid rgba(255,149,0,.3);border-radius:8px;
  padding:10px 12px;margin-bottom:8px;
  display:flex;align-items:center;gap:8px;
}
.pause-banner-icon{font-size:1.1rem}
.pause-banner-text{flex:1}
.pause-banner-title{font-size:.75rem;font-weight:700;color:var(--orange)}
.pause-banner-sub{font-size:.65rem;color:var(--text3);font-family:'JetBrains Mono',monospace;margin-top:1px}

.mon-pause-card{
  background:var(--dark2);border-radius:12px;padding:20px 24px;
  border:2px solid var(--border);transition:border-color .2s;
}
.mon-pause-active{border-color:rgba(255,149,0,.4);
  background:linear-gradient(160deg,rgba(255,149,0,.06) 0%,var(--dark2) 100%)}
.mon-pause-inactive{border-color:rgba(29,185,84,.3);
  background:linear-gradient(160deg,rgba(29,185,84,.04) 0%,var(--dark2) 100%)}

/* ── Keywords table ── */
.kw-table{width:100%;border-collapse:separate;border-spacing:0;font-size:.75rem;
  font-family:'JetBrains Mono',monospace}
.kw-table th{text-align:left;padding:8px 10px;color:var(--text3);font-weight:700;
  text-transform:uppercase;letter-spacing:.8px;font-size:.65rem;
  border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--dark2)}
.kw-table td{padding:6px 10px;border-bottom:1px solid var(--border);color:var(--text2)}
.kw-table tr:hover td{background:var(--dark3)}
.kw-tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.7rem;
  font-weight:600;background:var(--blue-dim);color:var(--blue);
  border:1px solid rgba(62,166,255,.2);max-width:180px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.kw-bar{height:4px;border-radius:2px;background:var(--dark5);overflow:hidden;min-width:40px}
.kw-bar-fill{height:100%;border-radius:2px;transition:width .3s}

/* ── Home: Channel Cards ── */
.home-title{font-size:1.6rem;font-weight:800;color:var(--text);letter-spacing:-.5px;margin-bottom:4px}
.home-sub{font-size:.85rem;color:var(--text3);margin-bottom:28px}
.ch-card{
  background:var(--dark2);border:1px solid var(--border);border-radius:14px;
  padding:22px;text-align:center;transition:all .2s;cursor:pointer;min-height:220px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;
}
.ch-card:hover{border-color:var(--red);transform:translateY(-2px);box-shadow:0 8px 24px rgba(255,0,0,.08)}
.ch-card-thumb{width:72px;height:72px;border-radius:50%;object-fit:cover;border:2px solid var(--border2);margin-bottom:4px}
.ch-card-thumb-placeholder{width:72px;height:72px;border-radius:50%;background:var(--red-dim);
  border:2px solid var(--border2);display:flex;align-items:center;justify-content:center;
  font-size:1.8rem;font-weight:800;color:var(--red);margin-bottom:4px}
.ch-card-name{font-size:.95rem;font-weight:700;color:var(--text);line-height:1.2}
.ch-card-stats{font-size:.75rem;color:var(--text3);font-family:'JetBrains Mono',monospace}
.ch-card-niche{font-size:.7rem;color:var(--blue);background:var(--blue-dim);
  padding:2px 10px;border-radius:10px;border:1px solid rgba(62,166,255,.15)}
.ch-card-add{
  background:var(--dark3);border:2px dashed var(--border2);border-radius:14px;
  padding:22px;text-align:center;transition:all .2s;cursor:pointer;min-height:220px;
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;
}
.ch-card-add:hover{border-color:var(--red);background:var(--red-dim)}
.ch-card-add-icon{font-size:2.5rem;color:var(--text3);line-height:1}
.ch-card-add-text{font-size:.85rem;color:var(--text3);font-weight:600}

/* ── Breadcrumb ── */
.breadcrumb{
  background:var(--dark2);border-bottom:1px solid var(--border);
  padding:8px 32px;display:flex;align-items:center;gap:8px;
  font-size:.78rem;color:var(--text3);font-family:'JetBrains Mono',monospace;
}
.breadcrumb a,.breadcrumb .bc-link{color:var(--text3);text-decoration:none;cursor:pointer}
.breadcrumb a:hover,.breadcrumb .bc-link:hover{color:var(--text)}
.breadcrumb .bc-sep{color:var(--border3)}
.breadcrumb .bc-current{color:var(--text);font-weight:600}

/* ── Cronograma ── */
.cron-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.cron-title{font-size:1.1rem;font-weight:800;color:var(--text);display:flex;align-items:center;gap:8px}
.cron-meta{font-size:.72rem;color:var(--text3);font-family:'JetBrains Mono',monospace}
.cron-progress-wrap{margin-bottom:20px}
.cron-progress-info{display:flex;justify-content:space-between;font-size:.72rem;
  color:var(--text3);margin-bottom:6px;font-family:'JetBrains Mono',monospace}
.cron-progress-bar{background:var(--dark5);border-radius:4px;height:8px;overflow:hidden}
.cron-progress-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,var(--red),#FF4444);transition:width .4s}

.cron-week-label{font-size:.68rem;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:1px;padding:10px 0 6px;
  font-family:'JetBrains Mono',monospace;border-bottom:1px solid var(--border);margin-bottom:8px}

.cron-entry{
  background:var(--dark2);border:1px solid var(--border);border-radius:10px;
  padding:12px 14px;margin-bottom:6px;transition:all .15s;
  border-left:3px solid var(--border);
}
.cron-entry:hover{border-color:var(--border3);transform:translateX(2px)}
.cron-entry.t-trending{border-left-color:#FF0000}
.cron-entry.t-brecha{border-left-color:#3EA6FF}
.cron-entry.t-evergreen{border-left-color:#1DB954}
.cron-entry.t-follow_up{border-left-color:#FF9500}
.cron-entry.t-serie{border-left-color:#A855F7}
.cron-entry.t-viral_reaccion{border-left-color:#FF6B9D}

.cron-entry-head{display:flex;align-items:center;gap:8px;margin-bottom:4px}
.cron-entry-date{font-size:.68rem;font-weight:700;color:var(--text3);
  font-family:'JetBrains Mono',monospace;min-width:90px}
.cron-entry-title{font-size:.84rem;font-weight:700;color:var(--text);flex:1;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cron-entry-score{font-size:.7rem;font-weight:800;color:var(--orange);
  font-family:'JetBrains Mono',monospace}

.cron-entry-detail{display:flex;gap:12px;flex-wrap:wrap;margin-top:4px}
.cron-tag{font-size:.62rem;font-weight:700;padding:2px 7px;border-radius:8px;
  font-family:'JetBrains Mono',monospace;letter-spacing:.3px}
.ct-trending{background:var(--red-dim);color:var(--red);border:1px solid rgba(255,0,0,.2)}
.ct-brecha{background:var(--blue-dim);color:var(--blue);border:1px solid rgba(62,166,255,.2)}
.ct-evergreen{background:var(--green-dim);color:var(--green);border:1px solid rgba(29,185,84,.2)}
.ct-follow_up{background:var(--orange-dim);color:var(--orange);border:1px solid rgba(255,149,0,.2)}
.ct-serie{background:var(--purple-dim);color:var(--purple);border:1px solid rgba(168,85,247,.2)}
.ct-viral_reaccion{background:rgba(255,107,157,.08);color:#FF6B9D;border:1px solid rgba(255,107,157,.2)}

.cron-status{font-size:.6rem;font-weight:700;padding:2px 7px;border-radius:8px;
  font-family:'JetBrains Mono',monospace}
.cs-pendiente{background:var(--dark5);color:var(--text4);border:1px solid var(--border)}
.cs-en_revision{background:var(--orange-dim);color:var(--orange);border:1px solid rgba(255,149,0,.2)}
.cs-aprobado{background:var(--blue-dim);color:var(--blue);border:1px solid rgba(62,166,255,.2)}
.cs-en_produccion{background:var(--orange-dim);color:var(--orange);border:1px solid rgba(255,149,0,.2)}
.cs-publicado{background:var(--green-dim);color:var(--green);border:1px solid rgba(29,185,84,.2)}
.cs-pospuesto{background:var(--purple-dim);color:var(--purple);border:1px solid rgba(168,85,247,.2)}
.cs-cancelado{background:var(--red-dim);color:var(--text4);border:1px solid rgba(255,0,0,.15)}

.cron-legend{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0 8px;
  padding:8px 0;border-top:1px solid var(--border)}
.cron-legend-item{display:flex;align-items:center;gap:4px;font-size:.62rem;
  color:var(--text3);font-family:'JetBrains Mono',monospace}
.cron-legend-dot{width:8px;height:8px;border-radius:2px;flex-shrink:0}
.cld-trending{background:#FF0000}.cld-brecha{background:#3EA6FF}
.cld-evergreen{background:#1DB954}.cld-follow_up{background:#FF9500}
.cld-serie{background:#A855F7}.cld-viral_reaccion{background:#FF6B9D}

.cron-comp-tl{background:var(--dark2);border:1px solid var(--border);border-radius:10px;
  padding:14px 16px;margin-top:12px}
.cron-comp-title{font-size:.72rem;font-weight:700;color:var(--text3);
  text-transform:uppercase;letter-spacing:1px;font-family:'JetBrains Mono',monospace;
  margin-bottom:10px}
.cron-comp-row{display:flex;align-items:center;gap:8px;padding:4px 0;
  font-size:.72rem;font-family:'JetBrains Mono',monospace}
.cron-comp-name{color:var(--text2);min-width:120px;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.cron-comp-dots{display:flex;gap:2px;flex:1}
.cron-comp-dot{width:14px;height:14px;border-radius:3px;display:flex;
  align-items:center;justify-content:center;font-size:.5rem;font-weight:700}
.ccd-empty{background:var(--dark4);color:transparent}
.ccd-pub{background:var(--red-dim);color:var(--red);border:1px solid rgba(255,0,0,.2)}
.ccd-us{background:var(--green-dim);color:var(--green);border:1px solid rgba(29,185,84,.2)}

.cron-empty{
  text-align:center;padding:40px 20px;
  background:var(--dark2);border:2px dashed var(--border2);border-radius:14px;
}
.cron-empty-icon{font-size:2.5rem;margin-bottom:8px}
.cron-empty-title{font-size:1rem;font-weight:700;color:var(--text);margin-bottom:4px}
.cron-empty-sub{font-size:.8rem;color:var(--text3);margin-bottom:16px}

/* ── Skeleton loading ── */
@keyframes sk-shimmer{0%{background-position:-400px 0}100%{background-position:400px 0}}
.sk{background:linear-gradient(90deg,var(--dark4) 25%,var(--dark5) 50%,var(--dark4) 75%);
  background-size:800px 100%;animation:sk-shimmer 1.6s ease-in-out infinite;border-radius:4px}
.sk-line{height:9px;margin-bottom:7px}
.sk-line.lg{height:13px;margin-bottom:9px}
.sk-line.sm{height:7px;margin-bottom:5px}
.sk-circle{border-radius:50%}
.sk-row{display:flex;align-items:center;gap:8px;padding:4px 0}
.sk-bar{height:5px;border-radius:3px;margin:10px 0 8px}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────
for k,v in {
    'guion_aprobado':None,'audio_generado':False,'musica_lista':False,
    'subs_generados':False,'kaggle_completado':False,'video_final':None,
    'guion_generado':None,'kaggle_running':False,'kaggle_logs':[],
    'horas_usadas':0.0,'nombre_proyecto':'mi_video_ep01',
    'nicho':'','idioma_canal':'Español','nicho_analizado':False,
    'analisis_nicho':None,'titulos_generados':None,'titulo_elegido':'',
    'titulo_framework':'','titulo_trigger':'','tema_video':'',
    'guion_texto_completo':None,
    'vista_actual':'home',
    'canal_activo_id':None,
    'canal_activo_nombre':None,
}.items():
    if k not in st.session_state: st.session_state[k]=v
s=st.session_state


_KEYS_WORKFLOW_POR_CANAL = [
    'nicho', 'nicho_analizado', 'analisis_nicho',
    'titulos_generados', 'titulo_elegido', 'titulo_framework', 'titulo_trigger',
    'tema_video', 'guion_texto_completo', 'guion_aprobado',
    'audio_generado', 'musica_lista', 'subs_generados', 'kaggle_completado',
    'video_final', 'kaggle_running', 'kaggle_logs',
    '_canal_data_cache',
]


def _navegar_a(vista, canal_id=None, canal_nombre=None):
    # Se compara contra '_canal_workflow_actual' (no contra 'canal_activo_id')
    # porque ir a Home pone canal_activo_id en None, y eso causaría un reset
    # falso al volver al MISMO canal desde Home.
    if canal_id is not None and canal_id != s.get('_canal_workflow_actual'):
        for k in _KEYS_WORKFLOW_POR_CANAL:
            if k in ('kaggle_logs',):
                s[k] = []
            elif k in ('audio_generado', 'musica_lista', 'subs_generados', 'kaggle_completado', 'kaggle_running', 'nicho_analizado'):
                s[k] = False
            elif k in ('nicho', 'titulo_elegido', 'titulo_framework', 'titulo_trigger', 'tema_video'):
                s[k] = ''
            else:
                s[k] = None
        s['_canal_workflow_actual'] = canal_id
    s['vista_actual'] = vista
    s['_health_check_pendiente'] = True
    if canal_id is not None:
        s['canal_activo_id'] = canal_id
        s['canal_activo_nombre'] = canal_nombre
        s['canal_seleccionado'] = canal_id
        s['canal_id_pipeline'] = canal_id
    if vista == 'home':
        s['canal_activo_id'] = None
        s['canal_activo_nombre'] = None


def _obtener_canal_data(canal_id, forzar=False):
    """estado_canal() cacheado en session_state por canal_id, para no
    repetir la misma llamada al pasar de Channel Dashboard a Workspace."""
    cache = s.get('_canal_data_cache')
    if not forzar and cache and cache.get('canal_id') == canal_id:
        return cache.get('data')
    import api_client as _ac
    data = _ac.estado_canal(canal_id)
    s['_canal_data_cache'] = {'canal_id': canal_id, 'data': data}
    return data


@st.cache_data(ttl=30)
def _cached_health_servicios():
    """Health de servicios cacheado 30s para no ralentizar cada rerun."""
    try:
        import api_client as _hc
        if not _hc.health():
            return None
        return _hc.health_servicios()
    except Exception:
        return None


@st.cache_data(ttl=30)
def _cached_pipeline_cola():
    """Cola de publicación cacheada 30s."""
    try:
        import api_client as _hc
        if not _hc.health():
            return None
        return _hc.pipeline_cola()
    except Exception:
        return None


@st.cache_data(ttl=30)
def _cached_eventos_recientes():
    """Últimos eventos de automatización cacheados 30s."""
    try:
        import api_client as _hc
        if not _hc.health():
            return None
        return _hc.listar_eventos(limit=15)
    except Exception:
        return None


@st.cache_data(ttl=30)
def _cached_scheduler():
    """Resumen del scheduler cacheado 30s."""
    try:
        import api_client as _hc
        if not _hc.health():
            return None
        return _hc.scheduler_resumen()
    except Exception:
        return None


@st.cache_data(ttl=10)
def _cached_pausa():
    """Estado de pausa cacheado 10s (TTL corto porque es critico)."""
    try:
        import api_client as _hc
        if not _hc.health():
            return None
        return _hc.scheduler_pausa()
    except Exception:
        return None


@st.cache_data(ttl=60)
def _cached_keywords_top():
    """Top keywords cacheado 60s."""
    try:
        import api_client as _hc
        if not _hc.health():
            return None
        return _hc.keywords_top(limit=30)
    except Exception:
        return None


@st.cache_data(ttl=60)
def _cached_keywords_stats():
    """Stats de keywords cacheado 60s."""
    try:
        import api_client as _hc
        if not _hc.health():
            return None
        return _hc.keywords_stats()
    except Exception:
        return None


@st.fragment(run_every="30s")
def _sidebar_api_section():
    """Sección API del sidebar: health, cola, eventos y scheduler.
    Se actualiza cada 30 s de forma independiente sin bloquear el contenido principal."""
    # ── Health de servicios ──
    st.divider()
    _sb_health = _cached_health_servicios()

    if _sb_health is None:
        st.markdown("""
        <div class="sb-health">
          <div class="sb-health-head">
            <span class="sb-health-title">📡 Servicios</span>
            <span class="sk sk-line lg" style="width:42px;margin:0;display:inline-block"></span>
          </div>
          <div class="sk sk-bar"></div>
          <div style="display:flex;justify-content:space-between;margin-bottom:10px">
            <span class="sk sk-line sm" style="width:60px;margin:0"></span>
            <span class="sk sk-line sm" style="width:40px;margin:0"></span>
          </div>
          <div class="sb-deptos" style="gap:6px">
            <div class="sk-row"><div class="sk" style="width:52px;height:6px;border-radius:10px"></div><span class="sk sk-line sm" style="flex:1;margin:0"></span><span class="sk" style="width:22px;height:7px;border-radius:3px"></span></div>
            <div class="sk-row"><div class="sk" style="width:52px;height:6px;border-radius:10px"></div><span class="sk sk-line sm" style="flex:1;margin:0"></span><span class="sk" style="width:22px;height:7px;border-radius:3px"></span></div>
            <div class="sk-row"><div class="sk" style="width:52px;height:6px;border-radius:10px"></div><span class="sk sk-line sm" style="flex:1;margin:0"></span><span class="sk" style="width:22px;height:7px;border-radius:3px"></span></div>
            <div class="sk-row"><div class="sk" style="width:52px;height:6px;border-radius:10px"></div><span class="sk sk-line sm" style="flex:1;margin:0"></span><span class="sk" style="width:22px;height:7px;border-radius:3px"></span></div>
          </div>
          <div class="sk-row" style="margin-top:8px">
            <span class="sk sk-circle" style="width:7px;height:7px;flex-shrink:0"></span>
            <span class="sk sk-line sm" style="width:90px;margin:0"></span>
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        _sb_score = _sb_health.get("score", 0)
        _sb_nivel = _sb_health.get("nivel", "critico")
        _sb_vivos = _sb_health.get("vivos", 0)
        _sb_total = _sb_health.get("total", 0)
        _sb_puede = _sb_health.get("puede_pipeline", False)
        _sb_mem = _sb_health.get("memoria_total_mb")
        _sb_criticos = _sb_health.get("criticos_caidos", [])
        _sb_desglose = _sb_health.get("desglose_departamentos", {})
        _sb_servicios = _sb_health.get("servicios", {})

        _sb_score_cls = "sb-h-ok" if _sb_nivel == "saludable" else ("sb-h-warn" if _sb_nivel == "degradado" else "sb-h-crit")
        _sb_bar_color = "var(--green)" if _sb_nivel == "saludable" else ("var(--orange)" if _sb_nivel == "degradado" else "var(--red)")
        _sb_bar_pct = min(_sb_score, 100)

        _SB_DEPTOS = [
            ("depto_0_inteligencia", "Intel"),
            ("depto_1_estrategia", "Estrat"),
            ("depto_2_guion", "Guión"),
            ("depto_3_visual", "Visual"),
            ("depto_4_audio", "Audio"),
            ("depto_5_cierre", "Cierre"),
            ("orquestador", "Orq"),
        ]

        _SB_DEPTO_AGENTS = {
            "depto_0_inteligencia": ["0.1_escaner_canal", "0.2_analizador_canal", "0.3_monitor_mercado", "0.4_asesor_estrategico", "0.5_tracker_performance", "sub_orq_inteligencia"],
            "depto_1_estrategia": ["1.1_investigador", "1.2_copywriter", "1.3_director_arte", "1.4_generador_miniatura", "sub_orq_estrategia"],
            "depto_2_guion": ["2.1_guionista", "sub_orq_guion"],
            "depto_3_visual": ["3.1_prompt_maker", "3.2_generador_visual", "sub_orq_visual"],
            "depto_4_audio": ["4.1_locucion", "4.2_musica", "4.3_subtitulos", "sub_orq_audio"],
            "depto_5_cierre": ["5.1_editor", "5.2_seo", "5.3_compliance", "5.4_policy_monitor", "5.5_publicador", "sub_orq_cierre"],
            "orquestador": ["orquestador_central"],
        }

        _sb_deptos_html = ""
        for _sbdk, _sbdl in _SB_DEPTOS:
            _sbd_info = _sb_desglose.get(_sbdk, {"vivos": 0, "total": 0})
            _sbd_v = _sbd_info["vivos"]
            _sbd_t = _sbd_info["total"]

            _dots_html = ""
            for _sba in _SB_DEPTO_AGENTS.get(_sbdk, []):
                _sba_st = _sb_servicios.get(_sba, {}).get("estado", "caido")
                _sba_c = "#1DB954" if _sba_st == "ok" else ("#FF9500" if _sba_st == "error" else "#FF0000")
                _dots_html += f'<span class="sb-depto-dot" style="background:{_sba_c}" title="{_html_escape(_sba)}"></span>'

            _sb_deptos_html += (
                f'<div class="sb-depto-row">'
                f'<div class="sb-depto-dots">{_dots_html}</div>'
                f'<span class="sb-depto-label">{_sbdl}</span>'
                f'<span class="sb-depto-count">{_sbd_v}/{_sbd_t}</span>'
                f'</div>'
            )

        _sb_pipe_icon = '<span class="dot on"></span>' if _sb_puede else '<span class="dot off"></span>'
        _sb_pipe_text = "Pipeline listo" if _sb_puede else "Pipeline bloqueado"
        _sb_pipe_color = "var(--green)" if _sb_puede else "var(--red)"

        _sb_crit_html = ""
        if _sb_criticos:
            _sb_crit_names = ", ".join(_html_escape(c) for c in _sb_criticos[:3])
            _sb_crit_extra = f" +{len(_sb_criticos)-3}" if len(_sb_criticos) > 3 else ""
            _sb_crit_html = (
                f'<div style="font-size:.65rem;color:var(--red);margin-top:6px;'
                f'font-family:\'JetBrains Mono\',monospace">'
                f'⚠ {_sb_crit_names}{_sb_crit_extra}</div>'
            )

        _sb_mem_html = f'<span style="font-size:.65rem;color:var(--text3);font-family:\'JetBrains Mono\',monospace">{_sb_mem} MB</span>' if _sb_mem else ""

        st.markdown(f"""
        <div class="sb-health">
          <div class="sb-health-head">
            <span class="sb-health-title">📡 Servicios</span>
            <span class="sb-health-score {_sb_score_cls}">{_sb_score}%</span>
          </div>
          <div class="sb-health-bar">
            <div class="sb-health-fill" style="width:{_sb_bar_pct}%;background:{_sb_bar_color}"></div>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="font-size:.68rem;color:var(--text3);font-family:'JetBrains Mono',monospace">{_sb_vivos}/{_sb_total} vivos</span>
            {_sb_mem_html}
          </div>
          <div class="sb-deptos">
            {_sb_deptos_html}
          </div>
          <div class="sb-pipeline-ready">
            {_sb_pipe_icon}
            <span style="color:{_sb_pipe_color}">{_sb_pipe_text}</span>
          </div>
          {_sb_crit_html}
        </div>""", unsafe_allow_html=True)

    if _sb_health is not None:
        _col_ref, _col_ar = st.columns([1, 1])
        with _col_ref:
            if st.button("🔄  Refrescar", key="sb_refresh_health", use_container_width=True):
                _cached_health_servicios.clear()
                _cached_pipeline_cola.clear()
                _cached_eventos_recientes.clear()
                _cached_scheduler.clear()
                _cached_pausa.clear()
                # La interacción del botón ya dispara el rerun del fragment automáticamente
        with _col_ar:
            _ar_sel = st.selectbox(
                "Auto-refresh",
                options=list(_REFRESH_INTERVALS.keys()),
                index=list(_REFRESH_INTERVALS.keys()).index(st.session_state["autorefresh_interval"]),
                key="sb_autorefresh_sel",
                label_visibility="collapsed",
            )
            if _ar_sel != st.session_state["autorefresh_interval"]:
                st.session_state["autorefresh_interval"] = _ar_sel
                # El cambio del selectbox dispara el rerun del fragment automáticamente

    # ── Cola de publicación ──
    st.divider()
    _sb_cola = _cached_pipeline_cola()

    if _sb_cola is None:
        st.markdown("""
        <div class="sb-queue">
          <div class="sb-queue-head">
            <span class="sb-queue-title">📋 Cola</span>
            <span class="sk sk-line sm" style="width:32px;margin:0;display:inline-block"></span>
          </div>
          <div class="sb-q-item" style="opacity:.7">
            <div class="sk sk-circle" style="width:20px;height:20px;flex-shrink:0"></div>
            <div class="sb-q-info">
              <div class="sk sk-line" style="width:80%;margin-bottom:4px"></div>
              <div class="sk sk-line sm" style="width:50%;margin:0"></div>
            </div>
            <span class="sk" style="width:28px;height:16px;border-radius:8px"></span>
          </div>
          <div class="sb-q-item" style="opacity:.5">
            <div class="sk sk-circle" style="width:20px;height:20px;flex-shrink:0"></div>
            <div class="sb-q-info">
              <div class="sk sk-line" style="width:65%;margin-bottom:4px"></div>
              <div class="sk sk-line sm" style="width:40%;margin:0"></div>
            </div>
            <span class="sk" style="width:28px;height:16px;border-radius:8px"></span>
          </div>
          <div class="sb-q-item" style="opacity:.3">
            <div class="sk sk-circle" style="width:20px;height:20px;flex-shrink:0"></div>
            <div class="sb-q-info">
              <div class="sk sk-line" style="width:72%;margin-bottom:4px"></div>
              <div class="sk sk-line sm" style="width:45%;margin:0"></div>
            </div>
            <span class="sk" style="width:28px;height:16px;border-radius:8px"></span>
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        _sq_buf = _sb_cola.get("buffer", {})
        _sq_buf_actual = _sq_buf.get("actual", 0)
        _sq_buf_max = _sq_buf.get("max", 3)
        _sq_en_proc = _sb_cola.get("en_proceso", [])
        _sq_listos = _sb_cola.get("listos_para_publicar", [])
        _sq_pubs = _sb_cola.get("publicados", [])
        _sq_errs = _sb_cola.get("con_error", [])

        _sq_buf_cls = "sb-q-full" if _sq_buf_actual >= _sq_buf_max else "sb-q-ok"

        _sq_items_html = ""

        if _sq_en_proc:
            _sq_items_html += '<div class="q-section-label">▶ En proceso</div>'
            for _sqp in _sq_en_proc[:3]:
                _sqp_titulo = _html_escape(_sqp.get("titulo", _sqp.get("proyecto_id", "?")))
                if len(_sqp_titulo) > 28:
                    _sqp_titulo = _sqp_titulo[:28] + "…"
                _sqp_fase = _sqp.get("fase_actual", "?")
                _sqp_pct = _sqp.get("progreso_pct", 0)
                _sq_items_html += (
                    f'<div class="sb-q-item q-item-process">'
                    f'<div class="sb-q-icon">⏳</div>'
                    f'<div class="sb-q-info">'
                    f'<div class="sb-q-title">{_sqp_titulo}</div>'
                    f'<div class="sb-q-meta">{_sqp_fase} · {_sqp_pct}%</div>'
                    f'</div>'
                    f'<span class="sb-q-badge">{_sqp_pct}%</span>'
                    f'</div>'
                )

        if _sq_listos:
            _sq_items_html += '<div class="q-section-label">✓ Listos para publicar</div>'
            for _sql in _sq_listos:
                _sql_titulo = _html_escape(_sql.get("titulo", _sql.get("proyecto_id", "?")))
                if len(_sql_titulo) > 28:
                    _sql_titulo = _sql_titulo[:28] + "…"
                _sql_canal = _html_escape(_sql.get("canal", ""))
                _sq_items_html += (
                    f'<div class="sb-q-item q-item-ready">'
                    f'<div class="sb-q-icon">✓</div>'
                    f'<div class="sb-q-info">'
                    f'<div class="sb-q-title">{_sql_titulo}</div>'
                    f'<div class="sb-q-meta">{_sql_canal}</div>'
                    f'</div>'
                    f'<span class="sb-q-badge">LISTO</span>'
                    f'</div>'
                )

        if _sq_errs:
            _sq_items_html += '<div class="q-section-label">✗ Con error</div>'
            for _sqe in _sq_errs[:2]:
                _sqe_titulo = _html_escape(_sqe.get("titulo", _sqe.get("proyecto_id", "?")))
                if len(_sqe_titulo) > 28:
                    _sqe_titulo = _sqe_titulo[:28] + "…"
                _sq_items_html += (
                    f'<div class="sb-q-item q-item-err">'
                    f'<div class="sb-q-icon">✗</div>'
                    f'<div class="sb-q-info">'
                    f'<div class="sb-q-title">{_sqe_titulo}</div>'
                    f'<div class="sb-q-meta">error</div>'
                    f'</div>'
                    f'<span class="sb-q-badge">ERR</span>'
                    f'</div>'
                )

        if _sq_pubs:
            _sq_items_html += '<div class="q-section-label">📺 Publicados</div>'
            for _sqpb in _sq_pubs[:3]:
                _sqpb_titulo = _html_escape(_sqpb.get("titulo", _sqpb.get("proyecto_id", "?")))
                if len(_sqpb_titulo) > 28:
                    _sqpb_titulo = _sqpb_titulo[:28] + "…"
                _sqpb_vid = _sqpb.get("youtube_video_id", "")
                _sqpb_meta = _sqpb_vid if _sqpb_vid else "publicado"
                _sq_items_html += (
                    f'<div class="sb-q-item q-item-pub">'
                    f'<div class="sb-q-icon">📺</div>'
                    f'<div class="sb-q-info">'
                    f'<div class="sb-q-title">{_sqpb_titulo}</div>'
                    f'<div class="sb-q-meta">{_html_escape(_sqpb_meta)}</div>'
                    f'</div>'
                    f'<span class="sb-q-badge">PUB</span>'
                    f'</div>'
                )

        if not _sq_items_html:
            _sq_items_html = '<div class="q-empty">Sin proyectos todavía</div>'

        st.markdown(f"""
        <div class="sb-queue">
          <div class="sb-queue-head">
            <span class="sb-queue-title">📋 Cola</span>
            <span class="sb-queue-buf {_sq_buf_cls}">{_sq_buf_actual}/{_sq_buf_max}</span>
          </div>
          {_sq_items_html}
        </div>""", unsafe_allow_html=True)

    # ── Eventos recientes ──
    st.divider()
    _sb_eventos = _cached_eventos_recientes()

    _EVENT_ICONS = {
        "pipeline_started": "🚀", "pipeline_completed": "✅", "pipeline_failed": "❌",
        "pipeline_phase": "📋", "agent_completed": "⚙️", "agent_failed": "💥",
        "system_startup": "🔌", "health_check": "💓",
    }
    _EVENT_LABELS = {
        "pipeline_started": "Pipeline iniciado",
        "pipeline_completed": "Pipeline completado",
        "pipeline_failed": "Pipeline falló",
        "pipeline_phase": "Fase",
        "agent_completed": "Agente OK",
        "agent_failed": "Agente falló",
        "system_startup": "Sistema iniciado",
        "health_check": "Health check",
    }

    if _sb_eventos is None:
        _sk_ev_rows = ""
        for _sk_op in [1.0, 0.7, 0.5, 0.35, 0.2]:
            _sk_w1 = ["85%", "70%", "78%", "60%", "72%"][int(_sk_op*4) % 5]
            _sk_w2 = ["55%", "45%", "62%", "38%", "50%"][int(_sk_op*4) % 5]
            _sk_ev_rows += (
                f'<div class="sb-ev" style="opacity:{_sk_op};border-left-color:var(--border3)">'
                f'<div class="sk sk-circle" style="width:18px;height:18px;flex-shrink:0;margin-top:1px"></div>'
                f'<div class="sb-ev-body">'
                f'<div class="sk sk-line" style="width:{_sk_w1};margin-bottom:4px"></div>'
                f'<div class="sk sk-line sm" style="width:{_sk_w2};margin:0"></div>'
                f'</div></div>'
            )
        st.markdown(f"""
        <div class="sb-events">
          <div class="sb-events-head">
            <span class="sb-events-title">📜 Eventos</span>
            <span class="sk sk-line sm" style="width:20px;margin:0;display:inline-block"></span>
          </div>
          {_sk_ev_rows}
        </div>""", unsafe_allow_html=True)
    elif not _sb_eventos:
        st.markdown("""
        <div class="sb-events">
          <div class="sb-events-head">
            <span class="sb-events-title">📜 Eventos</span>
            <span class="sb-events-count">0</span>
          </div>
          <div class="q-empty">Sin eventos registrados</div>
        </div>""", unsafe_allow_html=True)
    else:
        _sbe_html = ""
        for _ev in _sb_eventos[:10]:
            _ev_type = _ev.get("event_type", "?")
            _ev_status = _ev.get("status", "?")
            _ev_ts = _ev.get("timestamp", "")
            _ev_source = _ev.get("source", "")
            _ev_pid = _ev.get("proyecto_id", "")
            _ev_data = _ev.get("data") or {}
            _ev_dur = _ev.get("duration_seg")

            _ev_icon = _EVENT_ICONS.get(_ev_type, "📌")
            _ev_cls = "ev-error" if _ev_status == "error" else "ev-success"

            _ev_label = _EVENT_LABELS.get(_ev_type, _ev_type)
            if _ev_type == "pipeline_phase" and isinstance(_ev_data, dict):
                _ev_label = f"Fase: {_ev_data.get('fase', '?')}"
            elif _ev_type == "agent_completed":
                _ev_label = f"{_ev_source} OK"
            elif _ev_type == "agent_failed":
                _ev_label = f"{_ev_source} falló"

            _ev_time_short = _ev_ts[11:16] if len(_ev_ts) >= 16 else _ev_ts
            _ev_dur_str = f" · {_ev_dur:.1f}s" if _ev_dur else ""
            _ev_pid_str = f" · {_html_escape(_ev_pid[:12])}" if _ev_pid else ""

            _sbe_html += (
                f'<div class="sb-ev {_ev_cls}">'
                f'<div class="sb-ev-icon">{_ev_icon}</div>'
                f'<div class="sb-ev-body">'
                f'<div class="sb-ev-msg">{_html_escape(_ev_label)}</div>'
                f'<div class="sb-ev-time">{_ev_time_short}{_ev_dur_str}{_ev_pid_str}</div>'
                f'</div></div>'
            )

        st.markdown(f"""
        <div class="sb-events">
          <div class="sb-events-head">
            <span class="sb-events-title">📜 Eventos</span>
            <span class="sb-events-count">{len(_sb_eventos)}</span>
          </div>
          {_sbe_html}
        </div>""", unsafe_allow_html=True)

    # ── Scheduler y pausa ──
    st.divider()
    _sb_sched = _cached_scheduler()
    _sb_pausa = _cached_pausa()

    _sb_esta_pausado = _sb_pausa is not None and _sb_pausa.get("pausado", False)
    if _sb_esta_pausado:
        _sb_pausa_en = _sb_pausa.get("pausado_en", "")
        _sb_pausa_razon = _sb_pausa.get("razon", "")
        _sb_pausa_time = _sb_pausa_en[11:16] if _sb_pausa_en and len(_sb_pausa_en) >= 16 else ""
        _sb_pausa_sub = f"Desde {_sb_pausa_time}" + (f" — {_html_escape(_sb_pausa_razon)}" if _sb_pausa_razon else "")
        st.markdown(f"""
        <div class="pause-banner">
          <span class="pause-banner-icon">⏸️</span>
          <div class="pause-banner-text">
            <div class="pause-banner-title">AUTOMATIZACIÓN PAUSADA</div>
            <div class="pause-banner-sub">{_sb_pausa_sub}</div>
          </div>
        </div>""", unsafe_allow_html=True)
        if st.button("▶  Reanudar automatización", key="sb_resume_auto", use_container_width=True):
            try:
                import api_client as _pause_api
                _pause_api.scheduler_reanudar()
                _cached_pausa.clear()
                _cached_scheduler.clear()
                st.rerun()
            except Exception as _e:
                st.error(f"Error: {_e}")
    elif _sb_pausa is not None:
        if st.button("⏸  Pausar automatización", key="sb_pause_auto", use_container_width=True):
            try:
                import api_client as _pause_api
                _pause_api.scheduler_pausar()
                _cached_pausa.clear()
                _cached_scheduler.clear()
                st.rerun()
            except Exception as _e:
                st.error(f"Error: {_e}")

    if _sb_sched is None:
        _sk_task_rows = ""
        for _sk_op in [1.0, 0.65, 0.35]:
            _sk_tw = ["82%", "68%", "74%"][int(_sk_op*2) % 3]
            _sk_mw = ["60%", "50%", "55%"][int(_sk_op*2) % 3]
            _sk_task_rows += (
                f'<div class="sb-task" style="opacity:{_sk_op}">'
                f'<span class="sk sk-circle" style="width:7px;height:7px;flex-shrink:0"></span>'
                f'<div class="sb-task-info">'
                f'<div class="sk sk-line" style="width:{_sk_tw};margin-bottom:4px"></div>'
                f'<div class="sk sk-line sm" style="width:{_sk_mw};margin:0"></div>'
                f'</div></div>'
            )
        st.markdown(f"""
        <div class="sb-sched">
          <div class="sb-sched-head">
            <span class="sb-sched-title">🕐 Schedule</span>
            <span class="sk sk-line sm" style="width:50px;margin:0;display:inline-block"></span>
          </div>
          <div class="sb-sched-next" style="opacity:.6">
            <span class="sb-sched-next-icon sk sk-circle" style="width:20px;height:20px;display:inline-block"></span>
            <div class="sb-sched-next-info">
              <div class="sk sk-line sm" style="width:90px;margin-bottom:5px"></div>
              <div class="sk sk-line" style="width:120px;margin:0"></div>
            </div>
          </div>
          {_sk_task_rows}
        </div>""", unsafe_allow_html=True)
    else:
        _sc_tareas = _sb_sched.get("tareas", [])
        _sc_habilitadas = _sb_sched.get("habilitadas", 0)
        _sc_proxima = _sb_sched.get("proxima_ejecucion")
        _sc_proxima_nombre = _sb_sched.get("proxima_tarea", "")

        _sc_next_html = ""
        if _sc_proxima:
            _sc_prox_hora = _sc_proxima[11:16] if len(_sc_proxima) >= 16 else _sc_proxima
            _sc_next_html = (
                f'<div class="sb-sched-next">'
                f'<span class="sb-sched-next-icon">⏰</span>'
                f'<div class="sb-sched-next-info">'
                f'<div class="sb-sched-next-label">Próxima ejecución</div>'
                f'<div class="sb-sched-next-time">{_sc_prox_hora} — {_html_escape(_sc_proxima_nombre or "?")}</div>'
                f'</div></div>'
            )

        _sc_tasks_html = ""
        for _sct in _sc_tareas:
            _sct_hab = _sct.get("habilitado", False)
            _sct_dot_color = "#1DB954" if _sct_hab else "#FF0000"
            _sct_name = _html_escape(_sct.get("nombre", "?"))
            _sct_freq = _html_escape(_sct.get("hora_legible", _sct.get("frecuencia", "?")))
            _sct_last = _sct.get("ultima_ejecucion")
            _sct_last_str = _sct_last[11:16] if _sct_last and len(_sct_last) >= 16 else "nunca"
            _sct_status = _sct.get("ultimo_estado", "")
            _sct_status_icon = "✓" if _sct_status == "success" else ("✗" if _sct_status == "error" else "—")

            _sc_tasks_html += (
                f'<div class="sb-task">'
                f'<span class="sb-task-dot" style="background:{_sct_dot_color}"></span>'
                f'<div class="sb-task-info">'
                f'<div class="sb-task-name">{_sct_name}</div>'
                f'<div class="sb-task-meta">{_sct_freq} · último: {_sct_last_str} {_sct_status_icon}</div>'
                f'</div></div>'
            )

        st.markdown(f"""
        <div class="sb-sched">
          <div class="sb-sched-head">
            <span class="sb-sched-title">🕐 Schedule</span>
            <span class="sb-sched-count">{_sc_habilitadas} activas</span>
          </div>
          {_sc_next_html}
          {_sc_tasks_html}
        </div>""", unsafe_allow_html=True)


def _leer_logs(storage_dir: str, incluir_rotados: bool = False) -> list[str]:
    """Lee las líneas de log del archivo principal y opcionalmente los rotados."""
    log_dir = Path(storage_dir) / "logs"
    lineas = []
    if incluir_rotados:
        for i in [3, 2, 1]:
            rotado = log_dir / f"ytcreator.log.{i}"
            if rotado.exists():
                lineas.extend(rotado.read_text(encoding="utf-8", errors="replace").strip().split("\n"))
    principal = log_dir / "ytcreator.log"
    if principal.exists():
        lineas.extend(principal.read_text(encoding="utf-8", errors="replace").strip().split("\n"))
    return [l for l in lineas if l.strip()]


def _parsear_linea_log(linea: str) -> dict:
    """Parsea una línea de log al formato estructurado."""
    parts = linea.split(" | ", 3)
    if len(parts) >= 4:
        return {"ts": parts[0], "name": parts[1].strip(), "level": parts[2].strip(), "msg": parts[3]}
    return {"ts": "", "name": "", "level": "INFO", "msg": linea}


def _extraer_servicios_unicos(lineas_parseadas: list[dict]) -> list[str]:
    """Extrae los nombres de servicios únicos de las líneas de log."""
    nombres = sorted(set(l["name"] for l in lineas_parseadas if l["name"]))
    return nombres


_AGENTE_A_DEPTO = {
    "sub_orq_inteligencia": 0, "0.1_escaner_canal": 0, "0.2_analizador_canal": 0,
    "0.3_monitor_mercado": 0, "0.4_asesor_estrategico": 0, "0.5_tracker_performance": 0,
    "sub_orq_estrategia": 1, "1.1_investigador": 1, "1.2_copywriter": 1,
    "1.3_director_arte": 1, "1.4_generador_miniatura": 1,
    "sub_orq_guion": 2, "2.1_guionista": 2,
    "sub_orq_visual": 3, "3.1_prompt_maker": 3, "3.2_generador_visual": 3,
    "sub_orq_audio": 4, "4.1_locucion": 4, "4.2_musica": 4, "4.3_subtitulos": 4,
    "sub_orq_cierre": 5, "5.1_editor": 5, "5.2_seo": 5, "5.3_compliance": 5,
    "5.4_policy_monitor": 5, "5.5_publicador": 5,
}
_DEPTO_NOMBRES = ["Intel", "Estrategia", "Guión", "Visual", "Audio", "Cierre"]
_DEPTO_COLORES_HEX = ["#3EA6FF", "#A855F7", "#FF9500", "#1DB954", "#FF6B9D", "#6366F1"]


def _renderizar_timeline_html(historial: list[dict], titulo: str = "") -> str:
    """Genera un Gantt chart HTML puro a partir del historial de agentes."""
    if not historial:
        return ""

    from datetime import datetime as _dt

    entries = []
    for h in historial:
        inicio_str = h.get("inicio")
        fin_str = h.get("fin")
        if not inicio_str or not fin_str:
            continue
        try:
            inicio_dt = _dt.fromisoformat(inicio_str)
            fin_dt = _dt.fromisoformat(fin_str)
        except (ValueError, TypeError):
            continue
        entries.append({
            "agente": h.get("agente_id", "?"),
            "inicio": inicio_dt,
            "fin": fin_dt,
            "duracion": h.get("duracion_seg", 0) or (fin_dt - inicio_dt).total_seconds(),
            "estado": h.get("estado", "?"),
            "intentos": h.get("intentos", 1),
            "error": h.get("error"),
        })

    if not entries:
        return ""

    pipeline_start = min(e["inicio"] for e in entries)
    pipeline_end = max(e["fin"] for e in entries)
    total_seg = (pipeline_end - pipeline_start).total_seconds()
    if total_seg <= 0:
        total_seg = 1

    def _fmt_dur(seg):
        if seg >= 3600:
            return f"{seg/3600:.1f}h"
        if seg >= 60:
            return f"{seg/60:.1f}m"
        return f"{seg:.0f}s"

    # Eje de tiempo (ticks)
    n_ticks = min(8, max(3, int(total_seg / 30) + 1))
    tick_html = ""
    for i in range(n_ticks + 1):
        pct = (i / n_ticks) * 100
        seg_val = (i / n_ticks) * total_seg
        tick_html += f'<span class="tl-tick" style="left:{pct}%">{_fmt_dur(seg_val)}</span>'

    # Barras
    rows_html = ""
    for e in entries:
        offset_seg = (e["inicio"] - pipeline_start).total_seconds()
        left_pct = (offset_seg / total_seg) * 100
        width_pct = max((e["duracion"] / total_seg) * 100, 0.5)

        depto_idx = _AGENTE_A_DEPTO.get(e["agente"], 5)
        bar_cls = "b-err" if e["estado"] == "error" else f"b-{depto_idx}"

        label_short = e["agente"].split("_", 1)[-1] if "_" in e["agente"] else e["agente"]
        bar_text = _fmt_dur(e["duracion"])
        if width_pct > 8:
            bar_text = f'{_fmt_dur(e["duracion"])}'
        elif width_pct < 3:
            bar_text = ""

        retry_mark = f' ×{e["intentos"]}' if e["intentos"] > 1 else ""
        tooltip = f'{e["agente"]} — {_fmt_dur(e["duracion"])}{retry_mark}'

        rows_html += (
            f'<div class="tl-row">'
            f'<div class="tl-label" title="{_html_escape(e["agente"])}">{_html_escape(label_short)}</div>'
            f'<div class="tl-track">'
            f'<div class="tl-bar {bar_cls}" style="left:{left_pct:.2f}%;width:{width_pct:.2f}%" '
            f'title="{_html_escape(tooltip)}">{bar_text}</div>'
            f'</div></div>'
        )

    # Leyenda
    deptos_usados = sorted(set(_AGENTE_A_DEPTO.get(e["agente"], 5) for e in entries))
    legend_html = ""
    for di in deptos_usados:
        legend_html += (
            f'<div class="tl-legend-item">'
            f'<span class="tl-legend-dot" style="background:{_DEPTO_COLORES_HEX[di]}"></span>'
            f'{_DEPTO_NOMBRES[di]}</div>'
        )
    has_errors = any(e["estado"] == "error" for e in entries)
    if has_errors:
        legend_html += '<div class="tl-legend-item"><span class="tl-legend-dot" style="background:#FF0000"></span>Error</div>'

    # Resumen por fase
    fase_tiempos = {}
    for e in entries:
        di = _AGENTE_A_DEPTO.get(e["agente"], 5)
        nombre = _DEPTO_NOMBRES[di]
        fase_tiempos[nombre] = fase_tiempos.get(nombre, 0) + e["duracion"]
    resumen_parts = [f'{nombre}: {_fmt_dur(dur)}' for nombre, dur in fase_tiempos.items()]
    resumen_html = " · ".join(resumen_parts)

    return (
        f'<div class="tl-wrap">'
        f'<div class="tl-header">'
        f'<span class="tl-title">{_html_escape(titulo) if titulo else "Timeline del pipeline"}</span>'
        f'<span class="tl-duration">Total: {_fmt_dur(total_seg)}</span>'
        f'</div>'
        f'<div class="tl-axis">{tick_html}</div>'
        f'{rows_html}'
        f'<div style="font-size:.65rem;color:var(--text3);margin-top:8px;'
        f'font-family:\'JetBrains Mono\',monospace">{resumen_html}</div>'
        f'<div class="tl-legend">{legend_html}</div>'
        f'</div>'
    )


def _renderizar_logs_html(lineas_parseadas: list[dict], busqueda: str = "") -> str:
    """Genera el HTML del visor de logs con resaltado de búsqueda."""
    html_parts = []
    for lp in lineas_parseadas:
        ts = _html_escape(lp["ts"])
        name = _html_escape(lp["name"])
        level = lp["level"]
        msg = _html_escape(lp["msg"])

        lcls = "l-info"
        if "ERROR" in level:
            lcls = "l-err"
        elif "WARNING" in level:
            lcls = "l-warn"

        if busqueda and busqueda.lower() in (lp["ts"] + lp["name"] + lp["msg"]).lower():
            msg = msg.replace(
                _html_escape(busqueda),
                f'<mark style="background:rgba(255,255,0,.25);color:var(--text);border-radius:2px;padding:0 2px">{_html_escape(busqueda)}</mark>',
            )
            name_esc = _html_escape(busqueda)
            if name_esc.lower() in name.lower():
                name = name.replace(
                    name_esc,
                    f'<mark style="background:rgba(255,255,0,.25);color:var(--text);border-radius:2px;padding:0 2px">{name_esc}</mark>',
                )

        if name:
            html_parts.append(
                f'<div class="{lcls}">'
                f'<span class="l-time">{ts}</span> '
                f'<span class="l-name">{name}</span> '
                f'{msg}</div>'
            )
        else:
            html_parts.append(f'<div class="{lcls}">{msg}</div>')

    return "".join(html_parts)


# ══════════════════════════════════════════════════════════════
# SIDEBAR — Solo en workspace (panel derecho fijo)
# ══════════════════════════════════════════════════════════════
if s.get('vista_actual') in ('home', 'channel_dashboard'):
    _skip_sidebar = True
    st.markdown("""<style>
    section[data-testid="stSidebar"]{display:none!important}
    [data-testid="collapsedControl"]{display:none!important}
    .block-container{padding-left:80px!important}
    </style>""", unsafe_allow_html=True)
else:
    _skip_sidebar = False

with st.sidebar:
  if _skip_sidebar:
    pass
  else:
        pdir   = Path(f"proyectos/{s.get('canal_activo_id') or 'sin_canal'}/{s['nombre_proyecto']}")
        clips  = sorted((pdir/"videos").glob("*.mp4")) if (pdir/"videos").exists() else []
        audios = sorted((pdir/"audio").glob("*.mp3"))  if (pdir/"audio").exists()  else []
        subs   = sorted((pdir/"subs").glob("*.srt"))   if (pdir/"subs").exists()   else []
        final  = list((pdir/"output").glob("*.mp4"))   if (pdir/"output").exists() else []
        total  = len(s['guion_aprobado']['escenas']) if s['guion_aprobado'] else 0

        st.markdown(f"""
        <div class="sb-head">
          <div class="sb-title">📊 Estado del proyecto</div>
          <div class="sb-proj">{'📁 '+s['nombre_proyecto'] if s['nombre_proyecto'] else '—'}</div>
        </div>
        """, unsafe_allow_html=True)

        steps_sb = [
            ("📝","Guión",bool(s['guion_aprobado']),
             f"{s['guion_aprobado']['titulo'][:22]}..." if s['guion_aprobado'] else "Pendiente"),
            ("🎙️","Audio",s['audio_generado'],
             f"{len(audios)} audios" if audios else "Pendiente"),
            ("🚀","Kaggle",s['kaggle_completado'],
             f"{len(clips)}/{total} clips" if clips else "Pendiente"),
            ("💬","Subtítulos",s['subs_generados'],
             f"{len(subs)} archivos" if subs else "Pendiente"),
            ("🎞️","Ensamblar",bool(s['video_final']),
             "Video listo ✅" if s['video_final'] else "Pendiente"),
        ]
        first_p = next((i for i,(_,_,d,_) in enumerate(steps_sb) if not d), len(steps_sb))

        for i,(ic,nm,done,desc) in enumerate(steps_sb):
            cls  = "done" if done else ("active" if i==first_p else "pending")
            bdg  = f'<span class="sbadge b-ok">OK</span>' if done else (
                   f'<span class="sbadge b-run">NOW</span>' if i==first_p else
                   f'<span class="sbadge b-pend">—</span>')
            st.markdown(f"""
            <div class="sstep {cls}">
              <div class="si-wrap">{ic}</div>
              <div style="flex:1;min-width:0">
                <div class="sname">{nm}</div>
                <div class="sdesc">{desc}</div>
              </div>
              {bdg}
            </div>""", unsafe_allow_html=True)

        if total > 0:
            st.markdown('<div style="padding:10px 14px 0">', unsafe_allow_html=True)
            pct_a = min(len(audios)/total,1.0)
            pct_v = min(len(clips)/total,1.0)
            st.caption("Audios")
            st.progress(pct_a)
            st.caption(f"{len(audios)}/{total}")
            st.caption("Clips")
            st.progress(pct_v)
            st.caption(f"{len(clips)}/{total}")
            st.markdown('</div>', unsafe_allow_html=True)

        st.divider()

        # Próximo paso
        st.markdown('<div style="padding:0 14px">', unsafe_allow_html=True)
        st.markdown('<div class="section-label" style="padding:0">Próximo paso</div>', unsafe_allow_html=True)
        if not s['guion_aprobado']:
            st.info("→ Tab **Guión**")
        elif not s['audio_generado']:
            st.info("→ Tab **Audio**")
        elif not s['kaggle_completado']:
            st.info("→ Tab **Kaggle**")
        elif not s['subs_generados']:
            st.info("→ Tab **Subtítulos**")
        elif not s['video_final']:
            st.info("→ Tab **Ensamblar**")
        else:
            st.success("🎉 ¡Todo listo!")
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Sección API del sidebar (fragment independiente, auto-refresca cada 30 s) ──
        _sidebar_api_section()

# ══════════════════════════════════════════════════════════════
# MAIN CONTENT