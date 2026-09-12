LikeFF daily slot usage
======================

Deploy lssj.py and request_usage.py together and restart the API.
GET /usage lists all 30 slots. GET /usage?slot=1 returns, for example:
{"date":"2026-09-12","slot":1,"used":29,"max_limit":30,"remaining":1}

Each /likeff request with LikesGivenByAPI > 0 consumes one request on its slot.
Zero likes and failed requests do not consume a request. The /likeff response
includes these counters under usage, plus the existing slot_usage string.
Other endpoints, including /like, do not consume these LikeFF quotas.
Slots with configured tokens are selected in numeric order, advancing when a slot has 30 successful
requests or all its remaining capacity is reserved by in-flight requests.
Empty slots are skipped. A legacy flat tokens_likeff.json list belongs to slot 1
only; other slots need their own token entries or files. Manual /likeff and
AutoLikeFF use the same API quota. Authentication errors include the selected
slot so AutoLikeFF can refresh that slot before retrying.

Each quota day starts with 0 used and 30 remaining at 03:00 Asia/Phnom_Penh (UTC+7).
Before 03:00, the displayed date is the previous quota day's start date.
A request spanning 03:00 is accounted against the quota day it started.
The date changes automatically when accessed; no scheduled job is needed.
Counters persist in request_usage.sqlite3. REQUEST_USAGE_DB can specify another
path with an existing parent directory. Keep the database on persistent storage;
workers must share the same file. Separate hosts/files have separate quotas.

In-flight requests reserve capacity to prevent concurrent overbooking. Normal
failures release it immediately; reservations abandoned by crashed workers expire
after one hour. If a worker crashes after sending likes but before saving the
result, that success cannot be accounted for automatically.

API_MAX_REQUESTS is no longer used: the maximum is fixed at 30 per slot per day.
Previous global counters and UID assignments cannot establish how many requests
sent likes, so this new accounting starts at zero when first installed.
