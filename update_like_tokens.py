import json
import sys

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
        return lssj.fetch_guest_jwt_for_like_with_retry(uid, password)
    except BaseException as exc:
        if isinstance(exc, KeyboardInterrupt):
            raise
        raise RuntimeError(str(exc) or exc.__class__.__name__) from None


def update_token_file(tokens, token_file):
    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(tokens, f, ensure_ascii=False, indent=4)


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

    for account in accounts:
        uid = account.get("uid")
        password = account.get("password")
        if not uid or not password:
            failures.append({"uid": uid or "N/A", "password": password or "N/A", "error": "missing uid or password"})
            continue
        uid = str(uid)
        if uid in seen_uids:
            duplicate_uids.append(uid)
            continue
        seen_uids.add(uid)
        try:
            tokens.append(fetch_jwt(uid, password))
            print(f"updated token for UID {uid}")
        except BaseException as e:
            if isinstance(e, KeyboardInterrupt):
                raise
            failures.append({"uid": uid, "password": password, "error": str(e)})
            print(f"failed UID {uid}: {e}")

    update_token_file(tokens, token_file)
    print(f"{token_file} updated with {len(tokens)} token(s).")
    if failures:
        print("")
        print("🔄 UID/PASS Token Refresh Report")
        print("")
        print(f"🔁 Duplicate skipped: {len(duplicate_uids)}")
        print(f"❌ Failed token: {len(failures)}")
        print("")
        print("")
        print(f"🆔 Duplicate UID: {', '.join(duplicate_uids) if duplicate_uids else 'None'}")
        print("🔐 Failed UID/PASS:")
        for item in failures:
            print(f"- {item['uid']}:{item['password']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
