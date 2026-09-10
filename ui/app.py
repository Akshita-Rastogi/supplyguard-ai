import csv
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx
import streamlit as st
import streamlit.components.v1 as components

API = os.getenv("API_BASE_URL", "http://localhost:8000")
KEY = os.getenv("API_KEY", "demo-key")
ROOT = Path(__file__).resolve().parents[1]

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "turn_results" not in st.session_state:
    # Keep every result so later questions append instead of replacing the
    # citations, trace, and feedback controls from previous conversation turns.
    st.session_state.turn_results = (
        [{"question": "Earlier question", "result": st.session_state.last_result}]
        if st.session_state.last_result else []
    )
if "feedback_saved" not in st.session_state:
    st.session_state.feedback_saved = {}
if "question_input" not in st.session_state:
    st.session_state.question_input = ""
if "scroll_to_result" not in st.session_state:
    st.session_state.scroll_to_result = False
if "feedback_notice" not in st.session_state:
    st.session_state.feedback_notice = False
if st.session_state.pop("clear_question_on_rerun", False):
    # Prepare an empty composer for the next conversational turn.
    st.session_state.question_input = ""
    st.session_state.example_picker = ""


def api_error_message(exc: httpx.HTTPStatusError) -> str:
    """Render only the API's safe error detail together with its correlation ID."""
    try:
        detail = exc.response.json().get("detail", "request rejected")
    except ValueError:
        detail = "request rejected"
    request_id = exc.response.headers.get("x-request-id", "not supplied")
    return f"API request failed ({exc.response.status_code}): {detail}. Request ID: {request_id}"


def load_selected_example() -> None:
    """Copy the selected example into the editable question box."""
    selected = st.session_state.get("example_picker", "")
    if selected:
        st.session_state.question_input = selected


def restore_persisted_feedback(request_id: str) -> None:
    """Reconcile a turn with MongoDB when Streamlit session state is stale."""
    if request_id in st.session_state.feedback_saved:
        return
    try:
        response = httpx.get(
            f"{API}/v1/feedback/{request_id}", headers={"x-api-key": KEY}, timeout=5
        )
        if response.is_success and response.json().get("submitted"):
            st.session_state.feedback_saved[request_id] = (
                "Helpful" if response.json()["helpful"] else "Not helpful"
            )
    except (httpx.HTTPError, ValueError, KeyError):
        # A status refresh must never make the answer itself unavailable.
        return


@st.dialog("SupplyGuard is analyzing", width="small", dismissible=False)
def analyze_in_popup(question: str, tenant: str) -> None:
    """Run the blocking API request inside a modal progress experience."""
    started = time.perf_counter()
    try:
        with st.spinner("Classifying intent and selecting the safest execution path…"):
            st.caption("This may use local Ollama, MongoDB, Qdrant, and the MCP tool.")
            response = httpx.post(f"{API}/v1/ask", headers={"x-api-key": KEY},
                json={"tenant_id": tenant, "question": question,
                      "conversation_id": st.session_state.conversation_id}, timeout=120)
            response.raise_for_status()
            result = response.json()
        st.session_state.messages.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": result["answer"]},
        ])
        st.session_state.last_result = result
        st.session_state.turn_results.append({"question": question, "result": result})
        st.session_state.analysis_elapsed = time.perf_counter() - started
        st.session_state.scroll_to_result = True
        st.session_state.clear_question_on_rerun = True
        # Close the loader automatically and render the completed result page.
        st.rerun(scope="app")
    except httpx.HTTPStatusError as exc:
        st.error(api_error_message(exc))
    except httpx.HTTPError as exc:
        st.error(f"API connection failed safely: {type(exc).__name__}")
    if st.button("Close", type="primary", width="stretch"):
        st.rerun(scope="app")


st.set_page_config(page_title="SupplyGuard AI", page_icon="🛡️", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1250px; padding-top: 2rem}
.hero {padding: 1.4rem 1.6rem; border-radius: 18px; color: white;
background: linear-gradient(120deg,#102a43,#0f766e)}
.chip {display:inline-block;padding:.2rem .6rem;border-radius:999px;background:#e6fffa;color:#115e59;margin-right:.3rem}
</style>
<div class="hero"><h1>SupplyGuard AI</h1><p>Local evidence-grounded procurement and supply-chain decision intelligence</p>
<span class="chip">Ollama</span><span class="chip">Qdrant</span><span class="chip">MongoDB</span><span class="chip">MCP</span></div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Runtime")
    tenant = st.text_input("Tenant", "demo-corp")
    try:
        health = httpx.get(f"{API}/health/ready", timeout=3)
        if health.is_success:
            st.success("All services ready")
            st.json(health.json()["dependencies"], expanded=False)
            storage = httpx.get(
                f"{API}/v1/storage/stats", headers={"x-api-key": KEY}, timeout=5
            )
            if storage.is_success:
                with st.expander("Persistent storage counts"):
                    st.json(storage.json())
        else:
            st.warning("Dependencies are starting or degraded")
    except httpx.HTTPError:
        st.error("FastAPI is unavailable")
    st.caption("All model inference and embeddings remain local through Ollama.")

chat, corpus, evaluation, architecture = st.tabs(["Ask", "Corpus", "Evaluation", "How it works"])
with chat:
    st.subheader("Ask documents, data, or risk tools")
    context_col, reset_col = st.columns([4, 1])
    context_col.caption(
        f"Session memory: {len(st.session_state.messages) // 2} turn(s) in this chat"
    )
    if reset_col.button("New chat"):
        st.session_state.conversation_id = str(uuid4())
        st.session_state.messages = []
        st.session_state.last_result = None
        st.session_state.turn_results = []
        st.session_state.feedback_saved = {}
        st.session_state.feedback_notice = False
        st.session_state.question_input = ""
        st.session_state.scroll_to_result = False
        st.rerun()
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    with st.expander("Try the session-memory demonstration"):
        st.markdown(
            "1. Ask **What does NIST recommend for cyber supply-chain risk assessments?**  \n"
            "2. Without selecting **New chat**, ask **What about supplier monitoring?**  \n"
            "The second question is deliberately incomplete. The API resolves it using the "
            "bounded history associated with this conversation ID. The retrieved documents, "
            "not chat memory, remain the factual evidence."
        )
    examples = [
        "What procurement approach is appropriate for complex high-risk requirements?",
        "Which state has the most disaster declarations?",
        "Use the FEMA tool to count declarations for CA in 2025",
        "What does NIST recommend for cyber supply-chain risk assessments?",
        "What about supplier monitoring?",
    ]
    st.selectbox(
        "Try an example",
        [""] + examples,
        key="example_picker",
        on_change=load_selected_example,
        help="The final two examples form a two-turn memory demonstration.",
    )
    question = st.text_area("Question", key="question_input", height=90)
    if st.button("Analyze", type="primary", disabled=not question.strip()):
        analyze_in_popup(question.strip(), tenant)

    # Each turn keeps its own evidence, trace, and feedback state. Earlier turns
    # remain inspectable when another question is appended to the conversation.
    if st.session_state.turn_results:
        st.markdown("### Conversation results")
    for turn_number, turn in enumerate(st.session_state.turn_results, start=1):
        result = turn["result"]
        is_latest = turn_number == len(st.session_state.turn_results)
        if is_latest:
            st.markdown('<div id="analysis-result"></div>', unsafe_allow_html=True)
            if st.session_state.scroll_to_result:
                elapsed = st.session_state.get("analysis_elapsed", 0.0)
                st.toast(f"Analysis completed in {elapsed:.1f} seconds.", icon="✅")
                components.html(
                    """
                    <script>
                    const target = window.parent.document.getElementById('analysis-result');
                    if (target) target.scrollIntoView({behavior: 'smooth', block: 'start'});
                    </script>
                    """,
                    height=0,
                )
                st.session_state.scroll_to_result = False

        label = f"Turn {turn_number}: {turn['question'][:90]}"
        with st.container(border=True):
            st.markdown(f"#### {label}")
            a, b, c = st.columns(3)
            a.metric("Intent", result["intent"])
            b.metric("Evidence confidence", f"{result['confidence']:.0%}")
            c.metric("Citations", len(result["citations"]))
            st.markdown("##### Answer")
            st.write(result["answer"])
            for warning in result["warnings"]:
                st.warning(warning)
            with st.expander("Evidence and citations", expanded=is_latest):
                if not result["citations"]:
                    st.caption("This execution path returned no document citations.")
                for citation in result["citations"]:
                    st.markdown(
                        f"**{citation['title']} · {citation['locator']} · "
                        f"{citation['score']:.2f}**"
                    )
                    st.caption(citation["excerpt"])
            with st.expander("Tool execution trace"):
                st.json(result["tool_trace"])

            request_id = result["request_id"]
            restore_persisted_feedback(request_id)
            if request_id in st.session_state.feedback_saved:
                submitted_value = st.session_state.feedback_saved[request_id]
                if st.session_state.feedback_notice == request_id:
                    st.toast("Feedback successfully submitted to MongoDB.", icon="✅")
                    st.session_state.feedback_notice = False
                st.success(
                    f"Feedback already submitted as **{submitted_value}** and stored in MongoDB."
                )
                st.button("Feedback already submitted", disabled=True, width="stretch",
                          key=f"feedback-disabled-{request_id}")
            else:
                with st.form(f"feedback-{request_id}"):
                    helpful = st.radio("Was this helpful?", ["Helpful", "Not helpful"],
                                       horizontal=True)
                    reason = st.text_input("Optional reason")
                    if st.form_submit_button("Submit feedback", type="primary"):
                        try:
                            saved = httpx.post(f"{API}/v1/feedback",
                                headers={"x-api-key": KEY}, json={"request_id": request_id,
                                "helpful": helpful == "Helpful", "reason": reason or None},
                                timeout=10)
                            saved.raise_for_status()
                            st.session_state.feedback_saved[request_id] = helpful
                            st.session_state.feedback_notice = request_id
                            st.rerun(scope="app")
                        except httpx.HTTPStatusError as exc:
                            st.error(api_error_message(exc))
                        except httpx.HTTPError as exc:
                            st.error(f"Feedback connection failed safely: {type(exc).__name__}")
with corpus:
    st.subheader("Evidence corpus")
    rows = [
        ("World Bank Procurement Regulations", "154-page official PDF", "Narrative, tables, annexes"),
        ("World Bank Contract Management Guidance", "124-page official PDF", "Figures, workflows, tables"),
        ("NIST SP 800-161r1", "325-page official PDF", "Controls, appendices, dense tables"),
        ("OpenFEMA declarations", "70,402-row official CSV", "Dates, nulls, geography, categories"),
    ]
    st.dataframe(rows, column_config={0:"Source",1:"Size",2:"Challenges"}, hide_index=True, width="stretch")

with evaluation:
    st.subheader("Golden evaluation set")
    cases = json.loads((ROOT / "evaluation.json").read_text())
    st.dataframe(cases, hide_index=True, width="stretch")
    result_path = ROOT / "output/evaluation/evaluation_results.csv"
    if result_path.exists():
        st.subheader("Measured results")
        with result_path.open(encoding="utf-8", newline="") as handle:
            st.dataframe(list(csv.DictReader(handle)), hide_index=True, width="stretch")
    else:
        st.info("Run `docker compose exec api python scripts/evaluate.py` to create the measured Question / Expected / Actual / Pass-Fail table.")

with architecture:
    st.subheader("Decision path")
    st.code("Question → Intent router → {RAG | Mongo aggregation | MCP tool}\n"
            "RAG → Ollama embedding → Qdrant + lexical RRF → threshold/conflict checks\n"
            "→ Ollama grounded synthesis → citations + audit + feedback")
    st.markdown("Every response exposes intent, evidence score, citations, warnings, and tool trace so an evaluator can see *why* it answered.")
