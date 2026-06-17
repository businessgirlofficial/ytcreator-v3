"""
YTCreator Studio v3 — Pipeline completo YouTube
Flujo: Guión → Audio → Kaggle → Subtítulos → Ensamblar
Estado en sidebar derecho fijo
"""
import streamlit as st
import os, json, asyncio, requests, zipfile
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="YTCreator Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# ══════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════

# ── Header ────────────────────────────────────────────────────
keys_ok = bool(GROQ_KEY and KAGGLE_KEY and KAGGLE_USER)
st.markdown(f"""
<div class="hdr">
  <div class="hdr-brand">
    <span style="font-size:1.25rem">🎬</span>
    <span class="hdr-logo">YT<em>Creator</em> Studio</span>
    <span class="hdr-badge">v3</span>
  </div>
  <div class="hdr-st">
    <span class="dot {'on' if keys_ok else 'off'}"></span>
    {'sistema listo' if keys_ok else 'configura .env con tus API keys'}
  </div>
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

c_sp.markdown(f"""<div style="display:flex;align-items:center;gap:6px;height:100%;padding-top:28px">
<span class="dot {'on' if API_DISPONIBLE else 'off'}"></span>
<span style="font-size:.7rem;color:var(--text3);font-family:'JetBrains Mono',monospace">
{'agentes conectados' if API_DISPONIBLE else 'modo local (agentes no disponibles)'}</span>
</div>""", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 Guión", "🎙️ Audio", "🚀 Kaggle", "💬 Subtítulos", "🎞️ Ensamblar"])

# ══════════════════════════════════════════════════════════════
# TAB 1 — GUIÓN (Modo Pro — Sistema de 3 Fases)
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown('<div class="step-title">Guión — Modo Pro</div>', unsafe_allow_html=True)
    st.markdown('<div class="step-sub">Sistema de 3 fases: análisis del nicho con videos virales → ingeniería de títulos → guión con estructura viral probada.</div>', unsafe_allow_html=True)

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

                        mid_txt = f"""A mitad del guión, antes del punto {n_puntos}, agrega:
"Y el punto {n_puntos}... este es el que la mayoría pasa por alto. Quédate."""" if inc_midret else ""

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
                        parrafos = [p.strip() for p in guion_txt.split("

") if p.strip()]
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

            estilo = st.selectbox("Estilo visual", [
                "cinematico — Fotorrealista, dramático",
                "anime — Studio Ghibli, vibrante",
                "mistico — Fantasía etérea, mágico",
                "asmr — Macro, texturas, pastel",
                "stickman — Minimalista, pizarrón",
                "dibujo_mano — Acuarela, boceto"
            ])
            estilo_id = estilo.split(" — ")[0]

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
