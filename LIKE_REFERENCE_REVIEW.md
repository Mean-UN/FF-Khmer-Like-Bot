# Like reference review

The latest supplied script changes the client host for SG/BD and other non-IND/non-Americas regions to `https://clientbp.ppmainecoonghj.com`, and uses Unity 2018.4.12f1 headers. Both profile reads and LikeProfile sends now use these values. IND and Americas addresses stay as supplied.

| Reference function | Existing implementation and review result |
| --- | --- |
| `load_tokens` | `load_like_tokens` already reads the selected slot from disk for each API request. Retained slot support instead of switching everything to `tokens.json`. |
| `encrypt_message` | `BmwNoiNoiBmvYasYas` already uses the same AES key, IV, CBC mode and padding. Its output is bytes, avoiding the reference's bytes-to-hex-to-bytes conversion. |
| `create_protobuf_message` | `create_like_payload` uses the existing like protobuf's UID and region fields. |
| `send_request` | `send_like_request` now uses the reference headers, with current time for `X-GA-SV` instead of the frozen timestamp. HTTP status remains available for diagnostics. |
| `send_multiple_requests` | `send_like_requests` uses the new regional host and still attempts all 220 tokens in a 220-token slot, with 25 concurrent sends and a shared client. The reference's hard-coded 100 requests would reduce the current batch. |
| `create_protobuf`, `enc` | `create_like_count_payload` retains UID field 1 and flag field 2. The supplied script omits `uid_generator_pb2`, so the reference's renamed Python fields alone cannot establish different protobuf field numbers. |
| `make_request` | `fetch_like_info` uses the new host and headers, keeps timeouts and checks HTTP status before parsing. |
| `decode_protobuf` | The existing decoder already uses `like_count_pb2.Info`; no replacement needed. |
| `handle_requests` | Both existing like routes retain before/after counting, automatic FFInfo region detection, persistent region caching, slot accounting, and diagnostics. The region of the first sender token does not establish the target player's region. |
| `index` / startup | Existing application routes and startup retained. |

## Investigating 401 responses

`send_results.failed_tokens` identifies each failed send using a one-based position in the loaded token list, a 16-character SHA-256 fingerprint of the raw JWT, and its HTTP status (null for a network failure). JWTs, passwords and response bodies are not exposed. A fingerprint changes if that JWT is refreshed, so it can distinguish the token used in a request from a later replacement. No automatic retry is performed.

The supplied reference has no token refresh implementation. Refresh code is therefore unchanged. Successful login establishes that a JWT was issued; it does not establish acceptance by LikeProfile.

The host/header update matches the new reference but has not been demonstrated to eliminate the 79 HTTP 401 responses. Offline tests exercise both profile and send routing, timestamp generation, 220-token batches, and failure fingerprints. No live likes were sent.
