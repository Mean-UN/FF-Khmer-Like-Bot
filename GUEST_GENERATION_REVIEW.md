# Guest generation review

The new reference was read as source. Its compressed SecurityEngine helper was decoded for inspection, not executed. Its runtime dependency installer and account-generation loop were not run.

## Integrated changes

- Normal MajorRegister requests use the supplied `loginbp.ppmainecoonghj.com` endpoint and fields 16=1 and 17=1. The separate GHOST registration fields and route are retained.
- Registration/login requests use matching URL and Host values, Unity 2018.4.12f1 headers, a current X-GA-SV timestamp, and the existing OB55 release value.
- Guest login responses use the shared exact-length JWT parser, including compressed/encrypted responses. They no longer use the guest generator's separate parser.
- Guest registration alone no longer reports full success. If a later step fails, the UID/password and `guest_created` flag remain available, with the failed stage recorded.
- A region mismatch returns the created credentials and an error instead of creating additional accounts and discarding the first account's password.

## Reference details intentionally not copied

- The compressed helper changes AES/signing keys when its branding/password constants change. Existing password generation and correct encryption keys are retained.
- The reference login packet embeds client version 1.114.13, a fixed date, and fixed field lengths before replacing credentials. Existing structured OB55 serialization is retained.
- Fixed timestamps, copied cookies, and fixed-length JWT slicing are not required for the integration and were not copied.
- The reference ignores MajorRegister HTTP failures; this implementation checks them and preserves credentials on failure.
- Guest registration requests are not automatically retried inside the session, since a lost response could otherwise create another account.

The initial reference is a registration/login flow; the separate guest activation workflow is not replaced by that update. No live accounts were created during verification.

## Follow-up reference: region selection

The later reference adds ChooseNewbieChoice, ChooseRegion, and a second MajorLogin. The generator now uses these steps for non-GHOST accounts when the first login has no region or returns a different region. It preserves credentials and the provisional JWT on failure, checks HTTP failures, and requires the final login to confirm the same account ID and requested region. EU is sent as EUROPE and CIS as RU, matching the reference aliases. An account already in the requested region skips region selection.

The reference declares OB54 and client 1.126.9; these older values are not copied over the current OB55 configuration. Its automatic bio edits, branding checks, and cookie-fetching logic are not part of this fix. GetLoginData remains in the separate activation workflow.

Failures include `failed_stage`, an HTTP status when available, and a redacted `error_detail` for validation failures. A missing region in the first login is now treated as an incomplete onboarding state rather than immediately failing guest generation. The exact user-reported error was not supplied during this update, so this addresses the concrete missing step found in the comparison rather than establishing a live root cause.
