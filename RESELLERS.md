# Reseller usage and daily billing

Deploy `telegram_bot.py`, `reseller_bot.py`, `reseller_store.py`, and
`reseller_pricing.py` together, then restart the Telegram bot. No reseller
accounts are created automatically. The API slot tracker remains separate.

Owner commands:

```text
/seller 123456789 10
/seller summary
/seller summary 2026-09-13
/seller history 123456789
/seller disable 123456789
```

`/seller <id> <total>` adds that many request credits and enables access.
For example, 2 remaining plus `/seller <id> 10` gives 12 remaining. Credits
never reset or refill automatically. Unused credits carry over, and an exhausted
reseller stays at zero until the owner adds more. The amount must be positive.
Reprocessing the same Telegram message cannot add credits twice; a new command
message is a new top-up. Only the configured owner may add requests, record
payment, disable accounts, or view other sellers' records.

Reseller commands:

```text
/likeff 554940705
/autolikeff 554940705 10000
/extend 554940705 1000
/myautolike
/seller
/seller summary 2026-09-13
/seller history
```

The reseller's Telegram ID comes from the sender. Full first and last names
are displayed where Telegram supplies them. Names are refreshed on reseller
commands, and each purchase retains the name recorded at that time. If Telegram
cannot resolve a newly added user, their ID is shown until they use the bot.
Resellers can use their commands privately in either configured bot; they do
not gain owner permissions or access to anyone else's orders.
History shows the reseller's name and ID once, followed by seven entries per
page. Use Previous and Next buttons to navigate within the same message; no
page number needs to be typed. Only the owner or the history's reseller may
use its buttons. Both configured Telegram bots support navigation.

The primary bot privately alerts `OWNER_ID` after each successful manual
LikeFF purchase, new AutoLikeFF order, or reseller extension. Alerts include
the reseller's full name/ID, player UID, likes/package, charge, remaining
requests and daily total. Zero-like manual results and failed purchases do
not alert. Scheduled deliveries do not generate another purchase alert.
The owner must have started the primary bot and allow its private messages.
Alerts are queued in SQLite and sent by a background worker, with failed sends
retried every 30 seconds. Existing historical purchases are not backfilled.
Queued alerts survive restarts; a crash after Telegram accepts an alert but
before its acknowledgement is saved can result in a repeated notification.

At the 03:00 Cambodia billing cutoff, the owner receives a private daily bill
for each reseller with charges that day. Each bill has **Paid** and **Pending**
buttons. Paid records payment for that reseller and date only. Pending marks
that day's bill unpaid again (including undoing a mistaken Paid tap). Neither
button adds or removes reseller requests. Only the owner may use the buttons.
The bill message updates to show the payment status and amount due.

The worker checks every 30 seconds and waits for requests still in flight at
the cutoff to finish or release their holds. Empty days do not generate bills.
Automatic billing starts with the day the updated worker first runs; it does
not send all historical bills on installation. Thereafter, missed days and
failed sends are caught up after restart. Bill delivery records prevent normal
repeat sends. The same send/acknowledgement crash caveat as purchase alerts applies.
If a closed day's amount changes, an updated bill is sent; old bill buttons
cannot silently mark a different amount paid. `/seller paid <id>` opens the
current billing day's bill privately with its total and Paid/Pending buttons.
Opening it does not record payment: tap Paid after receiving the money.
An optional `YYYY-MM-DD` selects an older day. Later purchases remain due;
reopen the bill to pay the updated total. Manual bills do not replace the
automatic 03:00 bill or start its 24-hour reminder timer.

For a partial payment, use `/seller paid <id> 2.00`. This opens a private
confirmation for an **additional $2.00**, not a replacement paid total. Tap
**Confirm payment** after receiving the money. Amounts must be positive USD
values with at most two decimal places and cannot exceed the amount due.
Use `/seller paid <id> 2.00 YYYY-MM-DD` for an older billing day.
Confirmation is stored durably and repeated taps cannot add the payment again.
If the paid amount or bill changes before confirmation, open a new command.
Paid still settles the full displayed bill; Pending clears all payments for
that date. Neither action changes request credits or purchase charges.

Owner command `/seller payments <id>` shows payment changes, newest first,
including timestamp, billing day, owner ID, action, and the paid amount before
and after the change. This audit history starts with this update; previous
payment totals remain intact, but historical taps cannot be reconstructed.
Taps which do not change the amount do not add duplicate audit entries.

If a bill is still unpaid 24 hours after its initial message was sent, the owner
receives one private payment reminder with the same Paid/Pending buttons.
Paid bills are skipped. The reminder is sent once per bill revision, persists
across restarts, and failed sends retry every 30 seconds. It does not repeat
every day. Either message's buttons update both the original and reminder when
possible; requests and charges do not change. On upgrade, existing bills whose
send time was not previously stored begin their 24-hour timer at the upgrade.

## Counting and pricing

- Request credits are shared between manual LikeFF and newly created AutoLikeFF orders.
- Manual LikeFF consumes one request and charges $0.20 only for positive likes.
  Confirmed zero-like and failed results cost nothing and use no request.
- An AutoLikeFF order consumes one request and charges its exact package price
  on creation, even if the first delivery gives zero likes. Subsequent scheduled
  deliveries consume API slot capacity but never another reseller request or
  package charge. Duplicate commands/orders are rejected without new charges.
- A reseller's `/extend <uid> <package_likes>` consumes one more request and
  charges the added package's price once, regardless of zero-like deliveries.
  Resellers can extend only their own AutoLikeFF orders still present in the
  order list. Extensions appear separately in history and are included in
  daily AutoLikeFF totals. Adding 5K to a 5K order costs another $2.50; the two
  purchases are not repriced as one 10K package. Existing order reply styles
  are retained; charges appear in reseller reports.
- Only listed packages are accepted. Amounts are stored in integer USD cents.
  Two 5K orders cost $5.00; one 10K order costs $4.50. Reports sum recorded
  purchase charges and never reprice an aggregate number of likes.
- There is no prepaid money balance. Request credits are added only by the
  owner. Bills are grouped from 03:00 Cambodia time (UTC+7) through 02:59:59 the
  next calendar day. A new billing day does not replenish request credits.
  Purchases are billed on the day they started. Old bills/history are retained.
- Marking a day paid records its current charged amount; new charges later in
  that day remain due. Reprocessing the same payment-command message does not
  mark later purchases paid. This is a bookkeeping action, not a payment transfer.
- Disabling a seller stops new purchases. Existing charged orders continue.
  Removing an order as owner does not automatically reverse its creation charge.

| Likes | Package price |
| ---: | ---: |
| 220 | $0.20 |
| 1,000 | $0.50 |
| 2,000 | $1.00 |
| 3,000 | $1.50 |
| 4,000 | $2.00 |
| 5,000 | $2.50 |
| 6,000 | $2.75 |
| 7,000 | $3.25 |
| 8,000 | $3.75 |
| 9,000 | $4.25 |
| 10,000 | $4.50 |
| 20,000 | $8.50 |
| 30,000 | $12.00 |
| 50,000 | $19.00 |

## Persistence and uncertain requests

Keep `resellers.sqlite3` and the existing AutoLikeFF order JSON on persistent
storage, and back them up together. Completed orders remain in the reseller
ledger after they leave the active-order file. The SQLite ledger reserves
credits atomically so simultaneous commands cannot overspend them.
Run only one bot worker for the existing JSON-based AutoLikeFF scheduler.
Each delivery attempt is claimed and saved before the API request. Immediate
and scheduled workers share this claim, and delivery results are saved after
each order. Concurrent owner extensions are preserved; deleted orders are not
restored by late delivery results. After a crash with an already claimed attempt,
that order resumes on its next scheduled day to avoid an unconfirmed duplicate.

An accepted AutoLikeFF purchase and its order payload are saved in one database
transaction. If exporting to the order JSON is interrupted, the next order load
recovers it without billing again. A first attempt recovered by the scheduled
worker runs on its normal schedule.

A manual request is deducted only when a successful API response confirms
positive likes. Zero likes, API failures, invalid results and timeouts release
the reserved request automatically, with no charge, so the reseller can retry.
A timeout does not prove no likes were sent upstream; the billing policy is to
charge only confirmed successful results. Holds left by a crashed worker expire
after 10 minutes when the ledger is next accessed. No manual resolution command
is needed. Internal reference IDs still prevent duplicate processing, but are
hidden from the Telegram history display.

An existing database from the daily-limit version is migrated automatically:
the stored allowance becomes a one-time grant, and all recorded consumed or
pending requests are deducted. No credits are added during migration. The API's
30-per-slot daily reset is unchanged; this change applies only to resellers.

Offline checks: `python -m unittest test_resellers test_slot_integration -v`.
