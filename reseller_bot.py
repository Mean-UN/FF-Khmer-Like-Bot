"""Telegram reseller commands; all external actions use the existing bot helpers."""
import os
import threading
from datetime import date

from reseller_pricing import PACKAGE_PRICES_CENTS, format_usd, package_price_cents
from reseller_store import ResellerStore, SellerError


class ResellerFeatures:
    def __init__(self, core):
        self.core = core
        self.store = ResellerStore(os.path.join(core.BASE_DIR, "resellers.sqlite3"))

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
                    "group_id": "", "created_by": str(message.from_user.id),
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
        events = self.store.history(user_id, page=page)
        lines = [f"📜 RESELLER HISTORY · Page {page}", "━━━━━━━━━━━━━━━━━━━━"]
        for event in events:
            charge = event["cents"] if event["state"] == "charged" else 0
            lines.extend(["", f"👤 {event['name']} · {event['user_id']}",
                          f"🕒 {event['created_at'][:19].replace('T', ' ')}",
                          f"{event['kind'].upper()} · UID {event['uid']}",
                          f"🎯 Package: {event['package']:,} · ❤️ Sent: {event['likes']:,}",
                          f"💵 {format_usd(charge)} · {event['state']}"])
            if event["detail"]:
                lines.append(event["detail"][:200])
        if not events:
            lines.append("No history on this page.")
        lines.append("\nUse the next page number to see older history.")
        return "\n".join(lines)

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
            if owner and len(args) == 3 and args[0] == "paid":
                day = date.fromisoformat(args[2]).isoformat()
                cents = self.store.mark_paid(args[1], day, command_id=self.key(message))
                self.reply(message, f"✅ Recorded payment: {format_usd(cents)}\n📅 {day}\n🆔 {args[1]}")
                return
            if args and args[0] == "history":
                if owner:
                    if len(args) not in (2, 3):
                        raise SellerError("Use: /seller history <telegram_id> [page]")
                    target, page = args[1], int(args[2]) if len(args) == 3 else 1
                else:
                    if len(args) > 2:
                        raise SellerError("Use: /seller history [page]")
                    target, page = message.from_user.id, int(args[1]) if len(args) == 2 else 1
                if page < 1:
                    raise SellerError("Page must be positive")
                self.reply(message, self.history_text(target, page))
                return
            if not args or (args[0] == "summary" and len(args) <= 2):
                day = date.fromisoformat(args[1]).isoformat() if len(args) == 2 else self.store.day()
                self.reply(message, self.format_report(self.store.report(None if owner else message.from_user.id, day), day))
                return
            raise SellerError("Owner: /seller <id> <requests_to_add>, /seller summary [YYYY-MM-DD], /seller history <id> [page], /seller paid <id> <YYYY-MM-DD>, /seller disable <id>\nReseller: /seller, /seller history [page], /seller summary [YYYY-MM-DD]")
        except (ValueError, SellerError) as exc:
            self.reply(message, f"⚠️ {exc}")
