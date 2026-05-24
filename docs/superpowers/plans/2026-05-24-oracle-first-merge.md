# Oracle-First Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Oracle the primary runner/supervisor for long ChatGPT browser flows while keeping `ai_research_browser` as the local safety gate for real browser profile, login, account, plan, model, feature, screenshot, quota, and rate-limit checks.

**Architecture:** The merge boundary is `local real-session preflight -> local provider guard bundle -> Oracle runner/supervisor -> Oracle harvest/live output -> local normalized status`. Existing local CDP/Agent-Browser code remains the safe fallback and provider-specific UI guard layer; duplicated long-run/retry/reattach/output-harvest behavior moves behind an Oracle adapter.

**Tech Stack:** Python stdlib CLI, `unittest`, local `npx -y @steipete/oracle@0.13.0`, GitHub Actions public-safety workflow, existing `ai-research-browser` skill layout.

---

## Findings From Superagents

- Explorer A found duplicated local logic in `agent_browser_live_workflow_run`, `agent_browser_profile_workflow_run`, `build_ai_workflow_plan`, and long-run polling/output extraction. Oracle can own long-run status, reattach, session render, and harvest after local guards pass.
- Explorer B confirmed Oracle 0.13.0 supports the key primitives we should use: `--browser-attach-running`, `--remote-chrome`, `--browser-model-strategy`, `--browser-research`, `status --browser-tabs`, `session --render`, `session --harvest`, `session --live`, `--write-output`, `--browser-attachments`, `--browser-bundle-format`, `--perf-trace`, `--route`, and `--preflight`.
- Explorer C found the main gap: there is no mocked Oracle-first success-path test proving `workflow-run --oracle-mode assist|runner` can pass local guards, avoid real submit unless requested, and normalize Oracle output.

## Files

- Modify: `skills/software-development/ai-research-browser/scripts/ai_research_browser.py`
- Modify: `skills/software-development/ai-research-browser/tests/test_ai_research_browser.py`
- Modify: `skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py`
- Modify: `skills/software-development/oracle-ai-research-e2e/tests/test_oracle_ai_research_e2e_check.py`
- Modify: `.github/workflows/public-safety.yml`
- Modify: `skills/software-development/oracle-ai-research-e2e/SKILL.md`
- Modify: `README.md`

---

### Task 1: Add A Real Oracle Adapter Boundary

**Files:**
- Modify: `skills/software-development/ai-research-browser/scripts/ai_research_browser.py`
- Test: `skills/software-development/ai-research-browser/tests/test_ai_research_browser.py`

- [ ] **Step 1: Write failing unit tests for canonical Oracle commands**

Add tests near the existing Oracle tests:

```python
def test_build_oracle_runner_command_uses_oracle_lifecycle_flags(self):
    module = load_module()

    command = module.build_oracle_runner_command(
        prompt="Investigate safe browser automation",
        provider="chatgpt",
        mode="agent",
        cdp_port=9223,
        output_path=Path("/tmp/oracle-agent-output.md"),
        session_slug="chatgpt-agent-debug",
        files=["README.md"],
        artifact_privacy="redacted",
    )

    self.assertEqual(command[:3], ["npx", "-y", "@steipete/oracle@0.13.0"])
    self.assertIn("--engine", command)
    self.assertIn("browser", command)
    self.assertIn("--browser-attach-running", command)
    self.assertIn("--remote-chrome", command)
    self.assertIn("127.0.0.1:9223", command)
    self.assertIn("--browser-model-strategy", command)
    self.assertIn("current", command)
    self.assertIn("--browser-research", command)
    self.assertIn("deep", command)
    self.assertIn("--slug", command)
    self.assertIn("chatgpt-agent-debug", command)
    self.assertIn("--write-output", command)
    self.assertIn("/tmp/oracle-agent-output.md", command)
    self.assertIn("--file", command)
    self.assertIn("README.md", command)
    self.assertIn("<redacted-prompt>", command)
    self.assertNotIn("Investigate safe browser automation", command)

def test_build_oracle_harvest_commands_uses_status_session_live_and_harvest(self):
    module = load_module()

    commands = module.build_oracle_harvest_commands(
        session_id="oracle-session-123",
        output_path=Path("/tmp/oracle-output.md"),
        hours=72,
    )

    self.assertEqual(commands["status"], ["npx", "-y", "@steipete/oracle@0.13.0", "status", "--hours", "72", "--browser-tabs"])
    self.assertEqual(commands["render"], ["npx", "-y", "@steipete/oracle@0.13.0", "session", "oracle-session-123", "--render"])
    self.assertEqual(commands["harvest"], ["npx", "-y", "@steipete/oracle@0.13.0", "session", "oracle-session-123", "--harvest", "--write-output", "/tmp/oracle-output.md"])
    self.assertEqual(commands["live"], ["npx", "-y", "@steipete/oracle@0.13.0", "session", "oracle-session-123", "--live", "--write-output", "/tmp/oracle-output.md"])
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_ai_research_browser.py' -k oracle
```

Expected: fails because `build_oracle_runner_command` and `build_oracle_harvest_commands` do not exist.

- [ ] **Step 3: Add the Oracle adapter functions**

Add below `build_oracle_plan`:

```python
ORACLE_PACKAGE = "@steipete/oracle@0.13.0"


def oracle_base_command() -> list[str]:
    return ["npx", "-y", ORACLE_PACKAGE]


def oracle_safe_model(provider: str, mode: str, requested_model: str = "") -> str:
    provider_id = normalize_provider_name(provider)
    mode_id = slug(mode or "chat")
    if requested_model:
        return requested_model
    if provider_id == "chatgpt":
        return "GPT-5.5 Thinking"
    if provider_id == "gemini":
        return "gemini-3-pro"
    return ""


def build_oracle_runner_command(
    *,
    prompt: str,
    provider: str,
    mode: str,
    cdp_port: int,
    output_path: Path,
    session_slug: str,
    files: list[str] | None = None,
    artifact_privacy: str = "redacted",
    requested_model: str = "",
    browser_attachment_timeout: int | None = None,
) -> list[str]:
    provider_id = normalize_provider_name(provider)
    mode_id = slug(mode or "chat")
    command = [
        *oracle_base_command(),
        "--engine",
        "browser",
        "--browser-attach-running",
        "--remote-chrome",
        f"127.0.0.1:{int(cdp_port)}",
        "--browser-model-strategy",
        "current",
        "--model",
        oracle_safe_model(provider_id, mode_id, requested_model),
        "--slug",
        session_slug,
        "--write-output",
        str(output_path),
    ]
    if provider_id == "chatgpt" and mode_id in {"agent", "deep-research"}:
        command.extend(["--browser-research", "deep"])
    if browser_attachment_timeout:
        command.extend(["--browser-attachment-timeout", str(int(browser_attachment_timeout))])
    command.extend(["-p", prompt if artifact_privacy == "full" else "<redacted-prompt>"])
    for file_pattern in files or []:
        command.extend(["--file", file_pattern])
    return command


def build_oracle_harvest_commands(*, session_id: str, output_path: Path, hours: int = 72) -> dict[str, list[str]]:
    base = oracle_base_command()
    hours_text = str(int(hours))
    return {
        "status": [*base, "status", "--hours", hours_text, "--browser-tabs"],
        "render": [*base, "session", session_id, "--render"],
        "harvest": [*base, "session", session_id, "--harvest", "--write-output", str(output_path)],
        "live": [*base, "session", session_id, "--live", "--write-output", str(output_path)],
    }
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_ai_research_browser.py' -k oracle
```

Expected: Oracle tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/software-development/ai-research-browser/scripts/ai_research_browser.py skills/software-development/ai-research-browser/tests/test_ai_research_browser.py
git commit -m "feat: add Oracle runner adapter boundary"
```

---

### Task 2: Move Runner Mode From Payload-Only To Oracle-First Execution Plan

**Files:**
- Modify: `skills/software-development/ai-research-browser/scripts/ai_research_browser.py`
- Test: `skills/software-development/ai-research-browser/tests/test_ai_research_browser.py`

- [ ] **Step 1: Write failing tests for guarded Oracle runner success and blocked paths**

Add tests near `test_workflow_run_oracle_runner_is_blocked_by_local_guards`:

```python
def test_workflow_run_oracle_runner_success_requires_local_guarded_opened_payload(self):
    module = load_module()
    browser = {"id": "brave", "name": "Brave Browser", "default_port": 9223, "user_data_dir": "/tmp/brave"}
    profile = {"name": "Work", "directory": "Default", "path": "/tmp/brave/Default"}
    opened_payload = {
        "status": "opened",
        "provider": "chatgpt",
        "mode": "chat",
        "target_id": "target-1",
        "pre_submit_guard": {"allowed": True, "errors": []},
        "account_baseline": {"status": "ready", "eligible": True},
        "screenshot": "/tmp/pre-submit.png",
    }

    with mock.patch.object(module, "resolve_workflow_browser_profile", return_value=(browser, profile)), \
         mock.patch.object(module, "workflow_prompt_from_args", return_value="safe debug prompt"), \
         mock.patch.object(module, "paid_quota_cli_guard", return_value={"allowed": True, "errors": []}), \
         mock.patch.object(module, "build_real_session_preflight", return_value={"can_attach": True, "blockers": [], "cdp_owner_verification": {"ok": True}}), \
         mock.patch.object(module, "agent_browser_live_workflow_run", return_value=opened_payload), \
         mock.patch.object(module, "run_oracle_runner", return_value={"status": "started", "session_id": "oracle-1", "output_path": "/tmp/oracle.md"}):
        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main([
                "workflow-run",
                "--browser", "brave",
                "--profile", "work",
                "--provider", "chatgpt",
                "--mode", "agent",
                "--prompt", "safe debug prompt",
                "--oracle-mode", "runner",
                "--allow-paid-quota-use",
            ])

    payload = json.loads(out.getvalue())
    self.assertEqual(exit_code, 0)
    self.assertEqual(payload["oracle"]["runner_status"], "started")
    self.assertEqual(payload["oracle"]["session_id"], "oracle-1")

def test_workflow_run_oracle_runner_paid_submit_without_allow_blocks_before_oracle(self):
    module = load_module()

    with mock.patch.object(module, "run_oracle_runner") as run_oracle:
        out = StringIO()
        with redirect_stdout(out):
            exit_code = module.main([
                "workflow-run",
                "--browser", "brave",
                "--profile", "work",
                "--provider", "chatgpt",
                "--mode", "agent",
                "--prompt", "safe debug prompt",
                "--oracle-mode", "runner",
            ])

    payload = json.loads(out.getvalue())
    self.assertEqual(exit_code, 1)
    self.assertEqual(payload["status"], "blocked")
    run_oracle.assert_not_called()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_ai_research_browser.py' -k 'oracle_runner'
```

Expected: runner success test fails because `run_oracle_runner` is not implemented/called.

- [ ] **Step 3: Implement dry-run-safe `run_oracle_runner`**

Add below the adapter functions:

```python
def run_oracle_runner(
    *,
    prompt: str,
    provider: str,
    mode: str,
    cdp_port: int,
    run_dir: Path,
    artifact_privacy: str = "redacted",
    files: list[str] | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path = run_dir / "oracle-output.md"
    session_slug = f"ai-research-{normalize_provider_name(provider)}-{slug(mode or 'chat')}"
    command = build_oracle_runner_command(
        prompt=prompt,
        provider=provider,
        mode=mode,
        cdp_port=cdp_port,
        output_path=output_path,
        session_slug=session_slug,
        files=files,
        artifact_privacy=artifact_privacy,
    )
    payload = {
        "runner_status": "planned",
        "session_id": session_slug,
        "command": redact_command(command, privacy=artifact_privacy),
        "output_path": str(output_path),
        "execute": bool(execute),
    }
    if not execute:
        return payload
    result = subprocess.run(command, text=True, capture_output=True, timeout=7200)
    payload["returncode"] = result.returncode
    payload["stdout"] = "" if artifact_privacy != "full" else result.stdout[-4000:]
    payload["stderr"] = "" if artifact_privacy != "full" else result.stderr[-4000:]
    payload["runner_status"] = "started" if result.returncode == 0 else "blocked"
    return payload
```

- [ ] **Step 4: Wire runner mode after successful local guards**

In `cmd_workflow_run`, replace the current runner-only blocker block with this logic:

```python
        if oracle_mode == "runner":
            if payload.get("status") in {"opened", "submitted", "started", "verified", "captured"}:
                run_dir = Path(payload.get("status_json", Path(args.artifact_root).expanduser() / "oracle-status.json")).expanduser().parent
                runner_payload = run_oracle_runner(
                    prompt=prompt,
                    provider=args.provider,
                    mode=args.mode,
                    cdp_port=cdp_port,
                    run_dir=run_dir,
                    artifact_privacy=artifact_privacy,
                    execute=bool(args.submit),
                )
                oracle_payload.update(runner_payload)
            else:
                oracle_payload["runner_status"] = "blocked-by-local-guards"
                oracle_payload["runner_blocker"] = "Oracle runner requires successful local login/account/plan/feature/screenshot guards first."
```

Keep `execute=bool(args.submit)` so no real Oracle provider run happens on dry preflights.

- [ ] **Step 5: Run tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_ai_research_browser.py' -k 'oracle_runner or oracle_plan'
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add skills/software-development/ai-research-browser/scripts/ai_research_browser.py skills/software-development/ai-research-browser/tests/test_ai_research_browser.py
git commit -m "feat: route guarded Oracle runner through adapter"
```

---

### Task 3: Replace Local Long-Run Harvest For Oracle Mode With Oracle Session Commands

**Files:**
- Modify: `skills/software-development/ai-research-browser/scripts/ai_research_browser.py`
- Test: `skills/software-development/ai-research-browser/tests/test_ai_research_browser.py`

- [ ] **Step 1: Write failing tests for normalized Oracle harvest**

Add:

```python
def test_normalize_oracle_harvest_reads_output_file_and_keeps_session_commands(self):
    module = load_module()
    root = Path(tempfile.mkdtemp())
    output_path = root / "oracle-output.md"
    output_path.write_text("Final Oracle answer", encoding="utf-8")

    payload = module.normalize_oracle_harvest(
        session_id="oracle-1",
        output_path=output_path,
        status_result=subprocess.CompletedProcess(["oracle"], 0, "session ok", ""),
        harvest_result=subprocess.CompletedProcess(["oracle"], 0, "harvest ok", ""),
        artifact_privacy="redacted",
    )

    self.assertEqual(payload["runner_status"], "captured")
    self.assertEqual(payload["output"]["text"], "Final Oracle answer")
    self.assertEqual(payload["output"]["text_length"], len("Final Oracle answer"))
    self.assertIn("commands", payload)
    self.assertIn("harvest", payload["commands"])
    self.assertNotIn("session ok", json.dumps(payload))
```

- [ ] **Step 2: Run test and confirm failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_ai_research_browser.py' -k normalize_oracle_harvest
```

Expected: fails because `normalize_oracle_harvest` is missing.

- [ ] **Step 3: Implement normalization**

Add:

```python
def normalize_oracle_harvest(
    *,
    session_id: str,
    output_path: Path,
    status_result: subprocess.CompletedProcess[str] | None = None,
    harvest_result: subprocess.CompletedProcess[str] | None = None,
    artifact_privacy: str = "redacted",
) -> dict[str, Any]:
    text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    commands = build_oracle_harvest_commands(session_id=session_id, output_path=output_path)
    return {
        "runner_status": "captured" if text.strip() else "started",
        "session_id": session_id,
        "output": {
            "status": "captured" if text.strip() else "pending",
            "text": text,
            "text_length": len(text),
        },
        "commands": {key: redact_command(value, privacy=artifact_privacy) for key, value in commands.items()},
        "status_returncode": None if status_result is None else status_result.returncode,
        "harvest_returncode": None if harvest_result is None else harvest_result.returncode,
    }
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_ai_research_browser.py' -k 'normalize_oracle_harvest or oracle'
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/software-development/ai-research-browser/scripts/ai_research_browser.py skills/software-development/ai-research-browser/tests/test_ai_research_browser.py
git commit -m "feat: normalize Oracle session harvest output"
```

---

### Task 4: Extend Oracle E2E Checker To Prove Oracle-First Matrix Without Provider Submit

**Files:**
- Modify: `skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py`
- Modify: `skills/software-development/oracle-ai-research-e2e/tests/test_oracle_ai_research_e2e_check.py`

- [ ] **Step 1: Write failing checker tests**

Add tests:

```python
def test_quick_main_records_expected_public_safe_steps(self):
    module = load_module()
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return module.StepResult(name=kwargs.get("name", "step"), ok=True, returncode=0, expected_returncodes=[0], command=command, stdout="{}", stderr="")

    with mock.patch.object(module, "run_command", side_effect=fake_run):
        payload = module.run_checks(repo_root=Path("/repo"), quick=True, live=False, provider="chatgpt", mode="thinking")

    names = [step["name"] for step in payload["steps"]]
    self.assertIn("oracle_plan", names)
    self.assertIn("workflow_runner_blocked", names)
    self.assertIn("oracle_e2e_smoke_opt_in_block", names)

def test_checker_provider_matrix_accepts_google_gemini_deep_research(self):
    module = load_module()

    payload = module.build_provider_mode_matrix(["chatgpt:thinking", "chatgpt:agent", "google:deep-research", "gemini:deep-research"])

    self.assertIn(("chatgpt", "thinking"), payload)
    self.assertIn(("chatgpt", "agent"), payload)
    self.assertIn(("gemini", "deep-research"), payload)
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```bash
python3 -m unittest discover -s skills/software-development/oracle-ai-research-e2e/tests -p 'test_*.py'
```

Expected: fails because matrix helper is missing and `run_checks` lacks provider matrix arguments if not already present.

- [ ] **Step 3: Add matrix helper and checker arguments**

Implement:

```python
def build_provider_mode_matrix(items: list[str]) -> list[tuple[str, str]]:
    matrix = []
    for item in items:
        provider, _, mode = item.partition(":")
        provider = provider.strip()
        mode = mode.strip() or "thinking"
        if provider == "google":
            provider = "gemini"
        matrix.append((provider, mode))
    return matrix
```

Extend CLI parser with:

```python
parser.add_argument("--matrix", action="append", default=[], help="Provider:mode pair for public-safe Oracle checker matrix.")
```

When `--matrix` is supplied, run `oracle-plan` and opt-in-block smoke for each pair without setting `AI_RESEARCH_BROWSER_E2E=1`.

- [ ] **Step 4: Run tests**

Run:

```bash
python3 -m unittest discover -s skills/software-development/oracle-ai-research-e2e/tests -p 'test_*.py'
python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py --quick --json
```

Expected: tests pass and checker returns `ok=true`.

- [ ] **Step 5: Commit**

```bash
git add skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py skills/software-development/oracle-ai-research-e2e/tests/test_oracle_ai_research_e2e_check.py
git commit -m "test: expand Oracle E2E checker matrix"
```

---

### Task 5: Update CI To Run The Oracle-First Public-Safe Matrix

**Files:**
- Modify: `.github/workflows/public-safety.yml`

- [ ] **Step 1: Add CI matrix commands**

Change the Oracle checker step to:

```yaml
      - name: Run Oracle AI Research E2E checker
        run: |
          python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py --quick --json
          python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py --quick --json --skip-public-safety --matrix chatgpt:thinking --matrix chatgpt:agent --matrix chatgpt:deep-research --matrix gemini:deep-research
```

- [ ] **Step 2: Run public workflow commands locally**

Run:

```bash
python3 -m unittest discover -s skills/software-development/oracle-ai-research-e2e/tests -p 'test_*.py'
python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py --quick --json
python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py --quick --json --skip-public-safety --matrix chatgpt:thinking --matrix chatgpt:agent --matrix chatgpt:deep-research --matrix gemini:deep-research
scripts/audit-public-safety.sh
```

Expected: all commands pass.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/public-safety.yml
git commit -m "ci: run Oracle-first public-safe matrix"
```

---

### Task 6: Update Skill And README To Document The Merge Boundary

**Files:**
- Modify: `skills/software-development/oracle-ai-research-e2e/SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Document Oracle-first ownership**

Add this section to the skill:

```markdown
## Oracle-First Ownership Boundary

Use `ai_research_browser` for local safety proof:

- real CDP endpoint belongs to the intended browser/profile
- login/account/plan/model/feature/screenshot are visible
- ChatGPT Pro/Extended Pro/GPT-5.5 Pro is blocked for routine tests
- paid quota modes require `--allow-paid-quota-use`
- CAPTCHA, challenge, rate-limit, or account regression blocks before submit

Use Oracle after those guards pass:

- browser attach to the verified CDP endpoint
- long-running ChatGPT Research/Agent supervision
- session lifecycle, duplicate prompt guard, status, reattach
- `session --harvest`, `session --live`, and `session --render`
- browser file attachment delivery for Oracle consults

Do not reimplement Oracle session lifecycle in the local CLI. The local CLI only normalizes Oracle status into `status.json`.
```

- [ ] **Step 2: Document canonical commands**

Add examples:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py \
  workflow-run \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode agent \
  --strategy auto \
  --oracle-mode runner \
  --allow-paid-quota-use \
  --submit \
  --prompt "Debug why Oracle-first reattach is more stable than local polling."

npx -y @steipete/oracle@0.13.0 status --hours 72 --browser-tabs
npx -y @steipete/oracle@0.13.0 session <session-id> --harvest --write-output /tmp/oracle-output.md
```

- [ ] **Step 3: Run docs safety audit**

Run:

```bash
scripts/audit-public-safety.sh
```

Expected: public safety audit passes.

- [ ] **Step 4: Commit**

```bash
git add README.md skills/software-development/oracle-ai-research-e2e/SKILL.md
git commit -m "docs: describe Oracle-first merge boundary"
```

---

### Task 7: Final Verification And PR Update

**Files:**
- No source edits unless verification finds a defect.

- [ ] **Step 1: Run full local verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_ai_research_browser.py'
python3 -m unittest discover -s skills/software-development/oracle-ai-research-e2e/tests -p 'test_*.py'
node --test tests/skill-sync-doctor.test.mjs
scripts/audit-public-safety.sh
python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py --quick --json
```

Expected: all commands pass.

- [ ] **Step 2: Run safe Brave/ChatGPT preflight without submit**

Run:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py \
  workflow-run \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode thinking \
  --strategy auto \
  --oracle-mode assist \
  --prompt "Debug preflight only: verify Oracle-first integration without submitting." \
  --artifact-privacy redacted
```

Expected: status is `opened` or `blocked` with a clear guard reason; it must not choose sibling/clone silently and must not submit.

- [ ] **Step 3: Push and wait for GitHub checks**

Run:

```bash
git push
gh pr checks 1 --watch --interval 5
```

Expected: `audit` and `GitGuardian Security Checks` pass.

---

## Non-Negotiable Boundaries

- Oracle does not replace local login/account/plan/model/feature/screenshot guards.
- Oracle does not bypass CAPTCHA, Cloudflare, provider warnings, rate limits, or account regressions.
- ChatGPT Pro/Extended Pro/GPT-5.5 Pro remains blocked for routine automation tests.
- `workflow-run --oracle-mode runner` only executes Oracle when the local guarded workflow reaches `opened`, `submitted`, `started`, `verified`, or `captured`.
- `workflow-run` without `--submit` plans and validates only; it must not perform a real provider submit through Oracle.
- Real provider E2E remains opt-in with `AI_RESEARCH_BROWSER_E2E=1` and explicit paid quota permission.

## Self-Review

- Spec coverage: the plan covers Oracle-first runner integration, duplicate local logic replacement, local guard preservation, checker expansion, CI, docs, and final verification.
- Placeholder scan: no `TBD`, no open implementation holes, and each task includes concrete paths, code, and commands.
- Type consistency: functions use `Path`, `subprocess.CompletedProcess[str]`, existing `slug`, `normalize_provider_name`, `redact_command`, and current CLI patterns.
