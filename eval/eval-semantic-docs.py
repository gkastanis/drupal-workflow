"""Eval: measure impact of semantic docs on AI agent performance.

Uses git branches to create a clean comparison:
  A) default branch      — no docs/semantic/ (raw codebase)
  B) add-semantic-docs   — docs/semantic/ present (structural + tech specs)
  C) add-semantic-docs   — docs present + explicit prompt guidance

For each project, the script:
  1. Detects the default branch (main/master/develop)
  2. Checks out default → runs all questions (baseline)
  3. Checks out add-semantic-docs → runs without hint (organic discovery)
  4. Checks out add-semantic-docs → runs with hint (guided)
  5. Restores original branch

Setup (run once per project before eval):
  cd /path/to/project
  git checkout -b add-semantic-docs
  # run /drupal-bootstrap && /drupal-semantic init
  git add docs/semantic/ && git commit -m "feat: add semantic docs"
"""

import json
import os
import random
import shutil
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

# The branch that has docs/semantic/
SEMANTIC_BRANCH = "add-semantic-docs"

SYSTEM_APPEND = (
    "You are read-only. Do NOT modify any files. Do NOT access or display tokens, "
    "passwords, or secrets from .env or config files. Be concise — your output goes "
    "into a Slack message. Use Slack mrkdwn formatting. If asked to make changes, "
    "explain what should be changed and where."
)

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

# Variant definitions: (name, branch_key, hint)
# branch_key "default" = auto-detected default branch, "semantic" = SEMANTIC_BRANCH
VARIANTS = [
    ("baseline",  "default",  False),  # A: default branch, no docs
    ("with_docs", "semantic", False),  # B: semantic branch, no hint
    ("with_hint", "semantic", True),   # C: semantic branch + hint
]

# --- Test cases ---
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
    variant: str
    branch: str = ""
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


def clean_env() -> dict:
    env = {**os.environ}
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    # Per-model cache disable avoids the 401 bug from DISABLE_PROMPT_CACHING (issue #8632).
    # Combined with randomized variant order, this eliminates cache bias between variants.
    env["DISABLE_PROMPT_CACHING_SONNET"] = "1"
    return env


def git_run(project_dir: str, *args, timeout: int = 30) -> str:
    """Run a git command and return stdout. Raises on non-zero exit."""
    result = subprocess.run(
        ["git"] + list(args),
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, ["git"] + list(args),
            result.stdout, result.stderr,
        )
    return result.stdout.strip()


def git_checkout(project_dir: str, branch: str) -> bool:
    """Checkout a branch. Returns True on success."""
    try:
        git_run(project_dir, "checkout", branch)
        current = git_run(project_dir, "branch", "--show-current")
        if current != branch:
            state = current if current else "detached HEAD"
            print(f"  WARNING: expected branch {branch}, got {state}")
            return False
        return True
    except Exception as e:
        print(f"  ERROR checking out {branch}: {e}")
        return False


def detect_default_branch(project_dir: str) -> str:
    """Detect the default branch (main, master, or develop)."""
    for candidate in ["main", "master", "develop"]:
        if has_branch(project_dir, candidate):
            return candidate
    # Fallback: whatever HEAD points to on origin
    try:
        ref = git_run(project_dir, "symbolic-ref", "refs/remotes/origin/HEAD")
        return ref.split("/")[-1]
    except Exception:
        return "main"


def has_branch(project_dir: str, branch: str) -> bool:
    """Check if a branch exists locally."""
    try:
        return bool(git_run(project_dir, "branch", "--list", branch))
    except subprocess.CalledProcessError:
        return False


def hide_semantic_docs(project_dir: str) -> bool:
    """Temporarily rename docs/semantic/ so the baseline agent can't find it.
    Returns True if docs were hidden (and need restoring).
    Cleans up stale hidden dirs from prior crashed runs."""
    semantic = os.path.join(project_dir, "docs", "semantic")
    hidden = os.path.join(project_dir, "docs", ".semantic-hidden-by-eval")
    # Clean up stale hidden dir from a previous crash
    if os.path.isdir(hidden):
        shutil.rmtree(hidden)
    if os.path.isdir(semantic):
        os.rename(semantic, hidden)
        return True
    return False


def restore_semantic_docs(project_dir: str) -> None:
    """Restore docs/semantic/ after baseline run."""
    semantic = os.path.join(project_dir, "docs", "semantic")
    hidden = os.path.join(project_dir, "docs", ".semantic-hidden-by-eval")
    if os.path.isdir(hidden):
        # If semantic was recreated somehow, remove it first
        if os.path.isdir(semantic):
            shutil.rmtree(semantic)
        os.rename(hidden, semantic)


def run_once(project: str, question: str, question_type: str,
             variant_name: str, branch: str, with_hint: bool,
             run_num: int) -> Result:
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
        question_type=question_type, variant=variant_name,
        branch=branch, run=run_num,
    )

    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            env=clean_env(),
        )
        try:
            stdout, stderr = proc.communicate(input=prompt, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()  # Reap the killed process.
            result.time_seconds = TIMEOUT
            result.error = "TIMEOUT"
            return result

        result.time_seconds = round(time.monotonic() - start, 1)
        raw = stdout.strip()

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

        if proc.returncode != 0 and not result.output:
            result.error = (stderr or stdout or "non-zero exit")[:500]
        elif not result.output and stderr:
            result.error = stderr[:500]
        result.output_length = len(result.output)
    except Exception as e:
        result.time_seconds = round(time.monotonic() - start, 1)
        result.error = str(e)

    return result


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    results = []

    # Collect unique projects and detect branches
    projects = list(dict.fromkeys(p for p, _, _ in TESTS))

    print("=== PRE-CHECK ===\n")
    skip_projects = set()
    project_info = {}  # project -> {default_branch, original_branch}

    for project in projects:
        project_dir = os.path.join(REPOS_DIR, project)
        if not os.path.isdir(project_dir):
            print(f"  SKIP {project}: directory not found")
            skip_projects.add(project)
            continue

        original = git_run(project_dir, "branch", "--show-current")
        default = detect_default_branch(project_dir)
        has_sem = has_branch(project_dir, SEMANTIC_BRANCH)

        project_info[project] = {
            "original_branch": original,
            "default_branch": default,
        }

        if has_sem:
            print(f"  OK   {project}: default={default}, {SEMANTIC_BRANCH}=OK (on: {original})")
        else:
            print(f"  SKIP {project}: {SEMANTIC_BRANCH} branch missing")
            skip_projects.add(project)

    if skip_projects:
        print(f"\nMissing {SEMANTIC_BRANCH} branch for: {', '.join(skip_projects)}")
        print(f"Create with: git checkout -b {SEMANTIC_BRANCH} && "
              f"/drupal-bootstrap && /drupal-semantic init && "
              f"git add docs/semantic/ && git commit\n")

    active_tests = [(p, q, t) for p, q, t in TESTS if p not in skip_projects]
    if not active_tests:
        print("No projects available. Exiting.")
        return

    total_runs = len(active_tests) * len(VARIANTS) * RUNS_PER_QUESTION
    run_idx = 0

    print(f"\n=== RUNNING: {len(active_tests)} questions x {len(VARIANTS)} variants x {RUNS_PER_QUESTION} runs = {total_runs} total ===\n")

    for run_num in range(1, RUNS_PER_QUESTION + 1):
        print(f"--- RUN {run_num}/{RUNS_PER_QUESTION} ---\n")

        for i, (project, question, qtype) in enumerate(active_tests):
            project_dir = os.path.join(REPOS_DIR, project)
            info = project_info[project]
            short_q = question[:50]

            # Randomize variant order to eliminate prompt-cache bias
            shuffled_variants = list(VARIANTS)
            random.shuffle(shuffled_variants)

            for variant_name, branch_key, with_hint in shuffled_variants:
                run_idx += 1

                # Resolve branch
                if branch_key == "default":
                    branch = info["default_branch"]
                else:
                    branch = SEMANTIC_BRANCH

                if not git_checkout(project_dir, branch):
                    print(f"[{run_idx}/{total_runs}] SKIP {project} — {variant_name} — checkout failed")
                    continue

                # Hide docs/semantic/ during baseline so agent can't find them
                hidden = False
                if variant_name == "baseline":
                    hidden = hide_semantic_docs(project_dir)
                    if hidden:
                        print(f"  (hiding docs/semantic/ for clean baseline)")

                label = f"{variant_name:10s}"
                print(f"[{run_idx}/{total_runs}] {project} — {label} ({branch}) — {short_q}...")

                try:
                    r = run_once(
                        project, question, qtype,
                        variant_name, branch, with_hint, run_num,
                    )
                    results.append(r)

                    print(f"  {r.time_seconds}s | {r.output_length} chars | "
                          f"{r.num_turns} turns | ${r.cost_usd:.4f}"
                          f"{' | ERROR: ' + r.error[:60] if r.error else ''}")
                finally:
                    # Always restore docs even if run fails
                    if hidden:
                        restore_semantic_docs(project_dir)

            # Deltas
            vfq = [r for r in results if r.question == question and r.run == run_num]
            base = next((r for r in vfq if r.variant == "baseline"), None)
            docs = next((r for r in vfq if r.variant == "with_docs"), None)
            hint = next((r for r in vfq if r.variant == "with_hint"), None)

            if base and docs:
                dt = base.time_seconds - docs.time_seconds
                dc = base.cost_usd - docs.cost_usd
                print(f"  baseline→docs: {dt:+.1f}s | ${dc:+.4f}")
            if base and hint:
                dt = base.time_seconds - hint.time_seconds
                dc = base.cost_usd - hint.cost_usd
                print(f"  baseline→hint: {dt:+.1f}s | ${dc:+.4f}")
            print()

    # Restore original branches
    print("=== RESTORING BRANCHES ===")
    for project in projects:
        if project in skip_projects:
            continue
        project_dir = os.path.join(REPOS_DIR, project)
        orig = project_info[project]["original_branch"]
        git_checkout(project_dir, orig)
        print(f"  {project} → {orig}")

    # Save raw results
    raw_path = RESULTS_DIR / f"results-{timestamp}.json"
    with open(raw_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    # Generate report
    report_path = RESULTS_DIR / f"report-{timestamp}.md"
    with open(report_path, "w") as f:
        f.write("# Semantic Docs Eval Report (v3 — branch-based)\n\n")
        f.write(f"**Date:** {timestamp}\n")
        f.write(f"**Model:** {MODEL}\n")
        f.write(f"**Tests:** {len(active_tests)} questions x {len(VARIANTS)} variants x {RUNS_PER_QUESTION} runs\n")
        f.write(f"**Baseline:** default branch (no docs/semantic/)\n")
        f.write(f"**Semantic:** `{SEMANTIC_BRANCH}` branch (with docs/semantic/)\n\n")

        f.write("## Variants\n\n")
        f.write("| Variant | Branch | Hint | What it tests |\n")
        f.write("|---------|--------|------|---------------|\n")
        f.write(f"| baseline | default (main/master/develop) | no | Raw codebase exploration |\n")
        f.write(f"| with_docs | `{SEMANTIC_BRANCH}` | no | Agent discovers docs organically |\n")
        f.write(f"| with_hint | `{SEMANTIC_BRANCH}` | yes | Docs + explicit guidance |\n\n")

        # Per-question summary
        f.write("## Per-Question Results (averaged across runs)\n\n")
        f.write("| # | Type | Project | Baseline | +Docs | +Hint | Docs Speed | Hint Speed | Docs Cost | Hint Cost |\n")
        f.write("|---|------|---------|----------|-------|-------|-----------|-----------|----------|----------|\n")

        def fmt_pct(v):
            return f"**{v:+.0f}%**" if abs(v) > 15 else f"{v:+.0f}%"

        totals = {v: {"time": 0, "cost": 0} for v, _, _ in VARIANTS}

        for i, (project, question, qtype) in enumerate(active_tests):
            row = {}
            for vname, _, _ in VARIANTS:
                vr = [r for r in results
                      if r.project == project and r.question == question and r.variant == vname]
                if vr:
                    row[vname] = {
                        "time": sum(r.time_seconds for r in vr) / len(vr),
                        "cost": sum(r.cost_usd for r in vr) / len(vr),
                        "turns": sum(r.num_turns for r in vr) / len(vr),
                    }
                    totals[vname]["time"] += row[vname]["time"]
                    totals[vname]["cost"] += row[vname]["cost"]

            bt = row.get("baseline", {}).get("time", 0)
            dt = row.get("with_docs", {}).get("time", 0)
            ht = row.get("with_hint", {}).get("time", 0)
            bc = row.get("baseline", {}).get("cost", 0)
            dc = row.get("with_docs", {}).get("cost", 0)
            hc = row.get("with_hint", {}).get("cost", 0)

            ds = ((bt - dt) / bt * 100) if bt > 0 else 0
            hs = ((bt - ht) / bt * 100) if bt > 0 else 0
            dcs = ((bc - dc) / bc * 100) if bc > 0 else 0
            hcs = ((bc - hc) / bc * 100) if bc > 0 else 0

            f.write(
                f"| {i+1} | {qtype} | {project} "
                f"| {bt:.1f}s | {dt:.1f}s | {ht:.1f}s "
                f"| {fmt_pct(ds)} | {fmt_pct(hs)} | {fmt_pct(dcs)} | {fmt_pct(hcs)} |\n"
            )

        # Totals
        f.write(f"\n## Totals\n\n")
        f.write(f"| Metric | Baseline | +Docs | +Hint | Docs Delta | Hint Delta |\n")
        f.write(f"|--------|----------|-------|-------|-----------|------------|\n")

        bt = totals["baseline"]["time"]
        dt = totals["with_docs"]["time"]
        ht = totals["with_hint"]["time"]
        bc = totals["baseline"]["cost"]
        dc = totals["with_docs"]["cost"]
        hc = totals["with_hint"]["cost"]

        f.write(f"| Time | {bt:.1f}s | {dt:.1f}s | {ht:.1f}s | {(bt-dt)/bt*100 if bt else 0:+.0f}% | {(bt-ht)/bt*100 if bt else 0:+.0f}% |\n")
        f.write(f"| Cost | ${bc:.4f} | ${dc:.4f} | ${hc:.4f} | {(bc-dc)/bc*100 if bc else 0:+.0f}% | {(bc-hc)/bc*100 if bc else 0:+.0f}% |\n\n")

        # By category
        f.write("## By Question Category\n\n")
        f.write("| Category | Docs Speed | Hint Speed | Docs Cost | Hint Cost |\n")
        f.write("|----------|-----------|-----------|----------|----------|\n")

        categories = {}
        for project, question, qtype in active_tests:
            cat = qtype.split("_")[0]
            if cat not in categories:
                categories[cat] = {"ds": [], "hs": [], "dc": [], "hc": []}

            base_r = [r for r in results if r.project == project and r.question == question and r.variant == "baseline"]
            docs_r = [r for r in results if r.project == project and r.question == question and r.variant == "with_docs"]
            hint_r = [r for r in results if r.project == project and r.question == question and r.variant == "with_hint"]

            if base_r:
                bt = sum(r.time_seconds for r in base_r) / len(base_r)
                bc = sum(r.cost_usd for r in base_r) / len(base_r)
                if docs_r and bt > 0:
                    dt = sum(r.time_seconds for r in docs_r) / len(docs_r)
                    dc = sum(r.cost_usd for r in docs_r) / len(docs_r)
                    categories[cat]["ds"].append((bt - dt) / bt * 100)
                    if bc > 0:
                        categories[cat]["dc"].append((bc - dc) / bc * 100)
                if hint_r and bt > 0:
                    ht = sum(r.time_seconds for r in hint_r) / len(hint_r)
                    hc = sum(r.cost_usd for r in hint_r) / len(hint_r)
                    categories[cat]["hs"].append((bt - ht) / bt * 100)
                    if bc > 0:
                        categories[cat]["hc"].append((bc - hc) / bc * 100)

        for cat, v in sorted(categories.items()):
            avg = lambda lst: sum(lst) / len(lst) if lst else 0
            f.write(f"| {cat} | {avg(v['ds']):+.0f}% | {avg(v['hs']):+.0f}% | {avg(v['dc']):+.0f}% | {avg(v['hc']):+.0f}% |\n")

        # Key insight
        f.write("\n## Key Question: Does the agent find docs without a hint?\n\n")
        f.write("Compare `with_docs` vs `with_hint` — if similar, docs are discoverable organically.\n")
        f.write("If `with_hint` is significantly better, the hint adds real value beyond just having docs.\n\n")

        t_bt = totals["baseline"]["time"]
        t_dt = totals["with_docs"]["time"]
        t_ht = totals["with_hint"]["time"]
        c_bt = totals["baseline"]["cost"]
        c_dt = totals["with_docs"]["cost"]
        c_ht = totals["with_hint"]["cost"]
        if t_bt > 0:
            f.write(f"- Docs vs baseline: {(t_bt-t_dt)/t_bt*100:+.0f}% speed, {(c_bt-c_dt)/c_bt*100 if c_bt else 0:+.0f}% cost\n")
            f.write(f"- Hint vs baseline: {(t_bt-t_ht)/t_bt*100:+.0f}% speed, {(c_bt-c_ht)/c_bt*100 if c_bt else 0:+.0f}% cost\n")
        if t_dt > 0:
            f.write(f"- Hint vs docs-only: {(t_dt-t_ht)/t_dt*100:+.0f}% additional speedup from hint\n")

        # Detailed outputs
        f.write("\n## Detailed Outputs\n\n")
        for i, (project, question, qtype) in enumerate(active_tests):
            f.write(f"### Q{i+1}: {question}\n")
            f.write(f"**Project:** {project} | **Type:** {qtype}\n\n")

            for run_num in range(1, RUNS_PER_QUESTION + 1):
                f.write(f"#### Run {run_num}\n\n")
                for vname, _, _ in VARIANTS:
                    vr = [r for r in results if r.project == project
                          and r.question == question
                          and r.variant == vname and r.run == run_num]
                    if vr:
                        r = vr[0]
                        f.write(f"**{vname}** ({r.time_seconds}s, {r.num_turns} turns, ${r.cost_usd:.4f}, branch: {r.branch})\n")
                        f.write(f"```\n{r.output[:1500]}\n```\n\n")
            f.write("---\n\n")

    print(f"\nResults: {raw_path}")
    print(f"Report:  {report_path}")

    # Summary — use totals from report (averaged per-question sums, not raw sums)
    print("\n=== SUMMARY ===")
    for vname, _, _ in VARIANTS:
        vr = [r for r in results if r.variant == vname]
        if not vr:
            continue
        avg_t = sum(r.time_seconds for r in vr) / len(vr)
        avg_c = sum(r.cost_usd for r in vr) / len(vr)
        avg_turns = sum(r.num_turns for r in vr) / len(vr)
        print(f"  {vname:10s}: avg {avg_t:.1f}s/{avg_turns:.1f} turns/${avg_c:.4f} per question")

    s_bt = totals["baseline"]["time"]
    s_dt = totals["with_docs"]["time"]
    s_ht = totals["with_hint"]["time"]
    if s_bt > 0:
        print(f"\n  Docs speedup:  {(s_bt-s_dt)/s_bt*100:+.0f}%")
        print(f"  Hint speedup:  {(s_bt-s_ht)/s_bt*100:+.0f}%")
    if s_dt > 0:
        print(f"  Hint vs docs:  {(s_dt-s_ht)/s_dt*100:+.0f}% (additional value of hint)")


if __name__ == "__main__":
    main()
