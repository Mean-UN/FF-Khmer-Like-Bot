import json
import sys
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

import lssj

UIDPASS_FILE = "uidpass.json"
TOKEN_FILE = "tokens.json"
FILE_SETS = {
    "like": ("uidpass.json", "tokens.json"),
    "likeff": ("uidpass_likeff.json", "tokens_likeff.json"),
}


def parse_args(argv):
    args = list(argv)
    slot = None
    if "--slot" in args:
        index = args.index("--slot")
        try:
            slot = int(args[index + 1])
        except (IndexError, ValueError):
            raise ValueError("--slot requires a number")
        del args[index:index + 2]
    return args, slot


def slot_filename(filename, set_name, slot=None):
    if set_name == "likeff" and slot:
        root, dot, ext = filename.rpartition(".")
        if not dot:
            return f"{filename}_{slot}"
        return f"{root}_{slot}.{ext}"
    return filename


def read_uidpass(uidpass_file):
    with open(uidpass_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{uidpass_file} must contain a list of uid/password objects")
    return data


def fetch_jwt(uid, password):
    try:
        with requests.Session() as session:
            for attempt in range(3):
                try:
                    return lssj.fetch_guest_jwt_for_like_with_retry(uid, password, max_retries=1, session=session)
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(2 ** (attempt + 1))
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        raise RuntimeError(str(exc) or exc.__class__.__name__) from None


def update_token_file(tokens, token_file):
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=os.path.dirname(os.path.abspath(token_file)), delete=False) as f:
            name = f.name
            json.dump(tokens, f, ensure_ascii=False, indent=4)
        for attempt in range(6):
            try:
                os.replace(name, token_file)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.1 * (2 ** attempt))
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def read_tokens(token_file):
    try:
        with open(token_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []


def update_single_token(set_name, uid, password, slot=None):
    if set_name not in FILE_SETS:
        print(f"Unknown token set: {set_name}. Use one of: {', '.join(FILE_SETS)}")
        return 2
    _, token_file = FILE_SETS[set_name]
    token_file = slot_filename(token_file, set_name, slot)
    try:
        token_item = fetch_jwt(uid, password)
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        print(f"failed UID {uid}: {exc}")
        return 1
    tokens = read_tokens(token_file)
    uid = str(uid)
    replaced = False
    updated_tokens = []
    for item in tokens:
        if isinstance(item, dict) and str(item.get("uid")) == uid:
            if not replaced:
                updated_tokens.append(token_item)
                replaced = True
            continue
        updated_tokens.append(item)
    if not replaced:
        updated_tokens.append(token_item)
    update_token_file(updated_tokens, token_file)
    print(f"{token_file} updated for UID {uid}.")
    return 0


def main():
    try:
        args, slot = parse_args(sys.argv[1:])
    except ValueError as exc:
        print(str(exc))
        return 2
    set_name = args[0].lower() if len(args) > 0 else "like"
    if len(args) >= 3:
        return update_single_token(set_name, args[1], args[2], slot)
    if set_name not in FILE_SETS:
        print(f"Unknown token set: {set_name}. Use one of: {', '.join(FILE_SETS)}")
        return 2
    uidpass_file, token_file = FILE_SETS[set_name]
    uidpass_file = slot_filename(uidpass_file, set_name, slot)
    token_file = slot_filename(token_file, set_name, slot)
    accounts = read_uidpass(uidpass_file)
    tokens = []
    failures = []
    duplicate_uids = []
    seen_uids = set()

    unique_accounts = []
    for account in accounts:
        uid = account.get("uid") if isinstance(account, dict) else None
        password = account.get("password") if isinstance(account, dict) else None
        if not uid or not password:
            failures.append({"uid": uid or "N/A", "password": password or "N/A", "error": "missing uid or password"})
            continue
        uid = str(uid)
        if uid in seen_uids:
            duplicate_uids.append(uid)
            continue
        seen_uids.add(uid)
        unique_accounts.append((uid, password))

    def report_progress():
        print("REFRESH_PROGRESS " + json.dumps({
            "refreshed": len(tokens), "failed": len(failures),
            "unfinished": len(accounts) - len(duplicate_uids) - len(tokens) - len(failures),
            "duplicates": len(duplicate_uids), "duplicate_uids": duplicate_uids,
        }), flush=True)

    report_progress()

    def refresh_account(account):
        uid, password = account
        try:
            return fetch_jwt(uid, password), None
        except Exception:
            return None, {"uid": uid}

    saved_tokens = {str(item.get("uid")): item for item in read_tokens(token_file)
                    if isinstance(item, dict) and str(item.get("uid")) in seen_uids}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(refresh_account, account) for account in unique_accounts]
        for future in as_completed(jobs):
            token, failure = future.result()
            if failure:
                failures.append(failure)
                report_progress()
                print(f"failed UID {failure['uid']}")
            else:
                tokens.append(token)
                report_progress()
                saved_tokens[str(token["uid"])] = token
                # Batch checkpoints to avoid rewriting a large file per account.
                if len(tokens) == 1 or len(tokens) % 20 == 0:
                    update_token_file(list(saved_tokens.values()), token_file)
                print(f"updated token for UID {token['uid']}")

    if tokens or not accounts:
        update_token_file(list(saved_tokens.values()) if accounts else [], token_file)
        print(f"{token_file} updated with {len(tokens)} token(s).")
    else:
        print("No tokens refreshed; existing token file preserved.")
    print("REFRESH_STATS " + json.dumps({"refreshed": len(tokens), "failed": len(failures)}))
    if failures:
        print("")
        print("🔄 UID/PASS Token Refresh Report")
        print("")
        print(f"🔁 Duplicate skipped: {len(duplicate_uids)}")
        print(f"❌ Failed token: {len(failures)}")
        print("")
        print("")
        print(f"🆔 Duplicate UID: {', '.join(duplicate_uids) if duplicate_uids else 'None'}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
