# Reseller purchase API

This guide documents the current reseller API and Telegram output. Example IDs,
names, dates and balances are illustrative. Replace `https://YOUR-DOMAIN` with
your API base URL. Local development uses `http://127.0.0.1:5000`.

## Owner setup

Grant purchase requests through the owner's Telegram account:

```text
/seller 987654 10
```

This adds 10 requests; requests do not automatically reset each day.
Configure groups where the bot can send purchase and delivery updates:

```text
/autolikegroup set -1001234567890
/autolikegroup ls
```

The owner receives private billing alerts. API group messages use the main bot,
which must be able to send messages in the configured groups.

## Configuration and startup

The API and Telegram bot must share this project directory and `resellers.sqlite3`.
The bot must be running: it processes API purchases and delivers scheduled orders.
Existing owner `/seller <telegram_id> <requests>` grants and package prices apply.
Each purchase reserves one granted request. A confirmed immediate delivery of
zero likes releases that request, including when recovery is created or extended.
Positive delivery consumes the request. Scheduled package purchases still consume
one request; recovery never consumes a second one. Package billing is unchanged.

Set `RESELLER_API_KEYS` in the project's **`.env` file** or API process environment, mapping Telegram IDs to
separate randomly generated secret keys. Example configuration (replace the key):

```text
RESELLER_API_KEYS='{"987654":"replace-with-a-long-random-secret"}'
```

The API loads `.env` beside `lssj.py`, regardless of the launch directory.
Existing process environment variables take precedence. Restart the API after
changing `.env`; restart the bot after code updates.
Keys authenticate the seller; a Telegram ID alone is insufficient.

### Parallel workers and queue health

The bot defaults to four API workers. Configure the count in `.env` and restart
the bot:

```dotenv
RESELLER_API_WORKERS=4
```

Supported range: 1–16 (out-of-range numbers are clamped; invalid text uses 4).
Different UIDs can progress concurrently. API jobs for the same UID stay
sequential, including their first-delivery attempt. Scheduled delivery uses the
same UID locks. Order lists are locked only for reading/updating, not while
waiting for the upstream delivery response. More workers do not guarantee faster
upstream delivery; watch rate limits and server load before increasing the count.

Purchase and status responses now also include:

| Field | Meaning |
|---|---|
| `created_at` | Purchase queued timestamp |
| `started_at` | Worker claim timestamp, or null |
| `finished_at` | Processing result saved timestamp, or null for legacy/interrupted jobs |
| `queued_seconds` | Time waiting; stops increasing after a worker claims the job |
| `seller_queued` | This seller's currently queued purchases |
| `worker_online` | Worker coordinator heartbeat is less than 30 seconds old |
| `last_worker_seen` | Latest heartbeat timestamp, or null |
| `worker_count` | Number configured by the running bot, or 0 before its first heartbeat |

The heartbeat updates every five seconds independently of slow delivery calls.
`worker_online` is not a promise of successful upstream delivery. Responses use
`Cache-Control: no-store`. Optional `request_id` retry protection remains available.

## Purchase or automatically extend

```http
GET /autolikeff?uid=123456&total=1000&seller=987654
Authorization: Bearer replace-with-a-long-random-secret
```

`POST /autolikeff` accepts the same fields as form data. `total` is a listed
package, not days. Prices come from `reseller_pricing.py`; 200 is a recovery
quantity, not a purchasable package. `request_id` is optional. When omitted, each
call is a new purchase, even for the same UID, and reserves a separate reseller
request. The API generates an ID and returns it for status checks. Existing
orders follow the automatic extension rules below.

Clients may still supply a unique `request_id` and reuse it to retry a purchase
without buying again. Reusing an ID with changed UID or package is rejected.
Never put the API secret in the URL.

The response is HTTP 202 while queued/processing. This acknowledges the purchase
request, not successful delivery. Poll:

```http
GET /autolikeff/status?seller=987654&request_id=ID_RETURNED_BY_PURCHASE
Authorization: Bearer replace-with-a-long-random-secret
```

Rules:

- `total=220`: attempt delivery once. A confirmed delivery of 0–100 likes creates
  a new AutoLikeFF order for 200 likes, or adds 220 likes to that seller's existing
  order. A result above 100 does not add recovery.
- The recovery creates an order or extends that seller's existing order and is
  deferred until at least the next day. The bill remains one 220 package ($0.20).
- Other listed packages (for example 1000 at $0.50) create an order or add that
  package quantity to the seller's existing order. New orders start their first
  delivery immediately and send the result to the configured groups; extensions
  retain their daily schedule. The existing daily bot worker
  handles delivery and credits the actual likes returned; 220 per day is not an
  upstream guarantee.
- An order owned by another seller/owner is not changed. Rejection releases the
  held request without charging.
- Confirmed purchases use existing seller history, billing, and bot notifications.
  Successful API purchase/extension alerts go to the owner's private chat and all
  groups configured with `/autolikegroup set`. Use `/autolikegroup ls` to check
  those destinations. Private alerts retain seller billing details. Group alerts
  show the like result (name, UID, region, before/added/after likes and requests
  left), order-created confirmation, or the existing order-extension format.
  Recovery purchases send two separate group messages, in order: the like result,
  then the recovery order confirmation. Each message is tracked separately so a
  failed second send can be retried without repeating the first.
  New regular package orders say “First delivery is processing now.” Recovery
  orders say “Added to AutoLikeFF. Delivery starts tomorrow.” Recovery orders
  keep their next-day schedule; no extra immediate request is sent.
  Failed sends are retried; successful recipients
  are recorded so a retry for another group does not resend their alert. These
  are purchase alerts, not confirmation that all scheduled likes were delivered.
- Timeouts, malformed delivery results, and interrupted delivery become `unknown`.
  The request remains held, with no charge, for owner review. Do not submit a new
  request ID until the owner has checked delivery. These jobs are not replayed
  automatically after a restart.

The `completed` API state means processing finished; check `result.delivered` and
`result.queued_likes` to distinguish immediate delivery from scheduled work.
No separate extension URL is needed.

## Request parameters

| Parameter | Purchase | Status lookup | Meaning |
|---|---|---|---|
| `uid` | Required | Not used | Positive numeric player UID, at most 9223372036854775807 |
| `total` | Required | Not used | Package quantity from the price table, not days |
| `seller` | Required | Required | Telegram ID associated with the supplied API key |
| `request_id` | Optional | Required | Purchase reference; 1–80 letters, digits, underscores or hyphens |

Use `Authorization: Bearer YOUR_SECRET` on both endpoints. Opening the purchase
URL in an ordinary browser tab does not automatically attach this header.

POST accepts `application/x-www-form-urlencoded` fields. JSON request bodies are
not currently supported. Responses are JSON.

`request_id` identifies a purchase, not an AutoLikeFF order. Several purchases
may extend the same order. The order ID is `result.order.order_id` when present.

## Package prices

| `total` | USD price |
|---:|---:|
| 220 | $0.20 |
| 1000 | $0.50 |
| 2000 | $1.00 |
| 3000 | $1.50 |
| 4000 | $2.00 |
| 5000 | $2.50 |
| 6000 | $2.75 |
| 7000 | $3.25 |
| 8000 | $3.75 |
| 9000 | $4.25 |
| 10000 | $4.50 |
| 20000 | $8.50 |
| 30000 | $12.00 |
| 50000 | $19.00 |

Each purchase is priced separately using `reseller_pricing.py`.

## Request-count examples

Starting balance: 3 requests. These rows are independent examples.

| Purchase | Confirmed immediate result | Requests left | Scheduled recovery |
|---|---:|---:|---|
| 220 | 0 likes | 3 | New order: 200; existing order: +220 |
| 220 | 1–100 likes | 2 | New order: 200; existing order: +220 |
| 220 | 101+ likes | 2 | None |
| 1000 | Scheduled package purchase | 2 | Create/extend by 1000 |

Zero immediate likes releases the request reservation for the 220 package; its
$0.20 purchase charge still applies. This does not refund past purchases.
The zero-like rule does not refund a regular package purchase when its first
scheduled-order delivery returns zero. Actual delivery counters and request
credits are separate from package billing.

## PowerShell example

After updating `.env`, start the API and bot in separate terminals:

```powershell
python lssj.py
```

```powershell
python telegram_bot.py
```

Make one purchase and check its status:

```powershell
$baseUrl = 'http://127.0.0.1:5000'
$headers = @{ Authorization = 'Bearer YOUR_LONG_RANDOM_SECRET' }

$purchase = Invoke-RestMethod `
    -Uri "$baseUrl/autolikeff?uid=610085993&total=220&seller=987654" `
    -Headers $headers

$purchase | ConvertTo-Json -Depth 10

Invoke-RestMethod `
    -Uri "$baseUrl/autolikeff/status?seller=987654&request_id=$($purchase.request_id)" `
    -Headers $headers | ConvertTo-Json -Depth 10
```

Calling the first URL again without an ID buys again. Use the status endpoint
to check progress instead.

## cURL example

Form POST with an optional client-generated purchase ID:

```bash
curl --request POST 'https://YOUR-DOMAIN/autolikeff' \
  --header 'Authorization: Bearer YOUR_LONG_RANDOM_SECRET' \
  --data-urlencode 'uid=610085993' \
  --data-urlencode 'total=1000' \
  --data-urlencode 'seller=987654' \
  --data-urlencode 'request_id=purchase-001'
```

Reusing `purchase-001` with the same UID and package returns that purchase without
buying again. A different purchase needs a different ID, or omit it.

## Response examples

Queued purchase, HTTP **202**:

```json
{
  "success": true,
  "request_id": "66ad6fa1a82e4c0195f04c99e1a1bc42",
  "state": "queued",
  "uid": "610085993",
  "total": 220,
  "result": null
}
```

Confirmed immediate delivery, HTTP **200**:

```json
{
  "success": true,
  "request_id": "66ad6fa1a82e4c0195f04c99e1a1bc42",
  "state": "completed",
  "uid": "610085993",
  "total": 220,
  "result": {
    "delivered": 220,
    "queued_likes": 0,
    "delivery": {
      "PlayerNickname": "ONE❶ㅤEPA44",
      "Region": "SG",
      "LikesbeforeCommand": 23170,
      "LikesafterCommand": 23390
    },
    "order": null,
    "action": "delivered",
    "charge_cents": 20
  }
}
```

For scheduled purchases, `result.order` contains an order snapshot, including
`order_id`, `uid`, `total_likes`, `sent_likes`, and `next_run_date`. This is a
snapshot at purchase processing time, not a live delivery-progress endpoint.
`result.delivery` is null for regular package purchases; immediate first delivery
of those orders is reported through the bot's delivery updates.

| Result example | `delivered` | `queued_likes` | `action` |
|---|---:|---:|---|
| Zero likes, new recovery | 0 | 200 | `created` |
| Zero likes, existing order | 0 | 220 | `extended` |
| 50 likes, existing order | 50 | 220 | `extended` |
| New 1000 package | 0 | 1000 | `created` |
| Extend with 1000 package | 0 | 1000 | `extended` |

### States and HTTP codes

| State | HTTP | Meaning |
|---|---:|---|
| `queued` | 202 | Accepted; waiting for the bot worker |
| `processing` | 202 | Worker is handling the purchase |
| `completed` | 200 | Purchase processed; scheduled likes may still be outstanding |
| `failed` | 200 | Purchase rejected during processing; request released |
| `unknown` | 200 | Outcome needs owner review; automatic replay is disabled |

Check `state` and `result`, not only HTTP 200 or `success`. `success` is true for
queued/processing requests as well as completed requests.

Validation error example:

```json
{
  "success": false,
  "error": "No reseller requests available; ask the owner to add requests"
}
```

| HTTP | Error examples |
|---:|---|
| 401 | `Invalid reseller API key` |
| 400 | `Reseller access is disabled` |
| 400 | `No reseller requests available; ask the owner to add requests` |
| 400 | `Choose a listed like package` |
| 400 | `uid must be a positive 64-bit number` |
| 400 | `Request ID already used for a different purchase` |
| 404 | `Purchase not found` |

Processing failures put the explanation in `result.error`, for example:
`UID has an order owned by another user` or
`Delivery was not confirmed; request held for owner review`.

## Telegram output examples

### Immediate likes: group message

```text
✅ Like Request Processed Successfully
━━━━━━━━━━━━━━━━━━
👤 Name: ONE❶ㅤEPA44
🆔 UID: 610085993
🌍 Region: SG
👍 Likes Before: 23170
➕ Likes Added: 0
❤️ Total Now: 23170
📌 Requests Left: 3
━━━━━━━━━━━━━━━━━━
💥 Daily 220 Likes!
🚀 Contact @Mean_Un to purchase Likes.
```

If this triggers new recovery, send a **second, separate** message:

```text
✅ AUTOLIKEFF ORDER CREATED
━━━━━━━━━━━━━━━━━━━━━━━━
🧾 Order ID: 288
🆔 UID: 610085993
👤 Telegram User: Tath Ratana
🎯 Total Likes: 200
✅ Added to AutoLikeFF. Delivery starts tomorrow.
```

If it extends an existing 200-like order instead:

```text
✅ AUTOLIKEFF ORDER EXTENDED
━━━━━━━━━━━━━━━━━━
🧾 Order ID: 288
🆔 UID: 610085993
👤 Telegram User: Tath Ratana
🎯 Total Likes: 420
✅ Delivered: 0
⏳ Remaining: 420
```

### Regular package: created order, then first-delivery update

```text
✅ AUTOLIKEFF ORDER CREATED
━━━━━━━━━━━━━━━━━━━━━━━━
🧾 Order ID: 289
🆔 UID: 610085993
👤 Telegram User: Tath Ratana
🎯 Total Likes: 1,000
⏳ First delivery is processing now.
```

```text
💎 Tath Ratana Daily AutoLike Update
━━━━━━━━━━━━━━━
🆔 UID: 610085993
👤 Player: ONE❶ㅤEPA44

📊 Progress
👍 Likes Before: 23170
➕ Likes Added: 220
❤️ Current Likes: 23390
🎯 Total Delivered: 220/1000
━━━━━━━━━━━━━━━
📌 Status
📈 Progress: 22.00%
⏳ Remaining: 780
```

A confirmed zero-like result also produces this update, with zero added and
the balance unchanged. A delivery error produces a failure message instead.

### Owner's private billing alert

```text
🔔 RESELLER REQUEST SUCCESS
━━━━━━━━━━━━━━━━━━━━
👤 Tath Ratana
🆔 Telegram: 987654
🕒 2026-09-21 08:10:00
📌 AUTOLIKEFF ORDER
🎮 UID: 610085993
🎯 Package: 1,000 likes
💵 Charge: $0.50
🎟 Requests left now: 2
📅 Bill date: 2026-09-21
💵 Daily total: $0.50
```

Extensions use the `AUTOLIKEFF EXTENSION` label. Private billing includes price
and daily totals; group messages do not. If a historical seller profile is
missing, the alert shows `N/A (seller record missing)` for requests remaining.

## Troubleshooting

- **HTTP 202:** normal queue acceptance, not an error. Poll status.
- **Stays queued:** ensure the updated Telegram bot is running and both processes
  share the same project database.
- **401:** check the seller/key mapping and Authorization header; restart the API
  after editing `.env`. Existing environment variables override `.env` values.
- **No group output:** check `/autolikegroup ls`, bot permissions, and bot logs.
  Failed sends retry automatically; each successfully sent message is recorded.
- **Unknown outcome:** do not make another purchase just to check. Ask the owner
  to review delivery and the held request. There is no automatic unknown-job replay.
- **Restart after a processed purchase:** saved orders and queued alerts persist.
  A process interruption can leave first delivery to the daily scheduler; do not
  repeat the purchase to force it.
