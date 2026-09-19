# Updated guest generator

Run from this workspace:

```powershell
python guest_generator.py --region SG --count 1 --name-prefix MEAN --output generated_guests.json
```

The supplied NG-EROX reference is readable Python, not an encoded program. Its network code specifies OB54 and client 2.131.22. The updated entry point delegates to your project's direct Garena implementation instead of duplicating that older protocol, UI, or endless worker loops. No external activator is used.

The project configuration is OB55 / client 1.132.3, shared with `jwt_protocol.py`. Garena's official [OB55 patch notes](https://ff.garena.com/en/article/1712/) dated September 10, 2026 confirm OB55. They do not document the private login protocol's numeric client/version-code fields, which remain based on the previously supplied working reference.

The command defaults to one account and runs sequentially. Successful and partially created accounts are written atomically to the selected JSON list. A failure stops the batch. Credentials are saved in that local output file rather than printed.

Registration requests are serialized and spaced by at least five seconds within one process. HTTP 429 and application error 1006 trigger a shared cooldown. Numeric and HTTP-date `Retry-After` values are honored; without a usable value the local fallback is 60 seconds. That fallback is a client policy, not a promise that Garena's limit will have cleared. Failure results expose `retry_after_seconds`.

The gate is process-local. Separate API workers, bot processes, or other generators do not share its timer. Stop other generators when investigating a rate limit; restarting a process does not remove the upstream limit. No proxy rotation or external service is used to evade it.

Restart your API/bot after updating so its guest-registration calls also use the new gate. This update was verified with offline tests and did not create live accounts.
