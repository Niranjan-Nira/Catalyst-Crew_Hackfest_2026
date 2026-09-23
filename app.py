import os
import sys
import re
import json
import base64
import hashlib
import tempfile
import zipfile
import shutil
from pathlib import Path
import altair as alt
import streamlit as st
import pandas as pd

base_dir = Path(__file__).resolve().parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from src.diagnosis import DiagnosisEngine
from src.diagnosis.advanced_detectors import correlate_temporal_window
from src.rca import LocalRCAAgent
from src.rag import get_knowledge_base, retrieve_grounded_context, add_custom_document, build_llm_prompt
from src.reporting import CaseReportBuilder, generate_scorecard_data, PDFReportGenerator
from src.reporting.report_builder import (
    _build_action_items,
    _build_siem_action_records,
    _build_evidence_quality,
    _build_finding_root_cause_map,
    _build_report_chart_data,
    _default_impact_summary,
    _default_report_metadata,
    _sanitize_value,
)
from src.self_healing import SelfHealingScriptGenerator
from src.parsers.timeline_parser import parse_resource_timeline
from src.utils import resolve_diagnostic_dir
from src.config import LUNA_ENABLED
from src.rca.luna_solution import generate_luna_solution
from src.rca.luna_chat import answer_case_question
from src.reddit_assistant import (
    extract_primary_issue,
    build_local_solution_from_rca,
)


def extract_diagnostic_zip(uploaded_zip, upload_dir: Path) -> None:
    """Extract diagnostic folders while removing redundant archive wrapper folders."""
    diagnostic_folders = {
        "01_Timeline_And_Resources",
        "02_EventLogs",
        "03_WindowsUpdates",
        "04_HardwareDevices",
        "05_Disk",
        "06_Memory",
        "07_CPU",
        "08_SystemInfo",
        "09_ReliabilityMonitor",
        "10_Battery",
        "11_StartupApps",
        "12_Network",
        "13_AppLogs",
        "14_InstalledApps",
        "15_CrashDumps_WER",
        "16_Services_Processes",
        "_StatusReport",
    }

    with zipfile.ZipFile(uploaded_zip, "r") as zip_ref:
        for member in zip_ref.infolist():
            archive_parts = [part for part in member.filename.replace("\\", "/").split("/") if part]
            if not archive_parts or ".." in archive_parts:
                continue

            module_index = next(
                (index for index, part in enumerate(archive_parts) if part in diagnostic_folders),
                None,
            )
            if module_index is None:
                continue

            destination = upload_dir.joinpath(*archive_parts[module_index:])
            if member.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            with zip_ref.open(member, "r") as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)

st.set_page_config(
    page_title="Endpoint AI — The Self-Healing Intelligent Workstation",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS matching the original clean, modern theme
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        color: #f8fafc;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .metric-card h3 {
        margin: 0;
        font-size: 26px;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-card p {
        margin: 4px 0 0 0;
        font-size: 13px;
        color: #94a3b8;
    }
    .tier1-badge {
        background-color: #ef4444;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85em;
    }
    .tier2-badge {
        background-color: #f59e0b;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85em;
    }
    .tier3-badge {
        background-color: #10b981;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85em;
    }
    .tier4-badge {
        background-color: #6366f1;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        font-size: 0.85em;
    }
    /* Completely hide tab scrollbar across all browsers */
    div[data-baseweb="tab-list"] {
        overflow-x: auto !important;
        scrollbar-width: none !important;
        -ms-overflow-style: none !important;
    }
    div[data-baseweb="tab-list"]::-webkit-scrollbar {
        display: none !important;
        width: 0 !important;
        height: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

base_dir = Path(__file__).resolve().parent
# ----------------- FOLDER PATH INPUT: EMPTY BY DEFAULT -----------------
# Clear any query parameters so page refreshes (F5) always reset to clean and empty
if st.query_params:
    st.query_params.clear()

st.sidebar.title("🛡️ Endpoint AI Workstation")
st.sidebar.caption("Find the issue. Explain the cause. Choose the next action.")

st.sidebar.markdown("### 1. Select diagnostic data")
input_mode = st.sidebar.radio(
    "Input:",
    ["📁 Folder Path", "📦 Upload Diagnostic Zip"],
    horizontal=True,
    help="Choose whether to enter a directory path or upload a zip archive of diagnostic folders."
)

if input_mode == "📁 Folder Path":
    folder_input = st.sidebar.text_input(
        "Folder path:",
        value="",
        key="folder_path_input",
        placeholder=r"e.g. C:\Users\...\Hackfest B\Input file",
        help="Paste the path of any folder containing the 17 diagnostic folders (01_Timeline_And_Resources through 17_StatusReport)"
    )
else:
    uploaded_zip = st.sidebar.file_uploader(
        "Upload diagnostic ZIP:",
        type=["zip"],
        key="diagnostic_zip_uploader",
        help="Upload a zip file containing the diagnostic folders."
    )
    folder_input = ""
    if uploaded_zip is not None:
        archive_id = hashlib.sha1(uploaded_zip.getvalue()).hexdigest()[:12]
        upload_dir = Path(tempfile.gettempdir()) / "endpoint_ai_cases" / f"case_{archive_id}"
        if upload_dir.exists():
            shutil.rmtree(upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        extract_diagnostic_zip(uploaded_zip, upload_dir)
        folder_input = str(upload_dir)
        st.sidebar.success(f"✓ Extracted `{uploaded_zip.name}` successfully!")

# Standard 17 folders
EXPECTED_MODULES = [
    "01_Timeline_And_Resources",
    "02_EventLogs",
    "03_WindowsUpdates",
    "04_HardwareDevices",
    "05_Disk",
    "06_Memory",
    "07_CPU",
    "08_SystemInfo",
    "09_ReliabilityMonitor",
    "10_Battery",
    "11_StartupApps",
    "12_Network",
    "13_AppLogs",
    "14_InstalledApps",
    "15_CrashDumps_WER",
    "16_Services_Processes",
    "_StatusReport"
]

# ----------------- SIDEBAR: RAG KNOWLEDGE BASE STATS -----------------
st.sidebar.markdown("---")
st.sidebar.markdown("### 📚 Local knowledge base")

kb = get_knowledge_base()
kb_stats = kb.get_stats()

c_col1, c_col2 = st.sidebar.columns(2)
with c_col1:
    st.metric(label="Chunked Files", value=kb_stats["total_documents"])
with c_col2:
    st.metric(label="Total Chunks", value=kb_stats["total_chunks"])

st.sidebar.markdown(
    f"""
    <div style='background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 8px; padding: 10px 12px; margin-top: 6px; margin-bottom: 8px;'>
        <div style='font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px;'>Chunk Storage Size</div>
        <div style='font-size: 20px; font-weight: 700; color: #38bdf8; margin-top: 2px;'>{kb_stats['formatted_storage_size']}</div>
        <div style='font-size: 11px; color: #64748b; margin-top: 4px;'>Categories: {len(kb_stats['categories'])} &nbsp;|&nbsp; Avg: {kb_stats['avg_tokens_per_chunk']} tokens</div>
    </div>
    """,
    unsafe_allow_html=True
)

with st.sidebar.expander("📑 View Chunked Files List", expanded=False):
    for fname, cnt in sorted(kb_stats["files"].items(), key=lambda x: -x[1]):
        st.markdown(f"• **{fname}**: `{cnt} chunks`")


# If no path provided, show clean empty landing view
if not folder_input or not folder_input.strip():
    # Clear any previous session state so nothing from previous runs remains
    st.session_state.pop("diag_results", None)
    st.session_state.pop("rca_results", None)
    st.session_state.pop("current_device", None)
    
    st.title("Endpoint AI Workstation")
    st.markdown("A clear path from endpoint logs to evidence, root cause, and recommended action.")
    st.info("Start in the sidebar: choose a diagnostic folder or upload a ZIP, then select **Run analysis**.")

    st.markdown("### What this tool does")
    st.caption("Endpoint AI turns Windows diagnostic logs into a clear, evidence-backed case summary.")

    intro_col1, intro_col2 = st.columns(2)
    with intro_col1:
        st.markdown("#### How it works")
        st.markdown(
            "1. **Load data**  \n"
            "   Select a folder or upload a diagnostic ZIP.\n\n"
            "2. **Analyze signals**  \n"
            "   Correlate logs, failures, resources, and hardware events.\n\n"
            "3. **Explain the issue**  \n"
            "   Review ranked evidence, confidence, root cause, and next steps."
        )
    with intro_col2:
        st.markdown("#### What you receive")
        st.markdown(
            "- **Findings:** anomalies grouped by confidence\n"
            "- **Root cause:** evidence-backed explanations\n"
            "- **Actions:** safe remediation scripts with dry-run support\n"
            "- **Knowledge:** local troubleshooting guidance\n"
            "- **Report:** PDF, Markdown, and SIEM-ready JSON"
        )

    st.info("Start in the sidebar, choose your diagnostic data, and select **Run analysis**.")
    st.stop()

# Robust resolution of path (handles quotes, relative/absolute, and 1-2 level nested subfolders)
target_data_dir = resolve_diagnostic_dir(folder_input)

if not target_data_dir.exists() or not target_data_dir.is_dir():
    st.sidebar.error("Directory not found. Please verify the folder path.")
    st.error(f"Directory not found: `{folder_input}`. Please verify the path in the sidebar.")
    st.stop()

detected_count = sum(1 for mod in EXPECTED_MODULES if (target_data_dir / mod).exists())
if detected_count >= 10:
    st.sidebar.success(f"✓ Detected {detected_count}/17 folders in: `{target_data_dir.name}`")
else:
    st.sidebar.info(f"📁 Source: `{target_data_dir.name}` ({detected_count} standard folders detected)")

run_analysis = st.sidebar.button("🚀 Run analysis", type="primary", use_container_width=True)

# ----------------- MAIN HEADER -----------------
st.title("Endpoint AI Workstation")
st.markdown(f"**Current case:** `{target_data_dir.name}` &nbsp; · &nbsp; Evidence-based diagnosis and local RCA")

# Cache diagnosis & RCA results in session_state
if "current_device" not in st.session_state or st.session_state["current_device"] != str(target_data_dir) or run_analysis:
    with st.spinner("Reading logs and building the case report..."):
        diag_engine = DiagnosisEngine(target_data_dir)
        diag_results = diag_engine.run()

        rca_agent = LocalRCAAgent(target_data_dir)
        rca_results = rca_agent.run_rca(diag_results)

        st.session_state["current_device"] = str(target_data_dir)
        st.session_state["diag_results"] = diag_results
        st.session_state["rca_results"] = rca_results

diag_results = st.session_state.get("diag_results", {})
rca_results = st.session_state.get("rca_results", {})

tier1 = diag_results.get("tier1_anomalies", [])
tier2 = diag_results.get("tier2_possible_anomalies", [])
tier3 = rca_results.get("tier3_root_causes", [])
tier4 = rca_results.get("tier4_possible_root_causes", [])

# Top Metric Cards (Original Clean Slate Design)
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f"<div class='metric-card'><h3>🚨 {len(tier1)}</h3><p>Tier-1 Anomalies</p></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='metric-card'><h3>⚠️ {len(tier2)}</h3><p>Tier-2 Possible</p></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='metric-card'><h3>🔍 {len(tier3)}</h3><p>Tier-3 Root Causes</p></div>", unsafe_allow_html=True)
with col4:
    st.markdown(f"<div class='metric-card'><h3>💡 {len(tier4)}</h3><p>Tier-4 Hypotheses</p></div>", unsafe_allow_html=True)
with col5:
    st.markdown(f"<div class='metric-card'><h3>🛡️ {len(tier3)}</h3><p>Remediation Scripts</p></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ----------------- TAB MOVE ARROWS NAVIGATION CONTROLS -----------------
import streamlit.components.v1 as components

components.html(
    """
    <div style="display: flex; justify-content: space-between; align-items: center; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 8px; padding: 6px 14px; margin-bottom: 8px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <button id="move-left-btn" style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: #ffffff; border: 1px solid #38bdf8; border-radius: 6px; padding: 6px 14px; font-size: 13px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.2s ease; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
            &#9664; Move Tab Left
        </button>
        <div style="font-size: 12px; color: #94a3b8; font-weight: 600; display: flex; align-items: center; gap: 8px;">
            <span style="color: #38bdf8; font-size: 14px;">&#8644;</span>
            <span style="color: #cbd5e1; font-weight: bold;">Tab Navigation</span>
            <span style="font-size: 11px; color: #64748b;">(Click arrow buttons to move between tabs)</span>
        </div>
        <button id="move-right-btn" style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: #ffffff; border: 1px solid #38bdf8; border-radius: 6px; padding: 6px 14px; font-size: 13px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: all 0.2s ease; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">
            Move Tab Right &#9654;
        </button>
    </div>

    <script>
    const doc = window.parent.document;

    function getOuterTabList() {
        return doc.querySelector('div[data-baseweb="tab-list"]');
    }

    function getTabs() {
        const list = getOuterTabList();
        return list ? Array.from(list.querySelectorAll('button[data-baseweb="tab"]')) : [];
    }

    function restoreOuterTab() {
        const savedIndex = Number.parseInt(window.localStorage.getItem('endpoint-ai-active-tab') || '', 10);
        const tabs = getTabs();
        if (Number.isInteger(savedIndex) && tabs[savedIndex] && tabs[savedIndex].getAttribute('aria-selected') !== 'true') {
            tabs[savedIndex].click();
        }
    }

    function persistOuterTab() {
        const tabs = getTabs();
        const activeIdx = tabs.findIndex(t => t.getAttribute('aria-selected') === 'true');
        if (activeIdx >= 0) {
            window.localStorage.setItem('endpoint-ai-active-tab', String(activeIdx));
        }
    }

    function moveTab(direction) {
        const tabs = getTabs();
        const list = doc.querySelector('div[data-baseweb="tab-list"]');
        if (!tabs || !tabs.length) return;
        
        let activeIdx = tabs.findIndex(t => t.getAttribute('aria-selected') === 'true');
        if (activeIdx === -1) activeIdx = 0;
        
        let targetIdx = activeIdx + direction;
        if (targetIdx < 0) targetIdx = tabs.length - 1;
        if (targetIdx >= tabs.length) targetIdx = 0;
        
        tabs[targetIdx].click();
        tabs[targetIdx].scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        if (list) {
            list.scrollBy({ left: direction * 240, behavior: 'smooth' });
        }
    }

    document.getElementById('move-left-btn').addEventListener('click', (e) => {
        e.preventDefault();
        moveTab(-1);
    });

    document.getElementById('move-right-btn').addEventListener('click', (e) => {
        e.preventDefault();
        moveTab(1);
    });

    function enhanceTabList() {
        const list = getOuterTabList();
        if (list) {
            list.style.scrollBehavior = 'smooth';
            list.style.overflowX = 'auto';
            list.style.scrollbarWidth = 'none';
            list.style.msOverflowStyle = 'none';
        }
        if (!doc.getElementById('hide-tab-scrollbar-style')) {
            const style = doc.createElement('style');
            style.id = 'hide-tab-scrollbar-style';
            style.innerHTML = `
                div[data-baseweb="tab-list"] {
                    overflow-x: auto !important;
                    scrollbar-width: none !important;
                    -ms-overflow-style: none !important;
                }
                div[data-baseweb="tab-list"]::-webkit-scrollbar {
                    display: none !important;
                    height: 0 !important;
                    width: 0 !important;
                }
            `;
            doc.head.appendChild(style);
        }
    }

    enhanceTabList();
    restoreOuterTab();

    const outerTabList = getOuterTabList();
    if (outerTabList) {
        outerTabList.addEventListener('click', () => {
            window.setTimeout(persistOuterTab, 0);
        });
    }

    const tabObserver = new MutationObserver(() => {
        enhanceTabList();
        window.setTimeout(restoreOuterTab, 0);
    });
    tabObserver.observe(doc.body, { childList: true, subtree: true });
    </script>
    """,
    height=48
)

# Tabs
tab_labels = [
    "📈 Overview",
    "🔍 Findings",
    "🧠 Root cause",
    "📚 Knowledge",
    "🛠️ Actions",
    "🌐 Community",
    "📋 Report"
]
if LUNA_ENABLED:
    tab_labels.append("💬 Luna Chat")
tabs = st.tabs(tab_labels)

# ----------------- TAB 1: TELEMETRY -----------------
with tabs[0]:
    st.subheader("Overview")
    st.caption("Resource levels and activity around the detected incident.")
    timeline_file = target_data_dir / "01_Timeline_And_Resources" / "ResourceUtilization_Timeline.csv"
    if not timeline_file.exists():
        timeline_file = target_data_dir / "Timeline_And_Resources" / "ResourceUtilization_Timeline.csv"

    if timeline_file.exists():
        stats = parse_resource_timeline(timeline_file)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Samples Recorded", f"{stats['sample_count']}")
        c2.metric("Average CPU Usage", f"{stats['avg_cpu_percent']}%")
        c3.metric("Peak CPU Usage", f"{stats['max_cpu_percent']}%")
        min_avail = stats['min_available_mb']
        c4.metric("Lowest Available Memory", f"{int(min_avail) if min_avail else 'N/A'} MB", delta=f"{stats['min_percent_free_mem']}% free", delta_color="inverse")

        # Visual Charts
        if stats["timestamps"] and stats["cpu_values"]:
            df_chart = pd.DataFrame({
                "Timestamp": [t.split("T")[-1][:8] if "T" in t else t for t in stats["timestamps"]],
                "CPU Usage (%)": stats["cpu_values"],
                "Available Memory (MB)": stats["available_mb_values"]
            })
            st.markdown("#### CPU Utilization vs Available Memory Timeline")

            chart = alt.Chart(df_chart).transform_fold(
                ["CPU Usage (%)", "Available Memory (MB)"],
                as_=["Metric", "Value"]
            ).mark_line(point=False, strokeWidth=2.5).encode(
                x=alt.X("Timestamp:N", sort=None, title="Time"),
                y=alt.Y("Value:Q", title="Value"),
                color=alt.Color(
                    "Metric:N",
                    legend=alt.Legend(title=None),
                    scale=alt.Scale(domain=["CPU Usage (%)", "Available Memory (MB)"], range=["#38bdf8", "#34d399"])
                ),
                tooltip=["Timestamp:N", "Metric:N", "Value:Q"]
            ).properties(
                height=360,
                width=1200,
                title="CPU usage and memory availability over time"
            ).interactive()

            st.altair_chart(chart, use_container_width=True)

        # Advanced Statistical Variance Analytics & Micro-Spikes
        micro_spikes = diag_results.get("statistical_micro_spikes", [])
        mem_leaks = diag_results.get("monotonic_memory_leaks", [])

        if micro_spikes or mem_leaks:
            st.markdown("---")
            st.markdown("#### 🔬 Advanced Statistical Analytics & Micro-Spikes")
            st.caption("Rolling Z-Score & Interquartile Range (IQR) anomaly detection on live resource telemetry.")

            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                if micro_spikes:
                    st.warning(f"⚡ **{len(micro_spikes)} Statistical Micro-Spike(s) Detected (Z-Score > 2.5 or IQR Outlier)**")
                    for ms in micro_spikes[:4]:
                        st.markdown(f"- **{ms['type']}** at `{ms['timestamp']}`: {ms['summary']}")
                else:
                    st.success("✓ CPU and Memory variance within normal Gaussian distribution (no transient micro-spikes).")

            with col_stat2:
                if mem_leaks:
                    st.error(f"📈 **{len(mem_leaks)} Monotonic Memory Leak Trend(s) Identified**")
                    for ml in mem_leaks[:3]:
                        st.markdown(f"- **{ml['process_name']}**: +{ml['total_growth_mb']} MB growth ({int(ml['monotonic_ratio']*100)}% monotonic slope)")
                else:
                    st.success("✓ Linear regression verifies steady-state working sets across capture samples.")

        # Interactive Time-Machine Temporal Join Inspector (Diagnostic Cheat Sheet Step 2)
        st.markdown("---")
        st.markdown("#### Incident timeline")
        st.caption("Inspect process and file activity around a selected incident time.")

        # Collect all available incident timestamps, not only the first cluster start.
        candidate_timestamps = []
        for finding in tier1 + tier2:
            for field in ("start_time", "end_time", "timestamp", "event_time"):
                timestamp = finding.get(field)
                if timestamp and timestamp not in candidate_timestamps:
                    candidate_timestamps.append(timestamp)
        for ms in micro_spikes:
            if ms.get("timestamp") and ms.get("timestamp") not in candidate_timestamps:
                candidate_timestamps.append(ms.get("timestamp"))
        if not candidate_timestamps and stats["timestamps"]:
            resource_timestamps = stats["timestamps"]
            candidate_timestamps = list(dict.fromkeys([
                resource_timestamps[0],
                resource_timestamps[len(resource_timestamps) // 2],
                resource_timestamps[-1],
            ]))

        col_tm_sel, col_tm_win = st.columns([3, 1])
        with col_tm_sel:
            chosen_ts = st.selectbox(
                "Select Incident Timestamp to Inspect:",
                options=candidate_timestamps if candidate_timestamps else ["12:51:58"],
                index=0,
                key="time_machine_select"
            )
        with col_tm_win:
            chosen_win = st.selectbox("Temporal Window:", [30, 60, 120, 300], index=2, format_func=lambda x: f"±{x} seconds")

        if chosen_ts:
            tm_slice = correlate_temporal_window(target_data_dir, chosen_ts, window_seconds=chosen_win)
            procs = tm_slice.get("processes_in_window", [])
            files = tm_slice.get("files_in_window", [])

            col_proc, col_file = st.columns(2)
            with col_proc:
                st.markdown(f"**Processes Active Around {chosen_ts} (±{chosen_win}s)** — `{len(procs)} recorded`")
                if procs:
                    st.dataframe(pd.DataFrame(procs), height=220, use_container_width=True)
                else:
                    st.info(f"No process start/stop events within ±{chosen_win}s of {chosen_ts}.")

            with col_file:
                st.markdown(f"**Files Touched Around {chosen_ts} (±{chosen_win}s)** — `{len(files)} recorded`")
                if files:
                    st.dataframe(pd.DataFrame(files), height=220, use_container_width=True)
                else:
                    st.info(f"No file modification records within ±{chosen_win}s of {chosen_ts}.")
    else:
        st.info("Live timeline telemetry file not present for this device schema.")

# ----------------- TAB 2: DIAGNOSIS (COMPONENT 1) -----------------
with tabs[1]:
    st.subheader("Findings")
    st.caption("Issues are grouped by confidence so the strongest signals are easy to review first.")

    for a in tier1:
        with st.expander(f"🔴 {a['id']}. {a['title']} — {a['confidence']}% Confidence", expanded=True):
            st.markdown(f"**Category:** `{a['category']}` &nbsp;|&nbsp; **Source:** `{a.get('source_file', '')}`")
            st.markdown(f"**Confidence Reason:** *{a['confidence_reason']}*")
            st.markdown("**Evidence (Ranked):**")
            for idx, ev in enumerate(a.get("evidence", []), 1):
                st.markdown(f"{idx}. {ev}")

    st.markdown("---")
    st.subheader("Possible findings")
    st.caption("Signals worth monitoring, but not fully confirmed by the available data.")

    for b in tier2:
        with st.expander(f"🟡 {b['id']}. {b['title']} — {b['confidence']}% Confidence"):
            st.markdown(f"**Category:** `{b['category']}` &nbsp;|&nbsp; **Source:** `{b.get('source_file', '')}`")
            st.markdown(f"**Why 'Possible' Not Confirmed:** {b.get('confidence_reason', '')}")
            st.markdown("**Evidence:**")
            for ev in b.get("evidence", []):
                st.markdown(f"- {ev}")

# ----------------- TAB 3: RCA AGENT (COMPONENT 2) -----------------
with tabs[2]:
    st.subheader("Root cause and next action")
    st.caption("Each explanation connects the finding to evidence, confidence, and a recommended action.")

    for c in tier3:
        with st.container():
            st.markdown(f"### 🟢 {c['id']}. {c['title']}")
            st.markdown(f"**Target Anomaly:** `{c['target_anomaly_id']}` &nbsp;|&nbsp; **Confidence:** `{c['confidence']}%`")
            st.info(f"**Root Cause:** {c['root_cause']}")
            st.success(f"**Recommended Action:** {c['recommended_action']}")
            if c.get("rag_citations"):
                st.markdown(f"📖 **Grounded RAG Citations:** `{', '.join(c['rag_citations'])}`")

            learning_doc_name = f"validated_rca_{target_data_dir.name}_{c['id']}.md"
            learning_doc_key = re.sub(r"[^\w\-\.]", "_", learning_doc_name)
            learning_kb = get_knowledge_base()
            target_anomaly = next(
                (item for item in tier1 + tier2 if item.get("id") == c.get("target_anomaly_id")),
                {}
            )
            if learning_doc_key in learning_kb.indexed_files:
                st.success("✓ This accepted RCA is already captured in the knowledge base.")
            elif st.button(
                f"✅ Accept RCA & capture learning ({c['id']})",
                key=f"accept_rca_{target_data_dir}_{c['id']}"
            ):
                evidence_lines = "\n".join(
                    f"{idx}. {evidence}"
                    for idx, evidence in enumerate(target_anomaly.get("evidence", []), 1)
                )
                learning_doc = (
                    f"# Validated RCA: {c['title']}\n\n"
                    f"- **Workstation:** {target_data_dir.name}\n"
                    f"- **Target anomaly:** {c.get('target_anomaly_id', '')}\n"
                    f"- **Anomaly source:** {target_anomaly.get('source_file', 'Diagnosis output')}\n"
                    f"- **Confidence:** {c.get('confidence', '')}%\n"
                    f"- **Confidence rationale:** {c.get('confidence_reason', '')}\n\n"
                    f"## Root Cause\n{c.get('root_cause', '')}\n\n"
                    f"## Ranked Evidence\n{evidence_lines or 'Evidence retained in the diagnosis record.'}\n\n"
                    f"## Recommended Action\n{c.get('recommended_action', '')}\n\n"
                    f"## RAG Sources\n"
                    + "\n".join(f"- {source}" for source in c.get("rag_citations", []))
                    + "\n"
                )
                captured_chunks = add_custom_document(
                    learning_doc,
                    doc_name=learning_doc_name,
                    doc_type="validated_rca"
                )
                if captured_chunks:
                    st.session_state.setdefault("accepted_rcas", set()).add(learning_doc_name)
                    st.success(f"✓ Accepted RCA captured ({captured_chunks} knowledge chunk(s)).")
                else:
                    st.warning("The accepted RCA could not be added to the knowledge base.")
            st.markdown("---")

    st.subheader("Open hypotheses")
    st.caption("Plausible explanations with a clear next step for confirmation.")

    for d in tier4:
        with st.container():
            st.markdown(f"### 🟣 {d['id']}. {d['title']}")
            st.markdown(f"**Target Anomaly:** `{d['target_anomaly_id']}` &nbsp;|&nbsp; **Confidence:** `{d['confidence']}%`")
            st.warning(f"**Hypothesis:** {d['hypothesis']}")
            st.markdown(f"**Why 'Possible' Not Confirmed:** {d.get('why_possible_not_confirmed', '')}")
            st.markdown(f"🔬 **What Would Confirm It:** `{d['what_would_confirm_it']}`")
            st.markdown(f"**Recommended Action:** {d.get('recommended_action', '')}")
            if d.get("rag_citations"):
                st.markdown(f"📖 **Grounded RAG Citations:** `{', '.join(d['rag_citations'])}`")
            st.markdown("---")

# ----------------- TAB 4: RAG KNOWLEDGE EXPLORER -----------------
with tabs[3]:
    st.subheader("📚 Enterprise RAG Knowledge Hub")
    st.caption("Deterministic exact signal matching, Okapi BM25 keyword ranking, and semantic vector retrieval across all Hackathon Guides and Troubleshooting Encyclopedias.")

    kb = get_knowledge_base()
    kb_stats = kb.get_stats()

    # Knowledge Base Overview Metrics
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"<div class='metric-card'><h3>📄 {kb_stats['total_documents']}</h3><p>Indexed Documents</p></div>", unsafe_allow_html=True)
    with m2:
        st.markdown(f"<div class='metric-card'><h3>🧩 {kb_stats['total_chunks']}</h3><p>Knowledge Chunks</p></div>", unsafe_allow_html=True)
    with m3:
        st.markdown(f"<div class='metric-card'><h3>🏷️ {len(kb_stats['categories'])}</h3><p>Knowledge Categories</p></div>", unsafe_allow_html=True)
    with m4:
        st.markdown("<div class='metric-card'><h3>⚡ Hybrid</h3><p>Exact + BM25 + Semantic</p></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    rag_view1, rag_view2, rag_view3 = st.tabs([
        "🔍 Knowledge Search & Incident Grounding",
        "📖 Browse Troubleshooting Encyclopedia",
        "📥 Ingest & Manage Documents"
    ])

    # VIEW 1: SEARCH & INCIDENT GROUNDING
    with rag_view1:
        st.markdown("#### 🎯 Top 5 Endpoint Issues: RAG-Grounded Investigation Briefs")
        st.caption("Each brief combines the detected issue, supporting reason, grounded root cause, and recommended measures from the local knowledge base.")

        rca_by_anomaly = {
            item.get("target_anomaly_id"): item
            for item in tier3
            if item.get("target_anomaly_id")
        }
        top_issues = sorted(
            [item for item in tier1 if isinstance(item, dict)],
            key=lambda item: item.get("confidence", 0),
            reverse=True
        )[:5]

        for issue_idx, issue in enumerate(top_issues, 1):
            issue_id = issue.get("id", f"A{issue_idx}")
            issue_title = issue.get("title", "Detected endpoint issue")
            related_rca = rca_by_anomaly.get(issue_id, {})
            issue_reason = issue.get("confidence_reason") or (
                issue.get("evidence", ["Evidence recorded in the diagnosis results."])[0]
            )
            root_cause = related_rca.get(
                "root_cause",
                "No confirmed root cause is available yet; continue collecting corroborating evidence."
            )
            recommended_action = related_rca.get(
                "recommended_action",
                "Review the grounded evidence below and extend monitoring before remediation."
            )
            rag_query = f"{issue_title} {root_cause}"
            try:
                issue_rag_docs = retrieve_grounded_context(rag_query, top_k=3)
            except Exception:
                issue_rag_docs = []

            with st.expander(
                f"#{issue_idx} {issue_id}. {issue_title} — {issue.get('confidence', 'N/A')}% confidence",
                expanded=(issue_idx == 1)
            ):
                st.markdown(f"**Issue:** {issue_title}")
                st.markdown(f"**Why this issue was flagged:** {issue_reason}")
                st.info(f"**RAG-grounded root cause:** {root_cause}")
                st.success(f"**Measures to solve or contain it:** {recommended_action}")

                if issue_rag_docs:
                    st.markdown("**Knowledge used:**")
                    for doc in issue_rag_docs:
                        doc_name = doc.get("doc_title", doc.get("source", "Knowledge document"))
                        section = doc.get("title", "Relevant section")
                        snippet = " ".join(str(doc.get("content", "")).split())[:280]
                        st.markdown(f"- **{doc_name} — {section}:** {snippet}...")
                elif related_rca.get("rag_citations"):
                    citations = ", ".join(related_rca["rag_citations"])
                    st.caption(f"Knowledge citations: {citations}")

        if not top_issues:
            st.info("No diagnosed issues are available for RAG grounding. Run diagnosis from the sidebar first.")

        st.markdown("---")
        # Machine Anomaly Grounding Section
        active_anomalies = []
        for a in top_issues:
            title = a.get("title") or a.get("id", "Anomaly")
            active_anomalies.append({
                "display": f"🚨 [Tier 1] {a.get('id', '')}: {title[:75]}",
                "query": title
            })

        if active_anomalies:
            st.markdown("##### 🔎 Retrieve the playbook for one of the top five issues")
            col_inc1, col_inc2 = st.columns([3.5, 1.2])
            with col_inc1:
                chosen_incident = st.selectbox(
                    "Select an anomaly detected on this endpoint to retrieve its diagnostic playbook & runbook:",
                    options=["-- Select detected incident --"] + [x["display"] for x in active_anomalies],
                    key="incident_rag_dropdown"
                )
            with col_inc2:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                if st.button("🔍 Load Incident Playbook", type="primary", use_container_width=True):
                    if chosen_incident and chosen_incident != "-- Select detected incident --":
                        match = next((x for x in active_anomalies if x["display"] == chosen_incident), None)
                        if match:
                            st.session_state["active_rag_search"] = match["query"]
                            st.rerun()
            st.markdown("---")
        else:
            st.info("💡 **Active Incident Grounding**: When telemetry data is loaded in the sidebar, detected Tier 1–3 anomalies will automatically populate here for 1-click diagnostic runbook retrieval.")

        # Search Controls
        col_q, col_cat, col_k = st.columns([3, 1.5, 0.8])
        with col_q:
            if "active_rag_search" not in st.session_state:
                st.session_state["active_rag_search"] = ""
            search_query = st.text_input(
                "Search query / symptom / error code:",
                placeholder="e.g. 0xC0000005, Event 7000, Netwtw10, Wi-Fi disconnect, memory leak, or judging rules...",
                key="active_rag_search"
            )
        with col_cat:
            category_options = ["All"] + sorted(list(kb_stats["categories"].keys()))
            selected_category = st.selectbox("Category Filter:", options=category_options, index=0)
        with col_k:
            top_k_select = st.selectbox("Top K:", options=[3, 5, 8, 12], index=1)

        # Retrieval Execution
        if search_query and search_query.strip():
            try:
                search_results = retrieve_grounded_context(
                    search_query.strip(),
                    top_k=top_k_select,
                    category=selected_category if selected_category != "All" else None
                )
            except Exception as rag_err:
                search_results = []
                st.error(f"Knowledge search failed: {rag_err}")

            if search_results:
                st.markdown(f"**Found {len(search_results)} relevant knowledge chunks:**")
                for idx, r in enumerate(search_results, 1):
                    reasons_str = " | ".join(r.get("match_reasons", []))
                    badge_color = "#38bdf8" if "Exact" in reasons_str else "#10b981"
                    doc_t = r.get("doc_title", "Document")
                    sec_t = r.get("title") or r.get("section_title", "Section")
                    score_v = r.get("score", 0)

                    with st.expander(f"#{idx} [{doc_t}] {sec_t} — Score: {score_v}", expanded=(idx == 1)):
                        st.markdown(
                            f"**Source:** `{r.get('source', '')}` &nbsp;|&nbsp; "
                            f"**Category:** `{r.get('category', '')}` &nbsp;|&nbsp; "
                            f"**Match Type:** `<span style='color:{badge_color}; font-weight:bold;'>{reasons_str}</span>`",
                            unsafe_allow_html=True
                        )
                        st.caption(f"📍 **Breadcrumb:** {r.get('breadcrumb', '')}")

                        # Extracted Entity Badges
                        tags_html = []
                        if r.get("event_ids"):
                            tags_html.append(f"<b>Event IDs:</b> {', '.join(r['event_ids'])}")
                        if r.get("hex_codes"):
                            tags_html.append(f"<b>Hex Codes:</b> {', '.join(r['hex_codes'])}")
                        if r.get("wer_buckets"):
                            tags_html.append(f"<b>WER:</b> {', '.join(r['wer_buckets'])}")
                        if tags_html:
                            st.markdown(f"<div style='background-color:#1e293b; padding:6px 12px; border-radius:6px; margin:6px 0; font-size:12px;'>{' &nbsp;|&nbsp; '.join(tags_html)}</div>", unsafe_allow_html=True)

                        if r.get("expanded_query_used"):
                            st.caption(f"🔍 **Domain Query Expansion Applied:** `{r['expanded_query_used']}`")

                        # Multi-Hop Knowledge Link
                        mh = r.get("multihop_reference")
                        if mh:
                            st.markdown(
                                f"""
                                <div style='background: #0f172a; border: 1px solid #334155; border-left: 4px solid #6366f1; border-radius: 6px; padding: 8px 12px; margin: 8px 0;'>
                                    <div style='font-size: 11px; font-weight: bold; color: #818cf8; text-transform: uppercase;'>🔗 1-Hop Related Knowledge Node: [{mh.get('doc_title', '')}] {mh.get('title', '')} (Key: {mh.get('reference_key', '')})</div>
                                    <div style='font-size: 12px; color: #cbd5e1; margin-top: 3px;'>{mh.get('summary', '')}</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                        st.markdown("---")
                        st.markdown(r.get("content", ""))

                # Export Grounded Prompt Expander
                with st.expander("🤖 View Grounded LLM Prompt (Formatted for Hackathon Standards)"):
                    llm_prompt = build_llm_prompt(search_query, search_results)
                    st.code(llm_prompt, language="markdown")
            else:
                st.info(f"No knowledge base records found matching query: '{search_query}'. Try broader terms or check the event code.")
        else:
            st.markdown("""
            <div style='background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; margin-top: 12px;'>
                <h5 style='margin-top:0; color: #38bdf8;'>💡 How to Query the Endpoint Diagnostic Knowledge Base</h5>
                <ul style='font-size: 13px; color: #94a3b8; line-height: 1.6; margin-bottom: 0;'>
                    <li><b>Exact Stop Codes & Hex Exceptions:</b> Search <code>0xC0000005</code>, <code>0x0000003B</code>, <code>0x0000001A</code>, <code>0x193</code> for exact architectural dump analysis.</li>
                    <li><b>Windows Event IDs:</b> Search <code>Event 7000</code> (SCM service timeouts), <code>Kernel-Power 41</code> (dirty shutdown), <code>153</code> (disk retry), <code>8003</code> (WLAN disconnect).</li>
                    <li><b>Hardware & Device Codes:</b> Search <code>CM_PROB_FAILED_POST_START</code>, <code>Netwtw10</code>, <code>Storport</code>, <code>Intel-Gfx</code>.</li>
                    <li><b>Playbooks & Rules:</b> Search <code>Tier 1 anomalies</code>, <code>Diagnostic cheat sheet time join key</code>, or <code>Report.wer FILETIME</code> for methodology rubrics.</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

    # VIEW 2: BROWSE ENCYCLOPEDIA BY CATEGORY
    with rag_view2:
        st.markdown("#### 📖 Troubleshooting Encyclopedia & Playbook Explorer")
        st.caption("Browse indexed chapters, root causes, and diagnostic worksheets across all 10 volumes directly.")

        b_col1, b_col2 = st.columns([1, 2])
        with b_col1:
            cat_list = sorted(list(kb_stats["categories"].keys()))
            if not cat_list:
                cat_list = ["General"]
            chosen_cat = st.selectbox("1. Select Knowledge Category:", options=cat_list, key="browse_category_select")
            cat_chunks = [d for d in kb.documents if d.get("category") == chosen_cat]
            doc_titles = sorted(list(set(d.get("doc_title", "Unknown") for d in cat_chunks)))
            if not doc_titles:
                doc_titles = ["No documents found"]
            if "browse_volume_select" in st.session_state and st.session_state["browse_volume_select"] not in doc_titles:
                st.session_state["browse_volume_select"] = doc_titles[0]

            chosen_volume = st.selectbox(f"2. Select Volume / Guide ({len(doc_titles)} found):", options=doc_titles, key="browse_volume_select")
            vol_chunks = [d for d in cat_chunks if d.get("doc_title") == chosen_volume]
            st.caption(f"Showing {len(vol_chunks)} chapter section(s) in this volume.")

        with b_col2:
            if vol_chunks:
                st.markdown(f"### 📑 {chosen_volume}")
                for ch_idx, chunk in enumerate(vol_chunks, 1):
                    section_name = chunk.get("title") or chunk.get("section_title", f"Section {ch_idx}")
                    with st.expander(f"Section #{ch_idx}: {section_name}", expanded=(ch_idx == 1)):
                        st.markdown(f"**Source Document:** `{chunk.get('source', '')}` &nbsp;|&nbsp; **Category:** `{chunk.get('category', '')}`")
                        st.caption(f"📍 **Path:** {chunk.get('breadcrumb', '')}")
                        if chunk.get("event_ids") or chunk.get("hex_codes"):
                            meta_tags = []
                            if chunk.get("event_ids"):
                                meta_tags.append(f"<b>Event IDs:</b> {', '.join(chunk['event_ids'])}")
                            if chunk.get("hex_codes"):
                                meta_tags.append(f"<b>Hex:</b> {', '.join(chunk['hex_codes'])}")
                            st.markdown(f"<div style='font-size:12px; color:#38bdf8; margin: 4px 0;'>{' &nbsp;|&nbsp; '.join(meta_tags)}</div>", unsafe_allow_html=True)
                        st.markdown("---")
                        st.markdown(chunk.get("content", ""))

    # VIEW 3: INGEST & INVENTORY
    with rag_view3:
        col_ingest, col_inv = st.columns([1, 1])

        with col_ingest:
            st.markdown("#### 📥 Add Document to RAG Knowledge Base")
            st.caption("Upload or paste any new diagnostic guide, runbook, or cheat sheet to instantly make it queryable.")

            ingest_mode = st.radio("Ingestion Mode:", ["Upload File (.md, .txt, .csv, .pdf, .docx)", "Paste Text"], horizontal=True)

            if "Upload File" in ingest_mode:
                uploaded_file = st.file_uploader(
                    "Select document to add:",
                    type=["md", "txt", "csv", "json", "pdf", "docx", "doc"],
                    key="rag_file_upload",
                    help="Supported formats: PDF (.pdf), Word (.docx, .doc), Markdown (.md), Plain Text (.txt), CSV (.csv), JSON (.json)"
                )
                if uploaded_file is not None:
                    file_size_kb = len(uploaded_file.getvalue()) / 1024
                    st.caption(f"📄 Selected: `{uploaded_file.name}` ({file_size_kb:.1f} KB)")
                    if st.button("🚀 Ingest Uploaded File", type="primary", use_container_width=True):
                        try:
                            file_bytes = uploaded_file.getvalue()
                            num_chunks = add_custom_document(file_bytes, doc_name=uploaded_file.name)
                            if num_chunks > 0:
                                st.success(f"✓ Successfully indexed `{uploaded_file.name}` ({num_chunks} chunks added)!")
                                st.rerun()
                            else:
                                st.warning(f"No indexable text content could be extracted from `{uploaded_file.name}`.")
                        except Exception as ex:
                            st.error(f"Failed to ingest file: {ex}")

            else:
                doc_title_input = st.text_input("Document Title / Filename:", placeholder="e.g. Cisco_VPN_Troubleshooting_Guide.md")
                doc_content_input = st.text_area("Document Content (Markdown):", height=180, placeholder="# Title\n## Section 1\nDiagnostic procedure...")
                if st.button("🚀 Ingest Pasted Document", type="primary", use_container_width=True):
                    if doc_title_input.strip() and doc_content_input.strip():
                        num_chunks = add_custom_document(doc_content_input, doc_name=doc_title_input)
                        st.success(f"✓ Successfully indexed `{doc_title_input}` ({num_chunks} chunks added)!")
                        st.rerun()
                    else:
                        st.warning("Please provide both a document title and content.")

        with col_inv:
            st.markdown("#### 📑 Active Knowledge Base Inventory")
            st.caption(f"Currently indexed: {kb_stats['total_documents']} documents across 10 volumes and guides ({kb_stats.get('formatted_storage_size', '')}).")

            doc_summary_data = []
            for fname, count in sorted(kb_stats["files"].items(), key=lambda x: -x[1]):
                doc_summary_data.append({
                    "Document Name": fname,
                    "Chunks": count
                })

            df_inv = pd.DataFrame(doc_summary_data)
            st.dataframe(df_inv, height=260, use_container_width=True)


# ----------------- TAB 5: SELF-HEALING ACTIONS -----------------
with tabs[4]:
    st.subheader("⚡ Automated Self-Healing Remediation Engine")
    st.markdown("Concrete PowerShell remediation scripts with elevation checks, `-WhatIf` dry-run simulation, and automated rollback capabilities.")

    sim_mode = st.radio(
        "Remediation Execution Mode:",
        ["🛡️ Full Remediation (Elevated Admin)", "🔬 Dry-Run Simulation (-WhatIf)", "⏪ Reversible Rollback (-Rollback)"],
        horizontal=True,
        key="self_healing_mode_radio"
    )

    if "Dry-Run" in sim_mode:
        st.info("🔬 **Dry-Run Simulation Active**: Scripts leverage native PowerShell `[CmdletBinding(SupportsShouldProcess=$true)]` with `-WhatIf`. Run with `-WhatIf` to preview every service stop, restore point, and registry change without modifying system state.")
    elif "Rollback" in sim_mode:
        st.warning("⏪ **Reversible Rollback Active**: Run with `-Rollback` switch to cleanly reverse service shutdowns, re-enable startup parameters, and restore previous system state.")
    else:
        st.success("🛡️ **Full Remediation Active**: Scripts require elevated Administrator permissions and automatically trigger `Checkpoint-Computer` system restore points prior to taking corrective action.")

    remediation_targets = []
    if tier3:
        for c in tier3:
            remediation_targets.append({
                "id": c.get("id", "C?"),
                "title": c.get("title", ""),
                "action": c.get("recommended_action", "")
            })
    elif tier1:
        for a in tier1:
            remediation_targets.append({
                "id": a.get("id", "A?"),
                "title": a.get("title", ""),
                "action": a.get("evidence", [""])[0] if a.get("evidence") else ""
            })

    if not remediation_targets:
        st.info("ℹ️ No critical root causes or anomalies requiring automated PowerShell remediation were detected in this diagnostic dataset.")
    else:
        for idx, item in enumerate(remediation_targets):
            try:
                script_info = SelfHealingScriptGenerator.generate_script_for_finding(
                    str(item["id"]), str(item["title"]), str(item["action"])
                )
            except Exception as script_err:
                st.error(f"Could not generate remediation for {item['id']}: {script_err}")
                continue
            script_fname = script_info.get("name", f"Remediate-{item['id']}.ps1")
            with st.expander(f"🛠️ Remediation for {item['id']}: {script_fname}", expanded=True):
                st.markdown(f"**Description:** {script_info.get('description', '')}")
                st.caption(f"🔒 **Safety Guard:** {script_info.get('safety_guard', '')}")

                # Invocation helper
                if "Dry-Run" in sim_mode:
                    st.code(f".\\{script_fname} -WhatIf", language="powershell")
                elif "Rollback" in sim_mode:
                    st.code(f".\\{script_fname} -Rollback", language="powershell")
                else:
                    st.code(f".\\{script_fname}", language="powershell")

                st.markdown("**PowerShell Source Code:**")
                code_text = script_info.get("code", "")
                st.code(code_text, language="powershell")
                st.download_button(
                    label=f"💾 Download Script ({script_fname})",
                    data=code_text.encode("utf-8"),
                    file_name=script_fname,
                    mime="application/octet-stream",
                    key=f"dl_ps1_{item['id']}_{idx}"
                )

# ----------------- TAB 6: REDDIT AI SOLUTIONS & COMMUNITY INSIGHTS -----------------
with tabs[5]:
    st.subheader("🌐 Solution guide")
    st.caption("Local, case-grounded troubleshooting guidance")

    try:
        issue_info = extract_primary_issue(diag_results, rca_results)
    except Exception as issue_err:
        issue_info = {
            "primary_title": "Generic System Diagnostics",
            "query": "How to solve Windows application crash 0xC0000005",
            "details": f"Issue extraction unavailable: {issue_err}",
            "candidates": []
        }
        st.warning("The diagnosed issue could not be prepared; a generic troubleshooting query is available.")

    # 1. Diagnosed Issue & Query Banner
    st.markdown("#### 🎯 Diagnosed System Issue & Automated Query")

    col_pri1, col_pri2 = st.columns([2.5, 1])
    with col_pri1:
        st.markdown(
            f"""
            <div style='background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-left: 4px solid #38bdf8; border-radius: 8px; padding: 12px 16px;'>
                <div style='font-size: 11px; text-transform: uppercase; color: #94a3b8; font-weight: bold; letter-spacing: 0.5px;'>Primary Detected Issue</div>
                <div style='font-size: 16px; font-weight: 700; color: #f8fafc; margin-top: 3px;'>{issue_info['primary_title']}</div>
                <div style='font-size: 12px; color: #cbd5e1; margin-top: 4px;'>{issue_info['details']}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col_pri2:
        st.markdown(
            f"""
            <div style='background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-left: 4px solid #10b981; border-radius: 8px; padding: 12px 16px;'>
                <div style='font-size: 11px; text-transform: uppercase; color: #94a3b8; font-weight: bold; letter-spacing: 0.5px;'>AI Query Formulation</div>
                <div style='font-size: 14px; font-weight: 600; color: #38bdf8; margin-top: 3px;'>"{issue_info['query']}"</div>
                <div style='font-size: 11px; color: #64748b; margin-top: 4px;'>Based on this case's local evidence</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Keep the tab local-only: no community search or external summarization.
    local_solution = build_local_solution_from_rca(
        diag_results,
        rca_results,
        issue_details=issue_info.get("details", "")
    )
    case_key = str(target_data_dir.resolve())
    if st.session_state.get("luna_solution_case") != case_key:
        st.session_state.pop("luna_solution_result", None)
        st.session_state["luna_solution_case"] = case_key

    if LUNA_ENABLED:
        use_luna = st.toggle(
            "✨ Use Luna 5.6 to expand the local solution guide",
            value=False,
            key="use_luna_solution",
            help="Sends the current case findings and RCA to Luna 5.6. Reddit is not used."
        )
        if use_luna:
            if "luna_solution_result" not in st.session_state:
                with st.spinner("Luna 5.6 is preparing a clearer solution guide..."):
                    st.session_state["luna_solution_result"] = generate_luna_solution(
                        diag_results, rca_results
                    )
            luna_solution = st.session_state["luna_solution_result"]
            if luna_solution.get("is_online"):
                st.success("Luna 5.6 guidance is ready and will be included in the Case Report exports.")
            else:
                st.warning(luna_solution.get("error", "Luna was unavailable. Showing the local solution."))
        else:
            luna_solution = None
            st.session_state.pop("luna_solution_result", None)
    else:
        luna_solution = None
        st.info("Luna 5.6 is disabled. Set LUNA_ENABLED=1 and provide LUNA_API_KEY to enable this toggle.")
        st.session_state.pop("luna_solution_result", None)

    displayed_solution = luna_solution if luna_solution and luna_solution.get("summary") else local_solution
    st.session_state["active_luna_solution"] = luna_solution
    cached_payload = {"results": [], "summary": displayed_solution}

    if cached_payload:
        reddit_results = cached_payload.get("results", [])
        luna_summary = cached_payload.get("summary", {})

        st.markdown("---")

        # 3. Local solution or optional Luna synthesis card
        model_badge = "🟢 Live Luna 5.6 API" if luna_summary.get("is_online") else "🔵 Local RCA solution"
        st.markdown(
            f"""
            <div style='background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #38bdf8; border-radius: 10px; padding: 18px 22px; margin-bottom: 24px; box-shadow: 0 4px 12px rgba(56, 189, 248, 0.12);'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #334155; padding-bottom: 8px;'>
                    <span style='font-size: 14px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.8px;'>
                        🧭 Recommended solution
                    </span>
                    <span style='background-color: #0284c7; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;'>
                        {model_badge} &nbsp;|&nbsp; {luna_summary.get('model_used', 'Luna 5.6')}
                    </span>
                </div>
                <div style='color: #f1f5f9;'>
            """,
            unsafe_allow_html=True
        )
        st.markdown(luna_summary.get("summary", "No summary generated."))
        st.markdown("</div></div>", unsafe_allow_html=True)

        # 4. Consolidated Discussion Sources Table (All posts merged into the single solution above)
        source_label = "Community threads" if reddit_results else "Local RCA evidence"
        st.markdown(f"#### 📚 Solution sources ({len(reddit_results)} {source_label})")
        st.caption("The solution above is grounded in the current case's diagnosis and RCA. Live community threads are optional.")

        if not reddit_results:
            st.info("This solution is generated from the current input file's diagnosis, RCA, and local knowledge base.")
        else:
            sources_data = []
            for idx, item in enumerate(reddit_results, 1):
                raw_score = item.get("score", 0)
                try:
                    fmt_score = f"+{int(raw_score):,}"
                except Exception:
                    fmt_score = str(raw_score)

                sources_data.append({
                    "#": idx,
                    "Community": item.get("subreddit", "r/techsupport"),
                    "Score": fmt_score,
                    "Relevance": str(item.get("relevance", "High")),
                    "Discussion Title": item.get("title", ""),
                    "Reddit Link": item.get("url", "")
                })

            st.dataframe(
                pd.DataFrame(sources_data),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Reddit Link": st.column_config.LinkColumn("Reddit Link", display_text="🔗 View Thread")
                }
            )

# ----------------- TAB 7: CASE REPORT & DOWNLOADS (PDF & MD) -----------------
with tabs[6]:
    st.subheader("📋 Case Report & Export Downloads")
    st.caption("Consolidated diagnostic scorecard, anomaly evidence chains, local root cause analysis, and prescriptive remediation actions.")
    sanitize_report = st.checkbox(
        "🔒 Sanitize sensitive endpoint identifiers",
        value=True,
        help="Redact common usernames, IP addresses, and Windows user paths from generated reports."
    )
    report_coverage = {
        "detected": detected_count,
        "expected": len(EXPECTED_MODULES),
        "missing": [module for module in EXPECTED_MODULES if not (target_data_dir / module).exists()]
    }
    report_metadata = _default_report_metadata(
        target_data_dir.name, diag_results, report_coverage, sanitize_report
    )
    impact_summary = _default_impact_summary(diag_results, rca_results)
    action_items = _build_action_items(diag_results, rca_results)
    siem_actions = _build_siem_action_records(action_items)
    finding_root_causes = _build_finding_root_cause_map(diag_results, rca_results)
    evidence_quality = _build_evidence_quality(diag_results, rca_results, report_coverage)
    chart_data = _build_report_chart_data(diag_results, rca_results)
    report_luna_solution = st.session_state.get("active_luna_solution")

    # Generate both PDF and Markdown files
    pdf_dir = base_dir / "output"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    clean_name = target_data_dir.name.replace(' ', '_')
    pdf_filename = f"Anomaly_and_RCA_result_{clean_name}.pdf"
    pdf_path = pdf_dir / pdf_filename

    pdf_bytes = b""
    try:
        PDFReportGenerator.generate_pdf(
            pdf_path, diag_results, rca_results, title_text="Sample Anomaly and RCA",
            sanitize_report=sanitize_report, coverage=report_coverage,
            luna_solution=report_luna_solution,
            report_metadata=report_metadata, impact_summary=impact_summary
        )
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
    except PermissionError:
        # File is locked by an external viewer (e.g. Adobe Acrobat / browser tab)
        if pdf_path.exists():
            try:
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
            except Exception:
                pass
        if not pdf_bytes:
            alt_pdf_path = pdf_dir / f"Anomaly_and_RCA_result_{clean_name}_active.pdf"
            try:
                PDFReportGenerator.generate_pdf(
                    alt_pdf_path, diag_results, rca_results, title_text="Sample Anomaly and RCA",
                    sanitize_report=sanitize_report, coverage=report_coverage,
                    luna_solution=report_luna_solution,
                    report_metadata=report_metadata, impact_summary=impact_summary
                )
                with open(alt_pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                pdf_filename = alt_pdf_path.name
                pdf_path = alt_pdf_path
            except Exception:
                pass
    except Exception as pdf_err:
        st.warning(f"Notice: PDF generation encountered an issue: {pdf_err}")

    md_filename = f"Case_Report_{clean_name}.md"
    md_path = pdf_dir / md_filename
    try:
        report_md = CaseReportBuilder.build_markdown_report(
            target_data_dir.name, diag_results, rca_results,
            sanitize_report=sanitize_report, coverage=report_coverage,
            luna_solution=report_luna_solution,
            report_metadata=report_metadata, impact_summary=impact_summary
        )
        md_path.write_text(report_md, encoding="utf-8")
    except Exception as report_err:
        report_md = (
            f"# Diagnostic & Root Cause Analysis Case Report: {target_data_dir.name}\n\n"
            "Report generation was incomplete. The diagnostic results remain available in the SIEM export.\n\n"
            f"Generation error: {report_err}"
        )
        st.warning(f"Markdown report generation encountered an issue: {report_err}")

    # Build SIEM / ServiceNow standardized incident export
    try:
        siem_incident = {
            "schema_version": "1.3.0",
            "schema": "endpoint-diagnostic-incident",
            "incident_id": f"INC-{clean_name}",
            "target_workstation": target_data_dir.name,
            "classification": "ENDPOINT_STABILITY_FAILURE",
            "severity": "CRITICAL" if len(tier1) > 0 else "WARNING",
            "incident": {
                "metadata": report_metadata,
                "impact_summary": impact_summary,
                "evidence_quality": evidence_quality,
            },
            "tier1_anomalies_count": len(tier1),
            "tier2_possible_count": len(tier2),
            "tier3_root_causes_count": len(tier3),
            "tier4_hypotheses_count": len(tier4),
            "tier1_anomalies": tier1,
            "tier2_possible_anomalies": tier2,
            "tier3_root_causes": tier3,
            "tier4_possible_root_causes": tier4,
            "report_metadata": report_metadata,
            "impact_summary": impact_summary,
            "action_items": action_items,
            "actions": siem_actions,
            "finding_root_causes": finding_root_causes,
            "evidence_quality": evidence_quality,
            "chart_data": chart_data,
            "scorecard": generate_scorecard_data(diag_results, rca_results),
            "statistical_micro_spikes": diag_results.get("statistical_micro_spikes", []),
            "monotonic_memory_leaks": diag_results.get("monotonic_memory_leaks", []),
            "luna_model_used": rca_results.get("luna_model_used", "Luna 5.6")
        }
        if sanitize_report:
            siem_incident = _sanitize_value(siem_incident)
        siem_json_bytes = json.dumps(siem_incident, indent=2, default=str).encode("utf-8")
        json_filename = f"SIEM_Incident_{clean_name}.json"
        json_path = pdf_dir / json_filename
        json_path.write_bytes(siem_json_bytes)
        has_siem_json = True
    except Exception as siem_err:
        siem_json_bytes = b"{}"
        json_filename = "SIEM_Incident.json"
        has_siem_json = False
        st.warning(f"SIEM export generation encountered an issue: {siem_err}")

    col_dl1, col_dl2, col_dl3 = st.columns(3)
    with col_dl1:
        if pdf_bytes:
            st.download_button(
                label="📄 Download PDF Report (.pdf)",
                data=pdf_bytes,
                file_name=pdf_filename,
                mime="application/pdf",
                key="dl_pdf_btn",
                type="primary",
                use_container_width=True
            )
        else:
            st.button("📄 PDF Report (Generating...)", disabled=True, use_container_width=True)
    with col_dl2:
        st.download_button(
            label="📥 Download Markdown (.md)",
            data=report_md.encode("utf-8"),
            file_name=md_filename,
            mime="text/markdown",
            key="dl_md_btn",
            use_container_width=True
        )
    with col_dl3:
        if has_siem_json:
            st.download_button(
                label="📦 SIEM / JSON Export (.json)",
                data=siem_json_bytes,
                file_name=json_filename,
                mime="application/json",
                key="dl_siem_json_btn",
                use_container_width=True
            )
        else:
            st.button("📦 SIEM JSON (Unavailable)", disabled=True, use_container_width=True)

    st.markdown("---")
    st.markdown(report_md)

# ----------------- LAST TAB: LUNA CASE CHAT (OPT-IN) -----------------
if LUNA_ENABLED:
    with tabs[7]:
        st.subheader("💬 Luna 5.6 case chat")
        st.caption("Ask questions about the current input file. Answers use this case, local RAG guidance, and Luna's available general knowledge.")

        chat_case_key = str(target_data_dir.resolve())
        if st.session_state.get("luna_chat_case") != chat_case_key:
            st.session_state["luna_chat_case"] = chat_case_key
            st.session_state["luna_chat_history"] = []

        for message in st.session_state.get("luna_chat_history", []):
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        chat_question = st.chat_input("Ask about this case, evidence, root cause, or next step...")
        if chat_question and chat_question.strip():
            question = chat_question.strip()
            history = st.session_state.setdefault("luna_chat_history", [])
            history.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            with st.chat_message("assistant"):
                with st.spinner("Luna 5.6 is reviewing the case and knowledge base..."):
                    rag_results = retrieve_grounded_context(question, top_k=5, include_multihop=True)
                    answer = answer_case_question(
                        question,
                        rag_results,
                        diag_results,
                        rca_results,
                        conversation=history[:-1],
                    )
                if answer:
                    st.markdown(answer)
                    history.append({"role": "assistant", "content": answer})
                else:
                    fallback = "Luna is unavailable. Confirm `LUNA_ENABLED=1`, provide `LUNA_API_KEY`, and check the API connection."
                    st.warning(fallback)
                    history.append({"role": "assistant", "content": fallback})
