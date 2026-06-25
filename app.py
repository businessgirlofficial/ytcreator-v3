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
    st.session_state["autorefresh_interval"] = "30s"
_ar_interval = _REFRESH_INTERVALS[st.session_state["autorefresh_interval"]]
if _ar_interval > 0:
    st_autorefresh(interval=_ar_interval, key="global_autorefresh")

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
    'guion_texto_completo':None
}.items():
    if k not in st.session_state: st.session_state[k]=v
s=st.session_state


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
# SIDEBAR — Estado del proyecto (panel derecho fijo)
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    pdir   = Path(f"proyectos/{s['nombre_proyecto']}")
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

    # ── Health de servicios (siempre visible) ──
    st.divider()
    _sb_health = _cached_health_servicios()

    if _sb_health is None:
        st.markdown("""
        <div class="sb-health">
          <div class="sb-health-head">
            <span class="sb-health-title">📡 Servicios</span>
            <span class="sb-health-score sb-h-off">OFF</span>
          </div>
          <div style="font-size:.7rem;color:var(--text4)">Agentes no conectados</div>
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

        _sb_deptos_html = ""
        for _sbdk, _sbdl in _SB_DEPTOS:
            _sbd_info = _sb_desglose.get(_sbdk, {"vivos": 0, "total": 0})
            _sbd_v = _sbd_info["vivos"]
            _sbd_t = _sbd_info["total"]

            _SB_DEPTO_AGENTS = {
                "depto_0_inteligencia": ["0.1_escaner_canal", "0.2_analizador_canal", "0.3_monitor_mercado", "0.4_asesor_estrategico", "0.5_tracker_performance", "sub_orq_inteligencia"],
                "depto_1_estrategia": ["1.1_investigador", "1.2_copywriter", "1.3_director_arte", "1.4_generador_miniatura", "sub_orq_estrategia"],
                "depto_2_guion": ["2.1_guionista", "sub_orq_guion"],
                "depto_3_visual": ["3.1_prompt_maker", "3.2_generador_visual", "sub_orq_visual"],
                "depto_4_audio": ["4.1_locucion", "4.2_musica", "4.3_subtitulos", "sub_orq_audio"],
                "depto_5_cierre": ["5.1_editor", "5.2_seo", "5.3_compliance", "5.4_policy_monitor", "5.5_publicador", "sub_orq_cierre"],
                "orquestador": ["orquestador_central"],
            }

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
                st.rerun()
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
                st.rerun()

    # ── Cola de publicación (siempre visible) ──
    st.divider()
    _sb_cola = _cached_pipeline_cola()

    if _sb_cola is None:
        st.markdown("""
        <div class="sb-queue">
          <div class="sb-queue-head">
            <span class="sb-queue-title">📋 Cola</span>
            <span class="sb-queue-buf sb-h-off">—</span>
          </div>
          <div style="font-size:.7rem;color:var(--text4)">Sin conexión a agentes</div>
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
        _sq_total_items = len(_sq_en_proc) + len(_sq_listos) + len(_sq_pubs) + len(_sq_errs)

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

    # ── Eventos recientes (siempre visible) ──
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
        st.markdown("""
        <div class="sb-events">
          <div class="sb-events-head">
            <span class="sb-events-title">📜 Eventos</span>
          </div>
          <div style="font-size:.7rem;color:var(--text4)">Sin conexión</div>
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

    # ── Scheduler (tareas programadas) ──
    st.divider()
    _sb_sched = _cached_scheduler()
    _sb_pausa = _cached_pausa()

    # Banner de pausa global
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
        st.markdown("""
        <div class="sb-sched">
          <div class="sb-sched-head">
            <span class="sb-sched-title">🕐 Schedule</span>
          </div>
          <div style="font-size:.7rem;color:var(--text4)">Sin conexión</div>
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

# ══════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════

# ── Header ────────────────────────────────────────────────────
keys_ok = bool(GROQ_KEY and KAGGLE_KEY and KAGGLE_USER)
_hdr_health = _cached_health_servicios()

if _hdr_health:
    _hdr_score = _hdr_health.get("score", 0)
    _hdr_vivos = _hdr_health.get("vivos", 0)
    _hdr_total = _hdr_health.get("total", 0)
    _hdr_mem = _hdr_health.get("memoria_total_mb")
    _hdr_nivel = _hdr_health.get("nivel", "critico")
    _hdr_dot = "on" if _hdr_nivel == "saludable" else "off"
    _hdr_score_color = "#1DB954" if _hdr_nivel == "saludable" else ("#FF9500" if _hdr_nivel == "degradado" else "#FF0000")
    _hdr_status_html = (
        f'<div class="hdr-health">'
        f'<div class="hdr-health-item"><span class="dot {_hdr_dot}"></span>'
        f'<span class="hdr-health-num" style="color:{_hdr_score_color}">{_hdr_score}%</span> {_hdr_nivel}</div>'
        f'<div class="hdr-health-item">{_hdr_vivos}/{_hdr_total} servicios</div>'
        + (f'<div class="hdr-health-item">{_hdr_mem} MB</div>' if _hdr_mem else '')
        + '</div>'
    )
elif keys_ok:
    _hdr_status_html = (
        '<div class="hdr-st">'
        '<span class="dot on"></span>'
        'sistema listo'
        '</div>'
    )
else:
    _hdr_status_html = (
        '<div class="hdr-st">'
        '<span class="dot off"></span>'
        'configura .env con tus API keys'
        '</div>'
    )

st.markdown(f"""
<div class="hdr">
  <div class="hdr-brand">
    <span style="font-size:1.25rem">🎬</span>
    <span class="hdr-logo">YT<em>Creator</em> Studio</span>
    <span class="hdr-badge">v3</span>
  </div>
  {_hdr_status_html}
</div>
""", unsafe_allow_html=True)

# ── Pipeline bar ──────────────────────────────────────────────
pip_steps = [
    ("1","Guión",    bool(s['guion_aprobado'])),
    ("2","Audio",    s['audio_generado']),
    ("3","Kaggle",   s['kaggle_completado']),
    ("4","Subtítulos",s['subs_generados']),
    ("5","Ensamblar",bool(s['video_final'])),
]
fp = next((i for i,(_,_,d) in enumerate(pip_steps) if not d), 4)
hp = ""
for i,(num,name,done) in enumerate(pip_steps):
    cls = "done" if done else ("active" if i==fp else "")
    ic  = "✓" if done else num
    hp += f'<div class="ps {cls}"><span class="psn">{ic}</span>{name}</div>'
    if i < 4: hp += '<span class="pa">›</span>'
st.markdown(f'<div class="pip">{hp}</div>', unsafe_allow_html=True)

# ── Project bar ───────────────────────────────────────────────
c_np, c_sp = st.columns([3, 5])
nombre_proyecto = c_np.text_input(
    "📁 Nombre del proyecto", value=s['nombre_proyecto'],
    key="np_k", label_visibility="visible")
s['nombre_proyecto'] = nombre_proyecto
pdir = Path(f"proyectos/{nombre_proyecto}")
pdir.mkdir(parents=True, exist_ok=True)

# ── API check ────────────────────────────────────────────────
try:
    import api_client
    API_DISPONIBLE = api_client.health()
except Exception:
    API_DISPONIBLE = False

if _hdr_health and API_DISPONIBLE:
    _pb_puede = _hdr_health.get("puede_pipeline", False)
    _pb_criticos = len(_hdr_health.get("criticos_caidos", []))
    _pb_pipe_txt = "pipeline listo" if _pb_puede else f"pipeline bloqueado ({_pb_criticos} críticos caídos)"
    _pb_pipe_dot = "on" if _pb_puede else "off"
    c_sp.markdown(f"""<div style="display:flex;align-items:center;gap:12px;height:100%;padding-top:28px">
    <div style="display:flex;align-items:center;gap:5px">
      <span class="dot on"></span>
      <span style="font-size:.7rem;color:var(--text3);font-family:'JetBrains Mono',monospace">agentes conectados</span>
    </div>
    <div style="display:flex;align-items:center;gap:5px">
      <span class="dot {_pb_pipe_dot}"></span>
      <span style="font-size:.7rem;color:var(--text3);font-family:'JetBrains Mono',monospace">{_pb_pipe_txt}</span>
    </div>
    </div>""", unsafe_allow_html=True)
else:
    c_sp.markdown(f"""<div style="display:flex;align-items:center;gap:6px;height:100%;padding-top:28px">
    <span class="dot {'on' if API_DISPONIBLE else 'off'}"></span>
    <span style="font-size:.7rem;color:var(--text3);font-family:'JetBrains Mono',monospace">
    {'agentes conectados' if API_DISPONIBLE else 'modo local (agentes no disponibles)'}</span>
    </div>""", unsafe_allow_html=True)

# ── Modo Automático ──────────────────────────────────────────
if API_DISPONIBLE:
    with st.expander("⚡ Modo Automático — Pipeline completo con un click", expanded=False):
        st.markdown("""<div class="card primary" style="margin-bottom:12px">
        <div class="card-title">⚡ Lanzar pipeline completo</div>
        <div class="card-sub">Ejecuta todo el pipeline automáticamente: análisis de nicho → guión → audio → visual → subtítulos → ensamblado.
        El mismo pipeline que usa n8n para generar videos mientras duermes.</div>
        </div>""", unsafe_allow_html=True)

        col_auto1, col_auto2 = st.columns(2, gap="large")
        with col_auto1:
            auto_nicho = st.text_input("Nicho", value=s.get("nicho", ""),
                placeholder="ej: finanzas personales, psicología...", key="auto_nicho")
        with col_auto2:
            auto_canal = st.text_input("Canal", value=s.get("nombre_proyecto", "MiCanal"),
                key="auto_canal")

        if st.button("🚀  Lanzar pipeline automático", use_container_width=True, key="btn_auto"):
            if not auto_nicho.strip():
                st.error("❌  Ingresa el nicho")
            else:
                s["nicho"] = auto_nicho
                try:
                    import api_client
                    webhook_payload = {
                        "nicho": auto_nicho,
                        "canal": auto_canal or "MiCanal",
                    }
                    if s.get("canal_id_pipeline"):
                        webhook_payload["canal_id"] = s["canal_id_pipeline"]
                    result = api_client.webhook_trigger(**webhook_payload)
                    st.success(f"✅  Pipeline lanzado — Proyecto: **{result.get('proyecto_id')}**")
                    st.info("El pipeline corre en background. Recibirás una notificación en Telegram cuando termine.")

                    if result.get("proyecto_id"):
                        s["auto_proyecto_id"] = result["proyecto_id"]
                except Exception as e:
                    st.error(f"❌  Error al lanzar pipeline: {str(e)}")

        if s.get("auto_proyecto_id"):
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            if st.button("🔄  Ver estado del pipeline", use_container_width=True, key="btn_auto_status"):
                try:
                    import api_client
                    estado = api_client.pipeline_estado(s["auto_proyecto_id"])
                    fase = estado.get("fase_actual", "?")
                    st.markdown(f"""<div class="card">
                    <div class="card-title">📊 Proyecto: {s['auto_proyecto_id']}</div>
                    <div class="card-sub">
                    Fase actual: <strong>{fase}</strong><br>
                    Guión aprobado: {'✅' if estado.get('guion_aprobado') else '⏳'} ·
                    Visual listo: {'✅' if estado.get('visual_listo') else '⏳'} ·
                    Audio listo: {'✅' if estado.get('audio_listo') else '⏳'}<br>
                    Video final: {'✅ Listo!' if estado.get('video_final') else '⏳ En progreso...'}
                    </div></div>""", unsafe_allow_html=True)
                except Exception as e:
                    st.warning(f"No se pudo obtener estado: {str(e)}")

st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────
tab0, tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Canal", "📝 Guión", "🎙️ Audio", "🚀 Kaggle", "💬 Subtítulos", "🎞️ Ensamblar", "📡 Monitor"])

# ══════════════════════════════════════════════════════════════
# TAB 0 — CANAL (Channel Intelligence)
# ══════════════════════════════════════════════════════════════
with tab0:
    st.markdown('<div class="step-title">Channel Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-sub">Conecta tu canal de YouTube para analizar tu nicho, competidores y generar ideas de video basadas en datos reales.</div>', unsafe_allow_html=True)

    if not API_DISPONIBLE:
        st.warning("Los agentes no están conectados. Levanta los servicios con `python run_dev.py` para usar Channel Intelligence.")
    else:
        import api_client

        # ── Conectar canal ──
        with st.expander("🔗  Conectar canal de YouTube", expanded=not s.get("canales_conectados")):
            col_c1, col_c2 = st.columns([3, 1], gap="large")
            with col_c1:
                canal_input = st.text_input(
                    "URL del canal, @handle o Channel ID",
                    placeholder="ej: @MiCanal, https://youtube.com/@MiCanal, UCxxxxxxxx",
                    key="canal_input_ci",
                )
            with col_c2:
                st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
                btn_conectar = st.button("🔗  Conectar y escanear", use_container_width=True, key="btn_conectar_canal")

            if btn_conectar and canal_input.strip():
                with st.spinner("Escaneando canal... (esto puede tomar 30-60 segundos)"):
                    try:
                        resultado = api_client.conectar_canal(canal_input.strip())
                        canal_id = resultado.get("canal_id", "")
                        st.success(f"✅  Canal conectado: **{resultado.get('nombre', canal_id)}**")
                        s["canal_seleccionado"] = canal_id
                        s["canales_conectados"] = True
                    except Exception as e:
                        st.error(f"❌  Error al conectar canal: {str(e)}")

        # ── Lista de canales conectados ──
        try:
            canales = api_client.listar_canales()
        except Exception:
            canales = []

        if canales:
            st.markdown('<div class="section-label" style="margin-top:16px">Canales conectados</div>', unsafe_allow_html=True)
            opciones_canal = {c["canal_id"]: f"{c['nombre']} ({c.get('suscriptores', '?')} subs)" for c in canales}
            canal_sel = st.selectbox(
                "Seleccionar canal",
                options=list(opciones_canal.keys()),
                format_func=lambda x: opciones_canal.get(x, x),
                key="canal_selector",
            )
            s["canal_seleccionado"] = canal_sel

            if canal_sel:
                col_refresh, col_delete = st.columns([1, 1])
                with col_refresh:
                    if st.button("🔄  Refrescar datos", key="btn_refresh_canal", use_container_width=True):
                        with st.spinner("Refrescando..."):
                            try:
                                api_client.refrescar_canal(canal_sel)
                                st.success("✅  Datos actualizados")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")

                try:
                    canal_data = api_client.estado_canal(canal_sel)
                except Exception as e:
                    canal_data = None
                    st.error(f"Error al cargar canal: {str(e)}")

                if canal_data:
                    # ── Dashboard del canal ──
                    st.markdown('<div class="section-label" style="margin-top:16px">Dashboard</div>', unsafe_allow_html=True)
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Suscriptores", f"{canal_data.get('suscriptores', 0):,}")
                    m2.metric("Videos", f"{canal_data.get('video_count', 0):,}")
                    m3.metric("Vistas totales", f"{canal_data.get('vistas_totales', 0):,}")
                    perfil = canal_data.get("perfil", {})
                    m4.metric("Nicho", perfil.get("nicho_principal", "Sin analizar"))

                    # ── Perfil IA ──
                    if perfil.get("nicho_principal"):
                        with st.expander("🧠  Perfil analizado por IA", expanded=True):
                            col_p1, col_p2 = st.columns(2)
                            with col_p1:
                                st.markdown(f"**Nicho:** {perfil.get('nicho_principal', '-')}")
                                st.markdown(f"**Sub-nichos:** {', '.join(perfil.get('sub_nichos', []))}")
                                st.markdown(f"**Tono:** {perfil.get('tono', '-')}")
                                st.markdown(f"**Audiencia:** {perfil.get('audiencia_objetivo', '-')}")
                                st.markdown(f"**Frecuencia:** {perfil.get('frecuencia_publicacion', '-')}")
                            with col_p2:
                                st.markdown(f"**Keywords:** {', '.join(perfil.get('keywords_clave', []))}")
                                st.markdown(f"**Estilo visual:** {perfil.get('estilo_visual', '-')}")
                                st.markdown(f"**Formatos exitosos:** {', '.join(perfil.get('formatos_exitosos', []))}")
                                if perfil.get("patrones_titulo_exitosos"):
                                    st.markdown("**Patrones de título:**")
                                    for p in perfil["patrones_titulo_exitosos"]:
                                        st.markdown(f"  - {p}")

                    # ── Identidad Visual ──
                    id_visual = canal_data.get("identidad_visual", {})
                    with st.expander(
                        "🎨  Identidad Visual del Canal"
                        + (" ✅" if id_visual.get("configurado") else " — Sin configurar"),
                        expanded=not id_visual.get("configurado"),
                    ):
                        from shared.visual_styles import CATALOGO_ESTILOS, CATEGORIAS

                        if id_visual.get("configurado"):
                            st.success(f"Estilo activo: **{id_visual.get('estilo_slug')}**")
                            if id_visual.get("personaje_principal"):
                                st.markdown(f"**Personaje:** {id_visual.get('personaje_nombre', '')} — {id_visual['personaje_principal']}")
                            if id_visual.get("paleta_colores"):
                                st.markdown(f"**Paleta:** {id_visual['paleta_colores']}")
                            if id_visual.get("fondo_base"):
                                st.markdown(f"**Fondo base:** {id_visual['fondo_base']}")
                            if id_visual.get("elementos_recurrentes"):
                                st.markdown(f"**Elementos:** {', '.join(id_visual['elementos_recurrentes'])}")

                        st.markdown('<div class="section-label" style="margin-top:12px">Configurar identidad</div>', unsafe_allow_html=True)

                        iv_cat = st.selectbox(
                            "Categoria", [c["nombre"] for c in CATEGORIAS],
                            key="iv_cat_sel",
                        )
                        iv_cat_slug = next((c["slug"] for c in CATEGORIAS if c["nombre"] == iv_cat), None)
                        iv_estilos = [e for e in CATALOGO_ESTILOS if e["categoria"] == iv_cat_slug]
                        iv_opciones = [f"{e['slug']} — {e['nombre']} ({e['caso_uso']})" for e in iv_estilos]
                        iv_opciones.append("custom — Personalizado (tu propio estilo)")
                        iv_estilo = st.selectbox("Estilo visual", iv_opciones, key="iv_estilo_sel")
                        iv_slug = iv_estilo.split(" — ")[0]

                        if iv_slug == "custom":
                            iv_custom_tpl = st.text_area(
                                "Prompt template (debe contener {prompt})",
                                placeholder="cinematic photo {prompt} . your style keywords here",
                                key="iv_custom_tpl",
                            )
                            iv_custom_neg = st.text_input(
                                "Negative prompt",
                                placeholder="ugly, deformed, blurry...",
                                key="iv_custom_neg",
                            )

                        col_iv1, col_iv2 = st.columns(2, gap="large")
                        with col_iv1:
                            iv_personaje = st.text_area(
                                "Personaje principal (EN INGLES, opcional)",
                                value=id_visual.get("personaje_principal", ""),
                                placeholder="a young woman with short blue hair, round glasses, wearing a black hoodie",
                                key="iv_personaje",
                                height=80,
                            )
                            iv_nombre = st.text_input(
                                "Nombre del personaje",
                                value=id_visual.get("personaje_nombre", ""),
                                key="iv_nombre",
                            )
                            iv_elementos = st.text_input(
                                "Elementos recurrentes (separados por coma)",
                                value=", ".join(id_visual.get("elementos_recurrentes", [])),
                                placeholder="glowing crystal, floating screens",
                                key="iv_elementos",
                            )
                        with col_iv2:
                            iv_paleta = st.text_input(
                                "Paleta de colores",
                                value=id_visual.get("paleta_colores", ""),
                                placeholder="deep purple, electric blue, warm gold",
                                key="iv_paleta",
                            )
                            iv_fondo = st.text_area(
                                "Fondo/entorno base (EN INGLES, opcional)",
                                value=id_visual.get("fondo_base", ""),
                                placeholder="modern dark studio with ambient neon lighting",
                                key="iv_fondo",
                                height=80,
                            )
                            iv_ilum = st.text_input(
                                "Iluminacion",
                                value=id_visual.get("iluminacion", ""),
                                placeholder="dramatic side lighting with rim light",
                                key="iv_ilum",
                            )

                        if st.button("💾  Guardar identidad visual", key="btn_save_iv", use_container_width=True):
                            try:
                                payload_iv = {
                                    "estilo_slug": iv_slug,
                                    "personaje_principal": iv_personaje.strip() or None,
                                    "personaje_nombre": iv_nombre.strip() or None,
                                    "elementos_recurrentes": [e.strip() for e in iv_elementos.split(",") if e.strip()] if iv_elementos else [],
                                    "paleta_colores": iv_paleta.strip() or None,
                                    "fondo_base": iv_fondo.strip() or None,
                                    "iluminacion": iv_ilum.strip() or None,
                                }
                                if iv_slug == "custom":
                                    payload_iv["prompt_template"] = iv_custom_tpl
                                    payload_iv["negative_prompt"] = iv_custom_neg

                                api_client.set_identidad_visual(canal_sel, payload_iv)
                                st.success("✅  Identidad visual guardada")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {str(e)}")

                    # ── Top Videos ──
                    top_videos = canal_data.get("top_videos", [])
                    if top_videos:
                        with st.expander(f"🏆  Top {len(top_videos)} videos por vistas"):
                            for i, v in enumerate(top_videos, 1):
                                vistas = f"{v.get('vistas', 0):,}"
                                likes = f"{v.get('likes', 0):,}"
                                st.markdown(f"**{i}.** {v.get('titulo', '-')} — {vistas} vistas · {likes} likes")

                    # ── Competidores ──
                    competidores = canal_data.get("competidores", [])
                    with st.expander(f"⚔️  Competidores ({len(competidores)})", expanded=False):
                        if competidores:
                            for comp in competidores:
                                subs = f"{comp.get('suscriptores', 0):,}" if comp.get('suscriptores') else '?'
                                st.markdown(f"**{comp.get('nombre', '?')}** — {subs} subs")
                                tops = comp.get("top_videos", [])
                                if tops:
                                    for tv in tops[:3]:
                                        st.markdown(f"  - {tv.get('titulo', '-')} ({tv.get('vistas', 0):,} vistas)")

                        col_comp1, col_comp2 = st.columns([3, 1])
                        with col_comp1:
                            comp_input = st.text_input("Agregar competidor (@handle o URL)", key="comp_input_ci")
                        with col_comp2:
                            st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
                            if st.button("➕  Agregar", key="btn_add_comp", use_container_width=True):
                                if comp_input.strip():
                                    with st.spinner("Escaneando competidor..."):
                                        try:
                                            result = api_client.agregar_competidor(canal_sel, comp_input.strip())
                                            st.success(f"✅  Competidor agregado: {result.get('nombre', '')}")
                                        except Exception as e:
                                            st.error(f"Error: {str(e)}")

                    # ── Tendencias y Brechas ──
                    tendencias = canal_data.get("tendencias_nicho", [])
                    brechas = canal_data.get("brechas_contenido", [])
                    if tendencias or brechas:
                        with st.expander("📈  Tendencias y brechas de contenido", expanded=False):
                            if tendencias:
                                st.markdown("**Tendencias del nicho:**")
                                for t in tendencias:
                                    st.markdown(f"  - {t}")
                            if brechas:
                                st.markdown("**Brechas de contenido (oportunidades):**")
                                for b in brechas:
                                    st.markdown(f"  - {b}")

                    # ── Ideas de Video ──
                    ideas = canal_data.get("ideas_sugeridas", [])
                    with st.expander(f"💡  Ideas de video sugeridas ({len(ideas)})", expanded=bool(ideas)):
                        col_ideas_r, _ = st.columns([1, 3])
                        with col_ideas_r:
                            if st.button("🔄  Re-generar ideas", key="btn_refresh_ideas", use_container_width=True):
                                with st.spinner("Generando ideas..."):
                                    try:
                                        ideas = api_client.refrescar_ideas(canal_sel)
                                        st.success("✅  Ideas actualizadas")
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")

                        if ideas:
                            for i, idea in enumerate(ideas, 1):
                                score = idea.get("potencial_viral", 0)
                                st.markdown(f"""**{i}. {idea.get('titulo_sugerido', '-')}**
  - Potencial viral: **{score}/10** · Formato: {idea.get('formato_recomendado', '-')} · ~{idea.get('duracion_sugerida_min', '?')} min
  - {idea.get('razon', '')}""")
                                if st.button(f"🚀  Usar esta idea", key=f"btn_idea_{i}"):
                                    s["nicho"] = perfil.get("nicho_principal", "")
                                    s["titulo_elegido"] = idea.get("titulo_sugerido", "")
                                    s["canal_id_pipeline"] = canal_sel
                                    st.success(f"✅  Idea cargada. Ve al tab Guión para crear el video.")
                        else:
                            st.info("Conecta un canal y espera el análisis para ver ideas de video.")

                    # ── Quota ──
                    try:
                        quota = api_client.quota_hoy()
                        usadas = quota.get("unidades_usadas", 0)
                        limite = quota.get("limite", 10000)
                        pct = round(usadas / limite * 100, 1) if limite else 0
                        st.markdown(f'<div style="font-size:.75rem;color:var(--text3);margin-top:12px">📊 Quota YouTube API: {usadas:,} / {limite:,} unidades ({pct}%)</div>', unsafe_allow_html=True)
                    except Exception:
                        pass

# ══════════════════════════════════════════════════════════════
# TAB 1 — GUIÓN (Modo Pro — Sistema de 3 Fases)
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="step-title">Guión — Modo Pro</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-sub">Sistema de 3 fases: análisis del nicho con videos virales → ingeniería de títulos → guión con estructura viral probada.</div>', unsafe_allow_html=True)

    # ── Selector de canal (si hay canales conectados) ──
    if API_DISPONIBLE:
        try:
            canales_guion = api_client.listar_canales()
        except Exception:
            canales_guion = []
        if canales_guion:
            opciones_g = {"": "— Sin canal (modo libre) —"}
            opciones_g.update({c["canal_id"]: f"📊 {c['nombre']} ({c.get('nicho', 'sin nicho')})" for c in canales_guion})
            canal_guion = st.selectbox(
                "Canal", options=list(opciones_g.keys()),
                format_func=lambda x: opciones_g.get(x, x),
                index=list(opciones_g.keys()).index(s.get("canal_id_pipeline", "")) if s.get("canal_id_pipeline", "") in opciones_g else 0,
                key="canal_guion_sel",
            )
            if canal_guion:
                s["canal_id_pipeline"] = canal_guion
                try:
                    canal_info = api_client.estado_canal(canal_guion)
                    nicho_canal = canal_info.get("perfil", {}).get("nicho_principal", "")
                    if nicho_canal and not s.get("nicho"):
                        s["nicho"] = nicho_canal
                except Exception:
                    pass

    # Barra de fases
    fase_actual = 1
    if s.get("nicho_analizado"): fase_actual = 2
    if s.get("titulo_elegido"):  fase_actual = 3
    if s.get("guion_aprobado"):  fase_actual = 4
    fases_html = ""
    for i,(num,nombre) in enumerate([("1","Analizar nicho"),("2","Elegir título"),("3","Generar guión")],1):
        cls = "done" if fase_actual > i else ("active" if fase_actual == i else "")
        ic  = "✓" if fase_actual > i else num
        fases_html += f'<div class="ps {cls}"><span class="psn">{ic}</span>{nombre}</div>'
        if i < 3: fases_html += '<span class="pa">›</span>'
    st.markdown(f'<div class="pip" style="margin:0 -32px 24px;padding:0 32px">{fases_html}</div>', unsafe_allow_html=True)

    # ══ FASE 1 ════════════════════════════════════════════════
    with st.expander("📊  Fase 1 — Analizar nicho", expanded=(fase_actual==1)):
        st.markdown('<div class="section-label">Define tu nicho</div>', unsafe_allow_html=True)
        col_n1,col_n2 = st.columns([2,1],gap="large")
        with col_n1:
            nicho_input = st.text_input("Nicho del canal",
                value=s.get("nicho",""),
                placeholder="ej: historias de exploradores, auto-mejora masculina, misterios del universo...",
                key="nicho_inp")
            idioma_canal = st.selectbox("Idioma del canal",["Español","Inglés","Portugués"])
        with col_n2:
            st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
            buscar_virales = st.checkbox("🔍 Analizar videos virales del nicho",value=True,
                help="Groq analiza patrones de videos exitosos en este nicho para adaptar los frameworks")
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

        if st.button("📊  Analizar nicho y detectar frameworks",use_container_width=True):
            if not GROQ_KEY and not API_DISPONIBLE: st.error("❌  GROQ_API_KEY no encontrada en `.env`")
            elif not nicho_input.strip(): st.error("❌  Ingresa el nicho del canal")
            else:
                s["nicho"] = nicho_input
                s["idioma_canal"] = idioma_canal
                with st.spinner("🔍  Analizando nicho y patrones virales..."):
                    try:
                        if API_DISPONIBLE:
                            proy_id = f"proy_{s['nombre_proyecto']}"
                            try:
                                api_client.crear_proyecto(proy_id, s['nombre_proyecto'])
                            except Exception:
                                pass
                            output = api_client.analizar_nicho(proy_id, nicho_input)
                            analisis = {
                                "nicho": nicho_input,
                                "idioma": idioma_canal,
                                "analisis": {"descripcion": "", "tipo_audiencia": "",
                                             "mejor_formato": "", "duracion_ideal": ""},
                                "triggers_emocionales": [],
                                "palabras_power": [],
                                "frameworks_titulo": [],
                                "patrones_virales": output.get("patrones_virales", []),
                            }
                            s["analisis_nicho"]  = analisis
                            s["nicho_analizado"] = True
                            st.success(f"✅  Nicho analizado via agentes — {len(output.get('patrones_virales',[]))} patrones detectados")
                            st.rerun()
                        else:
                            from groq import Groq
                            c = Groq(api_key=GROQ_KEY)
                            buscar_txt = f"""
Analiza los videos más virales del nicho "{nicho_input}" en YouTube.
Considera: títulos que generan más clics, emociones dominantes,
formatos que funcionan mejor, palabras power más repetidas.
Usa ese análisis para adaptar los frameworks.""" if buscar_virales else ""

                            prompt_a = f"""Eres estratega experto en canales de YouTube virales.
Analiza el nicho: "{nicho_input}" para canal en {idioma_canal}.
{buscar_txt}
Responde SOLO en JSON válido sin markdown:
{{"nicho":"{nicho_input}","idioma":"{idioma_canal}",
"analisis":{{"descripcion":"descripción del nicho en 2 líneas","tipo_audiencia":"espectador típico",
"mejor_formato":"formato más efectivo","duracion_ideal":"duración óptima"}},
"triggers_emocionales":[{{"emocion":"nombre","descripcion":"por qué funciona","intensidad":"alta/media"}}],
"palabras_power":["p1","p2","p3","p4","p5","p6","p7","p8"],
"frameworks_titulo":[{{"nombre":"nombre fw","plantilla":"plantilla con ___","ejemplo":"ejemplo concreto en este nicho","por_que_funciona":"explicación psicológica","trigger":"emoción"}}],
"patrones_virales":["patrón 1","patrón 2","patrón 3","patrón 4","patrón 5"]}}
Genera 5 triggers, 8 palabras power, 8 frameworks y 5 patrones específicos para "{nicho_input}"."""

                            resp = c.chat.completions.create(
                                model="llama-3.3-70b-versatile",
                                messages=[{"role":"user","content":prompt_a}],
                                temperature=0.4,max_tokens=3000)
                            raw = resp.choices[0].message.content.strip()
                            if "```" in raw:
                                for p in raw.split("```"):
                                    p=p.strip()
                                    if p.startswith("{"): raw=p; break
                                    elif p.startswith("json"): raw=p[4:].strip(); break
                            analisis = json.loads(raw)
                            s["analisis_nicho"]  = analisis
                            s["nicho_analizado"] = True
                            st.success(f"✅  Nicho analizado — {len(analisis['frameworks_titulo'])} frameworks detectados")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌  {str(e)}")

    if s.get("nicho_analizado") and s.get("analisis_nicho"):
        an = s["analisis_nicho"]
        with st.expander("📋  Ver análisis del nicho",expanded=False):
            c1,c2 = st.columns(2)
            with c1:
                st.markdown(f"**🎯 Nicho:** {an.get('nicho','')}")
                st.markdown(f"**👥 Audiencia:** {an['analisis'].get('tipo_audiencia','')}")
                st.markdown(f"**📹 Formato ideal:** {an['analisis'].get('mejor_formato','')}")
                st.markdown(f"**⏱️ Duración:** {an['analisis'].get('duracion_ideal','')}")
                st.markdown("**⚡ Triggers emocionales:**")
                for t in an.get("triggers_emocionales",[]):
                    st.markdown(f"  • **{t['emocion']}** ({t['intensidad']}) — {t['descripcion']}")
            with c2:
                st.markdown("**💥 Palabras power:**")
                st.markdown("  "+"  ·  ".join(f"`{p}`" for p in an.get("palabras_power",[])))
                st.markdown("**🔍 Patrones virales:**")
                for pat in an.get("patrones_virales",[]): st.markdown(f"  • {pat}")

    # ══ FASE 2 ════════════════════════════════════════════════
    if s.get("nicho_analizado"):
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        with st.expander("🎯  Fase 2 — Ingeniería de títulos",expanded=(fase_actual==2)):
            st.markdown('<div class="section-label">Genera y elige tu título</div>', unsafe_allow_html=True)
            an = s.get("analisis_nicho",{})
            frameworks = an.get("frameworks_titulo",[])

            col_t1,col_t2 = st.columns([2,1],gap="large")
            with col_t1:
                tema_video = st.text_input("Tema específico del video",
                    value=s.get("tema_video",""),
                    placeholder="ej: señales de que alguien te admira en secreto, hábitos que destruyen tu energía...",
                    key="tema_inp")
                n_titulos = st.slider("Títulos a generar",5,15,10)
            with col_t2:
                st.markdown('<div class="section-label" style="margin-top:28px">Frameworks del nicho</div>', unsafe_allow_html=True)
                for fw in frameworks[:4]: st.caption(f"• {fw['nombre']}: `{fw['plantilla']}`")
            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

            if st.button("🎯  Generar títulos virales",use_container_width=True):
                if not tema_video.strip(): st.error("❌  Ingresa el tema del video")
                else:
                    s["tema_video"] = tema_video
                    with st.spinner(f"🎯  Generando {n_titulos} títulos..."):
                        try:
                            from groq import Groq
                            c = Groq(api_key=GROQ_KEY)
                            fw_str  = json.dumps(frameworks,ensure_ascii=False,indent=2)
                            tr_str  = json.dumps(an.get("triggers_emocionales",[]),ensure_ascii=False)
                            pw_str  = ", ".join(an.get("palabras_power",[]))

                            prompt_t = f"""Experto en títulos virales YouTube.
Nicho: "{s["nicho"]}" | Idioma: {s.get("idioma_canal","Español")} | Tema: "{tema_video}"
FRAMEWORKS: {fw_str}
TRIGGERS: {tr_str}
PALABRAS POWER: {pw_str}
Genera {n_titulos} títulos virales para "{tema_video}" en nicho "{s["nicho"]}".
REGLAS: 1)Usar framework del nicho 2)Incluir palabra power cuando natural
3)Curiosity gap obligatorio 4)Máx 60 chars 5)En {s.get("idioma_canal","Español")}
SOLO JSON sin markdown:
{{"titulos":[{{"titulo":"título completo","framework_usado":"nombre fw","trigger":"emoción",
"por_que_funciona":"explicación 1 línea","potencial_viral":"alto/medio","ctr_estimado":"% CTR"}}]}}"""

                            resp = c.chat.completions.create(
                                model="llama-3.3-70b-versatile",
                                messages=[{"role":"user","content":prompt_t}],
                                temperature=0.7,max_tokens=2000)
                            raw = resp.choices[0].message.content.strip()
                            if "```" in raw:
                                for p in raw.split("```"):
                                    p=p.strip()
                                    if p.startswith("{"): raw=p; break
                                    elif p.startswith("json"): raw=p[4:].strip(); break
                            resultado = json.loads(raw)
                            s["titulos_generados"] = resultado["titulos"]
                            st.success(f"✅  {len(resultado['titulos'])} títulos generados")
                            st.rerun()
                        except Exception as e: st.error(f"❌  {str(e)}")

            if s.get("titulos_generados"):
                st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
                st.markdown('<div class="section-label">Elige el mejor título</div>', unsafe_allow_html=True)
                for i,t in enumerate(s["titulos_generados"]):
                    pot = t.get("potencial_viral","medio")
                    col_pot = "#1DB954" if pot=="alto" else "#FF9500"
                    col_tit,col_btn = st.columns([5,1])
                    with col_tit:
                        st.markdown(f"""<div style="background:var(--dark2);border:1px solid var(--border);
border-radius:8px;padding:11px 14px;margin-bottom:7px;border-left:3px solid {col_pot}">
<div style="font-size:.87rem;font-weight:600;color:var(--text);margin-bottom:3px">{t["titulo"]}</div>
<div style="font-size:.7rem;color:var(--text3);display:flex;gap:14px;flex-wrap:wrap">
<span>📐 {t.get("framework_usado","")}</span><span>⚡ {t.get("trigger","")}</span>
<span>📊 CTR ~{t.get("ctr_estimado","—")}</span>
<span style="color:{col_pot}">● {pot.upper()}</span></div>
<div style="font-size:.7rem;color:var(--text2);margin-top:3px;font-style:italic">{t.get("por_que_funciona","")}</div>
</div>""",unsafe_allow_html=True)
                    with col_btn:
                        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
                        if st.button("✅",key=f"use_t_{i}",use_container_width=True):
                            s["titulo_elegido"]    = t["titulo"]
                            s["titulo_framework"]  = t.get("framework_usado","")
                            s["titulo_trigger"]    = t.get("trigger","")
                            st.rerun()

                st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
                titulo_custom = st.text_input("O escribe tu propio título:",placeholder="Título personalizado...")
                if titulo_custom and st.button("✅  Usar este título",use_container_width=True,key="use_custom"):
                    s["titulo_elegido"]   = titulo_custom
                    s["titulo_framework"] = "personalizado"
                    st.rerun()

    if s.get("titulo_elegido"):
        st.markdown(f"""<div style="background:var(--green-dim);border:1px solid rgba(29,185,84,.25);
border-radius:10px;padding:12px 16px;margin:10px 0;display:flex;align-items:center;gap:10px">
<span style="font-size:1.1rem">📺</span>
<div><div style="font-size:.68rem;color:var(--green);text-transform:uppercase;letter-spacing:.8px;
font-weight:700;margin-bottom:2px">Título elegido</div>
<div style="font-size:.9rem;font-weight:700;color:var(--text)">{s["titulo_elegido"]}</div></div>
</div>""",unsafe_allow_html=True)

    # ══ FASE 3 ════════════════════════════════════════════════
    if s.get("titulo_elegido"):
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        with st.expander("✍️  Fase 3 — Generar guión",expanded=(fase_actual==3)):
            st.markdown('<div class="section-label">Configuración del guión</div>', unsafe_allow_html=True)
            an = s.get("analisis_nicho",{})
            col_g1,col_g2 = st.columns(2,gap="large")
            with col_g1:
                dur_guion = st.selectbox("Duración objetivo",
                    ["5 min (~800 palabras)","10 min (~1,600 palabras)",
                     "15 min (~2,400 palabras)","20 min (~3,200 palabras)"])
                n_puntos = st.slider("Puntos en la lista",5,12,7)
                tono = st.selectbox("Tono",
                    ["Conversacional y cercano — como un amigo experto",
                     "Autoritativo y directo — experto con datos",
                     "Narrativo y dramático — storytelling",
                     "Motivacional e inspirador — coach"])
                tono_id = tono.split(" — ")[0]
            with col_g2:
                inc_datos  = st.checkbox("📊 Incluir datos y estadísticas",value=True)
                inc_midret = st.checkbox("🎯 Mid-video retention device",value=True)
                inc_ejemplos = st.checkbox("💬 Ejemplos y diálogos",value=True)
                cta_tipo = st.selectbox("CTA al final",
                    ["Suscribirse + ver otro video","Comentar su experiencia",
                     "Guardar el video","Aplicar + suscribirse"])
            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

            if st.button("✍️  Generar guión completo",use_container_width=True):
                with st.spinner("✍️  Generando guión con estructura viral..."):
                    try:
                        from groq import Groq
                        c = Groq(api_key=GROQ_KEY)
                        palabras_obj = int(dur_guion.split("~")[1].split(" ")[0].replace(",",""))
                        tr_str = ", ".join([t["emocion"] for t in an.get("triggers_emocionales",[])])
                        pw_str = ", ".join(an.get("palabras_power",[]))
                        pat_str = " | ".join(an.get("patrones_virales",[]))

                        mid_txt = (f'A mitad del guión, antes del punto {n_puntos}, agrega:\n'
                                   f'"Y el punto {n_puntos}... este es el que la mayoría pasa por alto. Quédate."') if inc_midret else ""

                        prompt_g = f"""Ghostwriter experto en YouTube viral.
NICHO: "{s["nicho"]}" | TÍTULO: "{s["titulo_elegido"]}" | IDIOMA: {s.get("idioma_canal","Español")}
DURACIÓN: {dur_guion} (~{palabras_obj:,} palabras) | PUNTOS: {n_puntos} | TONO: {tono_id}
TRIGGERS: {tr_str} | PALABRAS POWER: {pw_str}
PATRONES VIRALES: {pat_str}
AUDIENCIA: {an.get("analisis",{}).get("tipo_audiencia","general")}

ESTRUCTURA OBLIGATORIA:
1. HOOK (10-15s): escenario relatable → pregunta directa → promesa → transición
2. {n_puntos} PUNTOS, cada uno con:
   a) Título corto del punto
   b) Ejemplo relatable o micro-historia
   c) Explicación psicológica simplificada
   d) Takeaway claro y accionable
   e) Reframe de identidad del espectador
3. {mid_txt}
4. CIERRE: resumen + tease próximo video + {cta_tipo}

ESTILO: {tono_id} | {'Incluye datos específicos.' if inc_datos else ''} {'Incluye micro-ejemplos y diálogos breves.' if inc_ejemplos else ''}
Frases cortas directas + párrafos de explicación. Lenguaje conversacional, nunca académico.
~{palabras_obj:,} palabras. Solo el texto listo para narrar, continuo y fluido."""

                        resp = c.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role":"user","content":prompt_g}],
                            temperature=0.7,max_tokens=4000)
                        guion_txt = resp.choices[0].message.content.strip()
                        parrafos = [p.strip() for p in guion_txt.split("\n\n") if p.strip()]
                        escenas  = [{"numero":i+1,"narracion":p,"descripcion_visual":p[:80]+"..."}
                                    for i,p in enumerate(parrafos)]
                        s["guion_aprobado"] = {
                            "titulo":  s["titulo_elegido"],
                            "hook":    parrafos[0][:120]+"..." if parrafos else "",
                            "escenas": escenas,
                            "tags":    [s["nicho"]],
                            "descripcion_youtube": f"Video sobre {s.get('tema_video','')}"
                        }
                        s["guion_texto_completo"] = guion_txt
                        st.success(f"✅  Guión generado — {len(escenas)} párrafos · {len(guion_txt.split())} palabras")
                        st.rerun()
                    except Exception as e: st.error(f"❌  {str(e)}")

    if s.get("guion_aprobado") and s.get("guion_texto_completo"):
        g = s["guion_aprobado"]
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("📝 Estado","Generado ✅")
        c2.metric("🎬 Párrafos",len(g["escenas"]))
        c3.metric("📝 Palabras",len(s["guion_texto_completo"].split()))
        c4.metric("⏱️ ~Duración",f"{len(s['guion_texto_completo'].split())//160} min")

        with st.expander("📖  Ver guión completo",expanded=False):
            st.markdown(f"""<div style="background:var(--dark3);border-radius:10px;
padding:18px;font-size:.83rem;line-height:1.85;color:var(--text2);
max-height:380px;overflow-y:auto;white-space:pre-wrap">
{s["guion_texto_completo"]}</div>""",unsafe_allow_html=True)

        col_b1,col_b2 = st.columns(2)
        with col_b1:
            if st.button("✅  Aprobar guión → Audio",use_container_width=True):
                st.success("✅  Guión aprobado — continúa en Audio →")
                st.rerun()
        with col_b2:
            if st.button("🔄  Regenerar guión",use_container_width=True,key="regen_g"):
                s["guion_aprobado"] = None
                s["guion_texto_completo"] = None
                st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 2 — AUDIO
# ══════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="step-title">Audio</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-sub">Genera la narración con voz natural y descarga música de fondo libre de derechos para YouTube.</div>', unsafe_allow_html=True)

    if not s['guion_aprobado']:
        st.info("⚠️  Aprueba un guión primero en el tab Guión")
    else:
        g = s['guion_aprobado']
        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.markdown('<div class="section-label">Narración</div>', unsafe_allow_html=True)
            st.markdown('<div class="card"><div class="card-title">🎙️ Edge TTS</div><div class="card-sub">400+ voces naturales en español, inglés y portugués — gratis y sin límites de uso</div></div>', unsafe_allow_html=True)
            st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

            idioma = st.selectbox("Idioma", ["Español","Inglés","Portugués"])
            voces_m = {
                "Español": ["es-CO-SalomeNeural — Colombia (F)","es-CO-GonzaloNeural — Colombia (M)",
                            "es-MX-DaliaNeural — México (F)","es-MX-JorgeNeural — México (M)",
                            "es-ES-ElviraNeural — España (F)","es-ES-AlvaroNeural — España (M)",
                            "es-AR-ElenaNeural — Argentina (F)","es-AR-TomasNeural — Argentina (M)"],
                "Inglés":  ["en-US-JennyNeural — US (F)","en-US-GuyNeural — US (M)",
                            "en-GB-SoniaNeural — UK (F)","en-GB-RyanNeural — UK (M)",
                            "en-AU-NatashaNeural — AU (F)","en-AU-WilliamNeural — AU (M)"],
                "Portugués":["pt-BR-FranciscaNeural — Brasil (F)","pt-BR-AntonioNeural — Brasil (M)"]
            }
            voz_d  = st.selectbox("Voz", voces_m[idioma])
            voz_id = voz_d.split(" — ")[0]
            vel    = st.select_slider("Velocidad de narración",
                                       ["-20%","-10%","Normal","+10%","+20%"], value="Normal")
            rate_m = {"-20%":"-20%","-10%":"-10%","Normal":"+0%","+10%":"+10%","+20%":"+20%"}
            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

            if st.button("▶️  Generar narración", use_container_width=True):
                try:
                    import edge_tts
                    adir = Path(f"proyectos/{nombre_proyecto}/audio")
                    adir.mkdir(parents=True, exist_ok=True)
                    prog = st.progress(0); stat = st.empty()
                    for i,e in enumerate(g['escenas']):
                        stat.caption(f"🎙️  Escena {i+1}/{len(g['escenas'])}...")
                        ruta = adir/f"escena_{i+1:02d}.mp3"
                        async def gen_a(txt,r,v,ra):
                            com = edge_tts.Communicate(txt,v,rate=ra)
                            await com.save(str(r))
                        asyncio.run(gen_a(e['narracion'],ruta,voz_id,rate_m[vel]))
                        prog.progress((i+1)/len(g['escenas']))
                    stat.empty()
                    s['audio_generado'] = True
                    st.success(f"✅  {len(g['escenas'])} audios con {voz_d.split(' — ')[1]}")
                except ImportError:
                    st.error("❌  Ejecuta: `py -m pip install edge-tts`")
                except Exception as e:
                    st.error(f"❌  {str(e)}")

        with col2:
            st.markdown('<div class="section-label">Música de fondo</div>', unsafe_allow_html=True)
            st.markdown('<div class="card"><div class="card-title">🎵 Pixabay Music</div><div class="card-sub">Música libre de derechos, 100% legal para monetizar en YouTube. Descarga automática por mood</div></div>', unsafe_allow_html=True)
            st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

            mood   = st.selectbox("Mood del video",
                                   ["epic","calm","mysterious","inspiring",
                                    "dramatic","ambient","happy","sad","action"])
            vol_m  = st.slider("Volumen de la música (relativo a la voz)", 5, 40, 15)
            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

            if st.button("🎵  Buscar y descargar", use_container_width=True):
                if not PIXABAY_KEY:
                    st.warning("⚠️  PIXABAY_KEY no encontrada en `.env`")
                else:
                    with st.spinner(f"🔍  Buscando música '{mood}'..."):
                        try:
                            data = requests.get(
                                f"https://pixabay.com/api/music/?key={PIXABAY_KEY}&q={mood}&per_page=5",
                                timeout=10).json()
                            if data.get('hits'):
                                au = data['hits'][0].get('audio',{}).get('url','')
                                if au:
                                    mdir = Path(f"proyectos/{nombre_proyecto}/musica")
                                    mdir.mkdir(parents=True, exist_ok=True)
                                    r = requests.get(au, stream=True, timeout=30)
                                    with open(mdir/"background.mp3",'wb') as f:
                                        for ch in r.iter_content(8192): f.write(ch)
                                    s['musica_lista'] = True
                                    st.success(f"✅  Música '{mood}' descargada")
                        except Exception as e:
                            st.error(f"❌  {str(e)}")

            st.markdown("**O sube tu propio MP3:**")
            mp3_up = st.file_uploader("Arrastra aquí tu MP3 libre de derechos",
                                       type=['mp3'], label_visibility="collapsed")
            if mp3_up:
                mdir = Path(f"proyectos/{nombre_proyecto}/musica")
                mdir.mkdir(parents=True, exist_ok=True)
                (mdir/"background.mp3").write_bytes(mp3_up.read())
                s['musica_lista'] = True
                st.success(f"✅  Música subida: {mp3_up.name}")

# ══════════════════════════════════════════════════════════════
# TAB 3 — KAGGLE
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="step-title">Kaggle</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-sub">Lanza la generación de imágenes y videos en Kaggle. La GPU genera todas las escenas automáticamente.</div>', unsafe_allow_html=True)

    if not s['guion_aprobado']:
        st.info("⚠️  Aprueba un guión primero")
    else:
        g = s['guion_aprobado']
        col1, col2 = st.columns([1,1], gap="large")

        with col1:
            st.markdown('<div class="section-label">Parámetros</div>', unsafe_allow_html=True)

            from shared.visual_styles import CATALOGO_ESTILOS, CATEGORIAS, obtener_estilo

            cat_sel = st.selectbox("Categoria de estilo", [c["nombre"] for c in CATEGORIAS],
                key="kat_cat_sel")
            cat_slug = next((c["slug"] for c in CATEGORIAS if c["nombre"] == cat_sel), None)
            estilos_filtrados = [e for e in CATALOGO_ESTILOS if e["categoria"] == cat_slug]

            canal_estilo_default = None
            if s.get("canal_id_pipeline") and API_DISPONIBLE:
                try:
                    canal_info_k = api_client.estado_canal(s["canal_id_pipeline"])
                    id_vis = canal_info_k.get("identidad_visual", {})
                    if id_vis.get("configurado"):
                        canal_estilo_default = id_vis.get("estilo_slug")
                        st.caption(f"Estilo del canal: **{canal_estilo_default}** (puedes hacer override)")
                except Exception:
                    pass

            opciones_estilo = [f"{e['slug']} — {e['nombre']}" for e in estilos_filtrados]
            estilo = st.selectbox("Estilo visual", opciones_estilo, key="kat_estilo_sel")
            estilo_id = estilo.split(" — ")[0] if estilo else "cinematic"

            estilo_info = obtener_estilo(estilo_id)
            if estilo_info:
                st.caption(f"Caso de uso: {estilo_info['caso_uso']}")

            with st.expander("⚙️  Configuración avanzada"):
                c_mi, c_mv = st.columns(2)
                mi = c_mi.selectbox("Modelo imagen",
                    ["juggernaut — Mayor calidad","sdxl — Más rápido"])
                mv = c_mv.selectbox("Modelo video",
                    ["wan21 — Recomendado","skyreels — Máxima calidad",
                     "zoom — Más rápido","comparar — Prueba los 3"])
                mi_id = mi.split(" — ")[0]; mv_id = mv.split(" — ")[0]
                er = st.number_input("Escenas con video real (hook)",
                                      min_value=1, max_value=30, value=12,
                                      help="Las primeras N escenas tendrán video con IA (~primer minuto)")

            st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
            n_t = len(g['escenas'])
            c1,c2,c3 = st.columns(3)
            c1.metric("📝 Total", n_t)
            c2.metric("🎥 Video IA", min(er,n_t))
            c3.metric("🖼️ Zoom", max(n_t-er,0))

            st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
            hu = st.slider("⏱️  Horas GPU usadas esta semana", 0.0, 30.0, s['horas_usadas'], 0.5)
            s['horas_usadas'] = hu
            hr = 30.0-hu; pct = min((hu/30)*100,100)
            bc = "#1DB954" if pct<60 else ("#FF9500" if pct<85 else "#FF0000")
            st.markdown(f"""
            <div class="gpu-w">
              <div class="gpu-lbl">GPU Kaggle — Semana actual</div>
              <div class="gpu-bg"><div class="gpu-f" style="width:{pct:.0f}%;background:{bc}"></div></div>
              <div class="gpu-row">
                <span>Usado <b>{hu:.1f}h</b></span>
                <span>Restante <b style="color:{'#1DB954' if hr>5 else '#FF9500'}">{hr:.1f}h</b></span>
                <span>Total <b>30h</b></span>
              </div>
            </div>""", unsafe_allow_html=True)
            if hr > 0:
                mins = hr*60
                st.caption(f"~{int(mins/0.35)} imgs · ~{int(mins/2.5)} clips Wan 2.1 · ~{int(mins/35)} videos completos (240 esc.)")

        with col2:
            st.markdown('<div class="section-label">Lanzar y monitorear</div>', unsafe_allow_html=True)

            kernel_slug = st.text_input("Nombre del notebook en Kaggle",
                                         value="youtube-ai-studio-v7",
                                         help="Nombre exacto del notebook en tu cuenta de Kaggle")

            config_k = {
                "nombre_proyecto": nombre_proyecto, "estilo": estilo_id, "modo": "ambos",
                "modelo_imagen": mi_id, "modelo_video": mv_id, "escenas_video_real": er,
                "escenas": [e['descripcion_visual'] for e in g['escenas']],
                "narracion": [e['narracion'] for e in g['escenas']],
                "titulo": g.get('titulo',''), "tags": g.get('tags',[])
            }
            pdir2 = Path(f"proyectos/{nombre_proyecto}")
            pdir2.mkdir(parents=True, exist_ok=True)
            (pdir2/"config_kaggle.json").write_text(
                json.dumps(config_k, ensure_ascii=False, indent=2))

            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

            def get_headers():
                if KAGGLE_KEY.startswith('KGAT_'):
                    return {"Authorization":f"Bearer {KAGGLE_KEY}","Content-Type":"application/json"}
                import base64
                t = base64.b64encode(f"{KAGGLE_USER}:{KAGGLE_KEY}".encode()).decode()
                return {"Authorization":f"Basic {t}","Content-Type":"application/json"}

            cb1, cb2 = st.columns(2)
            with cb1:
                if st.button("🚀  Lanzar en Kaggle", use_container_width=True,
                              disabled=not(KAGGLE_USER and KAGGLE_KEY)):
                    with st.spinner("Lanzando..."):
                        try:
                            h = get_headers()
                            r = requests.get(
                                f"https://www.kaggle.com/api/v1/kernels/{KAGGLE_USER}/{kernel_slug}",
                                headers=h, timeout=10)
                            if r.status_code == 200:
                                r2 = requests.post(
                                    f"https://www.kaggle.com/api/v1/kernels/{KAGGLE_USER}/{kernel_slug}/run",
                                    headers=h, json={"gpu":True,"internet":True}, timeout=15)
                                if r2.status_code in [200,201]:
                                    s['kaggle_running'] = True
                                    s['kaggle_logs'].append("🚀 Notebook lanzado")
                                    st.success("✅  Lanzado en Kaggle")
                                else:
                                    s['kaggle_logs'].append(f"⚠️ Error {r2.status_code}")
                                    st.warning("⚠️  No se pudo lanzar automáticamente")
                                    with st.expander("📋  Copia este config al notebook"):
                                        st.code(json.dumps(config_k,ensure_ascii=False,indent=2),language="json")
                            elif r.status_code == 404:
                                st.error(f"❌  Notebook '{kernel_slug}' no encontrado")
                            else:
                                st.error(f"❌  Error {r.status_code}")
                        except Exception as e:
                            st.error(f"❌  {str(e)}")
                            with st.expander("📋  Config para copiar manualmente"):
                                st.code(json.dumps(config_k,ensure_ascii=False,indent=2),language="json")

            with cb2:
                if st.button("🔄  Ver estado", use_container_width=True):
                    if KAGGLE_USER and KAGGLE_KEY:
                        try:
                            h = get_headers()
                            r = requests.get(
                                f"https://www.kaggle.com/api/v1/kernels/{KAGGLE_USER}/{kernel_slug}",
                                headers=h, timeout=10)
                            if r.status_code == 200:
                                st_val = r.json().get('currentRunningVersion',{}).get('status','unknown')
                                icons  = {"complete":"✅","running":"⏳","error":"❌","queued":"🕐"}
                                st.info(f"{icons.get(st_val,'○')}  Estado: **{st_val}**")
                                if st_val == "complete": s['kaggle_running'] = False
                            else:
                                st.warning(f"No se pudo obtener estado ({r.status_code})")
                        except Exception as e:
                            st.error(f"❌  {str(e)}")

            st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
            st.markdown('<div class="section-label">Clips generados</div>', unsafe_allow_html=True)

            if st.button("📥  Descargar clips automáticamente", use_container_width=True):
                with st.spinner("Descargando outputs..."):
                    try:
                        h = get_headers()
                        r = requests.get(
                            f"https://www.kaggle.com/api/v1/kernels/{KAGGLE_USER}/{kernel_slug}/output",
                            headers=h, timeout=60, stream=True)
                        if r.status_code == 200:
                            dest = Path(f"proyectos/{nombre_proyecto}/videos")
                            dest.mkdir(parents=True, exist_ok=True)
                            zp = dest/"output.zip"
                            with open(zp,'wb') as f:
                                for ch in r.iter_content(8192): f.write(ch)
                            with zipfile.ZipFile(zp) as zf: zf.extractall(dest)
                            zp.unlink()
                            clips2 = list(dest.glob("*.mp4"))
                            s['kaggle_completado'] = True
                            st.success(f"✅  {len(clips2)} clips descargados")
                        else:
                            st.warning("⚠️  No hay outputs disponibles aún")
                    except Exception as e:
                        st.error(f"❌  {str(e)}")

            clips_up = st.file_uploader("O sube los clips manualmente",
                                         type=['mp4'], accept_multiple_files=True,
                                         label_visibility="visible")
            if clips_up:
                vdir2 = Path(f"proyectos/{nombre_proyecto}/videos")
                vdir2.mkdir(parents=True, exist_ok=True)
                for c in clips_up: (vdir2/c.name).write_bytes(c.read())
                s['kaggle_completado'] = True
                st.success(f"✅  {len(clips_up)} clips listos")

            if s['kaggle_logs']:
                st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
                lh = "".join(
                    f'<div class="{"lok" if "✅" in l or "🚀" in l else "lerr" if "❌" in l else "linf"}">{l}</div>'
                    for l in s['kaggle_logs'][-8:])
                st.markdown(f'<div class="mon">{lh}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# TAB 4 — SUBTÍTULOS
# ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="step-title">Subtítulos</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-sub">Genera subtítulos automáticos sincronizados con la narración. Whisper transcribe el audio y crea los archivos .SRT listos para el video final.</div>', unsafe_allow_html=True)

    if not s['audio_generado']:
        st.info("⚠️  Genera la narración primero en el tab Audio")
    else:
        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.markdown('<div class="section-label">Generación automática</div>', unsafe_allow_html=True)
            st.markdown('<div class="card"><div class="card-title">🤖 Whisper — OpenAI</div><div class="card-sub">Transcripción automática sincronizada con el audio. Genera archivos .SRT para cada escena</div></div>', unsafe_allow_html=True)
            st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

            modelo_w = st.selectbox("Modelo Whisper",
                ["base — Rápido (recomendado)","small — Más preciso","medium — Alta precisión"],
                help="'base' es suficiente para la mayoría de los casos")
            modelo_w_id = modelo_w.split(" — ")[0]

            idioma_w = st.selectbox("Idioma del audio",
                ["es — Español","en — Inglés","pt — Portugués","auto — Detectar automáticamente"])
            idioma_w_id = idioma_w.split(" — ")[0]
            if idioma_w_id == "auto": idioma_w_id = None

            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

            if st.button("💬  Generar subtítulos con Whisper", use_container_width=True):
                adir = Path(f"proyectos/{nombre_proyecto}/audio")
                sdir = Path(f"proyectos/{nombre_proyecto}/subs")
                sdir.mkdir(parents=True, exist_ok=True)
                audios_list = sorted(adir.glob("*.mp3")) if adir.exists() else []

                if not audios_list:
                    st.error("❌  No se encontraron archivos de audio")
                else:
                    try:
                        import whisper
                        prog = st.progress(0); stat = st.empty()
                        stat.caption(f"⏳  Cargando modelo Whisper {modelo_w_id}...")
                        model_wh = whisper.load_model(modelo_w_id)

                        for i, af in enumerate(audios_list):
                            stat.caption(f"💬  Transcribiendo {af.name} ({i+1}/{len(audios_list)})...")
                            opts = {"language": idioma_w_id} if idioma_w_id else {}
                            result = model_wh.transcribe(str(af), **opts)

                            # Generar SRT
                            srt_lines = []
                            for j, seg in enumerate(result['segments'], 1):
                                def fmt_t(t):
                                    h=int(t//3600); m=int((t%3600)//60)
                                    sc=int(t%60); ms=int((t%1)*1000)
                                    return f"{h:02d}:{m:02d}:{sc:02d},{ms:03d}"
                                srt_lines.append(str(j))
                                srt_lines.append(f"{fmt_t(seg['start'])} --> {fmt_t(seg['end'])}")
                                srt_lines.append(seg['text'].strip())
                                srt_lines.append("")

                            srt_path = sdir/f"{af.stem}.srt"
                            srt_path.write_text("\n".join(srt_lines), encoding='utf-8')
                            prog.progress((i+1)/len(audios_list))

                        stat.empty()
                        s['subs_generados'] = True
                        st.success(f"✅  {len(audios_list)} archivos SRT generados")

                    except ImportError:
                        st.error("❌  Ejecuta: `py -m pip install openai-whisper`")
                    except Exception as e:
                        st.error(f"❌  {str(e)}")

        with col2:
            st.markdown('<div class="section-label">Apariencia en el video</div>', unsafe_allow_html=True)
            st.markdown('<div class="card"><div class="card-title">🎨 Estilo de subtítulos</div><div class="card-sub">Configura la apariencia de los subtítulos en el video final</div></div>', unsafe_allow_html=True)
            st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

            fuente_s   = st.selectbox("Fuente", ["Arial","Impact","Verdana","Tahoma","Georgia"],
                                       help="Impact y Arial son las más usadas en YouTube")
            tamaño_s   = st.slider("Tamaño de fuente", 24, 72, 42)
            color_t    = st.color_picker("Color del texto", "#FFFFFF")
            color_b    = st.color_picker("Color del borde/sombra", "#000000")
            posicion_s = st.selectbox("Posición en pantalla", ["bottom","center","top"])
            estilo_s   = st.selectbox("Estilo", ["borde negro","fondo semitransparente","solo texto"])

            # Guardar config de subtítulos
            subs_config = {"fuente": fuente_s, "tamaño": tamaño_s,
                           "color_texto": color_t, "color_borde": color_b,
                           "posicion": posicion_s, "estilo": estilo_s}
            sdir2 = Path(f"proyectos/{nombre_proyecto}/subs")
            sdir2.mkdir(parents=True, exist_ok=True)
            (sdir2/"config_subs.json").write_text(json.dumps(subs_config, indent=2))

            if s['subs_generados']:
                srt_files = sorted(sdir2.glob("*.srt"))
                st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
                st.success(f"✅  {len(srt_files)} archivos SRT listos")
                if srt_files:
                    with st.expander("Ver subtítulos generados"):
                        sel = st.selectbox("Escena", [f.name for f in srt_files])
                        if sel:
                            content = (sdir2/sel).read_text(encoding='utf-8')
                            st.text(content[:500]+"..." if len(content)>500 else content)

# ══════════════════════════════════════════════════════════════
# TAB 5 — ENSAMBLAR
# ══════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<div class="step-title">Ensamblar</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-sub">Combina clips + narración + música + subtítulos en un video final listo para subir a YouTube.</div>', unsafe_allow_html=True)

    pdir3     = Path(f"proyectos/{nombre_proyecto}")
    ck        = sorted((pdir3/"videos").glob("*.mp4")) if (pdir3/"videos").exists() else []
    ak        = sorted((pdir3/"audio").glob("*.mp3"))  if (pdir3/"audio").exists()  else []
    mk_path   = (list((pdir3/"musica").glob("*.mp3"))[0]
                 if (pdir3/"musica").exists() and list((pdir3/"musica").glob("*.mp3")) else None)
    sk        = sorted((pdir3/"subs").glob("*.srt"))   if (pdir3/"subs").exists()   else []

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("🎬 Clips",   len(ck))
    c2.metric("🎙️ Audios",  len(ak))
    c3.metric("🎵 Música",  "✅" if mk_path else "⬜")
    c4.metric("💬 Subtítulos", len(sk))

    st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)

    if not ck:
        st.warning("⚠️  No hay clips de video. Completa el paso de Kaggle primero.")
    else:
        col1, col2 = st.columns(2, gap="large")
        with col1:
            st.markdown('<div class="section-label">Configuración de video</div>', unsafe_allow_html=True)
            usar_musica = st.checkbox("🎵 Agregar música de fondo", value=bool(mk_path))
            usar_subs   = st.checkbox("💬 Agregar subtítulos", value=bool(sk))
            vol_mus     = st.slider("Volumen música", 5, 40, 15)
            crossfade   = st.slider("Crossfade entre escenas (seg)", 0.0, 1.0, 0.3, 0.1)
            fps_f       = st.selectbox("FPS del video final", [24, 30], index=1)
            res_f       = st.selectbox("Resolución", ["1920x1080 — Full HD","1280x720 — HD"])

        with col2:
            st.markdown('<div class="section-label">Vista previa de configuración</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="card">
              <div class="card-title">📋 Resumen</div>
              <div style="font-size:.8rem;color:var(--text2);line-height:2">
                <div>🎬 Clips: <b style="color:var(--text)">{len(ck)}</b></div>
                <div>🎙️ Audios: <b style="color:var(--text)">{len(ak)}</b></div>
                <div>🎵 Música: <b style="color:var(--text)">{'Sí' if usar_musica and mk_path else 'No'}</b></div>
                <div>💬 Subtítulos: <b style="color:var(--text)">{'Sí' if usar_subs and sk else 'No'}</b></div>
                <div>⚡ FPS: <b style="color:var(--text)">{fps_f}</b></div>
                <div>🎯 Crossfade: <b style="color:var(--text)">{crossfade}s</b></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

        if st.button("🎬  ENSAMBLAR VIDEO FINAL", use_container_width=True):
            try:
                from moviepy.editor import (VideoFileClip, AudioFileClip,
                    CompositeAudioClip, concatenate_videoclips)

                odir = pdir3/"output"; odir.mkdir(exist_ok=True)
                prog = st.progress(0); stat = st.empty(); cp = []

                for i, c in enumerate(ck):
                    stat.caption(f"⚙️  {c.name} ({i+1}/{len(ck)})...")
                    v = VideoFileClip(str(c))
                    ap = (pdir3/"audio")/f"{c.stem}.mp3"
                    if ap.exists():
                        vz = AudioFileClip(str(ap))
                        if vz.duration > v.duration:
                            from moviepy.editor import vfx
                            v = v.fx(vfx.loop, duration=vz.duration)
                        else:
                            v = v.subclip(0, vz.duration)
                        if mk_path and usar_musica:
                            ms = AudioFileClip(str(mk_path)).volumex(vol_mus/100).subclip(0,vz.duration)
                            v = v.set_audio(CompositeAudioClip([vz,ms]))
                        else:
                            v = v.set_audio(vz)
                    cp.append(v)
                    prog.progress((i+1)/len(ck))

                stat.caption("🔗  Concatenando escenas...")
                fv = concatenate_videoclips(cp, method="compose",
                                             padding=-crossfade if crossfade>0 else 0)
                rf = odir/f"{nombre_proyecto}_FINAL.mp4"
                stat.caption("📤  Exportando video final...")
                fv.write_videofile(str(rf), fps=fps_f, codec="libx264",
                                    audio_codec="aac", verbose=False, logger=None)
                s['video_final'] = str(rf)
                stat.empty(); prog.empty()
                st.success("🎉  ¡Video final listo para YouTube!")
                with open(rf,"rb") as f:
                    st.download_button(
                        "⬇️  Descargar video final", f.read(),
                        file_name=f"{nombre_proyecto}_FINAL.mp4",
                        mime="video/mp4", use_container_width=True)

            except ImportError:
                st.error("❌  Ejecuta: `py -m pip install moviepy`")
            except Exception as e:
                st.error(f"❌  {str(e)}")
                st.exception(e)

        # Proyectos anteriores
        st.divider()
        st.markdown('<div class="section-label">Proyectos anteriores</div>', unsafe_allow_html=True)
        pbase = Path("proyectos")
        if pbase.exists():
            for p in sorted(pbase.iterdir(), reverse=True):
                if not p.is_dir(): continue
                cl = list((p/"videos").glob("*.mp4")) if (p/"videos").exists() else []
                fi = list((p/"output").glob("*.mp4")) if (p/"output").exists() else []
                sz = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())//1024//1024
                with st.expander(f"{'✅' if fi else '🔄'}  {p.name}  —  {sz} MB"):
                    c1,c2,c3 = st.columns(3)
                    c1.metric("Clips", len(cl))
                    c2.metric("Final", "✅" if fi else "⬜")
                    c3.metric("Tamaño", f"{sz} MB")
                    if fi:
                        with open(fi[0],"rb") as f:
                            st.download_button(f"⬇️  Descargar", f.read(),
                                file_name=fi[0].name, mime="video/mp4",
                                key=f"dl_{p.name}", use_container_width=True)

# ══════════════════════════════════════════════════════════════
# TAB 6 — MONITOR (Dashboard de monitoreo en tiempo real)
# ══════════════════════════════════════════════════════════════
with tab6:
    st.markdown('<div class="step-title">Monitor del Sistema</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-sub">Estado en tiempo real de todos los servicios, pipelines activos y logs del sistema.</div>', unsafe_allow_html=True)

    if not API_DISPONIBLE:
        st.warning("Los agentes no están conectados. Levanta los servicios con `python run_dev.py` para ver health y cola.")
        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    else:
        import api_client as _mc

        # ── Cargar datos ──
        _health_data = None
        _health_error = None

        try:
            _health_data = _mc.health_servicios()
        except Exception as _e:
            _health_error = str(_e)

        # ════════════════════════════════════════════════
        # SECCION 1 — Health del sistema
        # ════════════════════════════════════════════════
        st.markdown('<div class="section-label">Estado del sistema</div>', unsafe_allow_html=True)

        if _health_error:
            st.error(f"No se pudo obtener health de servicios: {_health_error}")
        elif _health_data:
            _score = _health_data.get("score", 0)
            _nivel = _health_data.get("nivel", "critico")
            _vivos = _health_data.get("vivos", 0)
            _total = _health_data.get("total", 0)
            _mem = _health_data.get("memoria_total_mb")
            _puede = _health_data.get("puede_pipeline", False)
            _criticos_caidos = _health_data.get("criticos_caidos", [])

            _col_score, _col_m1, _col_m2, _col_m3, _col_m4 = st.columns([1.2, 1, 1, 1, 1])

            with _col_score:
                st.markdown(f"""
                <div class="mon-score mon-{_nivel}">
                  <div class="mon-score-num">{_score}%</div>
                  <div class="mon-score-label">{_nivel.upper()}</div>
                </div>""", unsafe_allow_html=True)

            _col_m1.metric("Servicios", f"{_vivos}/{_total}")
            _col_m2.metric("Memoria", f"{_mem} MB" if _mem else "N/A")
            _col_m3.metric("Pipeline", "LISTO" if _puede else "NO LISTO")
            _col_m4.metric("Críticos caídos", len(_criticos_caidos))

            if _criticos_caidos:
                st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                _cc_html = " · ".join(
                    f'<span style="color:var(--red);font-family:\'JetBrains Mono\',monospace;font-size:.75rem">{c}</span>'
                    for c in _criticos_caidos
                )
                st.markdown(
                    f'<div style="background:var(--red-dim);border:1px solid rgba(255,0,0,.2);'
                    f'border-radius:8px;padding:10px 14px">'
                    f'<span style="font-size:.72rem;font-weight:700;color:var(--red);margin-right:8px">SERVICIOS CRÍTICOS CAÍDOS:</span>'
                    f'{_cc_html}</div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
            st.markdown('<div class="section-label">Departamentos</div>', unsafe_allow_html=True)

            _desglose = _health_data.get("desglose_departamentos", {})
            _servicios = _health_data.get("servicios", {})

            _DEPTO_LABELS = {
                "depto_0_inteligencia": ("🧠", "Inteligencia de Canal"),
                "depto_1_estrategia": ("🎯", "Estrategia"),
                "depto_2_guion": ("📝", "Guión"),
                "depto_3_visual": ("🎨", "Visual"),
                "depto_4_audio": ("🎙️", "Audio"),
                "depto_5_cierre": ("🎬", "Cierre & Publicación"),
                "orquestador": ("🧠", "Orquestador Central"),
            }
            _DEPTO_AGENTES = {
                "depto_0_inteligencia": ["0.1_escaner_canal", "0.2_analizador_canal", "0.3_monitor_mercado", "0.4_asesor_estrategico", "0.5_tracker_performance", "sub_orq_inteligencia"],
                "depto_1_estrategia": ["1.1_investigador", "1.2_copywriter", "1.3_director_arte", "1.4_generador_miniatura", "sub_orq_estrategia"],
                "depto_2_guion": ["2.1_guionista", "sub_orq_guion"],
                "depto_3_visual": ["3.1_prompt_maker", "3.2_generador_visual", "sub_orq_visual"],
                "depto_4_audio": ["4.1_locucion", "4.2_musica", "4.3_subtitulos", "sub_orq_audio"],
                "depto_5_cierre": ["5.1_editor", "5.2_seo", "5.3_compliance", "5.4_policy_monitor", "5.5_publicador", "sub_orq_cierre"],
                "orquestador": ["orquestador_central"],
            }
            _depto_keys = list(_DEPTO_LABELS.keys())
            for _row_deptos in [_depto_keys[:4], _depto_keys[4:]]:
                _cols = st.columns(len(_row_deptos), gap="medium")
                for _col, _dk in zip(_cols, _row_deptos):
                    with _col:
                        _icon, _label = _DEPTO_LABELS.get(_dk, ("⚙️", _dk))
                        _info = _desglose.get(_dk, {"vivos": 0, "total": 0})
                        _dv, _dt = _info["vivos"], _info["total"]
                        _dpct = round((_dv / _dt) * 100) if _dt > 0 else 0
                        _dcls = "mon-depto-ok" if _dpct == 100 else ("mon-depto-warn" if _dpct >= 50 else "mon-depto-down")
                        _dbar_color = "var(--green)" if _dpct == 100 else ("var(--orange)" if _dpct >= 50 else "var(--red)")
                        _srv_html = ""
                        for _aid in _DEPTO_AGENTES.get(_dk, []):
                            _srv = _servicios.get(_aid, {})
                            _srv_estado = _srv.get("estado", "caido")
                            _srv_color = "#1DB954" if _srv_estado == "ok" else ("#FF9500" if _srv_estado == "error" else "#FF0000")
                            _srv_puerto = _srv.get("puerto", "?")
                            _srv_mem = _srv.get("memoria_mb")
                            _srv_info = f":{_srv_puerto}" + (f" · {_srv_mem}MB" if _srv_mem else "")
                            _srv_html += f'<div class="mon-srv"><span class="mon-srv-dot" style="background:{_srv_color}"></span><span class="mon-srv-name">{_aid}</span><span class="mon-srv-info">{_srv_info}</span></div>'
                        st.markdown(f'<div class="mon-depto {_dcls}"><div class="mon-depto-head"><span class="mon-depto-name">{_icon} {_label}</span><span class="mon-depto-badge">{_dv}/{_dt}</span></div><div class="mon-depto-bar"><div class="mon-depto-fill" style="width:{_dpct}%;background:{_dbar_color}"></div></div>{_srv_html}</div>', unsafe_allow_html=True)
                st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

        # ════════════════════════════════════════════════
        # SECCION 2 — Cola de publicación
        # ════════════════════════════════════════════════
        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Cola de publicación</div>', unsafe_allow_html=True)

        _cola_data = _cached_pipeline_cola()
        _FASE_COLORS = {
            "estrategia": "var(--blue)", "guion": "var(--purple)",
            "visual": "var(--orange)", "audio": "var(--green)",
            "cierre": "#FF6B9D", "completado": "var(--green)",
            "publicado": "var(--green)", "error": "var(--red)",
            "desconocido": "var(--text4)",
        }
        _FASE_BG = {
            "estrategia": "var(--blue-dim)", "guion": "var(--purple-dim)",
            "visual": "var(--orange-dim)", "audio": "var(--green-dim)",
            "cierre": "rgba(255,107,157,.08)", "completado": "var(--green-dim)",
            "publicado": "var(--green-dim)", "error": "var(--red-dim)",
            "desconocido": "var(--dark5)",
        }
        _FASES_PIPELINE = ["estrategia", "guion", "visual", "audio", "cierre", "completado"]

        if not _cola_data:
            st.info("No se pudo obtener la cola de publicación.")
        else:
            _cq_buf = _cola_data.get("buffer", {})
            _cq_buf_actual = _cq_buf.get("actual", 0)
            _cq_buf_max = _cq_buf.get("max", 3)
            _cq_en_proc = _cola_data.get("en_proceso", [])
            _cq_listos = _cola_data.get("listos_para_publicar", [])
            _cq_pubs = _cola_data.get("publicados", [])
            _cq_errs = _cola_data.get("con_error", [])

            _cq_c1, _cq_c2, _cq_c3, _cq_c4, _cq_c5 = st.columns(5)
            _cq_c1.metric("En proceso", len(_cq_en_proc))
            _cq_c2.metric("Listos", len(_cq_listos))
            _cq_c3.metric("Publicados", len(_cq_pubs))
            _cq_c4.metric("Con error", len(_cq_errs))
            _cq_buf_color = "normal" if _cq_buf_actual < _cq_buf_max else "inverse"
            _cq_c5.metric("Buffer", f"{_cq_buf_actual}/{_cq_buf_max}", delta="lleno" if _cq_buf_actual >= _cq_buf_max else f"{_cq_buf_max - _cq_buf_actual} libres", delta_color=_cq_buf_color)

            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

            def _render_proyecto_card(_proj, _card_idx):
                _pid = _proj.get("proyecto_id", "?")
                _titulo = _proj.get("titulo", _pid)
                _fase = _proj.get("fase_actual", "desconocido")
                _canal = _proj.get("canal", "")
                _nicho = _proj.get("nicho", "")
                _agente = _proj.get("agente_actual")
                _progreso = _proj.get("progreso_pct", 0)
                _err_list = _proj.get("errores", [])
                _creado = _proj.get("creado_en", "")
                _pub_en = _proj.get("publicado_en", "")
                _yt_id = _proj.get("youtube_video_id", "")
                _fc = _FASE_COLORS.get(_fase, "var(--text3)")
                _fb = _FASE_BG.get(_fase, "var(--dark5)")

                _seg_html = ""
                for _fp in _FASES_PIPELINE:
                    _fp_done = _fase in ("completado", "publicado") if _fp == "completado" else (
                        _FASES_PIPELINE.index(_fp) < _FASES_PIPELINE.index(_fase) if _fase in _FASES_PIPELINE else False
                    )
                    _seg_color = "var(--green)" if _fp_done else ("var(--orange)" if _fase == _fp else "var(--dark5)")
                    _seg_html += f'<div class="mon-proj-seg" style="background:{_seg_color}" title="{_fp}"></div>'

                _extra_html = ""
                if _agente:
                    _extra_html += f'<div style="font-size:.7rem;color:var(--orange);margin-top:4px;font-family:\'JetBrains Mono\',monospace">▶ {_html_escape(str(_agente))}</div>'
                if _yt_id:
                    _extra_html += f'<div style="font-size:.7rem;color:var(--blue);margin-top:4px;font-family:\'JetBrains Mono\',monospace">📺 {_html_escape(_yt_id)}{" · pub " + _pub_en[:10] if _pub_en else ""}</div>'
                if _err_list:
                    _last_err = str(_err_list[-1])[:120]
                    _extra_html += f'<div style="font-size:.7rem;color:var(--red);margin-top:4px;font-family:\'JetBrains Mono\',monospace">✗ {_html_escape(_last_err)}</div>'

                _meta_parts = [_html_escape(x) for x in [_canal, _nicho] if x]
                if _creado:
                    _meta_parts.append(_creado[:16].replace("T", " "))
                _meta_html = f'<div style="font-size:.7rem;color:var(--text3);margin-top:2px;font-family:\'JetBrains Mono\',monospace">{" · ".join(_meta_parts)}</div>' if _meta_parts else ""

                st.markdown(f"""<div class="mon-proj"><div class="mon-proj-head"><span class="mon-proj-id">{_html_escape(_titulo)}</span><span class="mon-proj-fase" style="background:{_fb};color:{_fc};border:1px solid {_fc}">{_fase}</span><span style="font-size:.72rem;color:var(--text3);margin-left:auto;font-family:'JetBrains Mono',monospace">{_progreso}%</span></div>{_meta_html}<div class="mon-proj-bar">{_seg_html}</div>{_extra_html}</div>""", unsafe_allow_html=True)

                _hist = _proj.get("historial", [])
                if _hist:
                    with st.expander(f"⏱️  Timeline & historial — {_pid} ({len(_hist)} agentes)", expanded=False):
                        _tl_html = _renderizar_timeline_html(_hist, titulo=_titulo)
                        if _tl_html:
                            st.markdown(_tl_html, unsafe_allow_html=True)
                        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
                        st.markdown('<div class="section-label">Detalle por agente</div>', unsafe_allow_html=True)

                        _h_total_dur = sum(h.get("duracion_seg") or 0 for h in _hist)
                        _h_total_ok = sum(1 for h in _hist if h.get("estado") == "completado")
                        _h_total_err = sum(1 for h in _hist if h.get("estado") == "error")
                        _h_total_retries = sum((h.get("intentos") or 1) - 1 for h in _hist)

                        _hm1, _hm2, _hm3, _hm4 = st.columns(4)
                        _hm1.metric("Agentes", len(_hist))
                        _h_dur_fmt = f"{_h_total_dur/60:.1f} min" if _h_total_dur >= 60 else f"{_h_total_dur:.0f} seg"
                        _hm2.metric("Tiempo total", _h_dur_fmt)
                        _hm3.metric("Exitosos", _h_total_ok)
                        if _h_total_err > 0 or _h_total_retries > 0:
                            _hm4.metric("Errores / Reintentos", f"{_h_total_err} / {_h_total_retries}")
                        else:
                            _hm4.metric("Errores", "0")

                        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

                        for _hi, _hag in enumerate(_hist):
                            _hag_id = _hag.get("agente_id", "?")
                            _hag_estado = _hag.get("estado", "?")
                            _hag_dur = _hag.get("duracion_seg")
                            _hag_intentos = _hag.get("intentos", 1)
                            _hag_error = _hag.get("error")
                            _hag_inicio = _hag.get("inicio", "")
                            _hag_fin = _hag.get("fin", "")

                            _hag_cls = "a-ok" if _hag_estado == "completado" else ("a-err" if _hag_estado == "error" else "a-run")
                            _hag_icon = "✓" if _hag_estado == "completado" else ("✗" if _hag_estado == "error" else "▶")

                            _hag_dur_fmt = ""
                            if _hag_dur is not None:
                                if _hag_dur >= 60:
                                    _hag_dur_fmt = f"{_hag_dur/60:.1f}m"
                                else:
                                    _hag_dur_fmt = f"{_hag_dur:.1f}s"

                            _hag_meta_parts = []
                            if _hag_dur_fmt:
                                _hag_meta_parts.append(_hag_dur_fmt)
                            if _hag_intentos > 1:
                                _hag_meta_parts.append(f"{_hag_intentos} intentos")
                            if _hag_inicio:
                                _t = _hag_inicio
                                if "T" in _t:
                                    _t = _t.split("T")[1][:8]
                                _hag_meta_parts.append(_t)

                            _hag_meta = " · ".join(_hag_meta_parts)

                            _hag_pct = ""
                            if _hag_dur is not None and _h_total_dur > 0:
                                _hag_pct_val = round((_hag_dur / _h_total_dur) * 100)
                                _hag_pct = f"{_hag_pct_val}%"

                            _hag_err_html = ""
                            if _hag_error:
                                _hag_err_short = _hag_error[:150] + "..." if len(_hag_error) > 150 else _hag_error
                                _hag_err_html = (
                                    f'<div style="font-size:.67rem;color:var(--red);margin-left:32px;'
                                    f'margin-top:2px;font-family:\'JetBrains Mono\',monospace">'
                                    f'{_html_escape(_hag_err_short)}</div>'
                                )

                            st.markdown(f"""
                            <div class="mon-agent-row {_hag_cls}">
                              <div class="mon-agent-icon">{_hag_icon}</div>
                              <span class="mon-agent-name">{_html_escape(_hag_id)}</span>
                              <span class="mon-agent-meta">{_hag_meta}</span>
                              <span style="font-size:.65rem;color:var(--text4);font-family:'JetBrains Mono',monospace;
                                min-width:30px;text-align:right">{_hag_pct}</span>
                            </div>
                            {_hag_err_html}""", unsafe_allow_html=True)

            if _cq_en_proc:
                st.markdown(f'<div style="font-size:.75rem;font-weight:700;color:var(--orange);padding:8px 0 4px;display:flex;align-items:center;gap:6px"><span style="width:8px;height:8px;border-radius:50%;background:var(--orange);display:inline-block"></span>En proceso ({len(_cq_en_proc)})</div>', unsafe_allow_html=True)
                for _ci, _cp in enumerate(_cq_en_proc):
                    _render_proyecto_card(_cp, f"proc_{_ci}")
            if _cq_listos:
                st.markdown(f'<div style="font-size:.75rem;font-weight:700;color:var(--green);padding:12px 0 4px">✓ Listos para publicar ({len(_cq_listos)})</div>', unsafe_allow_html=True)
                for _ci, _cl in enumerate(_cq_listos):
                    _render_proyecto_card(_cl, f"listo_{_ci}")
            if _cq_errs:
                st.markdown(f'<div style="font-size:.75rem;font-weight:700;color:var(--red);padding:12px 0 4px">✗ Con error ({len(_cq_errs)})</div>', unsafe_allow_html=True)
                for _ci, _ce in enumerate(_cq_errs):
                    _render_proyecto_card(_ce, f"err_{_ci}")
            if _cq_pubs:
                with st.expander(f"📺  Publicados ({len(_cq_pubs)})", expanded=False):
                    for _ci, _cpb in enumerate(_cq_pubs):
                        _render_proyecto_card(_cpb, f"pub_{_ci}")
            if not _cq_en_proc and not _cq_listos and not _cq_errs and not _cq_pubs:
                st.info("No hay proyectos en el sistema todavía. Lanza un pipeline para empezar.")

    # ════════════════════════════════════════════════════════════
    # SECCION 3 — API Reference
    # ════════════════════════════════════════════════════════════
    st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)

    _gw_url = os.getenv("GATEWAY_URL", "http://localhost:7861")

    with st.expander("🔌  API Reference — Endpoints del Gateway", expanded=False):
        st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
        <div style="font-size:.78rem;color:var(--text2)">Base URL: <code style="color:var(--blue)">{_html_escape(_gw_url)}</code></div>
        <div style="display:flex;gap:8px">
          <a href="{_html_escape(_gw_url)}/docs" target="_blank"
            style="font-size:.7rem;color:var(--blue);text-decoration:none;
            padding:3px 10px;border:1px solid rgba(62,166,255,.25);border-radius:6px;
            font-family:'JetBrains Mono',monospace">Swagger UI ↗</a>
          <a href="{_html_escape(_gw_url)}/openapi.json" target="_blank"
            style="font-size:.7rem;color:var(--text3);text-decoration:none;
            padding:3px 10px;border:1px solid var(--border);border-radius:6px;
            font-family:'JetBrains Mono',monospace">OpenAPI JSON ↗</a>
        </div></div>""", unsafe_allow_html=True)

        _API_ENDPOINTS = [
            ("Pipeline", [
                ("POST", "/pipeline/ejecutar", "Ejecutar pipeline completo", True),
                ("POST", "/pipeline/webhook", "Trigger async (para n8n)", True),
                ("GET", "/pipeline/estado/{proyecto_id}", "Estado detallado del pipeline", True),
                ("GET", "/pipeline/cola", "Cola de publicación completa", True),
                ("POST", "/pipeline/kaggle-callback", "Callback de Kaggle", True),
                ("GET", "/download/{proyecto_id}/final", "Descargar video final", True),
            ]),
            ("Proyectos", [
                ("POST", "/proyectos", "Crear proyecto nuevo", True),
                ("GET", "/proyectos", "Listar todos los proyectos", True),
                ("GET", "/proyectos/{proyecto_id}", "Leer estado de un proyecto", True),
            ]),
            ("Agentes", [
                ("POST", "/agentes/{agente_id}/ejecutar", "Ejecutar un agente individual", True),
            ]),
            ("Channel Intelligence", [
                ("POST", "/canales/conectar", "Conectar y escanear canal", True),
                ("GET", "/canales", "Listar canales conectados", True),
                ("GET", "/canales/{canal_id}", "Datos completos del canal", True),
                ("POST", "/canales/{canal_id}/refrescar", "Refrescar datos del canal", True),
                ("DELETE", "/canales/{canal_id}", "Eliminar canal", True),
                ("POST", "/canales/{canal_id}/competidores", "Agregar competidor", True),
                ("DELETE", "/canales/{canal_id}/competidores/{comp_id}", "Eliminar competidor", True),
                ("GET", "/canales/{canal_id}/ideas", "Obtener ideas de video", True),
                ("POST", "/canales/{canal_id}/ideas/refrescar", "Re-generar ideas", True),
                ("GET", "/canales/{canal_id}/identidad-visual", "Leer identidad visual", True),
                ("POST", "/canales/{canal_id}/identidad-visual", "Guardar identidad visual", True),
            ]),
            ("Estilos & Recursos", [
                ("GET", "/estilos", "Catálogo de estilos visuales", False),
                ("GET", "/estilos/{slug}", "Detalle de un estilo", False),
                ("GET", "/quota/hoy", "Quota YouTube API del día", True),
            ]),
            ("Scheduling & Health", [
                ("GET", "/health", "Health check del gateway", False),
                ("GET", "/scheduling/health_servicios", "Health de todos los servicios", True),
                ("POST", "/scheduling/puede_generar", "¿Se puede generar un video?", True),
            ]),
        ]

        for _grp_name, _grp_endpoints in _API_ENDPOINTS:
            _grp_rows = ""
            for _method, _path, _desc, _auth in _grp_endpoints:
                _m_cls = f"api-{_method.lower()}"
                _auth_badge = '<span class="api-auth">API Key</span>' if _auth else ""
                _grp_rows += (
                    f'<div class="api-row">'
                    f'<span class="api-method {_m_cls}">{_method}</span>'
                    f'<span class="api-path">{_html_escape(_path)}</span>'
                    f'<span class="api-desc">{_html_escape(_desc)}</span>'
                    f'{_auth_badge}'
                    f'</div>'
                )

            st.markdown(f"""
            <div class="api-group">
              <div class="api-group-title">{_html_escape(_grp_name)} ({len(_grp_endpoints)})</div>
              {_grp_rows}
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""<div style="margin-top:8px;padding:10px 12px;background:var(--dark3);
        border-radius:8px;border:1px solid var(--border)">
        <div style="font-size:.72rem;font-weight:700;color:var(--text3);margin-bottom:6px;
          font-family:'JetBrains Mono',monospace">Autenticación</div>
        <div style="font-size:.73rem;color:var(--text2);line-height:1.7">
          Endpoints con <span class="api-auth" style="display:inline">API Key</span> requieren el header
          <code style="color:var(--blue)">X-API-Key</code> con el valor de
          <code style="color:var(--text3)">YTCREATOR_API_KEY</code> de tu <code>.env</code>.<br>
          Endpoints sin badge son públicos.
        </div></div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    # SECCION 4 — Eventos de automatización
    # ════════════════════════════════════════════════════════════
    st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Eventos de automatización</div>', unsafe_allow_html=True)

    _mon_eventos = _cached_eventos_recientes()

    if _mon_eventos is None and not API_DISPONIBLE:
        st.info("Conecta los agentes para ver el historial de eventos del sistema.")
    elif _mon_eventos is None:
        st.warning("No se pudieron obtener los eventos.")
    elif not _mon_eventos:
        st.info("No hay eventos registrados aún. Se registrarán automáticamente al ejecutar pipelines.")
    else:
        _mev_c1, _mev_c2, _mev_c3 = st.columns([1, 1, 1])
        try:
            _mev_stats = api_client.eventos_stats() if API_DISPONIBLE else {}
        except Exception:
            _mev_stats = {}

        _mev_total = _mev_stats.get("total", len(_mon_eventos))
        _mev_por_status = _mev_stats.get("por_status", {})
        _mev_exitos = _mev_por_status.get("success", 0)
        _mev_errores = _mev_por_status.get("error", 0)

        _mev_c1.metric("Total eventos", _mev_total)
        _mev_c2.metric("Exitosos", _mev_exitos)
        _mev_c3.metric("Errores", _mev_errores)

        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

        _mev_filter_col1, _mev_filter_col2 = st.columns([1, 1])
        with _mev_filter_col1:
            _mev_type_filter = st.selectbox(
                "Filtrar por tipo",
                ["Todos", "pipeline_started", "pipeline_completed", "pipeline_failed",
                 "pipeline_phase", "agent_completed", "agent_failed"],
                key="mon_ev_type_filter",
            )
        with _mev_filter_col2:
            _mev_status_filter = st.selectbox(
                "Filtrar por estado",
                ["Todos", "success", "error"],
                key="mon_ev_status_filter",
            )

        _mev_filtered = _mon_eventos
        if _mev_type_filter != "Todos":
            _mev_filtered = [e for e in _mev_filtered if e.get("event_type") == _mev_type_filter]
        if _mev_status_filter != "Todos":
            _mev_filtered = [e for e in _mev_filtered if e.get("status") == _mev_status_filter]

        if not _mev_filtered:
            st.info("No hay eventos que coincidan con los filtros.")
        else:
            _mev_rows = ""
            for _mev in _mev_filtered:
                _mev_ts = _mev.get("timestamp", "")
                _mev_type = _mev.get("event_type", "?")
                _mev_st = _mev.get("status", "?")
                _mev_src = _mev.get("source", "—")
                _mev_pid = _mev.get("proyecto_id", "—")
                _mev_dur = _mev.get("duration_seg")
                _mev_data = _mev.get("data") or {}

                _mev_type_cls = "met-pipeline" if "pipeline" in _mev_type else ("met-agent" if "agent" in _mev_type else "met-system")
                _mev_st_cls = "mes-success" if _mev_st == "success" else "mes-error"
                _mev_dur_str = f"{_mev_dur:.1f}s" if _mev_dur else "—"

                _mev_detail = ""
                if isinstance(_mev_data, dict):
                    if _mev_data.get("fase"):
                        _mev_detail = _mev_data["fase"]
                    elif _mev_data.get("nicho"):
                        _mev_detail = _html_escape(str(_mev_data["nicho"])[:30])
                    elif _mev_data.get("error"):
                        _mev_detail = _html_escape(str(_mev_data["error"])[:40])

                _mev_rows += (
                    f'<tr>'
                    f'<td style="white-space:nowrap;color:var(--text3);font-size:.68rem">{_html_escape(_mev_ts[5:19] if len(_mev_ts)>=19 else _mev_ts)}</td>'
                    f'<td><span class="mon-ev-type {_mev_type_cls}">{_html_escape(_mev_type)}</span></td>'
                    f'<td><span class="mon-ev-status {_mev_st_cls}">{_mev_st}</span></td>'
                    f'<td style="color:var(--text2)">{_html_escape(_mev_src)}</td>'
                    f'<td style="color:var(--text3)">{_html_escape(_mev_pid[:16] if _mev_pid else "—")}</td>'
                    f'<td style="color:var(--text3)">{_mev_dur_str}</td>'
                    f'<td style="color:var(--text3);font-size:.68rem">{_mev_detail}</td>'
                    f'</tr>'
                )

            st.markdown(f"""
            <div style="background:var(--dark2);border:1px solid var(--border);border-radius:10px;
                 padding:2px;overflow-x:auto;max-height:400px;overflow-y:auto;
                 scrollbar-width:thin;scrollbar-color:#1A2535 var(--dark2)">
              <table class="mon-events-table">
                <thead><tr>
                  <th>Hora</th><th>Tipo</th><th>Estado</th>
                  <th>Origen</th><th>Proyecto</th><th>Dur.</th><th>Detalle</th>
                </tr></thead>
                <tbody>{_mev_rows}</tbody>
              </table>
            </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    # ════════════════════════════════════════════════════════════
    # SECCION 5 — Scheduler (tareas programadas)
    # ════════════════════════════════════════════════════════════
    st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Tareas programadas</div>', unsafe_allow_html=True)

    # ── Control global de pausa ──
    _mon_pausa = _cached_pausa()
    _mon_esta_pausado = _mon_pausa is not None and _mon_pausa.get("pausado", False)

    if _mon_esta_pausado:
        _mp_en = _mon_pausa.get("pausado_en", "")
        _mp_razon = _mon_pausa.get("razon", "")
        _mp_por = _mon_pausa.get("pausado_por", "")
        _mp_time_str = _mp_en[0:19].replace("T", " ") if _mp_en else "?"

        st.markdown(f"""
        <div class="mon-pause-card mon-pause-active">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
            <span style="font-size:1.8rem">⏸️</span>
            <div>
              <div style="font-size:1rem;font-weight:800;color:var(--orange)">AUTOMATIZACIÓN PAUSADA</div>
              <div style="font-size:.75rem;color:var(--text3);font-family:'JetBrains Mono',monospace;margin-top:2px">
                Desde {_html_escape(_mp_time_str)} · por {_html_escape(_mp_por)}
                {(' — ' + _html_escape(_mp_razon)) if _mp_razon else ''}
              </div>
            </div>
          </div>
          <div style="font-size:.78rem;color:var(--text3);line-height:1.6">
            Mientras la automatización está pausada, n8n no podrá lanzar nuevos pipelines.
            Los pipelines manuales desde la UI tampoco se ejecutarán via webhook.
            Los servicios siguen activos — solo se bloquea la generación automática.
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        if st.button("▶  Reanudar automatización", key="mon_resume_auto", use_container_width=True):
            try:
                api_client.scheduler_reanudar()
                _cached_pausa.clear()
                _cached_scheduler.clear()
                st.rerun()
            except Exception as _mp_err:
                st.error(f"Error: {_mp_err}")
    elif _mon_pausa is not None:
        st.markdown("""
        <div class="mon-pause-card mon-pause-inactive">
          <div style="display:flex;align-items:center;gap:12px">
            <span style="font-size:1.8rem">▶️</span>
            <div>
              <div style="font-size:1rem;font-weight:800;color:var(--green)">AUTOMATIZACIÓN ACTIVA</div>
              <div style="font-size:.75rem;color:var(--text3);margin-top:2px">
                Las tareas programadas se ejecutan según su horario configurado.
              </div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        _mp_col1, _mp_col2 = st.columns([2, 1])
        with _mp_col1:
            _mp_razon_input = st.text_input(
                "Razón (opcional)", placeholder="ej: mantenimiento, debug...",
                key="mon_pause_reason", label_visibility="collapsed",
            )
        with _mp_col2:
            if st.button("⏸  Pausar todo", key="mon_pause_auto", use_container_width=True):
                try:
                    api_client.scheduler_pausar(razon=_mp_razon_input.strip() or None)
                    _cached_pausa.clear()
                    _cached_scheduler.clear()
                    st.rerun()
                except Exception as _mp_err:
                    st.error(f"Error: {_mp_err}")

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)

    _mon_sched = _cached_scheduler()

    if _mon_sched is None and not API_DISPONIBLE:
        st.info("Conecta los agentes para ver las tareas programadas.")
    elif _mon_sched is None:
        st.warning("No se pudo obtener el schedule.")
    else:
        _ms_tareas = _mon_sched.get("tareas", [])
        _ms_hab = _mon_sched.get("habilitadas", 0)
        _ms_prox = _mon_sched.get("proxima_ejecucion")
        _ms_prox_nombre = _mon_sched.get("proxima_tarea", "")

        _ms_c1, _ms_c2, _ms_c3 = st.columns(3)
        _ms_c1.metric("Total tareas", len(_ms_tareas))
        _ms_c2.metric("Habilitadas", _ms_hab)
        _ms_prox_display = f"{_ms_prox[11:16]}" if _ms_prox and len(_ms_prox) >= 16 else ("PAUSADO" if _mon_esta_pausado else "—")
        _ms_c3.metric("Próxima ejecución", _ms_prox_display)

        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

        for _mst_idx, _mst in enumerate(_ms_tareas):
            _mst_hab = _mst.get("habilitado", False)
            _mst_name = _mst.get("nombre", "?")
            _mst_desc = _mst.get("descripcion", "")
            _mst_cron = _mst.get("cron", "?")
            _mst_freq = _mst.get("frecuencia", "?")
            _mst_orq = _mst.get("orquestador", "?")
            _mst_endpoint = _mst.get("endpoint", "?")
            _mst_last = _mst.get("ultima_ejecucion")
            _mst_last_dur = _mst.get("ultima_duracion_seg")
            _mst_last_st = _mst.get("ultimo_estado", "")
            _mst_prox = _mst.get("proxima_ejecucion")
            _mst_tid = _mst.get("task_id", "?")

            _mst_dot = "🟢" if _mst_hab else "🔴"
            _mst_last_str = _mst_last[0:19].replace("T", " ") if _mst_last else "Nunca"
            _mst_dur_str = f"{_mst_last_dur:.1f}s" if _mst_last_dur else "—"
            _mst_prox_str = _mst_prox[11:16] if _mst_prox and len(_mst_prox) >= 16 else "—"
            _mst_st_icon = "✅" if _mst_last_st == "success" else ("❌" if _mst_last_st == "error" else "—")

            st.markdown(f"""
            <div class="mon-sched-card" style="margin-bottom:10px">
              <div class="mon-sched-card-head">
                <span class="mon-sched-card-name">{_mst_dot} {_html_escape(_mst_name)}</span>
                <span class="mon-sched-card-cron">{_html_escape(_mst_cron)}</span>
              </div>
              <div class="mon-sched-card-desc">{_html_escape(_mst_desc)}</div>
              <div class="mon-sched-card-meta">
                <span class="mon-sched-meta-item">📅 <strong>{_html_escape(_mst_freq)}</strong></span>
                <span class="mon-sched-meta-item">🔧 <strong>{_html_escape(_mst_orq)}</strong></span>
                <span class="mon-sched-meta-item">📍 <strong>{_html_escape(_mst_endpoint)}</strong></span>
                <span class="mon-sched-meta-item">⏰ Próx: <strong>{_mst_prox_str}</strong></span>
                <span class="mon-sched-meta-item">📊 Último: <strong>{_mst_last_str}</strong> {_mst_st_icon} ({_mst_dur_str})</span>
              </div>
            </div>""", unsafe_allow_html=True)

            _mst_col1, _mst_col2 = st.columns([1, 3])
            with _mst_col1:
                _mst_new_state = not _mst_hab
                _mst_btn_label = "⏸ Deshabilitar" if _mst_hab else "▶ Habilitar"
                if st.button(_mst_btn_label, key=f"sched_toggle_{_mst_tid}", use_container_width=True):
                    try:
                        api_client.scheduler_toggle(_mst_tid, _mst_new_state)
                        _cached_scheduler.clear()
                        st.rerun()
                    except Exception as _mst_err:
                        st.error(f"Error: {_mst_err}")

    # ════════════════════════════════════════════════════════════
    # ════════════════════════════════════════════════════════════
    # SECCION 6 — Keyword Performance Tracking
    # ════════════════════════════════════════════════════════════
    st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Keyword Performance</div>', unsafe_allow_html=True)

    _mon_kw_stats = _cached_keywords_stats()
    _mon_kw_top = _cached_keywords_top()

    if _mon_kw_stats is None and not API_DISPONIBLE:
        st.info("Conecta los agentes para ver el tracking de keywords.")
    elif _mon_kw_stats is None:
        st.warning("No se pudo obtener datos de keywords.")
    elif _mon_kw_stats.get("total_keywords", 0) == 0:
        st.info("No hay datos de keywords aún. Se registrarán automáticamente cuando el tracker de performance (agente 0.5) evalúe videos publicados en los checkpoints T+7d y T+30d.")
    else:
        _kw_c1, _kw_c2, _kw_c3, _kw_c4 = st.columns(4)
        _kw_c1.metric("Keywords trackeadas", _mon_kw_stats.get("total_keywords", 0))
        _kw_c2.metric("Videos analizados", _mon_kw_stats.get("total_videos_trackeados", 0))
        _kw_c3.metric("Registros totales", _mon_kw_stats.get("total_registros", 0))
        _kw_mejor = _mon_kw_stats.get("mejor_keyword")
        _kw_mejor_str = _kw_mejor["keyword"] if _kw_mejor else "—"
        _kw_c4.metric("Mejor keyword", _kw_mejor_str)

        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

        _kw_sort_col1, _kw_sort_col2 = st.columns([1, 1])
        with _kw_sort_col1:
            _kw_sort = st.selectbox(
                "Ordenar por",
                ["vistas_promedio", "ctr_promedio", "engagement_promedio", "usos", "mejor_vistas"],
                key="mon_kw_sort",
            )
        with _kw_sort_col2:
            _kw_min_usos = st.selectbox(
                "Mínimo de usos",
                [1, 2, 3, 5],
                key="mon_kw_min_usos",
            )

        if _kw_sort != "vistas_promedio" or _kw_min_usos != 1:
            try:
                _mon_kw_top = api_client.keywords_top(limit=30, ordenar_por=_kw_sort, min_usos=_kw_min_usos)
            except Exception:
                pass

        if _mon_kw_top:
            _kw_max_vistas = max((k.get("vistas_promedio", 0) or 0) for k in _mon_kw_top) if _mon_kw_top else 1
            if _kw_max_vistas == 0:
                _kw_max_vistas = 1

            _kw_rows = ""
            for _kw in _mon_kw_top:
                _kw_name = _html_escape(_kw.get("keyword", "?"))
                _kw_usos = _kw.get("usos", 0)
                _kw_vistas_avg = _kw.get("vistas_promedio", 0) or 0
                _kw_vistas_total = _kw.get("vistas_total", 0) or 0
                _kw_ctr = _kw.get("ctr_promedio")
                _kw_eng = _kw.get("engagement_promedio")
                _kw_mejor_v = _kw.get("mejor_vistas", 0) or 0
                _kw_mejor_t = _html_escape(_kw.get("mejor_titulo", "") or "")
                if len(_kw_mejor_t) > 30:
                    _kw_mejor_t = _kw_mejor_t[:30] + "…"

                _kw_bar_pct = min((_kw_vistas_avg / _kw_max_vistas) * 100, 100)
                _kw_bar_color = "var(--green)" if _kw_bar_pct >= 60 else ("var(--orange)" if _kw_bar_pct >= 30 else "var(--blue)")

                _kw_ctr_str = f"{_kw_ctr:.1f}%" if _kw_ctr is not None else "—"
                _kw_eng_str = f"{_kw_eng:.1f}%" if _kw_eng is not None else "—"

                _kw_rows += (
                    f'<tr>'
                    f'<td><span class="kw-tag">{_kw_name}</span></td>'
                    f'<td style="text-align:center">{_kw_usos}</td>'
                    f'<td style="text-align:right">{_kw_vistas_avg:,.0f}</td>'
                    f'<td><div class="kw-bar"><div class="kw-bar-fill" style="width:{_kw_bar_pct:.1f}%;background:{_kw_bar_color}"></div></div></td>'
                    f'<td style="text-align:right">{_kw_vistas_total:,}</td>'
                    f'<td style="text-align:center">{_kw_ctr_str}</td>'
                    f'<td style="text-align:center">{_kw_eng_str}</td>'
                    f'<td style="text-align:right">{_kw_mejor_v:,}</td>'
                    f'<td style="color:var(--text3);font-size:.68rem" title="{_kw_mejor_t}">{_kw_mejor_t}</td>'
                    f'</tr>'
                )

            st.markdown(f"""
            <div style="background:var(--dark2);border:1px solid var(--border);border-radius:10px;
                 padding:2px;overflow-x:auto;max-height:450px;overflow-y:auto;
                 scrollbar-width:thin;scrollbar-color:#1A2535 var(--dark2)">
              <table class="kw-table">
                <thead><tr>
                  <th>Keyword</th><th style="text-align:center">Usos</th>
                  <th style="text-align:right">Vistas avg</th><th></th>
                  <th style="text-align:right">Vistas total</th>
                  <th style="text-align:center">CTR avg</th>
                  <th style="text-align:center">Engage avg</th>
                  <th style="text-align:right">Mejor</th><th>Video</th>
                </tr></thead>
                <tbody>{_kw_rows}</tbody>
              </table>
            </div>""", unsafe_allow_html=True)
        else:
            st.info("No hay keywords que coincidan con los filtros seleccionados.")

    # ════════════════════════════════════════════════════════════
    # SECCION 7 — Logs en vivo (siempre visible, con o sin agentes)
    # ════════════════════════════════════════════════════════════
    st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Logs del sistema</div>', unsafe_allow_html=True)

    from shared.config import STORAGE_DIR as _LOG_STORAGE_DIR

    # Toolbar de controles
    _lc1, _lc2, _lc3, _lc4 = st.columns([1, 1, 1, 2])
    with _lc1:
        _log_n_lines = st.selectbox("Líneas", [50, 100, 200, 500], index=1, key="mon_log_lines")
    with _lc2:
        _log_level_filter = st.selectbox("Nivel", ["Todos", "Solo errores", "Solo warnings", "Errores + warnings"], key="mon_log_filter")
    with _lc3:
        _log_include_rotated = st.checkbox("Incluir historial", value=False, key="mon_log_rotated",
            help="Incluye archivos de log rotados (.1, .2, .3) para ver historial más antiguo")

    # Leer logs
    _all_raw_lines = _leer_logs(_LOG_STORAGE_DIR, incluir_rotados=_log_include_rotated)

    if not _all_raw_lines:
        st.info("No hay archivo de logs todavía. Se creará al ejecutar el primer pipeline.")
    else:
        # Parsear todas las líneas
        _all_parsed = [_parsear_linea_log(l) for l in _all_raw_lines]

        # Filtro por servicio
        _servicios_en_log = _extraer_servicios_unicos(_all_parsed)
        with _lc4:
            _log_srv_filter = st.selectbox("Servicio", ["Todos"] + _servicios_en_log, key="mon_log_srv")

        # Búsqueda
        _log_search = st.text_input("Buscar en logs", placeholder="proyecto_id, error, texto...", key="mon_log_search", label_visibility="collapsed")

        # Aplicar filtros
        _filtered = _all_parsed

        if _log_level_filter == "Solo errores":
            _filtered = [l for l in _filtered if "ERROR" in l["level"]]
        elif _log_level_filter == "Solo warnings":
            _filtered = [l for l in _filtered if "WARNING" in l["level"]]
        elif _log_level_filter == "Errores + warnings":
            _filtered = [l for l in _filtered if "ERROR" in l["level"] or "WARNING" in l["level"]]

        if _log_srv_filter != "Todos":
            _filtered = [l for l in _filtered if l["name"] == _log_srv_filter]

        if _log_search.strip():
            _sq = _log_search.strip().lower()
            _filtered = [l for l in _filtered if _sq in (l["ts"] + l["name"] + l["level"] + l["msg"]).lower()]

        # Estadísticas
        _total_shown = len(_filtered)
        _n_errors = sum(1 for l in _filtered if "ERROR" in l["level"])
        _n_warnings = sum(1 for l in _filtered if "WARNING" in l["level"])
        _n_info = _total_shown - _n_errors - _n_warnings

        st.markdown(f"""
        <div class="mon-log-stats">
          <div class="mon-log-stat">
            <span class="mon-log-stat-num" style="color:var(--text2)">{_total_shown}</span>
            <span style="color:var(--text3)">líneas</span>
          </div>
          <div class="mon-log-stat">
            <span class="mon-log-stat-num" style="color:var(--red)">{_n_errors}</span>
            <span style="color:var(--text3)">errores</span>
          </div>
          <div class="mon-log-stat">
            <span class="mon-log-stat-num" style="color:var(--orange)">{_n_warnings}</span>
            <span style="color:var(--text3)">warnings</span>
          </div>
          <div class="mon-log-stat">
            <span class="mon-log-stat-num" style="color:var(--blue)">{_n_info}</span>
            <span style="color:var(--text3)">info</span>
          </div>
          <div class="mon-log-stat" style="margin-left:auto">
            <span style="color:var(--text4)">{len(_all_raw_lines)} total en archivo</span>
          </div>
        </div>""", unsafe_allow_html=True)

        # Recortar al número pedido
        _display_lines = _filtered[-_log_n_lines:]

        if _display_lines:
            _logs_html = _renderizar_logs_html(_display_lines, busqueda=_log_search.strip())
            st.markdown(f'<div class="mon-log">{_logs_html}</div>', unsafe_allow_html=True)
        else:
            st.info("No hay logs que coincidan con los filtros seleccionados.")

        # Descarga
        _col_dl1, _col_dl2 = st.columns([1, 4])
        with _col_dl1:
            _dl_text = "\n".join(
                f"{l['ts']} | {l['name']} | {l['level']} | {l['msg']}" if l["name"] else l["msg"]
                for l in _filtered
            )
            st.download_button(
                "⬇️  Exportar logs",
                data=_dl_text,
                file_name="ytcreator_logs.txt",
                mime="text/plain",
                key="mon_log_download",
                use_container_width=True,
            )
