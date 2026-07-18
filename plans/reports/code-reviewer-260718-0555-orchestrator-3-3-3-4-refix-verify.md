# Re-review: Orchestrator Epic 3 Tasks 4-7 fixes (2d62ddf..ce76c3a)

## Verdict: ✅ Cả 2 fix Important đã confirm resolved, không regression.

## Fix 1 — Atomic result write (running->completed CAS)
- `state.py:46-77` `transition_run_status` nhận `extra_cols`, build SET clause động, gộp vào CÙNG 1 câu `UPDATE ... WHERE id=? AND status=?` — pattern giống hệt `transition_task_status` (`state.py:80-112`), cùng cách serialize JSON qua `extra_cols` dict.
- `state.py:138-145` `transition_and_audit` giờ thread `extra_cols` vào cả nhánh `kind=="run"` (trước đây chỉ nhánh `task` nhận).
- `service.py:498-503` (`orchestrate_run`) gọi `transition_and_audit(..., from_status="running", to_status="completed", extra_cols={"result": json.dumps(result)})` — 1 câu CAS duy nhất set cả status lẫn result. Không còn UPDATE riêng nào sau đó — grep xác nhận không còn statement nào update `result` ngoài atomic path này.
- Path `running->failed` (zero-tasks, `service.py:484-490`) không đổi, không set `result` (giữ NULL) — đúng như trước, không phải phạm vi fix.
- Không có lost-update / non-atomic window nào còn sót.

## Fix 2 — decompose_run line-count split
- `service.py:301-337` `_validate_and_route_task` — 37 dòng (bao gồm signature/docstring). Validate `TaskSchemaModel`, audit `task.dropped_invalid` / `task.routing_rejected` khi fail, trả `Task` object khi pass.
- `service.py:339-384` `decompose_run` — 46 dòng. Idempotency guard (`existing` check, return sớm không gọi LLM) giữ nguyên. List-comprehension gọi helper, filter `None`, bulk insert, audit `orchestrator.decomposed`.
- Cả 2 hàm ≤50 dòng. Tất cả audit type giữ nguyên (`task.dropped_invalid`, `task.routing_rejected`, `orchestrator.decomposed`).

## Minor — `_reassert_rls` trước audit
- Xác nhận có mặt trước mọi post-commit `_audit(...)` call: `decompose_run` (trước `orchestrator.decomposed`, `service.py:373`), `execute_task_row` (trước `task.executed` và `task.failed`, cả 2 nhánh try/except), `orchestrate_run` (trước `orchestrator.aggregated`, `service.py:504`). Không có site nào bị bỏ sót.

## Regression check
- Không phát hiện CAS race mới, không double-transition, không audit bị swallow.
- Report's test evidence (14 targeted integration tests + 31 `test_ports.py` + ruff clean) khớp với scope diff review — không rerun lại theo chỉ dẫn.

## Residual findings
Không có Critical/Important nào còn sót. Không có vấn đề mới phát sinh từ 2 fix.

## Unresolved questions
Không có.
