# Guest creation reference review

Compared guest creation with the supplied SIAM-X-RIXOR reference without executing its installer, compressed code, or network operations.

| Stage | Result |
| --- | --- |
| Compressed SecurityEngine | Inspected as text. Existing AES-CBC/padding and HMAC-SHA256 already match. Branding-dependent key corruption was not copied. |
| Guest registration | Retained compact JSON and signature over the exact transmitted bytes. Updated SDK user agent. Static DataDome cookies were not copied. |
| Token grant | Try the reference v2 JSON endpoint first, including device_id and numeric client fields; retain legacy form fallback. Reject nonzero response codes. |
| MajorRegister | Use loginbp.ppmainecoonghj.com, Unity 2018.4.12f1 headers, field 16 = 1 and field 17 = 1; remove previous fields 20/21. |
| MajorLogin | Use decoded reference fields through creation_login_fields, encoded with actual lengths for open_id/access_token. Remove mismatched Host override; generate X-GA-SV at request time. |
| Response | Retain protobuf parsing and AES response support instead of slicing JWT signatures at a fixed length. Require token and account ID. |
| Recovery | Retain created credentials if a later stage fails, existing names/passwords, proxy settings and application integration. |

The reference login payload reports version 1.114.13 despite OB55 headers; it is reproduced for guest creation only. Existing activation login fields remain separate. The reference selects language but does not send an explicit region field in MajorRegister or MajorLogin; actual regional placement requires server verification. The UI's requested region is only a fallback when the response does not report a region.

Validation uses mocked network responses. No live accounts were created, and upstream acceptance has not been established.

Token grant request follow-up: now sends compact JSON in the reference's field order, preserves the UID type returned by registration, and carries forward registration Authorization as the reference does. Application-level rejection codes from HTTP 200 responses are now included in sanitized diagnostics. Static DataDome cookies remain excluded; therefore this is not a claim that every header matches the standalone client or that live acceptance is established.

Follow-up API review: the generated MajorLogin request matches all 902 bytes of the supplied reference for its original placeholders. Guest creation now uses the shared response parser, including compressed/encrypted and malformed-trailing-field handling. Removed the local-variable shadowing bug in the old protobuf exception handler. Success now requires MajorLogin; guest_created separately indicates recoverable credentials. Region mismatches retain the account with a warning instead of silently discarding credentials and registering replacements. Removed synthetic forwarding headers from creation and the mismatched Host override from subsequent activation. Route-level tests cover these behaviors using real protobuf encoding and decoding.
