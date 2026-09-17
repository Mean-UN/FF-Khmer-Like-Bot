# JWT protocol update

The supplied reference is integrated in `jwt_protocol.py`, using its OB55 / 1.132.3 values and version code `2024010012`. These values are taken from the reference, not independently verified against the live service.

## API usage

Existing clients can continue using `GET /jwt?uid=123&pw=PASSWORD`.

Prefer POST JSON to avoid putting credentials in URLs:

```http
POST /jwt
Content-Type: application/json

{"uid":"123","pw":"PASSWORD"}
```

Direct access-token login inspects the token to obtain its open ID:

```http
POST /jwt
Content-Type: application/json

{"access_token":"ACCESS_TOKEN"}
```

The response retains `Guest_Auth` and `MajorLogin`, including `MajorLogin.jwt_token`, `account_id`, and `nickname`. Missing inputs return 400, authentication/inspection failures return 401, and MajorLogin failures return 502.

## Function compatibility

| Existing function | Integration |
| --- | --- |
| `jwt_login` | Uses the new guest OAuth, token inspection, login request and response parsing. |
| `build_major_login_request` | Delegates to the new reference payload builder. |
| `fetch_guest_jwt_for_like` | Uses the same new OAuth and MajorLogin helpers. |
| `fetch_guest_jwt_for_like_with_retry` | Uses the updated fetch function and retains its retries. |
| `update_tokens_from_uidpass`, `update_like_tokens_from_uidpass`, `update_likeff_tokens_from_uidpass` | Receive the update through the fetch function. |
| `update_like_tokens.fetch_jwt` | Receives the update through the existing retry wrapper. |
| `bio_major_login` | Separate platform-aware login payload; needs independent adaptation and validation. |
| `create_guest_account_with_proxy`, `guest_activation.activate_guest` | Separate registration/activation workflows; reference is a login-only script and does not replace them. |
| Async account-info login flow | Separate request/schema; not migrated by this change. |

Existing protobuf modules are retained: reference response field 1 maps to `account_id`, 2 to `lock_region`, 10 to `server_url`, 21 to `kts`, 22 to `ak`, and 23 to `aiv`. Loading the reference's duplicate descriptor names into the default pool is unnecessary and could cause conflicts.

Response parsing handles plaintext, gzip, zlib, raw deflate, bounded prefix offsets, AES-CBC responses, and a final JWT extraction fallback. A response without a token is rejected. JWT fallback claims are unverified metadata, and no region is invented. TLS verification stays enabled. The reference's public-IP lookup is omitted; client IP remains `0.0.0.0` as in the existing API.

## Verification

Run `python -m unittest test_jwt_protocol test_token_refresh test_slot_integration test_resellers` for offline protocol, route, refresh, slot and reseller tests. Live login requires valid account credentials and has not been verified by this update.

## Like API reference update

`/like` and `/likeff` now use the supplied like reference's Android 9 user agent and OB55 headers. The release value is shared with `jwt_protocol.RELEASE_VERSION`. Raw JWTs and already prefixed Bearer tokens are both accepted internally.

`like_server_url` selects the India host for IND, the US host for BR/US/SAC/NA, and `clientbp.ggpolarbear.com` for other supported regions. `fetch_like_info` and `send_like_requests` use saved JWTs directly; the existing regional-token login remains a fallback when no token is available.

Existing encrypted protobuf payloads match the supplied like/profile request structure. Token files, API responses, slot handling and request accounting retain their existing behavior. Token refresh uses the local JWT protocol integrated above; the reference's external credential-taking JWT service is not required.

Offline checks: `python -m unittest test_like_protocol test_jwt_protocol test_slot_integration test_token_refresh test_resellers`. No live likes are sent by these checks.

## Automatic region detection

UID-only `/like` and `/likeff` requests read `regions.json` first. On a cache miss they use the same `fetch_player_personal_show` function as `/meanffinfo`. The lookup validates `basicInfo.accountId` and `basicInfo.region`, saves the returned region to `regions.json`, and updates the in-memory cache. Successful `/meanffinfo` requests now also populate that persistent cache. No region parameter is required. A failed profile lookup returns `REGION_LOOKUP_FAILED` with a profile-check URL and does not send likes.
