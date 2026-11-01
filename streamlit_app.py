"""Interactive, trace-driven cache replacement policy explorer."""
from collections import Counter
import math

import plotly.express as px
import streamlit as st

from cache_simulator.workloads import (
    correlated_workload,
    loop_workload,
    scan_workload,
    zipfian_workload,
)
from dashboard_simulation import (
    POLICY_FACTORIES,
    compare_policies,
    hit_rate_timeline,
    parse_trace_text,
    policy_parameters,
    policy_state,
    replay_prefix,
)


st.set_page_config(
    page_title="Cache Policy Playground",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #0b1020; }
    [data-testid="stSidebar"] { background: #10182b; }
    .hero {
        padding: 1.4rem 1.6rem; border: 1px solid #293754; border-radius: 18px;
        background: linear-gradient(120deg, #142442 0%, #111a2c 65%, #17273a 100%);
        margin-bottom: 1rem;
    }
    .hero h1 { margin: 0 0 .35rem 0; color: #eef5ff; }
    .hero p { color: #b7c8df; margin: 0; font-size: 1.05rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def cached_comparison(requests: tuple, capacities: tuple):
    return compare_policies(requests, capacities)


@st.cache_data(show_spinner=False)
def cached_timeline(requests: tuple, capacity: int):
    return hit_rate_timeline(requests, capacity)


@st.cache_data(show_spinner=False)
def cached_generated_workload(
    workload: str,
    request_count: int,
    seed: int,
    num_pages: int,
    zipf_alpha: float,
    working_set_size: int,
    scan_size: int,
    loop_size: int,
    burst_length: int,
    burst_probability: float,
    group_size: int,
):
    if workload == "Zipfian":
        return zipfian_workload(
            request_count, num_pages, alpha=zipf_alpha, seed=seed
        )
    if workload == "Scan-polluted":
        cycle_size = 500 + scan_size
        cycles = max(1, math.ceil(request_count / cycle_size))
        return scan_workload(
            working_set_size=working_set_size,
            scan_size=scan_size,
            cycles=cycles,
            seed=seed,
        )[:request_count]
    if workload == "Correlated references":
        return correlated_workload(
            num_requests=request_count,
            num_pages=num_pages,
            burst_length=burst_length,
            burst_prob=burst_probability,
            seed=seed,
            correlation_group_size=group_size,
        )
    if workload == "Cyclic loop":
        return loop_workload(
            loop_size=loop_size,
            cycles=max(1, math.ceil(request_count / loop_size)),
        )[:request_count]
    raise ValueError(f"Unknown generated workload: {workload}")


def build_trace():
    with st.sidebar:
        st.header("Trace and cache")
        workload = st.selectbox(
            "Request stream",
            [
                "Zipfian",
                "Scan-polluted",
                "Correlated references",
                "Cyclic loop",
                "Upload a trace",
            ],
        )
        request_count = st.slider(
            "Requests to simulate",
            min_value=500,
            max_value=30000,
            value=6000,
            step=500,
        )
        seed = st.number_input("Random seed", min_value=0, value=42, step=1)

        num_pages = 1000
        zipf_alpha = 0.9
        working_set_size = 100
        scan_size = 500
        loop_size = 64
        burst_length = 4
        burst_probability = 0.4
        group_size = 8

        if workload in ("Zipfian", "Correlated references"):
            num_pages = st.slider(
                "Distinct page IDs", min_value=16, max_value=5000, value=1008, step=16
            )
        if workload == "Zipfian":
            zipf_alpha = st.slider(
                "Zipf skew (higher = more concentrated)",
                min_value=0.1,
                max_value=1.5,
                value=0.9,
                step=0.1,
            )
        if workload == "Scan-polluted":
            working_set_size = st.slider(
                "Hot working-set size", min_value=8, max_value=512, value=100, step=8
            )
            scan_size = st.slider(
                "One-time scan length", min_value=32, max_value=3000, value=512, step=32
            )
        if workload == "Correlated references":
            burst_length = st.slider(
                "Maximum repeats per page", min_value=2, max_value=12, value=4
            )
            burst_probability = st.slider(
                "Probability of a correlated burst",
                min_value=0.0,
                max_value=1.0,
                value=0.4,
                step=0.05,
            )
            group_size = st.slider(
                "Pages per correlation group", min_value=2, max_value=64, value=8, step=2
            )
        if workload == "Cyclic loop":
            loop_size = st.slider(
                "Pages in loop", min_value=4, max_value=1024, value=64, step=4
            )

        uploaded_trace = None
        if workload == "Upload a trace":
            uploaded_trace = st.file_uploader(
                "Text trace (.txt or .csv)",
                type=["txt", "csv", "log"],
                help="One page ID per line, or timestamp,page_id[,size] per line. Lines beginning with # are ignored.",
            )
            st.caption(
                "Page IDs are not anonymized. Upload only traces you are authorized to use."
            )

        capacity = st.slider(
            "Cache capacity (pages)", min_value=1, max_value=512, value=64, step=1
        )
        replay_policy = st.selectbox(
            "Policy to inspect step by step",
            list(POLICY_FACTORIES),
            index=list(POLICY_FACTORIES).index("CAR"),
        )

    if workload == "Upload a trace":
        if uploaded_trace is None:
            st.info("Upload a trace in the sidebar to start the simulation.")
            st.stop()
        try:
            trace_text = uploaded_trace.getvalue().decode("utf-8-sig")
            requests = parse_trace_text(trace_text, max_requests=request_count)
        except UnicodeDecodeError:
            st.error("The uploaded trace must be UTF-8 encoded text.")
            st.stop()
        except ValueError as error:
            st.error(str(error))
            st.stop()
        source_label = f"Uploaded trace: {uploaded_trace.name}"
    else:
        requests = cached_generated_workload(
            workload,
            request_count,
            int(seed),
            num_pages,
            zipf_alpha,
            working_set_size,
            scan_size,
            loop_size,
            burst_length,
            burst_probability,
            group_size,
        )
        source_label = f"Synthetic {workload.lower()} workload"

    if len(requests) < 1:
        st.error("The selected trace has no requests to simulate.")
        st.stop()
    return requests, capacity, replay_policy, source_label


def render_replay(requests, capacity, policy_name):
    st.subheader("Replay the same trace, request by request")
    st.caption(
        "Drag the slider to rewind or fast-forward. Each selected policy is replayed "
        "from an empty cache so its state is deterministic at every step."
    )
    request_count = st.slider(
        "Requests processed",
        min_value=0,
        max_value=len(requests),
        value=min(250, len(requests)),
        step=1,
        key="replay_request_count",
    )
    policy, event = replay_prefix(policy_name, requests, capacity, request_count)

    if event:
        event_label = "HIT" if event["hit"] else "MISS"
        evicted = event["evicted_pages"]
        evicted_label = ", ".join(map(str, evicted)) if evicted else "none"
        first, second, third, fourth = st.columns(4)
        first.metric("Request", f"#{event['request_number']}")
        second.metric("Page requested", str(event["page_id"]))
        third.metric("Outcome", event_label)
        fourth.metric("Evicted", evicted_label)
    else:
        st.info("The cache is empty. Move the slider forward to process requests.")

    parameters = policy_parameters(policy)
    if parameters:
        st.caption("Live policy parameters: " + " · ".join(parameters))
    st.caption(
        f"Resident pages: {len(policy)} / {capacity} · "
        f"Hit rate so far: {policy.hit_ratio:.2f}% · "
        f"Misses: {policy.misses:,}"
    )

    state_rows = policy_state(policy)
    if state_rows:
        st.dataframe(state_rows, hide_index=True, width="stretch")
    else:
        st.caption("No queue entries yet.")

    if event:
        left, right = st.columns(2)
        left.metric("Resident before request", event["resident_before"])
        right.metric("Resident after request", event["resident_after"])


def render_comparison(requests, capacity):
    st.subheader("Compare policies on identical requests")
    st.caption(
        "Hit rate is the fraction of this trace served from the simulated cache. "
        "Miss rate is its complement; neither is a production latency measurement."
    )
    capacities = tuple(
        sorted(
            {
                max(1, capacity // 2),
                capacity,
                min(1024, capacity * 2),
            }
        )
    )
    request_key = tuple(requests)
    with st.spinner("Running the same request stream through each policy…"):
        results = cached_comparison(request_key, capacities)
        timeline = cached_timeline(request_key, capacity)

    selected_results = [row for row in results if row["Capacity"] == capacity]
    leader = max(selected_results, key=lambda row: row["Hit rate (%)"])
    lru = next(row for row in selected_results if row["Policy"] == "LRU")
    difference = leader["Hit rate (%)"] - lru["Hit rate (%)"]
    summary, improvement, count = st.columns(3)
    summary.metric(
        "Best hit rate on this trace",
        f"{leader['Hit rate (%)']:.2f}%",
        leader["Policy"],
    )
    improvement.metric(
        "Difference vs LRU",
        f"{difference:+.2f} percentage points",
        help="An empirical result for this selected trace and cache capacity only.",
    )
    count.metric("Requests compared", f"{len(requests):,}")

    left, right = st.columns(2)
    with left:
        st.markdown(f"**Hit rate at capacity {capacity}**")
        fig = px.bar(
            selected_results,
            x="Policy",
            y="Hit rate (%)",
            color="Policy",
            text_auto=".2f",
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig.update_layout(
            showlegend=False,
            yaxis_range=[0, 100],
            margin=dict(l=10, r=10, t=15, b=10),
        )
        st.plotly_chart(fig, width="stretch")
    with right:
        st.markdown("**How cache size changes hit rate**")
        fig = px.line(
            results,
            x="Capacity",
            y="Hit rate (%)",
            color="Policy",
            markers=True,
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig.update_layout(
            yaxis_range=[0, 100],
            margin=dict(l=10, r=10, t=15, b=10),
            legend_title_text="Policy",
        )
        st.plotly_chart(fig, width="stretch")

    st.markdown("**Cumulative hit rate over the request stream**")
    timeline_fig = px.line(
        timeline,
        x="Requests processed",
        y="Cumulative hit rate (%)",
        color="Policy",
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    timeline_fig.update_layout(
        yaxis_range=[0, 100],
        margin=dict(l=10, r=10, t=15, b=10),
        legend_title_text="Policy",
    )
    st.plotly_chart(timeline_fig, width="stretch")
    st.dataframe(
        sorted(selected_results, key=lambda row: row["Hit rate (%)"], reverse=True),
        hide_index=True,
        width="stretch",
    )


def render_workload(requests):
    st.subheader("What did the policies receive?")
    st.caption(
        "Every policy sees this exact ordered sequence. These synthetic traces are "
        "controlled scenarios, not measurements from production systems."
    )
    counts = Counter(requests)
    left, right = st.columns([1.5, 1])
    with left:
        sample_count = min(1000, len(requests))
        fig = px.line(
            x=list(range(1, sample_count + 1)),
            y=requests[:sample_count],
            labels={"x": "Request number", "y": "Page ID"},
            title=f"First {sample_count:,} requests",
        )
        fig.update_traces(line=dict(color="#61d6c6", width=1.5))
        fig.update_layout(margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(fig, width="stretch")
    with right:
        top_pages = counts.most_common(15)
        fig = px.bar(
            x=[count for _, count in reversed(top_pages)],
            y=[str(page) for page, _ in reversed(top_pages)],
            orientation="h",
            labels={"x": "Requests", "y": "Page ID"},
            title="Most requested pages",
        )
        fig.update_layout(margin=dict(l=10, r=10, t=45, b=10))
        st.plotly_chart(fig, width="stretch")

    st.download_button(
        "Download this request stream as CSV",
        data="page_id\n" + "\n".join(map(str, requests)),
        file_name="cache_policy_trace.csv",
        mime="text/csv",
    )


def render_research_guide():
    st.subheader("Research ideas behind the policies")
    st.caption(
        "The papers motivate mechanisms and evaluation questions. This repository "
        "implements teaching/simulation versions; it does not reproduce paper figures "
        "or production systems."
    )

    cards = [
        {
            "name": "LRU · recency baseline",
            "mechanism": "Evict the least recently requested resident page.",
            "tradeoff": "Simple and intuitive; a one-time scan can displace useful pages.",
            "question": "Does recent use predict reuse in this workload?",
            "source": "Classic baseline; no paper implementation is claimed here.",
            "url": None,
        },
        {
            "name": "CLOCK · second chance",
            "mechanism": "A circular hand clears reference bits and evicts an unreferenced page.",
            "tradeoff": "Avoids LRU-style list movement on each hit, but has no frequency adaptation.",
            "question": "How does a low-metadata recency policy respond to a scan?",
            "source": "Classic baseline; no paper implementation is claimed here.",
            "url": None,
        },
        {
            "name": "ARC · adaptive recency/frequency",
            "mechanism": "T1/T2 resident lists and B1/B2 ghost histories adapt target p.",
            "tradeoff": "Learns a recency/frequency balance; ghost metadata and list updates add work.",
            "question": "Does workload feedback outperform a fixed recency/frequency split?",
            "source": "Megiddo and Modha, FAST '03.",
            "url": "https://www.usenix.org/legacy/events/fast03/tech/full_papers/megiddo/megiddo.pdf",
        },
        {
            "name": "CAR · clock-based adaptive replacement",
            "mechanism": "CAR combines T1/T2 and B1/B2 with reference bits and adaptive p.",
            "tradeoff": "Uses clock-style second chances rather than moving list entries on every hit.",
            "question": "How does feedback from ghost hits shift the recency/frequency target?",
            "source": "Bansal and Modha, FAST '04.",
            "url": "https://www.usenix.org/legacy/events/fast04/tech/full_papers/bansal/bansal.pdf",
        },
        {
            "name": "CART · temporal filtering",
            "mechanism": "The CAR-family algorithm adds S/L filter state and an additional target q.",
            "tradeoff": "Attempts to distinguish temporally clustered activity from lasting reuse.",
            "question": "Does filtering short bursts help under this trace's temporal pattern?",
            "source": "CART is presented alongside CAR in the FAST '04 work.",
            "url": "https://www.usenix.org/legacy/events/fast04/tech/full_papers/bansal/bansal.pdf",
        },
        {
            "name": "S3-FIFO · segmented FIFO",
            "mechanism": "Small, Main, and Ghost FIFOs use bounded reuse counters and ghost re-admission.",
            "tradeoff": "Low-complexity FIFO organization; no explicit Clock2Q+ correlation-window gate.",
            "question": "Do the new-policy results change when short-lived correlated hits are filtered?",
            "source": "Yang et al., SOSP '23, “FIFO queues are all you need for cache eviction.”",
            "url": "https://doi.org/10.1145/3600006.3613147",
        },
        {
            "name": "Clock2Q+ · correlation-aware promotion",
            "mechanism": "A small FIFO, main clock, and ghost queue; a correlation window suppresses early promotion evidence.",
            "tradeoff": "Targets correlated metadata bursts; this synthetic generator does not validate production metadata behavior.",
            "question": "Does window-gated promotion help on correlated references versus S3-FIFO?",
            "source": "Zhai et al., PVLDB 19(12), 2026.",
            "url": "https://doi.org/10.14778/3827998.3828002",
        },
    ]

    for offset in range(0, len(cards), 2):
        columns = st.columns(2)
        for column, card in zip(columns, cards[offset : offset + 2]):
            with column:
                with st.container(border=True):
                    st.markdown(f"### {card['name']}")
                    st.markdown(f"**Mechanism**  \n{card['mechanism']}")
                    st.markdown(f"**Trade-off**  \n{card['tradeoff']}")
                    st.markdown(f"**Try asking**  \n{card['question']}")
                    if card["url"]:
                        st.markdown(f"**Paper:** [{card['source']}]({card['url']})")
                    else:
                        st.caption(card["source"])

    st.warning(
        "Interpretation guardrail: a higher hit rate here is not proof that a policy "
        "is universally better. The dashboard does not model storage latency, dirty "
        "pages, metadata bytes, synchronization contention, or the real traces and "
        "system setup used by the cited papers."
    )


requests, cache_capacity, selected_policy, trace_label = build_trace()
unique_pages = len(set(requests))

st.markdown(
    f"""
    <div class="hero">
      <h1>Cache Policy Playground</h1>
      <p>Watch replacement decisions unfold, then compare seven policies on the same trace.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

summary_columns = st.columns(4)
summary_columns[0].metric("Trace", trace_label)
summary_columns[1].metric("Requests", f"{len(requests):,}")
summary_columns[2].metric("Unique pages", f"{unique_pages:,}")
summary_columns[3].metric("Cache size", f"{cache_capacity:,} pages")
st.info(
    "Controlled simulation only: page IDs are requests, and a hit rate is not a "
    "production latency or paper-reproduction result."
)

replay_tab, compare_tab, workload_tab, research_tab = st.tabs(
    ["▶ Live replay", "⇄ Compare policies", "◉ Workload", "▤ Research guide"]
)
with replay_tab:
    render_replay(requests, cache_capacity, selected_policy)
with compare_tab:
    render_comparison(requests, cache_capacity)
with workload_tab:
    render_workload(requests)
with research_tab:
    render_research_guide()
