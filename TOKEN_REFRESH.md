# Token refresh

The seven-hour automatic cycle refreshes three token sets/slots concurrently.
Each updater refreshes four accounts concurrently, with its own HTTP session
per account and up to three attempts, waiting two and then four seconds
between failed attempts. Successful accounts are not retried. Actual duration depends on upstream
responses; each slot subprocess retains its 15-minute timeout. Concurrent
full-slot requests from automatic refresh, manual commands, and AutoLikeFF
recovery in the same bot process share one running job and its result.
This does not coordinate separate bot processes or standalone updater runs.

At the end of an automatic cycle, the owner receives one LikeFF completion
summary: checked/successful/failed slots, refreshed/failed accounts, and elapsed
time. The separate `like` set is excluded from LikeFF totals. Interrupted slots
without final counts are explicitly marked unknown. Summary messages use the
same durable delivery queue as failure alerts.

Full-slot refresh failures from automatic, manual, and AutoLikeFF recovery
calls queue a compact private owner report in `token_refresh_alerts.sqlite3`.
A separate worker retries delivery every 30 seconds, including after restart.
The updater flushes progress counters before work and after every account
result. Timeouts retain captured progress: reports show confirmed failures,
generated tokens, and unfinished accounts separately. Generated tokens may
not all have reached the latest disk checkpoint. If the updater fails before
reading accounts and emitting any progress, counts remain unavailable.
Slots with token files but missing credentials are checked and reported too.
The bot must remain running and the owner must allow private messages from it.
If the process stops after Telegram accepts a message but before acknowledging
it in SQLite, a duplicate notification can occur on restart.

Reports omit passwords and raw error output. Token files are replaced
atomically after the first successful account, every 20 successes, and at
completion. Temporary Windows file-sharing locks are retried with short
backoff. Process failures log their exception type without account passwords.
If every account fails, the existing token file is retained;
this does not guarantee those older tokens remain valid. Partial success
preserves older tokens for configured accounts that failed while saving fresh
tokens for successes. Removed accounts are excluded on a successful write.

Deploy `telegram_bot.py`, `update_like_tokens.py`, `lssj.py`, and
`token_refresh_alerts.py` together, then restart the bot and API.
Verification uses mocked authentication and Telegram; no real token refreshes
or messages are sent by `test_token_refresh.py`.
