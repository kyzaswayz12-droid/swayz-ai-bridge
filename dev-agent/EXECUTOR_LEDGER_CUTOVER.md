# Executor ledger compatibility — deployment blocker

The existing Droplet 2 files are not interchangeable with the trusted
executor's required admission and GBP budget ledgers:

- `data/tasks.sqlite3` has `tasks` and `audit`, not `admitted_jobs`.
- `data/budget.sqlite3` has `reservations` from the legacy USD
  `BudgetStore`, not `gbp_reservations` from `GBPBudget`.
- The legacy budget uses USD 5/day and 20 **calls**, not GBP 5/day and
  20 **development jobs**. Treating them as the same would be unsafe.

The trusted entrypoint now rejects incompatible schemas before executing.
Do not point the executor at these legacy files or create parallel active
ledgers while another dispatcher can spend against the old ones.

## Required before activation

1. Inspect read-only table columns and active writers on Droplet 2. Confirm
   which job and budget ledgers all live OpenAI/Anthropic dispatch paths use.
2. Select **one authoritative quota and GBP spending gate** shared by every
   dispatch path. Migrate or reconcile outstanding USD reservations using
   owner-approved FX rates and verified billing; block dispatch during cutover.
3. Verify `admitted_jobs(job_id,day_utc)` and
   `gbp_reservations(request_id,provider,day_utc,reserved_gbp,status,actual_gbp)`
   exist in the chosen canonical stores and that all producers write them.
4. Test concurrency, UTC rollover, duplicate IDs, restart recovery and
   stop enforcement before creating `/etc/swayz/trusted-executor.json`.
5. Keep the one-shot systemd unit static and the stop engaged until supervised
   end-to-end execution is approved.

No automatic migration or conversion is performed by this PR.
