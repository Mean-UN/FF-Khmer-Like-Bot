"""Telegram reseller commands; all external actions use the existing bot helpers."""
import os
import json
import threading
import re
from datetime import date

from reseller_pricing import PACKAGE_PRICES_CENTS, format_usd, package_price_cents
from reseller_store import ResellerStore, SellerError


class ResellerFeatures:
    def __init__(self, core):
        self.core = core
        self.store = ResellerStore(os.path.join(core.BASE_DIR, "resellers.sqlite3"))
        self.owner_alert_wakeup = threading.Event()

    def send_owner_alerts(self):
        owner_id = getattr(self.core, "OWNER_ID", 0)
        if not owner_id:
            return
        for event in self.store.pending_owner_alerts():
            try:
                report = self.store.report(event["user_id"], event["day"])[0]
                labels = {"likeff": "LIKEFF", "autolikeff": "AUTOLIKEFF ORDER", "autolikeff_extend": "AUTOLIKEFF EXTENSION"}
                lines = ["🔔 RESELLER REQUEST SUCCESS", "━━━━━━━━━━━━━━━━━━━━",
                         f"👤 {event['name']}", f"🆔 Telegram: {event['user_id']}",
                         f"🕒 {event['created_at'][:19].replace('T', ' ')}",
                         f"📌 {labels[event['kind']]}", f"🎮 UID: {event['uid']}"]
                if event["kind"] == "likeff":
                    lines.append(f"❤️ Likes sent: {event['likes']:,}")
                else:
                    lines.append(f"🎯 Package: {event['package']:,} likes")
                lines.extend([f"💵 Charge: {format_usd(event['cents'])}",
                              f"🎟 Requests left now: {report['remaining']}",
                              f"📅 Bill date: {event['day']}", f"💵 Daily total: {format_usd(report['cents'])}"])
                self.core.bot.send_message(int(owner_id), "\n".join(lines), parse_mode=None)
                self.store.owner_alert_sent(event["event_id"])
            except Exception as exc:
                self.core.logger.warning("Reseller owner alert failed; will retry: %s", exc)
                break

    def process_owner_alerts(self):
        while True:
            self.owner_alert_wakeup.clear()
            try:
                self.send_owner_alerts()
                self.send_daily_bills()
                self.send_bill_reminders()
            except Exception:
                self.core.logger.exception("Reseller owner alert worker failed")
            self.owner_alert_wakeup.wait(30)

    def bill_view(self, bill, reminder=False):
        payload = json.loads(bill["payload"])
        manual = [event for event in payload["events"] if event["kind"] == "likeff"]
        auto = [event for event in payload["events"] if event["kind"] != "likeff"]
        paid = self.store.bill_paid_amount(bill)
        total = bill["total_cents"]
        title = "⏰ RESELLER PAYMENT REMINDER" if reminder else "🧾 RESELLER DAILY BILL"
        lines = [title, "━━━━━━━━━━━━━━━━━━━━", f"📅 {bill['day']}", "",
                 f"👤 {payload['name']}", f"🆔 {bill['user_id']}",
                 f"💎 LikeFF: {len(manual)} req · {format_usd(sum(e['cents'] for e in manual))}",
                 f"🔁 AutoLikeFF: {len(auto)} orders/extensions · {sum(e['package'] for e in auto):,} likes"]
        packages = {}
        for event in auto:
            key = (event["package"], event["cents"])
            packages[key] = packages.get(key, 0) + 1
        for (package, cents), count in sorted(packages.items()):
            lines.append(f"  • {package:,} × {count} · {format_usd(cents * count)}")
        lines.extend(["", f"💵 Total: {format_usd(total)}", f"✅ Paid: {format_usd(paid)}",
                      f"🧾 Due: {format_usd(max(0, total - paid))}",
                      "✅ Status: Paid" if paid >= total else "⏳ Status: Pending"])
        keyboard = self.core.InlineKeyboardMarkup(row_width=2)
        keyboard.row(self.core.InlineKeyboardButton("✅ Paid", callback_data=f"sellerbill:{bill['bill_id']}:paid"),
                     self.core.InlineKeyboardButton("⏳ Pending", callback_data=f"sellerbill:{bill['bill_id']}:pending"))
        return "\n".join(lines), keyboard

    def send_daily_bills(self):
        owner_id = getattr(self.core, "OWNER_ID", 0)
        if not owner_id:
            return
        self.store.prepare_daily_bills()
        for bill in self.store.pending_daily_bills():
            try:
                text, keyboard = self.bill_view(bill)
                sent = self.core.bot.send_message(int(owner_id), text, parse_mode=None, reply_markup=keyboard)
                self.store.daily_bill_sent(bill["bill_id"], int(owner_id), sent.message_id)
            except Exception as exc:
                self.core.logger.warning("Daily reseller bill failed; will retry: %s", exc)
                break

    def bill_callback(self, call):
        active_bot = self.core.active_bot_for(call)
        if not self.core.is_owner(call.from_user.id):
            active_bot.answer_callback_query(call.id, "Owner only.", show_alert=True)
            return
        if active_bot is not self.core.bot:
            active_bot.answer_callback_query(call.id, "Use the bill in your private chat with the main bot.", show_alert=True)
            return
        try:
            prefix, raw_id, status = str(call.data or "").split(":")
            if prefix != "sellerbill" or not raw_id.isascii() or not raw_id.isdigit():
                raise SellerError("Invalid bill")
            if not getattr(call, "message", None) or call.message.chat.id != self.core.OWNER_ID:
                raise SellerError("Use the bill sent to your private chat")
            bill = self.store.set_bill_status(int(raw_id), status, call.message.chat.id, call.message.message_id, actor_id=call.from_user.id)
        except ValueError as exc:
            active_bot.answer_callback_query(call.id, str(exc), show_alert=True)
            return
        active_bot.answer_callback_query(call.id, "Payment recorded." if status.startswith("partial") else ("Marked paid." if status == "paid" else "Marked pending (unpaid)."))
        messages = [(bill["chat_id"], bill["message_id"], False),
                    (bill["reminder_chat_id"], bill["reminder_message_id"], True)]
        messages.extend(self.store.manual_bill_messages(bill["bill_id"]))
        for chat_id, message_id, reminder in messages:
            if message_id is None:
                continue
            text, keyboard = self.bill_view(bill, reminder=reminder)
            try:
                active_bot.edit_message_text(text=text, chat_id=chat_id,
                                             message_id=message_id, parse_mode=None, reply_markup=keyboard)
            except Exception as exc:
                if "message is not modified" not in str(exc).lower():
                    self.core.logger.warning("Bill status saved but message update failed: %s", exc)

    def send_bill_reminders(self):
        owner_id = getattr(self.core, "OWNER_ID", 0)
        if not owner_id:
            return
        for bill in self.store.due_bill_reminders():
            try:
                # A payment may have been recorded after the queue was read.
                if self.store.bill_paid_amount(bill) >= bill["total_cents"]:
                    continue
                text, keyboard = self.bill_view(bill, reminder=True)
                sent = self.core.bot.send_message(int(owner_id), text, parse_mode=None, reply_markup=keyboard)
                self.store.bill_reminder_sent(bill["bill_id"], int(owner_id), sent.message_id)
            except Exception as exc:
                self.core.logger.warning("Reseller bill reminder failed; will retry: %s", exc)
                break

    def allowed(self, user_id):
        seller = self.store.seller(user_id)
        return bool(seller and seller["active"])

    def remember(self, user):
        self.store.remember(user.id, self.core.requester_name(user), getattr(user, "username", None) or "")

    def key(self, message):
        bot = self.core.active_bot_for(message)
        return f"{bot.token.split(':')[0]}:{message.chat.id}:{message.message_id}"

    def reply(self, message, text):
        self.core.send_long_message(message, text, parse_mode=None)

    def reconcile_orders(self, orders):
        pending = self.store.pending_orders()
        if not pending:
            return orders
        existing = {order.get("seller_event_id") for order in orders}
        for key, order in pending:
            extension = order.get("_seller_extension")
            if extension:
                target = next((item for item in orders if item.get("seller_event_id") == order.get("seller_event_id")), None)
                if target is None:
                    target = {field: value for field, value in order.items() if field != "_seller_extension"}
                    orders.append(target)
                extensions = target.setdefault("seller_extensions", [])
                if not any(item["event_id"] == key for item in extensions):
                    offset = int(target["total_likes"])
                    target["total_likes"] = offset + extension["likes"]
                    extensions.append({"event_id": key, "offset": offset})
                    target["extended_at"] = extension["created_at"]
                    target.pop("remove_after_save", None)
                    if target.get("status") == "completed":
                        target["status"] = "active"
                        target["next_run_date"] = self.core.next_autolike_run_date(kind="likeff")
                continue
            if key not in existing:
                orders.append(order)
                existing.add(key)
        # Billing and the order payload are saved together in SQLite first.
        # A crash before export can be recovered without charging twice.
        self.core.save_autolike_orders(orders, "likeff")
        self.store.exported([key for key, _ in pending])
        self.owner_alert_wakeup.set()
        return orders

    def manual_call(self, message, params):
        self.remember(message.from_user)
        key = self.key(message)
        try:
            self.store.reserve(message.from_user.id, key, "likeff", params["uid"])
        except SellerError as exc:
            return {"success": False, "error": str(exc)}
        try:
            data = self.core.call_api("likeff", params)
        except Exception:
            data = {"success": False, "error": "Request failed. No reseller request deducted; please try again."}
        if not isinstance(data, dict):
            data = {"success": False, "error": "Invalid API response. No reseller request deducted."}
        error = str(data.get("error") or "")
        if data.get("success") and "LikesGivenByAPI" not in data:
            error = "Missing like count. No reseller request deducted."
            data = {"success": False, "error": error}
        try:
            likes = int(data.get("LikesGivenByAPI", 0) or 0) if data.get("success") and not error else 0
        except (TypeError, ValueError):
            likes = 0
            error = "Invalid like count. No reseller request deducted."
            data = {"success": False, "error": error}
        self.store.finish_manual(key, likes, error)
        if likes > 0:
            self.owner_alert_wakeup.set()
        report = self.store.report(message.from_user.id)[0]
        return {**data, "seller_charge": format_usd(20 if likes > 0 else 0),
                "seller_requests": f"{report['remaining']} left",
                "seller_daily_total": format_usd(report["cents"])}

    def create_order(self, message):
        self.remember(message.from_user)
        parts = message.text.split()
        if len(parts) != 3 or not parts[1].isascii() or not parts[1].isdigit() or not parts[2].isascii() or not parts[2].isdigit():
            self.reply(message, "📌 Use: /autolikeff <uid> <package_likes>\nExample: /autolikeff 554940705 10000\n📦 Packages: " + ", ".join(str(n) for n in PACKAGE_PRICES_CENTS))
            return
        try:
            uid, package = str(int(parts[1])), int(parts[2])
            if not 0 < int(uid) <= 9223372036854775807:
                raise SellerError("UID must be a positive 64-bit number")
            package_price_cents(package)
            key = self.key(message)
            with self.core.autolike_lock:
                orders = self.core.load_autolike_orders("likeff")
                if self.core.find_existing_autolike_order(orders, uid):
                    raise SellerError("An active order already exists for this UID. No request or charge added.")
                order = {
                    "order_id": self.core.next_autolike_order_id(orders), "kind": "likeff", "uid": uid,
                    "total_likes": package, "sent_likes": 0,
                    "telegram_user_id": str(message.from_user.id),
                    "telegram_user_name": self.core.requester_name(message.from_user),
                    "telegram_username": getattr(message.from_user, "username", None) or "",
                    "group_id": self.core.resolve_autolike_group_id(message),
                    "created_by": str(message.from_user.id),
                    "created_at": self.store.now().strftime("%d %b %Y %H:%M:%S"),
                    "status": "active", "last_period": "", "last_error": "",
                    "next_run_date": self.core.next_autolike_run_date(kind="likeff"),
                    "seller_event_id": key,
                    "notification_bot_id": self.core.active_bot_for(message).token.split(":")[0],
                }
                self.store.reserve(message.from_user.id, key, "autolikeff", uid, package, order)
                self.reconcile_orders(orders)
        except (ValueError, SellerError) as exc:
            self.reply(message, f"❌ {exc}")
            return
        except Exception:
            self.core.logger.exception("Reseller order export failed")
            self.reply(message, "⚠️ Order processing interrupted. Check /seller history before retrying; saved orders will be recovered by the worker.")
            return
        threading.Thread(target=self.core.deliver_autolike_order_now, args=(order["order_id"], "likeff"), kwargs={"expected_order": dict(order)}, daemon=True).start()
        self.reply(message, "\n".join([
            "✅ AUTOLIKEFF ORDER CREATED", "━━━━━━━━━━━━━━━━━━━━━━━━",
            f"🧾 Order ID: {order['order_id']}", f"🆔 UID: {uid}",
            f"👤 Telegram User: {self.core.requester_name(message.from_user)}",
            f"🎯 Total Likes: {package:,}", "⏳ First delivery is processing now.",
        ]))

    def extend_order(self, message):
        self.remember(message.from_user)
        parts = message.text.split()
        try:
            if len(parts) != 3 or not parts[1].isascii() or not parts[1].isdigit() or not parts[2].isascii() or not parts[2].isdigit():
                raise SellerError("Use: /extend <uid> <package_likes>")
            uid, package = str(int(parts[1])), int(parts[2])
            package_price_cents(package)
            key = self.key(message)
            with self.core.autolike_lock:
                orders = self.core.load_autolike_orders("likeff")
                target = next((order for order in orders if str(order.get("uid")) == uid
                               and order.get("seller_event_id")
                               and str(order.get("created_by")) == str(message.from_user.id)
                               and order.get("status") in ("active", "completed")), None)
                if target is None:
                    raise SellerError("Your AutoLikeFF order was not found. No request or charge added.")
                payload = {**target, "_seller_extension": {"likes": package, "created_at": self.store.now().strftime("%d %b %Y %H:%M:%S")}}
                self.store.reserve(message.from_user.id, key, "autolikeff_extend", uid, package, payload)
                self.reconcile_orders(orders)
        except ValueError as exc:
            self.reply(message, f"❌ {exc}")
            return
        except Exception:
            self.core.logger.exception("Reseller extension export failed")
            self.reply(message, "⚠️ Extension processing interrupted. Check /seller history before retrying; saved extensions will be recovered by the worker.")
            return
        text = self.core.format_autolike_order(target, title="✅ AUTOLIKEFF ORDER EXTENDED", kind="likeff")
        self.core.active_bot_for(message).reply_to(message, text, parse_mode="HTML")

    def format_report(self, reports, day):
        lines = ["📊 RESELLER DAILY USAGE", "━━━━━━━━━━━━━━━━━━━━", f"📅 {day}"]
        for report in reports:
            charged = [e for e in report["events"] if e["state"] == "charged"]
            manual = [e for e in charged if e["kind"] == "likeff"]
            auto = [e for e in charged if e["kind"] in ("autolikeff", "autolikeff_extend")]
            auto_label = "orders/extensions" if any(e["kind"] == "autolikeff_extend" for e in auto) else "orders"
            lines.extend(["", f"👤 {report['name']}", f"🆔 {report['user_id']}",
                          f"📊 Requests used this day: {report['used']}",
                          f"🎟 Requests left now: {report['remaining']}",
                          f"💎 LikeFF: {len(manual)} req · {format_usd(sum(e['cents'] for e in manual))}",
                          f"🔁 AutoLikeFF: {len(auto)} {auto_label} · {sum(e['package'] for e in auto):,} likes"])
            packages = {}
            for event in auto:
                key = (event["package"], event["cents"])
                packages[key] = packages.get(key, 0) + 1
            for (package, cents), count in sorted(packages.items()):
                lines.append(f"  • {package:,} × {count} · {format_usd(cents * count)}")
            lines.extend([f"💵 Daily total: {format_usd(report['cents'])}",
                          f"✅ Paid: {format_usd(report['paid'])}",
                          f"🧾 Due: {format_usd(max(0, report['cents'] - report['paid']))}"])
            if report["pending"]:
                lines.append(f"⏳ Processing: {report['pending']} req")
            if not report["active"]:
                lines.append("⛔ Reseller disabled")
        if not reports:
            lines.append("\nNo resellers found.")
        elif len(reports) > 1:
            lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", f"💵 All sellers: {format_usd(sum(r['cents'] for r in reports))}",
                          f"🧾 Total due: {format_usd(sum(max(0, r['cents'] - r['paid']) for r in reports))}"])
        return "\n".join(lines)

    def history_text(self, user_id, page):
        events, _, _ = self.store.history_page(user_id, page)
        return self.format_history(user_id, events)

    def format_history(self, user_id, events):
        seller = self.store.seller(user_id)
        name = seller["name"] if seller else (events[0]["name"] if events else str(user_id))
        lines = ["📜 RESELLER HISTORY", "━━━━━━━━━━━━━━━━━━━━", "", f"👤 {name}", f"🆔 {user_id}"]
        for event in events:
            charge = event["cents"] if event["state"] == "charged" else 0
            lines.extend(["",
                          f"🕒 {event['created_at'][:19].replace('T', ' ')}",
                          f"{event['kind'].upper()} · UID {event['uid']}",
                          f"🎯 Package: {event['package']:,} · ❤️ Sent: {event['likes']:,}",
                          f"💵 {format_usd(charge)} · {event['state']}"])
        if not events:
            lines.extend(["", "No history yet."])
        return "\n".join(lines)

    def history_view(self, user_id, page=1):
        events, page, pages = self.store.history_page(user_id, page)
        keyboard = self.core.InlineKeyboardMarkup(row_width=3)
        buttons = []
        if page > 1:
            buttons.append(self.core.InlineKeyboardButton("⬅️ Previous", callback_data=f"sellerhist:{user_id}:{page - 1}"))
        if pages > 1:
            buttons.append(self.core.InlineKeyboardButton(f"{page} / {pages}", callback_data=f"sellerhist:{user_id}:{page}"))
        if page < pages:
            buttons.append(self.core.InlineKeyboardButton("Next ➡️", callback_data=f"sellerhist:{user_id}:{page + 1}"))
        if buttons:
            keyboard.row(*buttons)
        return self.format_history(user_id, events), keyboard if buttons else None

    def history_callback(self, call):
        active_bot = self.core.active_bot_for(call)
        try:
            prefix, target, raw_page = str(call.data or "").split(":")
            if prefix != "sellerhist" or not target.isascii() or not target.isdigit() or not raw_page.isascii() or not raw_page.isdigit():
                raise ValueError("Invalid page")
            if not (self.core.is_owner(call.from_user.id) or str(call.from_user.id) == target):
                active_bot.answer_callback_query(call.id, "You can only view your own history.", show_alert=True)
                return
            if not getattr(call, "message", None):
                raise ValueError("History message unavailable")
            text, keyboard = self.history_view(target, int(raw_page))
        except ValueError:
            active_bot.answer_callback_query(call.id, "Invalid history page.", show_alert=True)
            return
        # Acknowledge every tap, including tapping the current page indicator.
        active_bot.answer_callback_query(call.id)
        try:
            active_bot.edit_message_text(text=text, chat_id=call.message.chat.id,
                                         message_id=call.message.message_id, reply_markup=keyboard, parse_mode=None)
        except Exception as exc:
            if "message is not modified" not in str(exc).lower():
                self.core.logger.warning("Could not update reseller history page: %s", exc)

    def command(self, message):
        active_bot = self.core.active_bot_for(message)
        if self.core.command_belongs_to_other_bot(message, active_bot):
            return
        owner = self.core.is_owner(message.from_user.id)
        seller = self.store.seller(message.from_user.id)
        if not owner and not seller:
            self.reply(message, "⛔ Reseller access required.")
            return
        if seller:
            self.remember(message.from_user)
        args = message.text.split()[1:]
        try:
            if owner and len(args) == 2 and args[0].isascii() and args[0].isdigit() and args[1].isascii() and args[1].isdigit():
                user_id, limit = str(int(args[0])), int(args[1])
                if int(user_id) <= 0 or self.core.is_owner(int(user_id)):
                    raise SellerError("Choose a reseller's positive Telegram user ID")
                record = self.core.telegram_user_record(user_id)
                self.store.configure(user_id, record.get("name") or user_id, record.get("username") or "", limit, grant_id=self.key(message))
                remaining = self.store.report(user_id)[0]["remaining"]
                self.reply(message, f"✅ RESELLER REQUESTS ADDED\n━━━━━━━━━━━━━━━━━━━━\n👤 {record.get('name') or user_id}\n🆔 {user_id}\n➕ Added: {limit} req\n🎟 Requests left: {remaining}\n📌 No automatic reset")
                return
            if owner and len(args) == 2 and args[0] == "disable":
                self.store.disable(args[1])
                self.reply(message, "✅ Reseller disabled. History is preserved and existing orders continue.")
                return
            if owner and len(args) == 2 and args[0] == "payments":
                seller_record = self.store.seller(args[1])
                if not seller_record:
                    raise SellerError("Reseller not found")
                lines = ["📜 RESELLER PAYMENT HISTORY", "━━━━━━━━━━━━━━━━━━━━", f"👤 {seller_record['name']}", f"🆔 {args[1]}"]
                for entry in self.store.payment_history(args[1]):
                    delta = entry["after_cents"] - entry["before_cents"]
                    lines.extend(["", f"🕒 {entry['created_at'][:19].replace('T', ' ')}", f"📅 Bill: {entry['day']}",
                                  f"📌 {entry['action'].upper()} · {'+' if delta >= 0 else '-'}{format_usd(abs(delta))}",
                                  f"✅ Paid: {format_usd(entry['before_cents'])} → {format_usd(entry['after_cents'])}", f"👤 Changed by: {entry['actor_id']}"])
                if len(lines) == 4:
                    lines.extend(["", "No payment changes recorded yet."])
                self.reply(message, "\n".join(lines))
                return
            if owner and len(args) in (2, 3, 4) and args[0] == "paid":
                day, cents = self.store.day(), None
                if len(args) >= 3:
                    if len(args) == 3 and re.fullmatch(r"\d{4}-\d{2}-\d{2}", args[2]):
                        day = date.fromisoformat(args[2]).isoformat()
                    else:
                        if not re.fullmatch(r"[0-9]{1,9}(?:\.[0-9]{1,2})?", args[2]):
                            raise SellerError("Use a positive dollar amount with at most 2 decimal places, for example: /seller paid <id> 2.00")
                        whole, _, fraction = args[2].partition(".")
                        cents = int(whole) * 100 + int(fraction.ljust(2, "0"))
                        if len(args) == 4:
                            day = date.fromisoformat(args[3]).isoformat()
                bill = self.store.manual_bill(args[1], day)
                text, keyboard = self.bill_view(bill)
                intent_id = None
                if cents is not None:
                    intent_id = self.store.prepare_partial_payment(bill, cents, self.key(message))
                    text += f"\n\n💵 Payment received: {format_usd(cents)}\nTap Confirm payment to add this amount."
                    keyboard = self.core.InlineKeyboardMarkup(row_width=1)
                    keyboard.row(self.core.InlineKeyboardButton("✅ Confirm payment", callback_data=f"sellerbill:{bill['bill_id']}:partial{intent_id}"))
                try:
                    sent = self.core.bot.send_message(int(self.core.OWNER_ID), text, parse_mode=None, reply_markup=keyboard)
                except Exception:
                    self.core.logger.exception("Could not send manual reseller bill")
                    self.reply(message, "⚠️ Could not send your bill. Open the main bot's private chat, send /start, then retry /seller paid " + args[1] + ". Payment was not changed.")
                    return
                self.store.manual_bill_sent(bill["bill_id"], int(self.core.OWNER_ID), sent.message_id)
                if intent_id is not None:
                    self.store.partial_payment_sent(intent_id, int(self.core.OWNER_ID), sent.message_id)
                if message.chat.id != self.core.OWNER_ID or active_bot is not self.core.bot:
                    self.reply(message, "🧾 Bill sent to your private chat with the main bot. Use its button to record payment.")
                return
            if args and args[0] == "history":
                if owner:
                    if len(args) not in (2, 3):
                        raise SellerError("Use: /seller history <telegram_id>")
                    target, page = args[1], int(args[2]) if len(args) == 3 else 1
                else:
                    if len(args) > 2:
                        raise SellerError("Use: /seller history")
                    target, page = message.from_user.id, int(args[1]) if len(args) == 2 else 1
                if page < 1:
                    raise SellerError("Page must be positive")
                if not str(target).isascii() or not str(target).isdigit():
                    raise SellerError("Telegram ID must be a number")
                target = str(int(target))
                text, keyboard = self.history_view(target, page)
                active_bot.reply_to(message, text, parse_mode=None, reply_markup=keyboard)
                return
            if not args or (args[0] == "summary" and len(args) <= 2):
                day = date.fromisoformat(args[1]).isoformat() if len(args) == 2 else self.store.day()
                self.reply(message, self.format_report(self.store.report(None if owner else message.from_user.id, day), day))
                return
            if owner:
                raise SellerError("Use: /seller <id> <requests_to_add>, /seller summary [YYYY-MM-DD], /seller history <id>, /seller paid <id> [amount] [YYYY-MM-DD], /seller payments <id>, /seller disable <id>.")
            raise SellerError("Use: /seller, /seller history, /seller summary [YYYY-MM-DD]")
        except (ValueError, SellerError) as exc:
            self.reply(message, f"⚠️ {exc}")
