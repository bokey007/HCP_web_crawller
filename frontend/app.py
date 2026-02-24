"""
HCP Web Crawler — Streamlit Dashboard
A visually rich, dark-themed dashboard for uploading HCP Excel files,
monitoring agent processing, and viewing/exporting results.
"""

from __future__ import annotations

import time

import requests
import streamlit as st

# ── Page Config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="HCP Web Crawler — AI Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Constants ────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000/api/v1"

# ── Custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Global ───────────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        background-color: #f4f5f7;
        font-family: 'Inter', 'Segoe UI', sans-serif;
        color: #1a1a1a;
    }

    /* ── Sidebar ──────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background-color: #08312A;
        border-right: 1px solid #E5E3DE;
    }
    
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span, 
    section[data-testid="stSidebar"] li {
        color: #ffffff !important;
    }

    section[data-testid="stSidebar"] .stMarkdown h1 {
        color: #00E47C !important;
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    /* ── KPI Cards ────────────────────────────────────────────────── */
    .kpi-card {
        background: #ffffff;
        border: 1px solid #E5E3DE;
        border-radius: 8px;
        padding: 24px;
        text-align: center;
        transition: all 0.2s ease;
        min-height: 140px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }

    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.08);
        border-color: #00E47C;
    }

    .kpi-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #08312A;
        margin-bottom: 4px;
        line-height: 1.2;
    }

    .kpi-value.green {
        color: #1a8f59;
    }

    .kpi-label {
        font-size: 0.85rem;
        color: #666666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
    }

    /* ── Main Container ──────────────────────────────────────────── */
    .glass-container {
        background: #ffffff;
        border: 1px solid #E5E3DE;
        border-radius: 8px;
        padding: 32px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.02);
    }

    /* ── Status Badges ────────────────────────────────────────────── */
    .badge-found {
        background-color: #e6f9f0;
        color: #1a8f59;
        border: 1px solid #1a8f59;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .badge-partial {
        background-color: #fff8e6;
        color: #d97706;
        border: 1px solid #d97706;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .badge-not-found {
        background-color: #f3f4f6;
        color: #6b7280;
        border: 1px solid #d1d5db;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .badge-error {
        background-color: #fef2f2;
        color: #dc2626;
        border: 1px solid #dc2626;
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.75rem;
        font-weight: 600;
    }

    /* ── Headers ──────────────────────────────────────────────────── */
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #08312A;
        text-align: left;
        margin-bottom: 4px;
        letter-spacing: -0.5px;
    }

    .subtitle {
        color: #666666;
        text-align: left;
        font-size: 1rem;
        margin-bottom: 32px;
    }

    /* ── Upload area ─────────────────────────────────────────────── */
    .upload-area {
        background: #fafafa;
        border: 1px dashed #cccccc;
        border-radius: 8px;
        padding: 40px;
        text-align: center;
        transition: all 0.2s ease;
    }

    .upload-area:hover {
        border-color: #08312A;
        background: #f0fdf6;
    }

    /* ── Override Streamlit defaults ──────────────────────────────── */
    .stDataFrame {
        border-radius: 8px;
        border: 1px solid #E5E3DE;
    }

    .stProgress > div > div {
        background-color: #00E47C;
        border-radius: 10px;
    }
    
    div[data-testid="stButton"] button {
        background-color: #08312A;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    div[data-testid="stButton"] button:hover {
        background-color: #06231e;
        color: white;
        box-shadow: 0 4px 12px rgba(8, 49, 42, 0.2);
    }
    
    /* Expander styling for results */
    div[data-testid="stExpander"] {
        border: 1px solid #E5E3DE;
        border-radius: 8px;
        background: #ffffff;
        box-shadow: 0 1px 4px rgba(0,0,0,0.02);
    }

    /* ── Tabs ─────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 16px;
        border-bottom: 1px solid #E5E3DE;
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border: none;
        color: #666666;
        font-weight: 600;
        padding-bottom: 12px;
    }

    .stTabs [aria-selected="true"] {
        color: #08312A !important;
        border-bottom: 3px solid #00E47C !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Helper Functions ─────────────────────────────────────────────────

def api_call(method: str, endpoint: str, **kwargs):
    """Make an API call to the backend."""
    try:
        resp = getattr(requests, method)(f"{API_BASE}{endpoint}", **kwargs)
        resp.raise_for_status()
        return resp
    except requests.exceptions.ConnectionError:
        st.error("⚠️ Cannot connect to the backend API. Is the server running?")
        return None
    except requests.exceptions.HTTPError as exc:
        st.error(f"API Error: {exc.response.text}")
        return None


def get_badge_html(status: str) -> str:
    """Return HTML for a status badge."""
    mapping = {
        "FOUND": ("badge-found", "✅ Found"),
        "PARTIAL": ("badge-partial", "⚠️ Partial"),
        "NOT_FOUND": ("badge-not-found", "— Not Found"),
        "PROCESSING": ("badge-not-found", "⏳ Processing"),
        "ERROR": ("badge-error", "❌ Error"),
    }
    css_class, label = mapping.get(status, ("badge-not-found", status))
    return f'<span class="{css_class}">{label}</span>'


# ── Sidebar ──────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<h1 style="color:#00E47C;font-size:1.8rem;">Boehringer<br/>Ingelheim</h1>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("**HCP Contact Discovery Engine**")
    st.markdown("")
    st.markdown(
        "Upload an Excel sheet with Healthcare Provider details and let the AI agent "
        "search the open internet to securely find their contact information."
    )
    st.markdown("---")
    st.markdown("##### 🌐 Trusted Sources")
    st.markdown("""
    - 🏥 Doximity
    - 📋 NPI Profile
    - 🏛️ Government (.gov)
    - 🎓 Education (.edu)
    - 🏨 Hospital websites
    """)
    st.markdown("---")
    st.markdown(
        "<div style='color: rgba(255,255,255,0.5); font-size: 0.75rem;'>"
        "v2.0.0 • Enterprise Edition</div>",
        unsafe_allow_html=True,
    )

# ── Main Content ─────────────────────────────────────────────────────

st.markdown('<div class="main-title">HCP Web Crawler</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">AI Agent for Automated Healthcare Provider Contact Discovery</div>',
    unsafe_allow_html=True,
)

# ── Stats Dashboard (always visible at top) ──────────────────────────
resp = api_call("get", "/stats")
if resp:
    stats = resp.json()
    cols = st.columns(6)

    kpi_data = [
        (stats.get("total_records_processed", 0), "Records Processed", ""),
        (stats.get("hcps_found", 0), "HCPs Found", "green"),
        (stats.get("hcps_not_found", 0), "Not Found", ""),
        (f"{stats.get('success_rate_pct', 0)}%", "Success Rate", "green"),
        (f"{stats.get('hours_saved', 0)}h", "Hours Saved", "gold"),
        (f"${stats.get('dollars_saved', 0):,.0f}", "Dollars Saved", "gold"),
    ]

    for col, (value, label, color_class) in zip(cols, kpi_data):
        with col:
            st.markdown(
                f"""<div class="kpi-card">
                    <div class="kpi-value {color_class}">{value}</div>
                    <div class="kpi-label">{label}</div>
                </div>""",
                unsafe_allow_html=True,
            )

st.markdown("<div style='margin-bottom:16px'></div>", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────
tab_upload, tab_monitor, tab_results = st.tabs(["📤 Upload", "📊 Monitor", "📋 Results"])

# ── Tab 1: Upload ────────────────────────────────────────────────────
with tab_upload:

    st.markdown("### 📤 Upload HCP Excel File")
    st.markdown(
        "Upload a `.xlsx` file with columns: **PROJECT_ID**, FIRST_NAME, "
        "MIDDLE_NAME, LAST_NAME, ADDRESS_LINE_1, ADDRESS_LINE_2, CITY, STATE_CODE"
    )

    uploaded_file = st.file_uploader(
        "Choose an Excel file",
        type=["xlsx", "xls"],
        help="The file must contain a PROJECT_ID column. Other columns are optional.",
    )

    if uploaded_file:
        st.success(f"📄 **{uploaded_file.name}** — {uploaded_file.size / 1024:.1f} KB")

        # Preview
        try:
            import pandas as pd
            df_preview = pd.read_excel(uploaded_file, nrows=5)
            st.markdown("**Preview (first 5 rows):**")
            st.dataframe(df_preview, use_container_width=True)
            uploaded_file.seek(0)  # Reset for upload
        except Exception:
            st.warning("Could not preview the file, but it will still be processed.")

        if st.button("🚀 Start Processing", type="primary", use_container_width=True):
            with st.spinner("Uploading and starting agent..."):
                resp = api_call(
                    "post",
                    "/upload",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue())},
                )
                if resp:
                    data = resp.json()
                    st.session_state["active_job_id"] = data["job_id"]
                    st.session_state["total_records"] = data["total_records"]
                    st.success(
                        f"✅ Job created! ID: `{data['job_id'][:8]}...` — "
                        f"{data['total_records']} records queued."
                    )
                    st.info("Switch to the **📊 Monitor** tab to track progress.")




# ── Tab 2: Monitor ───────────────────────────────────────────────────
with tab_monitor:

    st.markdown("### 📊 Processing Monitor")

    job_id = st.session_state.get("active_job_id", "")

    resp = api_call("get", "/jobs")
    if resp and resp.status_code == 200:
        jobs = resp.json()
        if jobs:
            options = {j["job_id"]: f"📁 {j['filename']} ({j['total_records']} rows) • {j['status']} • {j['created_at'][:16].replace('T', ' ')}" for j in jobs}
            
            default_index = 0
            if job_id in options:
                default_index = list(options.keys()).index(job_id)
            
            job_id = st.selectbox(
                "Select a Job to Monitor:",
                options=list(options.keys()),
                format_func=lambda x: options[x],
                index=default_index
            )
        else:
            job_id = None
    else:
        job_id = None

    if job_id:
        resp = api_call("get", f"/jobs/{job_id}")
        if resp:
            progress = resp.json()
            status = progress.get("status", "PENDING")

            # Status indicator
            status_colors = {
                "PENDING": "🟡",
                "PROCESSING": "🔵",
                "COMPLETED": "🟢",
                "FAILED": "🔴",
            }
            st.markdown(
                f"**Status:** {status_colors.get(status, '⚪')} {status} "
                f"| **Records:** {progress.get('processed_records', 0)}/{progress.get('total_records', 0)}"
            )

            # Progress bar
            pct = progress.get("progress_pct", 0) / 100
            st.progress(pct, text=f"{progress.get('progress_pct', 0)}% complete")

            # Mini stats 
            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("✅ Found", progress.get("found_count", 0))
            mc2.metric("❌ Not Found", progress.get("not_found_count", 0))
            mc3.metric("⚠️ Errors", progress.get("error_count", 0))
            mc4.metric("📊 Processed", progress.get("processed_records", 0))

            if status == "COMPLETED":
                st.success("🎉 Processing complete! Check the **📋 Results** tab.")
            elif status == "FAILED":
                st.error("Processing failed. Check server logs for details.")
            elif status in ("PENDING", "PROCESSING"):
                st.info("⏳ Auto-refreshing every 5 seconds…")
                time.sleep(5)
                st.rerun()

    else:
        st.info("Upload a file first to start monitoring.")




# ── Tab 3: Results ───────────────────────────────────────────────────
with tab_results:

    st.markdown("### 📋 Search Results")

    result_job_id = st.session_state.get("active_job_id", "")

    resp = api_call("get", "/jobs")
    if resp and resp.status_code == 200:
        jobs = resp.json()
        if jobs:
            options = {j["job_id"]: f"📁 {j['filename']} ({j['total_records']} rows) • {j['status']} • {j['created_at'][:16].replace('T', ' ')}" for j in jobs}
            
            default_index = 0
            if result_job_id in options:
                default_index = list(options.keys()).index(result_job_id)
            elif jobs:
                result_job_id = jobs[0]["job_id"] # default to most recent if no active job
            
            result_job_id = st.selectbox(
                "Select Job for Results:",
                options=list(options.keys()),
                format_func=lambda x: options[x],
                index=default_index,
                key="results_job_select"
            )
        else:
            result_job_id = None

    if result_job_id:
        resp = api_call("get", f"/jobs/{result_job_id}/results")
        if resp:
            results = resp.json()

            if results:
                # Filter
                filter_col1, filter_col2 = st.columns(2)
                with filter_col1:
                    status_filter = st.multiselect(
                        "Filter by status:",
                        ["FOUND", "PARTIAL", "NOT_FOUND", "ERROR"],
                        default=["FOUND", "PARTIAL", "NOT_FOUND", "ERROR"],
                    )

                filtered = [r for r in results if r.get("match_status") in status_filter]

                # Results table
                for r in filtered:
                    name = f"{r.get('first_name', '')} {r.get('middle_name', '')} {r.get('last_name', '')}".strip()
                    status = r.get("match_status", "NOT_FOUND")
                    badge = get_badge_html(status)
                    conf = r.get("confidence_score", 0)

                    with st.expander(
                        f"{name} — {r.get('city', '')}, {r.get('state_code', '')} "
                        f"| {status} ({conf:.0f}%)",
                        expanded=(status == "FOUND"),
                    ):
                        st.markdown(badge, unsafe_allow_html=True)

                        rcol1, rcol2 = st.columns(2)
                        with rcol1:
                            st.markdown(f"**📞 Phone:** {r.get('phone', '—') or '—'}")
                            st.markdown(f"**📧 Email:** {r.get('email', '—') or '—'}")
                            st.markdown(f"**📍 Address:** {r.get('full_address', '—') or '—'}")
                        with rcol2:
                            st.markdown(f"**🆔 Project ID:** `{r.get('project_id', '')}`")
                            st.markdown(f"**🎯 Confidence:** {conf:.1f}%")
                            source_urls = r.get("source_urls", [])
                            if source_urls:
                                st.markdown("**🔗 Sources:**")
                                for url in source_urls:
                                    st.markdown(f"- [{url[:60]}...]({url})")

                        if r.get("verification_reasoning"):
                            st.markdown(f"**📝 Reasoning:** {r['verification_reasoning']}")

                # Export button
                st.markdown("---")
                if st.button("📥 Export to Excel", type="primary", use_container_width=True):
                    resp = api_call("get", f"/jobs/{result_job_id}/export")
                    if resp:
                        st.download_button(
                            label="💾 Download Excel File",
                            data=resp.content,
                            file_name=f"hcp_results_{result_job_id[:8]}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )
            else:
                st.info("No results yet. Processing may still be in progress.")
    else:
        st.info("Enter a Job ID to view results.")


