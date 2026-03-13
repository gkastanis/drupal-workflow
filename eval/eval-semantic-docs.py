"""Eval: compare Claude responses with vs without semantic docs.

Runs each test question twice against the same project:
  A) WITHOUT hint → explores codebase from scratch
  B) WITH hint    → reads docs/semantic/ first (structural index + tech specs)

Measures wall-clock time, token usage, cost, and saves outputs for
manual quality comparison.

Improvements over v1:
- Hint covers full doc stack (FEATURE_MAP, tech specs, structural index)
- Questions target proven high-value categories (broad awareness, cross-module,
  scoping, onboarding) — avoids known low-value categories (debugging, grep-friendly)
- Pre-check: skips "with hint" variant if docs/semantic/ doesn't exist
- Two runs per question for variance measurement
"""

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

CLAUDE_BIN = "claude"
REPOS_DIR = "/mnt/storage2/repos"
RESULTS_DIR = Path("/srv/pb/logs/eval-semantic-docs")
MODEL = "sonnet"
TIMEOUT = 300
RUNS_PER_QUESTION = 2

SYSTEM_APPEND = (
    "You are read-only. Do NOT modify any files. Do NOT access or display tokens, "
    "passwords, or secrets from .env or config files. Be concise — your output goes "
    "into a Slack message. Use Slack mrkdwn formatting. If asked to make changes, "
    "explain what should be changed and where."
)

# Full-stack hint: structural index (Layer 2) + semantic docs (Layer 3)
HINT = (
    "This project has pre-generated documentation at docs/semantic/. "
    "Read these files FIRST before exploring code:\n"
    "1. docs/semantic/FEATURE_MAP.md — compact overview of all features with structural counts\n"
    "2. docs/semantic/00_BUSINESS_INDEX.md — feature registry, user stories, business rules\n"
    "3. docs/semantic/tech/*.md — per-feature tech specs with Logic ID tables mapping business logic to file:function\n"
    "4. docs/semantic/structural/services.md — all services with injected dependencies\n"
    "5. docs/semantic/DEPENDENCY_GRAPH.md — cross-module dependencies and hotspots\n"
    "Start with FEATURE_MAP.md (smallest, highest density), then drill into specific tech specs as needed."
)

# --- Test cases ---
# Focus on question types proven to benefit from semantic docs:
# - Broad awareness (status, overview, onboarding)
# - Cross-module analysis (what touches X, dependencies)
# - Scoping (what would I need to change)
# - Feature inventory (list modules, capabilities)
#
# Avoid question types proven to NOT benefit:
# - Debugging ("X is broken, find it")
# - Narrow grep ("where is function X")
# - Deep code tracing ("trace execution of X")
# - Small surface area (single theme/template)

TESTS = [
    # Category: Onboarding / broad awareness
    ("pb/technocan",
     "I'm new to this project. Give me a quick overview: what does it do, what are the main features, and how is the code organized?",
     "onboarding"),

    ("pb/elvial",
     "What's the current status of this project? What are the main features and content types?",
     "status_overview"),

    # Category: Feature inventory
    ("europa/ddc",
     "How many custom modules does this project have and what does each one do? Include any key services.",
     "module_inventory"),

    ("pb/candia-b2b",
     "What commerce-related features are built? List the custom order workflows, pricing logic, and integrations.",
     "feature_inventory"),

    # Category: Cross-module / impact analysis
    ("pb/candia-b2b",
     "We need to change how product pricing works. What modules, services, and hooks are involved in price calculation? What's the blast radius?",
     "cross_module_impact"),

    ("pb/elvial",
     "We want to add a new product category with its own listing page and sitemap entry. What existing features, content types, and views would be affected?",
     "scoping_new_feature"),

    # Category: Architecture understanding
    ("pb/hellasfin",
     "Explain the data model: what are the main entity types, how do they relate to each other, and what are the key business rules?",
     "architecture_data_model"),

    ("pb/istolab",
     "What's the overall architecture? How many custom modules, what are the main services, and how do they depend on each other?",
     "architecture_overview"),
]


@dataclass
class Result:
    project: str
    question: str
    question_type: str
    variant: str  # "with_hint" or "without_hint"
    run: int = 1
    time_seconds: float = 0.0
    output: str = ""
    error: str = ""
    output_length: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    num_turns: int = 0


def has_semantic_docs(project: str) -> bool:
    """Check if project has docs/semantic/ with content."""
    semantic_dir = os.path.join(REPOS_DIR, project, "docs", "semantic")
    if not os.path.isdir(semantic_dir):
        return False
    # Must have at least FEATURE_MAP.md or 00_BUSINESS_INDEX.md
    return (
        os.path.isfile(os.path.join(semantic_dir, "FEATURE_MAP.md"))
        or os.path.isfile(os.path.join(semantic_dir, "00_BUSINESS_INDEX.md"))
    )


def clean_env() -> dict:
    env = {**os.environ}
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    return env


def run_once(project: str, question: str, question_type: str,
             with_hint: bool, run_num: int) -> Result:
    variant = "with_hint" if with_hint else "without_hint"
    cwd = os.path.join(REPOS_DIR, project)

    hint_text = f"\n{HINT}" if with_hint else ""
    prompt = f"""You are a helpful assistant for the PointBlank cooperative.
You are answering a question from a team member on Slack about the project: {project}
{hint_text}

Current question: {question}"""

    args = [
        CLAUDE_BIN,
        "--model", MODEL,
        "--disallowedTools", "Write,Edit",
        "--append-system-prompt", SYSTEM_APPEND,
        "--print",
        "--output-format", "json",
        "--no-session-persistence",
        "--dangerously-skip-permissions",
        "-p", "-",
    ]

    result = Result(
        project=project, question=question,
        question_type=question_type, variant=variant, run=run_num,
    )

    start = time.monotonic()
    try:
        proc = subprocess.run(
            args,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=cwd,
            env=clean_env(),
        )
        result.time_seconds = round(time.monotonic() - start, 1)
        raw = proc.stdout.strip()

        try:
            data = json.loads(raw)
            result.output = data.get("result", "")
            result.cost_usd = data.get("total_cost_usd", 0)
            result.num_turns = data.get("num_turns", 0)
            usage = data.get("usage", {})
            result.input_tokens = usage.get("input_tokens", 0)
            result.output_tokens = usage.get("output_tokens", 0)
            result.cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)
            result.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
        except json.JSONDecodeError:
            result.output = raw
            result.error = "JSON parse failed"

        if not result.output and proc.stderr:
            result.error = proc.stderr[:500]
        result.output_length = len(result.output)
    except subprocess.TimeoutExpired:
        result.time_seconds = TIMEOUT
        result.error = "TIMEOUT"
    except Exception as e:
        result.time_seconds = round(time.monotonic() - start, 1)
        result.error = str(e)

    return result


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    results = []

    # Pre-check which projects have semantic docs
    print("=== PRE-CHECK: Semantic docs availability ===")
    for project, _, _ in TESTS:
        has_docs = has_semantic_docs(project)
        status = "HAS docs/semantic/" if has_docs else "NO docs/semantic/ — with_hint will search blindly"
        print(f"  {project}: {status}")
    print()

    total_runs = len(TESTS) * 2 * RUNS_PER_QUESTION
    run_idx = 0

    for run_num in range(1, RUNS_PER_QUESTION + 1):
        print(f"=== RUN {run_num}/{RUNS_PER_QUESTION} ===\n")

        for i, (project, question, qtype) in enumerate(TESTS):
            short_q = question[:55]

            # WITHOUT hint first (no cache benefit from prior reads)
            run_idx += 1
            print(f"[{run_idx}/{total_runs}] {project} — WITHOUT — {short_q}...")
            r_without = run_once(project, question, qtype, with_hint=False, run_num=run_num)
            results.append(r_without)
            print(f"  {r_without.time_seconds}s | {r_without.output_length} chars | "
                  f"{r_without.num_turns} turns | ${r_without.cost_usd:.4f}")

            # WITH hint
            run_idx += 1
            print(f"[{run_idx}/{total_runs}] {project} — WITH    — {short_q}...")
            r_with = run_once(project, question, qtype, with_hint=True, run_num=run_num)
            results.append(r_with)
            print(f"  {r_with.time_seconds}s | {r_with.output_length} chars | "
                  f"{r_with.num_turns} turns | ${r_with.cost_usd:.4f}")

            delta_t = r_without.time_seconds - r_with.time_seconds
            delta_cost = r_without.cost_usd - r_with.cost_usd
            print(f"  delta: {delta_t:+.1f}s | ${delta_cost:+.4f}\n")

    # Save raw results
    raw_path = RESULTS_DIR / f"results-{timestamp}.json"
    with open(raw_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    # Generate report
    report_path = RESULTS_DIR / f"report-{timestamp}.md"
    with open(report_path, "w") as f:
        f.write("# Semantic Docs Eval Report (v2)\n\n")
        f.write(f"**Date:** {timestamp}\n")
        f.write(f"**Model:** {MODEL}\n")
        f.write(f"**Tests:** {len(TESTS)} questions x {RUNS_PER_QUESTION} runs\n")
        f.write(f"**Hint:** Full doc stack (FEATURE_MAP → BUSINESS_INDEX → tech specs → structural)\n\n")

        # Per-question summary (averaged across runs)
        f.write("## Per-Question Results (averaged)\n\n")
        f.write("| # | Type | Project | W/o Time | W/ Time | Speed | W/o Cost | W/ Cost | Cost | Turns W/o | Turns W/ |\n")
        f.write("|---|------|---------|----------|---------|-------|----------|---------|------|-----------|----------|\n")

        total_wo_t = total_w_t = total_wo_c = total_w_c = 0

        for i, (project, question, qtype) in enumerate(TESTS):
            wo = [r for r in results if r.question == question and r.variant == "without_hint"]
            w = [r for r in results if r.question == question and r.variant == "with_hint"]

            avg_wo_t = sum(r.time_seconds for r in wo) / len(wo)
            avg_w_t = sum(r.time_seconds for r in w) / len(w)
            avg_wo_c = sum(r.cost_usd for r in wo) / len(wo)
            avg_w_c = sum(r.cost_usd for r in w) / len(w)
            avg_wo_turns = sum(r.num_turns for r in wo) / len(wo)
            avg_w_turns = sum(r.num_turns for r in w) / len(w)

            total_wo_t += avg_wo_t
            total_w_t += avg_w_t
            total_wo_c += avg_wo_c
            total_w_c += avg_w_c

            speed_pct = ((avg_wo_t - avg_w_t) / avg_wo_t * 100) if avg_wo_t > 0 else 0
            cost_pct = ((avg_wo_c - avg_w_c) / avg_wo_c * 100) if avg_wo_c > 0 else 0

            speed_str = f"**{speed_pct:+.0f}%**" if abs(speed_pct) > 15 else f"{speed_pct:+.0f}%"
            cost_str = f"**{cost_pct:+.0f}%**" if abs(cost_pct) > 15 else f"{cost_pct:+.0f}%"

            f.write(
                f"| {i+1} | {qtype} | {project} "
                f"| {avg_wo_t:.1f}s | {avg_w_t:.1f}s | {speed_str} "
                f"| ${avg_wo_c:.4f} | ${avg_w_c:.4f} | {cost_str} "
                f"| {avg_wo_turns:.0f} | {avg_w_turns:.0f} |\n"
            )

        f.write(f"\n## Totals\n\n")
        f.write(f"| Metric | Without | With | Delta |\n")
        f.write(f"|--------|---------|------|-------|\n")
        speed_total = ((total_wo_t - total_w_t) / total_wo_t * 100) if total_wo_t > 0 else 0
        cost_total = ((total_wo_c - total_w_c) / total_wo_c * 100) if total_wo_c > 0 else 0
        f.write(f"| Time | {total_wo_t:.1f}s | {total_w_t:.1f}s | {speed_total:+.0f}% |\n")
        f.write(f"| Cost | ${total_wo_c:.4f} | ${total_w_c:.4f} | {cost_total:+.0f}% |\n\n")

        # By question type
        f.write("## By Question Category\n\n")
        f.write("| Category | Avg Speed Delta | Avg Cost Delta |\n")
        f.write("|----------|----------------|----------------|\n")
        categories = {}
        for i, (project, question, qtype) in enumerate(TESTS):
            wo = [r for r in results if r.question == question and r.variant == "without_hint"]
            w = [r for r in results if r.question == question and r.variant == "with_hint"]
            avg_wo_t = sum(r.time_seconds for r in wo) / len(wo)
            avg_w_t = sum(r.time_seconds for r in w) / len(w)
            avg_wo_c = sum(r.cost_usd for r in wo) / len(wo)
            avg_w_c = sum(r.cost_usd for r in w) / len(w)

            cat = qtype.split("_")[0]  # onboarding, status, module, feature, cross, scoping, architecture
            if cat not in categories:
                categories[cat] = {"speed": [], "cost": []}
            if avg_wo_t > 0:
                categories[cat]["speed"].append((avg_wo_t - avg_w_t) / avg_wo_t * 100)
            if avg_wo_c > 0:
                categories[cat]["cost"].append((avg_wo_c - avg_w_c) / avg_wo_c * 100)

        for cat, vals in sorted(categories.items()):
            avg_speed = sum(vals["speed"]) / len(vals["speed"]) if vals["speed"] else 0
            avg_cost = sum(vals["cost"]) / len(vals["cost"]) if vals["cost"] else 0
            f.write(f"| {cat} | {avg_speed:+.0f}% | {avg_cost:+.0f}% |\n")

        # Detailed outputs
        f.write("\n## Detailed Outputs\n\n")
        for i, (project, question, qtype) in enumerate(TESTS):
            f.write(f"### Q{i+1}: {question}\n")
            f.write(f"**Project:** {project} | **Type:** {qtype}\n\n")

            for run_num in range(1, RUNS_PER_QUESTION + 1):
                wo = [r for r in results if r.question == question
                      and r.variant == "without_hint" and r.run == run_num]
                w = [r for r in results if r.question == question
                     and r.variant == "with_hint" and r.run == run_num]
                if wo:
                    r = wo[0]
                    f.write(f"#### Run {run_num} WITHOUT ({r.time_seconds}s, {r.num_turns} turns, ${r.cost_usd:.4f})\n")
                    f.write(f"```\n{r.output[:2000]}\n```\n\n")
                if w:
                    r = w[0]
                    f.write(f"#### Run {run_num} WITH ({r.time_seconds}s, {r.num_turns} turns, ${r.cost_usd:.4f})\n")
                    f.write(f"```\n{r.output[:2000]}\n```\n\n")
            f.write("---\n\n")

    print(f"\nResults: {raw_path}")
    print(f"Report:  {report_path}")

    # Print summary
    print("\n=== SUMMARY ===")
    wo_all = [r for r in results if r.variant == "without_hint"]
    w_all = [r for r in results if r.variant == "with_hint"]
    t_wo = sum(r.time_seconds for r in wo_all) / RUNS_PER_QUESTION
    t_w = sum(r.time_seconds for r in w_all) / RUNS_PER_QUESTION
    c_wo = sum(r.cost_usd for r in wo_all) / RUNS_PER_QUESTION
    c_w = sum(r.cost_usd for r in w_all) / RUNS_PER_QUESTION
    turns_wo = sum(r.num_turns for r in wo_all) / len(wo_all)
    turns_w = sum(r.num_turns for r in w_all) / len(w_all)
    print(f"Time:  without={t_wo:.1f}s  with={t_w:.1f}s  ({(t_wo-t_w)/t_wo*100:+.0f}%)")
    print(f"Cost:  without=${c_wo:.4f}  with=${c_w:.4f}  ({(c_wo-c_w)/c_wo*100:+.0f}%)")
    print(f"Turns: without={turns_wo:.1f}  with={turns_w:.1f}")


if __name__ == "__main__":
    main()
