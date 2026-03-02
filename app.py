"""MariaStudy — RAG Study Assistant for Medical Students (PT-PT)"""
import os
import re as _re
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import plotly.graph_objects as go

from src import subjects as sub_store
from src import rag
from src import llm
from src import progress as prog
from src.vectorstore import collection_count
from src import vectorstore

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MariaStudy",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Base ──────────────────────────────────────────────────────────────── */
html, body, [class*="css"], .stMarkdown, button, input, select, textarea, label {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    -webkit-font-smoothing: antialiased;
}

/* ── App background ────────────────────────────────────────────────────── */
.stApp { background: #F1F5F9; }
.ms-dark .stApp { background: #0B1120; }
.main .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1120px; }

/* Hide Streamlit chrome */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent; height: 0; }

/* ── Sidebar ───────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #0F1E30 !important;
    box-shadow: 2px 0 24px rgba(0,0,0,0.18);
}
[data-testid="stSidebar"] * { color: #94A3B8 !important; }
[data-testid="stSidebar"] .stMarkdown h2 {
    color: #F1F5F9 !important;
    font-size: 1.1rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
}
[data-testid="stSidebar"] hr { border-color: #1E3045 !important; opacity: 1 !important; }
[data-testid="stSidebar"] input {
    background: #1E3045 !important;
    border: 1px solid #2D4A63 !important;
    color: #E2E8F0 !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div {
    background: #1E3045 !important;
    border: 1px solid #2D4A63 !important;
    color: #E2E8F0 !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] label { color: #64748B !important; font-size: 0.78rem !important; }

/* Sidebar nav — inactive */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    border: none !important;
    border-radius: 8px !important;
    color: #94A3B8 !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    padding: 0.45rem 0.75rem !important;
    margin-bottom: 2px !important;
    text-align: left !important;
    box-shadow: none !important;
    transition: background 0.15s !important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
    background: #1E3045 !important;
    color: #E2E8F0 !important;
}

/* Sidebar nav — active */
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    background: rgba(0,122,255,0.15) !important;
    border: none !important;
    border-radius: 8px !important;
    color: #007AFF !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    padding: 0.45rem 0.75rem !important;
    margin-bottom: 1px !important;
    text-align: left !important;
    box-shadow: none !important;
}

/* ── Buttons ────────────────────────────────────────────────────────────── */
[data-testid="stBaseButton-primary"] {
    background: #007AFF !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    letter-spacing: -0.01em !important;
    box-shadow: none !important;
    transition: opacity 0.15s ease !important;
}
[data-testid="stBaseButton-primary"]:hover { opacity: 0.85 !important; }
[data-testid="stBaseButton-secondary"] {
    border-radius: 10px !important;
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    transition: opacity 0.15s ease !important;
}

/* ── Tabs ──────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 2px solid #E2E8F0;
    gap: 0;
    background: transparent;
}
[data-testid="stTabs"] [role="tab"] {
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    padding: 0.6rem 1.1rem !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -2px !important;
    color: #64748B !important;
    background: transparent !important;
    box-shadow: none !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #2563EB !important;
    border-bottom-color: #2563EB !important;
}
.ms-dark [data-testid="stTabs"] [role="tablist"] { border-bottom-color: #1E293B; }
.ms-dark [data-testid="stTabs"] [role="tab"] { color: #64748B !important; }
.ms-dark [data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: #60A5FA !important; border-bottom-color: #60A5FA !important; }

/* ── Expander ──────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    background: white !important;
    box-shadow: none !important;
    overflow: hidden !important;
}
.ms-dark [data-testid="stExpander"] {
    border-color: #1E293B !important;
    background: #1E293B !important;
}

/* ── Metrics ───────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: white;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    border: 1px solid #E2E8F0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
[data-testid="stMetricLabel"] {
    color: #64748B !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stMetricValue"] {
    color: #0F172A !important;
    font-size: 1.75rem !important;
    font-weight: 700 !important;
}
.ms-dark [data-testid="stMetric"] { background: #1E293B; border-color: #334155; }
.ms-dark [data-testid="stMetricValue"] { color: #F1F5F9 !important; }
.ms-dark [data-testid="stMetricLabel"] { color: #94A3B8 !important; }

/* ── Inputs ────────────────────────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea {
    border-radius: 8px !important;
    border: 1.5px solid #E2E8F0 !important;
    font-size: 0.9rem !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.12) !important;
}
.ms-dark .stTextInput input, .ms-dark .stTextArea textarea {
    background: #1E293B !important;
    border-color: #334155 !important;
    color: #E2E8F0 !important;
}
.stSelectbox > div > div {
    border-radius: 8px !important;
    border: 1.5px solid #E2E8F0 !important;
    transition: border-color 0.15s !important;
}
.ms-dark .stSelectbox > div > div {
    background: #1E293B !important;
    border-color: #334155 !important;
}

/* ── Alerts ────────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 10px !important;
    border: none !important;
    font-size: 0.9rem !important;
}

/* ── Progress bar ──────────────────────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #2563EB, #60A5FA) !important;
    border-radius: 4px !important;
}

/* ── Scrollbar ─────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
.ms-dark ::-webkit-scrollbar-thumb { background: #334155; }

/* ═══ Custom HTML components ═══════════════════════════════════════════════ */

/* Page title */
.page-title {
    font-size: 1.7rem;
    font-weight: 800;
    color: #0F172A;
    letter-spacing: -0.03em;
    margin-bottom: 0.2rem;
    line-height: 1.2;
}
.page-sub {
    color: #64748B;
    font-size: 0.92rem;
    margin-bottom: 1.5rem;
}
.ms-dark .page-title { color: #F1F5F9; }
.ms-dark .page-sub   { color: #94A3B8; }

/* Cards */
.ms-card {
    background: white;
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    margin-bottom: 1rem;
    border: 1px solid #F1F5F9;
    transition: box-shadow 0.2s;
}
.ms-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.09); }
.ms-dark .ms-card {
    background: #1E293B;
    border-color: #334155;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.ms-card-blue {
    background: linear-gradient(135deg, #1E40AF, #2563EB);
    color: white;
    border-radius: 14px;
    padding: 1.6rem 1.8rem;
    margin-bottom: 1rem;
    box-shadow: 0 4px 20px rgba(37,99,235,0.3);
}

/* Flashcard */
.flashcard {
    background: white;
    border-radius: 20px;
    padding: 3rem 2.5rem;
    text-align: center;
    box-shadow: 0 8px 32px rgba(0,0,0,0.1), 0 2px 8px rgba(0,0,0,0.06);
    min-height: 240px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    border: 2px solid #F1F5F9;
    transition: all 0.2s;
}
.ms-dark .flashcard {
    background: #1E293B;
    border-color: #334155;
    box-shadow: 0 8px 32px rgba(0,0,0,0.35);
}
.flashcard-back {
    background: linear-gradient(135deg, #EFF6FF, #DBEAFE);
    border: 2px solid #93C5FD;
}
.ms-dark .flashcard-back {
    background: linear-gradient(135deg, #1E3A5F, #1E3660);
    border-color: #2563EB;
}
.flashcard-front-label {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #94A3B8;
    margin-bottom: 1rem;
}
.flashcard-text {
    font-size: 1.25rem;
    font-weight: 600;
    color: #0F172A;
    line-height: 1.6;
}
.ms-dark .flashcard-text { color: #E2E8F0; }
.flashcard-source {
    margin-top: 1.2rem;
    font-size: 0.78rem;
    color: #94A3B8;
    font-style: italic;
}

/* Badges */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}
.badge-green  { background: #D1FAE5; color: #065F46; }
.badge-yellow { background: #FEF3C7; color: #92400E; }
.badge-blue   { background: #DBEAFE; color: #1E40AF; }
.badge-red    { background: #FEE2E2; color: #991B1B; }
.ms-dark .badge-green  { background: #064E3B; color: #6EE7B7; }
.ms-dark .badge-yellow { background: #451A03; color: #FCD34D; }
.ms-dark .badge-blue   { background: #1E3A5F; color: #93C5FD; }
.ms-dark .badge-red    { background: #450A0A; color: #FCA5A5; }

/* Topic chips */
.topic-chip {
    display: inline-block;
    background: #EFF6FF;
    color: #1E40AF;
    border: 1px solid #BFDBFE;
    border-radius: 20px;
    padding: 4px 14px;
    margin: 3px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
}
.topic-chip:hover { background: #DBEAFE; border-color: #93C5FD; }
.ms-dark .topic-chip {
    background: #1E3A5F;
    color: #93C5FD;
    border-color: #2563EB;
}

/* Citation box */
.cite-box {
    background: #F8FAFC;
    border-left: 3px solid #2563EB;
    padding: 0.65rem 1rem;
    border-radius: 0 10px 10px 0;
    font-size: 0.83rem;
    color: #334155;
    margin: 5px 0;
}
.ms-dark .cite-box {
    background: #1E293B;
    border-left-color: #3B82F6;
    color: #94A3B8;
}

/* Chat bubbles */
.chat-user {
    background: linear-gradient(135deg, #1E40AF, #2563EB);
    color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 0.9rem 1.2rem;
    margin: 0.5rem 0;
    max-width: 80%;
    margin-left: auto;
    font-size: 0.92rem;
    box-shadow: 0 2px 8px rgba(37,99,235,0.25);
}
.chat-assistant {
    background: white;
    border: 1px solid #E2E8F0;
    border-radius: 18px 18px 18px 4px;
    padding: 0.9rem 1.2rem;
    margin: 0.5rem 0;
    max-width: 90%;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    font-size: 0.92rem;
    color: #0F172A;
}
.ms-dark .chat-assistant {
    background: #1E293B;
    border-color: #334155;
    color: #E2E8F0;
}

/* Quiz radio */
div[data-testid="stRadio"] label { font-size: 0.92rem !important; padding: 5px 0; }
</style>
""", unsafe_allow_html=True)

# ── Dark mode override — iOS palette (injected when toggle is on) ─────────────
_DARK_CSS = """
<style>
/* iOS system dark backgrounds */
.stApp, [data-testid="stAppViewContainer"] { background: #000000 !important; }
.main .block-container { background: transparent !important; }
section[data-testid="stSidebar"] { background: #0A0A0A !important; }

/* Text */
p, span, li, h1, h2, h3, h4, h5 { color: #F5F5F7 !important; }
[data-testid="stMarkdownContainer"] * { color: #F5F5F7 !important; }
label { color: rgba(255,255,255,0.5) !important; }

/* Buttons — iOS blue */
[data-testid="stBaseButton-primary"] {
    background: #0A84FF !important;
    color: #ffffff !important;
    box-shadow: none !important;
}
[data-testid="stBaseButton-secondary"] {
    background: rgba(255,255,255,0.08) !important;
    border-color: transparent !important;
    color: #F5F5F7 !important;
}

/* Metrics — iOS grouped card */
[data-testid="stMetric"] {
    background: #1C1C1E !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 14px !important;
}
[data-testid="stMetricValue"] { color: #F5F5F7 !important; }
[data-testid="stMetricLabel"] { color: rgba(255,255,255,0.45) !important; }

/* Expander — iOS section group */
[data-testid="stExpander"] {
    background: #1C1C1E !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 14px !important;
}
[data-testid="stExpander"] * { color: #F5F5F7 !important; }
[data-testid="stExpander"] summary svg { fill: rgba(255,255,255,0.4) !important; }

/* Inputs */
.stTextInput input, .stTextArea textarea {
    background: #1C1C1E !important;
    border-color: rgba(255,255,255,0.12) !important;
    color: #F5F5F7 !important;
}
.stSelectbox > div > div {
    background: #1C1C1E !important;
    border-color: rgba(255,255,255,0.12) !important;
    color: #F5F5F7 !important;
}

/* Tabs */
[data-testid="stTabs"] [role="tablist"] { border-bottom-color: rgba(255,255,255,0.1) !important; }
[data-testid="stTabs"] [role="tab"] { color: rgba(255,255,255,0.4) !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #0A84FF !important;
    border-bottom-color: #0A84FF !important;
}

/* Custom components */
.ms-card {
    background: #1C1C1E !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    color: #F5F5F7 !important;
}
.flashcard {
    background: #1C1C1E !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
}
.flashcard-back {
    background: linear-gradient(135deg, #0A2240, #0A1F3D) !important;
    border-color: #0A84FF !important;
}
.flashcard-text { color: #F5F5F7 !important; }
.cite-box {
    background: rgba(255,255,255,0.05) !important;
    border-left-color: #0A84FF !important;
    color: rgba(255,255,255,0.6) !important;
}
.chat-assistant {
    background: #1C1C1E !important;
    border-color: rgba(255,255,255,0.08) !important;
    color: #F5F5F7 !important;
}
.page-title { color: #F5F5F7 !important; }
.page-sub { color: rgba(255,255,255,0.45) !important; }
.topic-chip {
    background: rgba(10,132,255,0.15) !important;
    color: #0A84FF !important;
    border-color: rgba(10,132,255,0.3) !important;
}
.badge-green  { background: rgba(52,199,89,0.15)  !important; color: #34C759 !important; }
.badge-yellow { background: rgba(255,204,0,0.15)  !important; color: #FFD60A !important; }
.badge-blue   { background: rgba(10,132,255,0.15) !important; color: #0A84FF !important; }
.badge-red    { background: rgba(255,69,58,0.15)  !important; color: #FF453A !important; }
</style>
"""


# ── Session state defaults ────────────────────────────────────────────────────
_DEFAULTS = {
    "page": "home",
    "subject_id": None,
    "chat_history": [],         # [{role, content, sources}]
    "flashcards": [],
    "card_idx": 0,
    "show_back": False,
    "quiz_questions": [],
    "quiz_answers": {},
    "quiz_submitted": False,
    "quiz_topic": "",
    "quiz_score": None,
    "dark_mode": False,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def nav(page: str):
    st.session_state["page"] = page
    st.rerun()


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _sidebar():
    with st.sidebar:
        st.markdown("## 🩺 MariaStudy")
        st.markdown("---")

        # New UC (at the top)
        with st.expander("➕ Nova Unidade Curricular"):
            new_name = st.text_input("Nome", key="new_subject_name", label_visibility="collapsed", placeholder="Ex: Cardiologia")
            if st.button("Criar", use_container_width=True):
                if new_name.strip():
                    s = sub_store.create_subject(new_name.strip())
                    st.session_state["subject_id"] = s["id"]
                    st.session_state["page"] = "files"
                    st.rerun()

        st.markdown("---")

        subjects = sub_store.list_subjects()

        # Subject selector
        if subjects:
            options = {s["id"]: s["name"] for s in subjects}
            current = st.session_state["subject_id"]
            if current not in options:
                current = list(options.keys())[0]
                st.session_state["subject_id"] = current

            selected = st.selectbox(
                "📂 Unidade Curricular activa",
                options=list(options.keys()),
                format_func=lambda x: options[x],
                index=list(options.keys()).index(current),
            )
            if selected != st.session_state["subject_id"]:
                st.session_state["subject_id"] = selected
                st.session_state["chat_history"] = []
                st.session_state["flashcards"] = []
                st.session_state["quiz_questions"] = []
                st.rerun()
        else:
            st.info("Cria uma Unidade Curricular para começar.")
            st.session_state["subject_id"] = None

        # Navigation
        st.markdown("---")
        pages = [
            ("🏠", "home", "Início"),
            ("📁", "files", "Ficheiros"),
            ("🗂️", "topics", "Tópicos"),
            ("💬", "qa", "Perguntas & Respostas"),
            ("🃏", "flashcards", "Flashcards"),
            ("📝", "quiz", "Quiz"),
            ("📊", "progress", "Progresso"),
        ]
        for icon, key, label in pages:
            active = st.session_state["page"] == key
            if st.button(
                f"{icon} {label}",
                key=f"nav_{key}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                nav(key)

        # Dark mode toggle
        st.markdown("---")
        dark = st.session_state["dark_mode"]
        if st.button(
            "☀️ Modo Claro" if dark else "🌙 Modo Escuro",
            use_container_width=True,
            key="toggle_dark",
        ):
            st.session_state["dark_mode"] = not dark
            st.rerun()


# ── Helper ────────────────────────────────────────────────────────────────────

def _require_subject():
    """Returns subject dict or stops with a message."""
    sid = st.session_state["subject_id"]
    if not sid:
        st.warning("Selecciona ou cria uma Unidade Curricular primeiro.")
        st.stop()
    s = sub_store.get_subject(sid)
    if not s:
        st.warning("Unidade Curricular não encontrada.")
        st.stop()
    return s


def _require_files(subject: dict):
    if not subject["files"]:
        st.info("Ainda não há ficheiros nesta Unidade Curricular. Vai a **Ficheiros** para fazer upload.")
        st.stop()


# ── Pages ─────────────────────────────────────────────────────────────────────

def _page_home():
    st.markdown('<p class="page-title">🩺 MariaStudy</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Vais ser a melhor Pediatra do Mundo!</p>', unsafe_allow_html=True)

    subjects = sub_store.list_subjects()

    if not subjects:
        st.markdown("""
        <div class="ms-card-blue">
        <h3 style="color:white;margin:0">Bem-vindo!</h3>
        <p style="color:#d6eaf8;margin-top:0.5rem">
        Começa por criar uma Unidade Curricular (ex: Cardiologia, Farmacologia) e faz upload dos teus PDFs.<br>
        O sistema irá extrair o conteúdo e preparar tudo para estudo.
        </p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Cross-subject search
    subjects_with_files = [s for s in subjects if s.get("files")]
    if len(subjects_with_files) >= 1:
        st.markdown("#### 🔎 Pesquisa em todas as Unidades Curriculares")
        with st.form("cross_search_form", clear_on_submit=False):
            cross_q = st.text_input(
                "Pesquisa global",
                placeholder="Ex: mecanismo de acção dos beta-bloqueadores…",
                label_visibility="collapsed",
            )
            cross_submitted = st.form_submit_button("Pesquisar", type="primary")

        if cross_submitted and cross_q.strip():
            with st.spinner("A pesquisar em todas as Unidades Curriculares…"):
                results = rag.search_all_subjects(cross_q, subjects_with_files, top_k=3)
            if results:
                st.markdown(f"**{len(results)} Unidade(s) Curricular(es) com resultados relevantes:**")
                for r in results:
                    relevance = max(0, round((1 - r["best_distance"]) * 100))
                    with st.expander(f"📚 {r['subject_name']} — {relevance}% relevância"):
                        for chunk in r["chunks"][:2]:
                            st.markdown(
                                f'<div class="cite-box">📄 <b>{chunk["metadata"]["file"]}</b> • '
                                f'Pág. {chunk["metadata"]["page"]}<br><small>{chunk["text"][:300]}…</small></div>',
                                unsafe_allow_html=True,
                            )
                        if st.button(f"Continuar em {r['subject_name']}", key=f"goto_{r['subject_id']}"):
                            st.session_state["subject_id"] = r["subject_id"]
                            st.session_state["chat_history"] = []
                            nav("qa")
            else:
                st.info("Nenhum resultado relevante encontrado.")

        st.markdown("---")

    st.markdown(f"**{len(subjects)} Unidade(s) Curricular(es)**")
    cols = st.columns(min(3, len(subjects)))
    for i, s in enumerate(subjects):
        with cols[i % 3]:
            n_files = len(s.get("files", []))
            n_chunks = collection_count(s["id"])
            st.markdown(f"""
            <div class="ms-card">
            <div style="font-size:1.1rem;font-weight:800;color:#1B4F72">{s['name']}</div>
            <div style="margin-top:0.5rem">
                <span class="badge badge-blue">{n_files} ficheiro(s)</span>
                <span class="badge badge-green" style="margin-left:4px">{n_chunks} excertos</span>
            </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Abrir", key=f"open_{s['id']}", use_container_width=True):
                st.session_state["subject_id"] = s["id"]
                nav("files")


def _page_files():
    s = _require_subject()
    st.markdown(f'<p class="page-title">📁 Ficheiros — {s["name"]}</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Faz upload de PDFs para serem processados e incorporados.</p>', unsafe_allow_html=True)

    # Upload
    with st.container():
        st.markdown('<div class="ms-card">', unsafe_allow_html=True)
        col_opts1, col_opts2 = st.columns(2)
        with col_opts1:
            enable_imgs = st.toggle("Extrair legendas de imagens (requer chamadas à API Groq)", value=False)
        with col_opts2:
            upload_type = st.radio(
                "Tipo de ficheiro",
                ["📚 Apontamentos", "📝 Exercícios"],
                horizontal=True,
                help="Exercícios são usados para enriquecer os quizzes, mas não para Q&A.",
            )
        file_type_val = "exercises" if "Exercícios" in upload_type else "notes"

        uploaded = st.file_uploader(
            "Selecciona ficheiros",
            type=["pdf", "txt", "md"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        if uploaded and st.button("⬆️ Processar e Incorporar", type="primary", use_container_width=True):
            any_ok = False
            for f in uploaded:
                existing = [x["name"] for x in s.get("files", [])]
                if f.name in existing:
                    st.warning(f"'{f.name}' já existe nesta Unidade Curricular.")
                    continue
                bar = st.progress(0, text="A extrair texto…")
                status = st.empty()

                def _cb(pct, msg, _bar=bar):
                    _bar.progress(min(pct, 0.95), text=msg)

                status.info(f"⏳ A processar **{f.name}**…")
                n = rag.ingest_file(
                    s["id"], f.read(), f.name,
                    enable_images=enable_imgs,
                    progress_cb=_cb,
                    file_type=file_type_val,
                )
                bar.progress(1.0, text="Concluído!")
                if n > 0:
                    status.success(f"✅ **{f.name}** — {n} excertos incorporados.")
                    any_ok = True
                else:
                    status.error(f"❌ Não foi possível processar {f.name}.")
            if any_ok:
                with st.spinner("A extrair tópicos e resumo…"):
                    rag._refresh_topics_and_summary(s["id"])
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # File list
    st.markdown("### Ficheiros incorporados")
    s = sub_store.get_subject(s["id"])  # refresh
    if not s["files"]:
        st.info("Ainda sem ficheiros.")
        return

    for file_info in s["files"]:
        col1, col2, col3, col4 = st.columns([4, 2, 2, 1])
        with col1:
            icon = "📝" if file_info.get("type") == "exercises" else "📄"
            st.markdown(f"{icon} **{file_info['name']}**")
        with col2:
            st.markdown(f"<span class='badge badge-blue'>{file_info.get('pages', '?')} págs.</span>", unsafe_allow_html=True)
        with col3:
            current_type = file_info.get("type", "notes")
            new_type_label = "📚 Apontamentos" if current_type == "exercises" else "📝 Exercícios"
            if st.button(new_type_label, key=f"type_{file_info['name']}", help="Mudar tipo", use_container_width=True):
                new_type = "notes" if current_type == "exercises" else "exercises"
                sub_store.set_file_type(s["id"], file_info["name"], new_type)
                st.rerun()
        with col4:
            if st.button("🗑️", key=f"del_{file_info['name']}", help="Remover ficheiro"):
                rag.delete_file(s["id"], file_info["name"])
                st.success(f"'{file_info['name']}' removido.")
                st.rerun()


def _page_topics():
    s = _require_subject()
    _require_files(s)
    st.markdown(f'<p class="page-title">🗂️ Tópicos — {s["name"]}</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Tópicos extraídos dos teus documentos. Podes adicionar ou remover tópicos manualmente.</p>', unsafe_allow_html=True)

    topics = s.get("topics", [])
    summary = s.get("summary", "")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### Tópicos de Estudo")
        if topics:
            for t in topics:
                btn_col, del_col = st.columns([5, 1])
                with btn_col:
                    if st.button(t, key=f"topic_{t}", use_container_width=True):
                        st.session_state["quiz_topic"] = t
                        nav("qa")
                with del_col:
                    if st.button("✕", key=f"del_topic_{t}", help=f"Remover «{t}»"):
                        new_topics = [x for x in topics if x != t]
                        sub_store.update_topics(s["id"], new_topics)
                        st.rerun()
        else:
            st.info("Nenhum tópico extraído. Faz upload de ficheiros.")

        with st.form("add_topic_form", clear_on_submit=True):
            new_topic = st.text_input("Adicionar tópico manualmente", placeholder="ex: Síndrome Nefrótico")
            if st.form_submit_button("➕ Adicionar", use_container_width=True):
                if new_topic.strip() and new_topic.strip() not in topics:
                    sub_store.update_topics(s["id"], topics + [new_topic.strip()])
                    st.rerun()

    with col2:
        st.markdown("#### Resumo do Documento")
        if summary:
            with st.container(border=True):
                st.markdown(summary)
        else:
            st.info("Resumo ainda não gerado.")

        btn_label = "🔄 Regenerar Resumo" if summary else "📄 Gerar Resumo"
        if st.button(btn_label, use_container_width=True):
            with st.spinner("A gerar resumo do documento…"):
                from src.vectorstore import sample_spread
                spread = sample_spread(s["id"], n=40)
                if spread:
                    sample = " ".join(c["text"] for c in spread)
                    existing_topics = s.get("topics") or None
                    new_summary = llm.generate_summary(sample, topics=existing_topics)
                    if new_summary:
                        sub_store.update_summary(s["id"], new_summary)
                        st.rerun()
                    else:
                        st.error("Não foi possível gerar o resumo. Tenta novamente.")
                else:
                    st.error("Sem conteúdo suficiente.")


def _page_qa():
    s = _require_subject()
    _require_files(s)
    st.markdown(f'<p class="page-title">💬 Perguntas & Respostas — {s["name"]}</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Faz perguntas sobre os teus documentos. Todas as respostas incluem citações.</p>', unsafe_allow_html=True)

    topics = s.get("topics", [])

    # Topic filter + suggested questions row
    col_filter, col_clear = st.columns([4, 1])
    with col_filter:
        topic_options = ["🔍 Todos os tópicos"] + topics
        selected_topic = st.selectbox(
            "Filtrar por tópico",
            topic_options,
            key="qa_topic_filter",
            label_visibility="collapsed",
            help="Restringe a pesquisa a um tópico específico para respostas mais focadas.",
        )
        active_topic = None if selected_topic == "🔍 Todos os tópicos" else selected_topic
    with col_clear:
        if st.session_state["chat_history"] and st.button("🗑️ Limpar", use_container_width=True):
            st.session_state["chat_history"] = []
            st.rerun()

    if active_topic:
        st.markdown(
            f'<div class="cite-box">🎯 Pesquisa focada em: <b>{active_topic}</b></div>',
            unsafe_allow_html=True,
        )

    # Suggested questions
    if topics:
        display_topics = [active_topic] if active_topic else topics[:6]
        with st.expander("💡 Sugestões de perguntas"):
            cols = st.columns(3)
            suggestions = [
                f"Explica {t}" for t in display_topics[:3]
            ] + [
                f"Quais os critérios de diagnóstico de {t}?" for t in display_topics[:3]
            ]
            for i, q in enumerate(suggestions[:6]):
                with cols[i % 3]:
                    if st.button(q, key=f"suggest_{i}", use_container_width=True):
                        st.session_state["chat_history"].append({"role": "user", "content": q, "sources": [], "topic": active_topic})
                        with st.spinner("A pesquisar…"):
                            res = rag.ask(s["id"], q, topic_filter=active_topic)
                        st.session_state["chat_history"].append({
                            "role": "assistant", "content": res["answer"], "sources": res["sources"],
                        })
                        st.rerun()

    # Chat history
    for msg_idx, msg in enumerate(st.session_state["chat_history"]):
        if msg["role"] == "user":
            topic_badge = f' <span class="badge badge-blue">{msg.get("topic")}</span>' if msg.get("topic") else ""
            st.markdown(f'<div class="chat-user">{msg["content"]}{topic_badge}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-assistant">{msg["content"]}</div>', unsafe_allow_html=True)
            if msg.get("sources"):
                with st.expander("📚 Fontes citadas"):
                    for i, src in enumerate(msg["sources"], 1):
                        st.markdown(
                            f'<div class="cite-box">[{i}] 📄 <b>{src["file"]}</b> • Página {src["page"]}</div>',
                            unsafe_allow_html=True,
                        )
            # Follow-up suggestions (only for last assistant message)
            if msg.get("followups") and msg_idx == len(st.session_state["chat_history"]) - 1:
                st.markdown("**🔗 Aprofundar:**")
                fu_cols = st.columns(len(msg["followups"]))
                for fi, fq in enumerate(msg["followups"]):
                    with fu_cols[fi]:
                        if st.button(fq, key=f"fu_{msg_idx}_{fi}", use_container_width=True):
                            st.session_state["chat_history"].append({"role": "user", "content": fq, "sources": [], "topic": active_topic})
                            with st.spinner("A pesquisar…"):
                                res = rag.ask(s["id"], fq, topic_filter=active_topic)
                                followups = llm.suggest_followups(fq, res["answer"])
                            st.session_state["chat_history"].append({
                                "role": "assistant", "content": res["answer"],
                                "sources": res["sources"], "followups": followups,
                            })
                            st.rerun()

    # Input
    st.markdown("---")
    with st.form("qa_form", clear_on_submit=True):
        question = st.text_area(
            "A tua pergunta",
            placeholder="Ex: Quais são os critérios de diagnóstico para…",
            label_visibility="collapsed",
            height=80,
        )
        submitted = st.form_submit_button("Enviar →", type="primary", use_container_width=True)

    if submitted and question.strip():
        st.session_state["chat_history"].append({"role": "user", "content": question, "sources": [], "topic": active_topic})
        with st.spinner("A pesquisar e a gerar resposta…"):
            res = rag.ask(s["id"], question, topic_filter=active_topic)
            followups = llm.suggest_followups(question, res["answer"])
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": res["answer"],
            "sources": res["sources"],
            "followups": followups,
        })
        st.rerun()


def _cloze_front(text: str) -> str:
    """Replace {{c1::term}} with _____ for display on card front."""
    return _re.sub(r"\{\{c\d+::([^}]+)\}\}", "<u>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</u>", text)


def _cloze_back(text: str) -> str:
    """Highlight the answer term on card back."""
    return _re.sub(r"\{\{c\d+::([^}]+)\}\}", r"<b style='color:#4f8ef7'>\1</b>", text)


def _page_flashcards():
    s = _require_subject()
    _require_files(s)
    st.markdown(f'<p class="page-title">🃏 Flashcards — {s["name"]}</p>', unsafe_allow_html=True)

    topics = s.get("topics", [])
    srs_stats = prog.get_srs_stats(s["id"])

    tab_study, tab_deck, tab_favs = st.tabs([
        "📖 Estudar",
        f"🗃️ Baralho ({srs_stats['total']})",
        f"⭐ Favoritos ({srs_stats.get('favorites', 0)})",
    ])

    # ── Favorites tab ────────────────────────────────────────────────────────
    with tab_favs:
        fav_cards = prog.get_favorite_cards(s["id"])
        if not fav_cards:
            st.info("Ainda não marcaste nenhuma carta como favorita. Usa ⭐ durante o estudo.")
        else:
            for i, fc in enumerate(fav_cards):
                label = _cloze_front(fc["frente"]) if fc.get("card_type") == "cloze" else fc["frente"]
                with st.expander(f"⭐ {label}", expanded=False):
                    st.markdown(f"**Resposta:** {fc['verso']}")
                    if fc.get("fonte"):
                        st.markdown(f"<span class='badge badge-blue'>📄 {fc['fonte']}</span>", unsafe_allow_html=True)
                    if st.button("Remover dos favoritos", key=f"unfav_{i}"):
                        prog.toggle_favorite(s["id"], fc)
                        st.rerun()

    # ── Deck tab ─────────────────────────────────────────────────────────────
    with tab_deck:
        deck_cards = prog.get_deck_cards(s["id"])

        # Import section
        with st.expander("📥 Importar flashcards"):
            st.markdown(
                "Cola as tuas flashcards abaixo. Formato suportado (uma por linha):\n"
                "- **Separado por tab:** `frente\\tverso` ou `frente\\tverso\\tfonte`\n"
                "- **Separado por ponto e vírgula:** `frente;verso;fonte`\n"
                "- Linhas com `#` são ignoradas (comentários)\n"
                "- Cloze Anki é suportado: `A {{c1::insulina}} é produzida pelo pâncreas`"
            )
            import_text = st.text_area("Colar flashcards", height=150, placeholder="frente\tverso\nfrente2\tverso2")
            uploaded = st.file_uploader("Ou carrega ficheiro (.txt, .tsv)", type=["txt", "tsv"])
            if uploaded:
                import_text = uploaded.read().decode("utf-8")
            if st.button("📥 Importar", type="primary", use_container_width=True):
                if import_text and import_text.strip():
                    parsed = prog.parse_import_text(import_text)
                    if parsed:
                        added = prog.import_cards(s["id"], parsed)
                        st.success(f"{added} carta(s) nova(s) importada(s) ({len(parsed) - added} duplicadas ignoradas).")
                        st.rerun()
                    else:
                        st.error("Não foi possível interpretar o texto. Verifica o formato.")

        if not deck_cards:
            st.info("O baralho está vazio. Gera flashcards no separador Estudar ou importa acima.")
        else:
            # Stats row
            status_counts = {}
            for dc in deck_cards:
                status_counts[dc["status"]] = status_counts.get(dc["status"], 0) + 1
            cols = st.columns(len(status_counts))
            labels = {"nova": "🆕 Novas", "para rever": "🔁 Para rever", "a aprender": "📚 A aprender", "dominada": "✅ Dominadas"}
            for col, (status, count) in zip(cols, status_counts.items()):
                col.metric(labels.get(status, status), count)

            st.markdown("---")

            # Study due button
            due_cards = [c for c in deck_cards if c["status"] in ("nova", "para rever")]
            if due_cards:
                if st.button(f"🚀 Estudar {len(due_cards)} carta(s) pendentes", type="primary", use_container_width=True):
                    st.session_state["flashcards"] = due_cards
                    st.session_state["card_idx"] = 0
                    st.session_state["show_back"] = False
                    nav("flashcards")
                    st.rerun()

            # Card list
            search = st.text_input("🔍 Pesquisar no baralho", placeholder="termo ou palavra-chave")
            filtered = [c for c in deck_cards if not search or search.lower() in c["frente"].lower() or search.lower() in c["verso"].lower()]
            st.markdown(f"**{len(filtered)} carta(s)**")
            for i, dc in enumerate(filtered):
                badge = {"nova": "🆕", "para rever": "🔁", "a aprender": "📚", "dominada": "✅"}.get(dc["status"], "")
                type_badge = "🔵" if dc.get("card_type") == "cloze" else "⬜"
                label = _cloze_front(dc["frente"]) if dc.get("card_type") == "cloze" else dc["frente"]
                with st.expander(f"{badge} {type_badge} {label[:80]}", expanded=False):
                    st.markdown(f"**Verso:** {dc['verso']}")
                    if dc.get("fonte"):
                        st.markdown(f"<span class='badge badge-blue'>📄 {dc['fonte']}</span>", unsafe_allow_html=True)
                    meta_col, del_col = st.columns([3, 1])
                    meta_col.caption(f"Intervalo: {dc['interval']}d · Repetições: {dc['reps']} · Próxima: {dc['next_review']}")
                    if del_col.button("🗑️ Apagar", key=f"del_card_{i}"):
                        prog.delete_card(s["id"], dc["frente"])
                        st.rerun()

    # ── Study tab ────────────────────────────────────────────────────────────
    with tab_study:
        with st.expander("⚙️ Gerar novas flashcards", expanded=not bool(st.session_state["flashcards"])):
            ALL_SUBJECT = "🌐 Toda a UC"
            topic_options = [ALL_SUBJECT] + topics + ["(personalizado)"]
            sel_topic = st.selectbox("Tópico", topic_options, key="fc_topic_sel")
            if sel_topic == "(personalizado)":
                topic_input = st.text_input("Escreve o tópico", key="fc_topic_custom")
            else:
                topic_input = sel_topic

            n_cards = st.slider("Número de flashcards", 5, 20, 10)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("✨ Gerar Flashcards", type="primary", use_container_width=True):
                    if topic_input:
                        with st.spinner(f"A gerar {n_cards} flashcards…"):
                            if topic_input == ALL_SUBJECT:
                                chunks = vectorstore.sample_spread(s["id"], n=16)
                                topic_label = s["name"]
                            else:
                                chunks = rag.get_topic_chunks(s["id"], topic_input, top_k=8)
                                topic_label = topic_input
                            if chunks:
                                cards = llm.generate_flashcards(chunks, topic_label, n_cards)
                                # Save all cards to deck immediately
                                for c in cards:
                                    prog.save_card_to_deck(s["id"], c)
                                cards = prog.sort_cards_by_due(s["id"], cards)
                                st.session_state["flashcards"] = cards
                                st.session_state["card_idx"] = 0
                                st.session_state["show_back"] = False
                            else:
                                st.error("Sem conteúdo relevante para este tópico.")
                        st.rerun()
            with col2:
                due_count = srs_stats["due"] + srs_stats.get("new", 0)
                if due_count > 0:
                    if st.button(f"🔁 Rever pendentes ({due_count})", use_container_width=True):
                        due_deck = [c for c in prog.get_deck_cards(s["id"]) if c["status"] in ("nova", "para rever")]
                        if due_deck:
                            st.session_state["flashcards"] = due_deck
                            st.session_state["card_idx"] = 0
                            st.session_state["show_back"] = False
                            st.rerun()

        # SRS stats
        if srs_stats["total"] > 0:
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Total", srs_stats["total"])
            c2.metric("🆕 Novas", srs_stats.get("new", 0))
            c3.metric("✅ Dominadas", srs_stats["mastered"])
            c4.metric("🔁 Para rever", srs_stats["due"])
            c5.metric("⭐ Favoritas", srs_stats.get("favorites", 0))

        cards = st.session_state["flashcards"]
        if not cards:
            return

        idx = st.session_state["card_idx"]
        if idx >= len(cards):
            st.success("🎉 Reviste todas as flashcards!")
            if st.button("Começar de novo"):
                st.session_state["card_idx"] = 0
                st.session_state["show_back"] = False
                st.rerun()
            return

        card = cards[idx]
        is_cloze = card.get("card_type") == "cloze"
        show_back = st.session_state["show_back"]
        is_fav = prog.is_favorite(s["id"], card.get("frente", ""))

        st.progress(idx / len(cards), text=f"Carta {idx + 1} de {len(cards)}")

        if not show_back:
            front_text = _cloze_front(card.get("frente", "")) if is_cloze else card.get("frente", "")
            card_type_label = "Cloze" if is_cloze else "Frente"
            st.markdown(f"""
            <div class="flashcard">
                <div class="flashcard-front-label">{card_type_label}</div>
                <div class="flashcard-text">{front_text}</div>
            </div>
            """, unsafe_allow_html=True)
            btn_col, fav_col = st.columns([4, 1])
            with btn_col:
                if st.button("👁️ Revelar resposta", type="primary", use_container_width=True):
                    st.session_state["show_back"] = True
                    st.rerun()
            with fav_col:
                fav_label = "⭐" if is_fav else "☆"
                if st.button(fav_label, use_container_width=True, help="Adicionar/remover favorito"):
                    prog.toggle_favorite(s["id"], card)
                    st.rerun()
        else:
            back_text = _cloze_back(card.get("verso", "")) if is_cloze else card.get("verso", "")
            st.markdown(f"""
            <div class="flashcard flashcard-back">
                <div class="flashcard-front-label">Verso</div>
                <div class="flashcard-text">{back_text}</div>
                <div class="flashcard-source">📄 {card.get('fonte', '')}</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("**Como correu?**")
            c1, c2, c3, c4, c_fav = st.columns(5)
            with c1:
                if st.button("🔁 Outra vez", use_container_width=True):
                    prog.save_flashcard_result(s["id"], card, "again")
                    cards.append(cards.pop(idx))
                    st.session_state["flashcards"] = cards
                    st.session_state["show_back"] = False
                    st.rerun()
            with c2:
                if st.button("😓 Difícil", use_container_width=True):
                    prog.save_flashcard_result(s["id"], card, "hard")
                    st.session_state["card_idx"] += 1
                    st.session_state["show_back"] = False
                    st.rerun()
            with c3:
                if st.button("👍 Bom", use_container_width=True, type="primary"):
                    prog.save_flashcard_result(s["id"], card, "good")
                    st.session_state["card_idx"] += 1
                    st.session_state["show_back"] = False
                    st.rerun()
            with c4:
                if st.button("✅ Fácil", use_container_width=True):
                    prog.save_flashcard_result(s["id"], card, "easy")
                    st.session_state["card_idx"] += 1
                    st.session_state["show_back"] = False
                    st.rerun()
            with c_fav:
                fav_label = "⭐" if is_fav else "☆"
                if st.button(fav_label, use_container_width=True):
                    prog.toggle_favorite(s["id"], card)
                    st.rerun()


def _page_quiz():
    s = _require_subject()
    _require_files(s)
    st.markdown(f'<p class="page-title">📝 Quiz — {s["name"]}</p>', unsafe_allow_html=True)

    topics = s.get("topics", [])

    # Config form
    if not st.session_state["quiz_questions"]:
        ALL_SUBJECT_Q = "🌐 Toda a UC"
        with st.form("quiz_config"):
            st.markdown("### Configurar Quiz")
            topic_opts = [ALL_SUBJECT_Q] + topics + ["(personalizado)"]
            sel = st.selectbox("Tópico", topic_opts)
            if sel == "(personalizado)":
                topic = st.text_input("Escreve o tópico")
            else:
                topic = sel

            col1, col2 = st.columns(2)
            with col1:
                n_q = st.select_slider("Número de questões", [5, 10, 15], value=5)
            with col2:
                diff = st.selectbox("Dificuldade", ["Fácil", "Médio", "Difícil"])

            go = st.form_submit_button("🚀 Gerar Quiz", type="primary", use_container_width=True)

        if go and topic:
            with st.spinner("A gerar quiz…"):
                if topic == ALL_SUBJECT_Q:
                    chunks = vectorstore.sample_spread(s["id"], n=16)
                    topic_label = s["name"]
                else:
                    chunks = rag.get_topic_chunks(s["id"], topic, top_k=10)
                    topic_label = topic
                if not chunks:
                    st.error("Sem conteúdo relevante para este tópico.")
                    return
                questions = llm.generate_quiz(chunks, topic_label, n_q, diff)
                st.session_state["quiz_questions"] = questions
                st.session_state["quiz_topic"] = topic_label
                st.session_state["quiz_answers"] = {}
                st.session_state["quiz_submitted"] = False
                st.session_state["quiz_score"] = None
            st.rerun()
        return

    questions = st.session_state["quiz_questions"]
    topic = st.session_state["quiz_topic"]
    submitted = st.session_state["quiz_submitted"]

    st.markdown(f"**Tema:** {topic} &nbsp;|&nbsp; **{len(questions)} questões**")

    if not submitted:
        with st.form("quiz_form"):
            for i, q in enumerate(questions):
                st.markdown(f"**{i+1}. {q['pergunta']}**")
                ans = st.radio(
                    f"q{i}",
                    q["opcoes"],
                    index=None,
                    key=f"q_{i}",
                    label_visibility="collapsed",
                )
                st.session_state["quiz_answers"][i] = ans
                st.markdown("---")

            submit_quiz = st.form_submit_button("✅ Submeter", type="primary", use_container_width=True)

        if submit_quiz:
            score = 0
            answers = {}
            for i, q in enumerate(questions):
                user_ans = st.session_state.get(f"q_{i}")
                correct_idx = q.get("correta", 0)
                correct_opt = q["opcoes"][correct_idx] if correct_idx < len(q["opcoes"]) else ""
                is_correct = user_ans == correct_opt
                if is_correct:
                    score += 1
                answers[i] = {"user": user_ans, "correct": correct_opt, "is_correct": is_correct}

            st.session_state["quiz_submitted"] = True
            st.session_state["quiz_score"] = score
            st.session_state["quiz_answers"] = answers
            prog.save_quiz_result(s["id"], topic, score, len(questions))
            st.rerun()
    else:
        score = st.session_state["quiz_score"]
        total = len(questions)
        pct = round(score / total * 100)

        color = "badge-green" if pct >= 70 else ("badge-yellow" if pct >= 40 else "badge-red")
        st.markdown(
            f'<div class="ms-card"><h2 style="text-align:center;color:#1B4F72">'
            f'Resultado: <span class="{color} badge">{score}/{total} ({pct}%)</span></h2></div>',
            unsafe_allow_html=True,
        )

        for i, q in enumerate(questions):
            ans_info = st.session_state["quiz_answers"].get(i, {})
            is_correct = ans_info.get("is_correct", False)
            icon = "✅" if is_correct else "❌"
            color_bg = "#D5F5E3" if is_correct else "#FADBD8"

            with st.expander(f"{icon} {i+1}. {q['pergunta']}"):
                st.markdown(
                    f'<div style="background:{color_bg};padding:0.6rem;border-radius:8px;margin-bottom:0.5rem">'
                    f'<b>A tua resposta:</b> {ans_info.get("user", "—")}</div>',
                    unsafe_allow_html=True,
                )
                if not is_correct:
                    st.markdown(
                        f'<div style="background:#D5F5E3;padding:0.6rem;border-radius:8px;margin-bottom:0.5rem">'
                        f'<b>Resposta correcta:</b> {ans_info.get("correct", "—")}</div>',
                        unsafe_allow_html=True,
                    )
                st.markdown(f"**Explicação:** {q.get('explicacao', '')}")
                st.markdown(
                    f'<div class="cite-box">📄 {q.get("fonte", "")}</div>',
                    unsafe_allow_html=True,
                )

        if st.button("🔄 Novo Quiz", use_container_width=True, type="primary"):
            st.session_state["quiz_questions"] = []
            st.session_state["quiz_submitted"] = False
            st.session_state["quiz_score"] = None
            st.rerun()


def _page_progress():
    s = _require_subject()
    st.markdown(f'<p class="page-title">📊 Progresso — {s["name"]}</p>', unsafe_allow_html=True)

    history = prog.get_quiz_history(s["id"])
    srs = prog.get_srs_stats(s["id"])
    files = s.get("files", [])
    total_pages = sum(f.get("pages", 0) for f in files)
    n_chunks = collection_count(s["id"])

    # Stats row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ficheiros", len(files))
    c2.metric("Páginas incorporadas", total_pages)
    c3.metric("Excertos no sistema", n_chunks)
    c4.metric("Quizzes realizados", len(history))

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Histórico de Quizzes")
        if history:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[f"{h['date']} — {h['topic'][:20]}" for h in history],
                y=[h["pct"] for h in history],
                marker_color=["#2ECC71" if h["pct"] >= 70 else ("#F39C12" if h["pct"] >= 40 else "#E74C3C") for h in history],
                text=[f"{h['pct']}%" for h in history],
                textposition="auto",
            ))
            fig.update_layout(
                yaxis_title="Percentagem (%)",
                yaxis_range=[0, 100],
                plot_bgcolor="white",
                paper_bgcolor="white",
                margin=dict(l=10, r=10, t=10, b=80),
                font=dict(family="Nunito"),
                xaxis_tickangle=-35,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Ainda não realizaste nenhum quiz.")

    with col2:
        st.markdown("#### Evolução por Tópico")
        topic_stats = prog.get_topic_stats(s["id"])
        if topic_stats:
            for ts in topic_stats:
                pct = ts["avg_pct"]
                color = "#2ECC71" if pct >= 70 else ("#F39C12" if pct >= 40 else "#E74C3C")
                badge_class = "badge-green" if pct >= 70 else ("badge-yellow" if pct >= 40 else "badge-red")
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;align-items:center;"
                    f"padding:6px 0;border-bottom:1px solid #EBF5FB'>"
                    f"<span style='font-weight:600'>{ts['topic']}</span>"
                    f"<span><span class='badge {badge_class}'>{pct}%</span> "
                    f"<span style='color:#888;font-size:0.85em'>{ts['attempts']}× tentativas</span></span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("Ainda não realizaste nenhum quiz.")

    st.markdown("---")
    st.markdown("#### Flashcards (SRS)")
    if srs["total"] > 0:
        col3, col4 = st.columns(2)
        with col3:
            labels = ["Dominadas", "Em aprendizagem", "Para rever hoje"]
            values = [srs["mastered"], srs["learning"] - srs["due"], srs["due"]]
            values = [max(0, v) for v in values]
            fig2 = go.Figure(go.Pie(
                labels=labels,
                values=values,
                hole=0.5,
                marker_colors=["#2ECC71", "#3498DB", "#E74C3C"],
                textinfo="label+percent",
            ))
            fig2.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="white",
                font=dict(family="Nunito"),
                showlegend=False,
            )
            st.plotly_chart(fig2, use_container_width=True)
        with col4:
            c1, c2 = st.columns(2)
            c1.metric("Total estudadas", srs["total"])
            c2.metric("Favoritas", srs.get("favorites", 0))
            c1.metric("Dominadas (≥21d)", srs["mastered"])
            c2.metric("Para rever hoje", srs["due"])
    else:
        st.info("Ainda não estudaste flashcards nesta Unidade Curricular.")

    # Delete subject
    st.markdown("---")
    with st.expander("⚠️ Zona de perigo"):
        st.warning(f"Eliminar a Unidade Curricular **{s['name']}** apaga todos os ficheiros, excertos e progresso.")
        if st.button("🗑️ Eliminar Unidade Curricular", type="secondary"):
            from src.vectorstore import delete_collection
            delete_collection(s["id"])
            sub_store.delete_subject(s["id"])
            st.session_state["subject_id"] = None
            st.session_state["page"] = "home"
            st.rerun()


# ── Main ──────────────────────────────────────────────────────────────────────

_PAGES = {
    "home": _page_home,
    "files": _page_files,
    "topics": _page_topics,
    "qa": _page_qa,
    "flashcards": _page_flashcards,
    "quiz": _page_quiz,
    "progress": _page_progress,
}


def main():
    _sidebar()
    if st.session_state.get("dark_mode"):
        st.markdown(_DARK_CSS, unsafe_allow_html=True)
    page_fn = _PAGES.get(st.session_state["page"], _page_home)
    page_fn()


if __name__ == "__main__":
    main()
