#!/usr/bin/env python3
"""Prune Paste clipboard history down to commands and links.

Usage:
  paste_prune.py report    read-only: category table, projected sizes, review.md
  paste_prune.py apply     prune (Paste must be quit)
  paste_prune.py verify    integrity and orphan checks

Policy: keep commands and links. Delete everything else, every item that holds a
credential, links that carry >100 KB page captures, and older duplicate copies
(the newest copy stays). Items in pinned lists are never touched.
"""
import csv, json, os, plistlib, re, shutil, sqlite3, subprocess, sys, time
from urllib.parse import quote

BASE = os.path.expanduser("~/Library/Application Support/com.wiheads.paste")
DB = os.path.join(BASE, "Paste.db")
SEARCH = os.path.join(BASE, "search.db")
EXT = os.path.join(BASE, ".Paste_SUPPORT/_EXTERNAL_DATA")
HERE = os.path.dirname(os.path.abspath(__file__))
REVIEW = os.path.join(HERE, "review.md")
HEAVY = 100 * 1024
MB = 1048576
KEEP_CATS = {"command", "url"}


def connect(path, readonly):
    if readonly:
        return sqlite3.connect(f"file:{quote(path)}?mode=ro", uri=True)
    return sqlite3.connect(path)


def pinned_pks(con):
    lists = [r[0] for r in con.execute(
        "SELECT Z_PK FROM ZSNIPPETLIST WHERE ZIDENTIFIER != 'sharedPasteboardHistory'")]
    q = f"SELECT Z_6SNIPPETS FROM Z_6LISTS WHERE Z_13LISTS IN ({','.join('?' * len(lists))})"
    return set(r[0] for r in con.execute(q, lists))


# ---------- blob decoding ----------
def ext_uuid(blob):
    return blob[1:37].decode("ascii", "ignore") if blob and blob[:1] == b"\x02" else None


def blob_payload(blob):
    if blob[:1] == b"\x01":
        return blob[1:]
    u = ext_uuid(blob)
    if u:
        fp = os.path.join(EXT, u)
        if not os.path.exists(fp):
            return None
        d = open(fp, "rb").read()
        return d[1:] if d[:1] == b"\x01" else d
    return blob


def extract_text(blob):
    data = blob_payload(blob)
    if not data:
        return ""
    try:
        obj = plistlib.loads(data)
    except Exception:
        return ""
    objs = obj.get("$objects", []) if isinstance(obj, dict) else []
    plain, html = [], []
    for o in objs:
        s = None
        if isinstance(o, str):
            if o == "$null" or o.startswith(("NS", "public.", "com.apple", "dyn.")) or "$" in o:
                continue
            s = o
        elif isinstance(o, bytes):
            try:
                s = o.decode("utf-8")
            except UnicodeDecodeError:
                continue
        if not s or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", s) or s.startswith("bplist"):
            continue  # binary fragments
        if re.fullmatch(r"[a-z0-9-]+(\.[A-Za-z0-9_-]+){2,}", s.strip()):
            continue  # pasteboard type identifiers like com.microsoft.Word.foo
        (html if s.strip().startswith(("<", "{\\rtf")) else plain).append(s)
    if plain:
        return max(plain, key=len)
    return max(html, key=len) if html else ""


# ---------- classifier ----------
CMDS = set("""git cd ls cat grep rg find awk sed echo export source cp mv rm mkdir touch chmod chown
curl wget ssh scp rsync tar zip unzip python python3 pip pip3 node npm npx yarn pnpm brew docker kubectl
helm terraform cdk sam aws brazil brazil-build brazil-recursive-cmd brazil-path mwinit ada cr sudo su repo
gh git-review kill killall pkill ps top df du tmux screen vim nano code open say defaults launchctl plutil
sqlite3 jq make cargo go java javac gradle gradlew mvn bash zsh sh adb fastboot logcat stat lsof netstat
dig nslookup ping kinit jupyter conda mise uv pytest pod xcodebuild codesign systemctl journalctl dmesg
mount umount diskutil hdiutil ip scutil networksetup""".split())
URL_RE = re.compile(r"https?://\S+")
ARN_RE = re.compile(r"arn:aws:")
HOST_RE = re.compile(r"^(dev-dsk-[\w-]+|[\w.-]*(amazon\.com|\.dev|\.net|\.io))$")


STOPWORDS = set("""a an the and or but if so to of in on at by for with from as is are was were be been
it its this that these those i we you he she they me us our your my their them what which who when where
why how can could should would will just not no do does did have has had there here then than also about
into over some any all more very really okay ok like""".split())
# English words that are also tool names: need technical evidence before counting as a command
AMBIGUOUS = set("make open say find source code top cat kill go screen mount pod touch ping dig stat "
                "export echo repo cr ada defaults".split())
SHELL_SIG = re.compile(r"(^|\s)--?[A-Za-z]|[|&;$`<>{}=]|~/|\./")
PROMPT = re.compile(r"^\s*(?:\(\d{2}-\d{2}-\d{2} [\d:]+\)\s*<\d+>\s*\[[^\]]*\]\s*\S+\s*[%$#]"
                    r"|\S+@\S+:\S*\s*[$#%]|\S*(?:dev-dsk|MacBook|\.local)\S*\s*[%$#]|\$)\s+")
LOG_LINE = re.compile(r"^\s*(\[?\d{2,4}[-/]\d{1,2}[-/]\d{1,4}|\[?\d{1,2}:\d{2}(:\d{2})?"
                      r"|(INFO|DEBUG|WARN(ING)?|ERROR|FATAL|TRACE)\b|[=*#~-]{5,}|[EWIDV]/\w+)")


def is_sentence(line):
    if SHELL_SIG.search(line):
        return False
    toks = [t.strip(".,;:!?\"'()[]") for t in line.split()]
    words = [t for t in toks if t.replace("'", "").isalpha()]
    return (len(words) >= 6 and len(words) >= 0.6 * len(toks)
            and sum(w.lower() in STOPWORDS for w in words) >= 0.25 * len(words))


def cmd_line(line):
    line = PROMPT.sub("", line, count=1).strip()
    if not line or is_sentence(line):
        return False
    toks = line.split()
    first = toks[0].strip("`$").lstrip("!").split("/")[-1]
    if first in CMDS:
        if first not in AMBIGUOUS:
            return True
        return bool(SHELL_SIG.search(line) or any(re.search(r"[./~_:=\d-]", t) for t in toks[1:])
                    or (len(toks) <= 3 and not any(t.lower() in STOPWORDS for t in toks)))
    env = re.match(r"^(?:[A-Z_][A-Z0-9_]*=\S*\s*)+(\S*)", line)  # FOO=1 or FOO=1 make ...
    if env and (not env.group(1) or env.group(1).split("/")[-1] in CMDS):
        return True
    return bool(line.startswith(("./", "~/", "/usr/", "/bin/", "/opt/"))
                or line.endswith(" \\")
                or " ssh://" in line
                or (re.match(r"^[\w./-]+\s", line) and len(line) < 600
                    and re.search(r"(^|\s)--?[A-Za-z][\w-]*(=|\s|$)", line)))


def is_cmd(t):
    lines = [l for l in t.splitlines() if l.strip() and not l.strip().startswith("#")]
    if not lines or len(lines) > 20:
        return False
    return sum(cmd_line(l) for l in lines) >= 0.5 * len(lines)


def is_output(t):
    lines = [l for l in t.splitlines() if l.strip()]
    if len(lines) < 3:
        return False
    if len(lines) > 5 and any(PROMPT.match(l) for l in lines):
        return True
    return sum(bool(LOG_LINE.match(l)) for l in lines) >= 0.4 * len(lines)


def prose_ratio(t):
    lines = [l for l in t.splitlines() if l.strip()]
    return sum(is_sentence(l) for l in lines) / len(lines) if lines else 0


SECRET_PATTERNS = [(k, re.compile(p)) for k, p in [
    ("private_key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("aws_key_id", r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("github", r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    ("slack", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("llm_key", r"\bsk-(ant-)?[A-Za-z0-9_-]{20,}"),
    ("google_key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    ("bearer", r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    ("telegram_bot", r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b"),
    ("npm", r"\bnpm_[A-Za-z0-9]{36}\b"),
    ("conn_string", r"\b\w+://[^\s:/@]+:[^\s@/]{3,}@"),
    ("assignment", r"(?i)\b(pass(word|wd|code)?|pwd|secret|token|api[_-]?key|access[_-]?key"
                   r"|client[_-]?secret|authorization)\b[\"']?\s*[:=]\s*[\"']?\S{4,}"),
    ("phrase", r"(?i)\b(password|passcode|passphrase|pin|pwd)\s+(is|was)\s+\S{4,}"),
]]


def looks_like_password(t):
    if not (8 <= len(t) <= 64) or re.search(r"\s", t):
        return False
    if t.startswith(("/", "~", "./")) or "://" in t or re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", t):
        return False
    if re.search(r"\.(com|net|org|io|py|txt|md|csv|json|log|sh|pdf|png|jpe?g|html?)$", t, re.I):
        return False
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", t):
        return False
    if re.fullmatch(r"[0-9a-fA-F-]+", t) and len(t) < 32:
        return False
    if re.fullmatch(r"[A-Za-z0-9-]+(\.[A-Za-z0-9_-]+){2,}", t):
        return False  # dotted identifiers like com.vendor.thing.v2
    mixed = all(re.search(p, t) for p in (r"[a-z]", r"[A-Z]", r"\d"))
    strong_symbol = re.search(r"[^A-Za-z0-9._-]", t)
    classes = sum(bool(re.search(p, t)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    return mixed or (strong_symbol and classes >= 3)


def secret_match(t):
    """(kind, match span) of the first credential-looking thing in t, else None."""
    for kind, rx in SECRET_PATTERNS:
        m = rx.search(t)
        if m:
            return kind, m.span()
    s = t.strip()
    return ("password_like", (0, len(t))) if looks_like_password(s) else None


def classify(t):
    t = t.strip()
    if not t:
        return "empty"
    if t[:1] in "{[":
        try:
            json.loads(t)
            return "json"
        except ValueError:
            pass
    if is_cmd(t):
        return "command"
    urls = URL_RE.findall(t)
    if urls and (sum(len(u) for u in urls) >= 0.6 * len(t) or len(t) < 200):
        return "url"
    if is_output(t):
        return "output"
    if prose_ratio(t) >= 0.5:
        return "prose"
    if ARN_RE.search(t) or HOST_RE.match(t):
        return "artifact"
    codey = sum([
        bool(re.search(r"[;{}]\s*$", t, re.M)),
        bool(re.search(r"\b(def|function|class|import|const|let|var|public|private|return|SELECT|FROM|WHERE)\b", t)),
        bool(re.search(r"^\s*[\w-]+:\s", t, re.M) and len(t.splitlines()) > 1),
        t[:1] == "<",
        bool(re.search(r"/[\w.-]+/[\w.-]+", t)),
    ])
    return "artifact" if codey >= 2 and len(t) < 8000 else "prose"


# ---------- load + select ----------
def load_items(con):
    pinned = pinned_pks(con)
    items = {}
    for pk, created, tlen, img, nfiles, thumb in con.execute(
            "SELECT Z_PK, ZCREATEDAT, ZTEXTLENGTH, ZIMAGESIZE, ZNUMBEROFFILES, "
            "COALESCE(length(ZPREVIEW),0)+COALESCE(length(ZPREVIEW1),0)+COALESCE(length(ZPREVIEW2),0) "
            "FROM ZSNIPPET"):
        items[pk] = dict(pk=pk, created=created or 0, tlen=tlen or 0, img=img, nfiles=nfiles or 0,
                         db=thumb, ext=0, uuids=[], text="", pinned=pk in pinned)
    for spk, blob in con.execute("SELECT ZSNIPPET, ZPASTEBOARDITEMS FROM ZSNIPPETDATA"):
        it = items.get(spk)
        if not it or not blob:
            continue
        it["db"] += len(blob)
        u = ext_uuid(blob)
        if u:
            it["uuids"].append(u)
            fp = os.path.join(EXT, u)
            it["ext"] += os.path.getsize(fp) if os.path.exists(fp) else 0
        txt = extract_text(blob)
        if len(txt) > len(it["text"]):
            it["text"] = txt
    for it in items.values():
        if it["img"] is not None and it["tlen"] == 0:
            it["cat"] = "image"
        elif it["nfiles"] > 0 and it["tlen"] == 0:
            it["cat"] = "file"
        else:
            it["cat"] = classify(it["text"])
        it["secret"] = secret_match(it["text"]) if it["text"] else None
        if it["secret"] and it["secret"][0] == "password_like" and it["ext"] > HEAVY:
            it["secret"] = None  # a copied password never carries a heavy rich payload
        if it["secret"]:
            it["cat"] = "secret"
    return list(items.values())


def select(items):
    kill, seen = [], set()
    for it in sorted(items, key=lambda i: -i["created"]):  # newest first: dedup keeps the newest copy
        key = (it["cat"], re.sub(r"\s+", " ", it["text"]).strip())
        if it["pinned"]:
            seen.add(key)
            continue
        if (it["cat"] not in KEEP_CATS or key in seen
                or (it["cat"] == "url" and it["ext"] > HEAVY)):
            kill.append(it)
        else:
            seen.add(key)
    return kill


def one_line(s, n):
    return re.sub(r"\s+", " ", s)[:n]


def rescue_lines(items, kill):
    """Command lines that exist only inside items being deleted."""
    norm = lambda l: re.sub(r"\s+", " ", PROMPT.sub("", l, count=1)).strip()
    killed = set(i["pk"] for i in kill)
    kept = set()
    for i in items:
        if i["pk"] not in killed:
            kept.update(norm(l) for l in i["text"].splitlines())
    out = {}
    for i in kill:
        for l in i["text"].splitlines():
            n = norm(l)
            if (cmd_line(l) and len(n) > 8 and n not in kept
                    and not re.fullmatch(r"[A-Z_][A-Z0-9_]*=\S*", n) and not secret_match(n)):
                out.setdefault(n, None)
    return list(out)


# ---------- commands ----------
def report():
    con = connect(DB, readonly=True)
    items = load_items(con)
    con.close()
    kill = select(items)
    killed = set(i["pk"] for i in kill)

    by = {}
    for it in items:
        b = by.setdefault(it["cat"], [0, 0, 0])
        b[0] += 1; b[1] += it["db"]; b[2] += it["ext"]
    print(f"snippets: {len(items)}   pinned (never touched): {sum(i['pinned'] for i in items)}\n")
    print(f"{'category':9}{'items':>7}{'db MB':>8}{'ext MB':>8}  action")
    for c in ("command", "url", "json", "artifact", "secret", "prose", "output", "image", "file", "empty"):
        if c in by:
            n, d, e = by[c]
            print(f"{c:9}{n:>7}{d / MB:>8.0f}{e / MB:>8.0f}  {'keep' if c in KEEP_CATS else 'DELETE'}")
    dups = sum(1 for i in kill if i["cat"] in KEEP_CATS)
    kept = [i for i in items if i["pk"] not in killed]
    print(f"\ndelete {len(kill)} items ({dups} of them duplicate or page-capture commands/links); "
          f"keep {len(kept)}: {sum(i['cat'] == 'command' for i in kept)} commands, "
          f"{sum(i['cat'] == 'url' for i in kept)} links, {sum(i['pinned'] for i in kept)} pinned")

    db_now = os.path.getsize(DB)
    ext_now = sum(os.path.getsize(os.path.join(EXT, f)) for f in os.listdir(EXT))
    s_now = sum(os.path.getsize(SEARCH + x) for x in ("", "-wal") if os.path.exists(SEARCH + x))
    total = kept_chars = 0
    sc = connect(SEARCH, readonly=True)
    for ident, n in sc.execute("SELECT identifier, length(content) FROM documents"):
        total += n or 0
        pk = ident.rsplit("/p", 1)[-1]
        if not (pk.isdigit() and int(pk) in killed):
            kept_chars += n or 0
    sc.close()
    rows = [("Paste.db", db_now, db_now - sum(i["db"] for i in kill)),
            ("external", ext_now, ext_now - sum(i["ext"] for i in kill)),
            ("search.db", s_now, s_now * kept_chars / total if total else s_now)]
    rows.append(("TOTAL", sum(r[1] for r in rows), sum(r[2] for r in rows)))
    print()
    for name, now, after in rows:
        print(f"  {name:10}{now / MB:8.0f} MB  ->  ~{after / MB:4.0f} MB")
    print(f"  disk freed once you delete the backup folder: ~{(rows[-1][1] - rows[-1][2]) / MB / 1024:.2f} GB")

    heavy = sorted((i for i in kill if i["cat"] == "url" and i["ext"] > HEAVY), key=lambda i: -i["ext"])
    cats = lambda c: [i for i in items if i["cat"] == c]
    with open(REVIEW, "w") as f:
        f.write("# Paste prune review\n\nContains clipboard plaintext. Delete this file after review.\n")
        cmds = sorted((i for i in kept if i["cat"] == "command"), key=lambda i: i["text"].lower())
        f.write(f"\n## COMMANDS, kept ({len(cmds)})\n\n")
        f.writelines(f"- `{one_line(i['text'], 200).replace('`', chr(39))}`\n" for i in cmds)
        for c in ("json", "artifact"):
            f.write(f"\n## {c.upper()}, deleted ({len(cats(c))}), first 40\n\n")
            f.writelines(f"- {one_line(i['text'], 160)}\n" for i in cats(c)[:40])
        secrets = [i for i in kill if i["secret"]]
        f.write(f"\n## CREDENTIALS, deleted ({len(secrets)}), values masked\n\n")
        for i in secrets:
            kind, (a, b) = i["secret"]
            val = i["text"][a:b].strip()
            f.write(f"- {kind} | ...{one_line(i['text'][max(0, a - 40):a], 40)}[{val[:2]}…{len(val)} chars]\n")
        f.write(f"\n## PAGE-CAPTURE LINKS, deleted ({len(heavy)})\n\n")
        f.writelines(f"- {i['ext'] / MB:.1f} MB | {one_line(i['text'], 140)}\n" for i in heavy)
        prose = sorted(cats("prose"), key=lambda i: -i["created"])
        f.write(f"\n## PROSE, deleted ({len(prose)}), newest 100\n\n")
        f.writelines(f"- {one_line(i['text'], 140)}\n" for i in prose[:100])
    print(f"\nreview file: {REVIEW}")


def apply():
    if subprocess.run(["pgrep", "-x", "Paste"], capture_output=True).stdout.strip():
        sys.exit("ABORT: Paste is running. Quit it first (menu bar icon > Quit Paste).")

    con = connect(DB, readonly=False)
    items = load_items(con)
    kill = select(items)
    pks = [i["pk"] for i in kill]
    rescued = rescue_lines(items, kill)
    with open(os.path.join(HERE, "rescued_commands.txt"), "w") as f:
        f.write("\n".join(rescued) + "\n")
    print(f"rescued {len(rescued)} command lines -> {os.path.join(HERE, 'rescued_commands.txt')}")

    bdir = os.path.join(HERE, "backup-" + time.strftime("%Y%m%d-%H%M%S"))
    os.makedirs(os.path.join(bdir, "ext"))
    for src, name in ((DB, "Paste.db"), (SEARCH, "search.db")):
        if os.path.exists(src):
            s, d = sqlite3.connect(src), sqlite3.connect(os.path.join(bdir, name))
            s.backup(d)
            d.close(); s.close()
    with open(os.path.join(bdir, "manifest.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pk", "category", "external_uuids"])
        w.writerows((i["pk"], i["cat"], " ".join(i["uuids"])) for i in kill)
    print(f"backup: {bdir}")

    con.execute("CREATE TEMP TABLE _k(pk INTEGER PRIMARY KEY)")
    with con:
        con.executemany("INSERT INTO _k VALUES(?)", [(p,) for p in pks])
        con.execute("DELETE FROM Z_6LISTS WHERE Z_6SNIPPETS IN (SELECT pk FROM _k)")
        con.execute("DELETE FROM ZSNIPPETDATA WHERE ZSNIPPET IN (SELECT pk FROM _k)")
        con.execute("DELETE FROM ZSNIPPET WHERE Z_PK IN (SELECT pk FROM _k)")
    con.execute("VACUUM")
    con.close()
    print(f"deleted {len(pks)} snippets from Paste.db")

    if os.path.exists(SEARCH):
        killset = set(pks)
        sc = sqlite3.connect(SEARCH)
        drop = [(ident,) for (ident,) in sc.execute("SELECT identifier FROM documents")
                if ident.rsplit("/p", 1)[-1].isdigit() and int(ident.rsplit("/p", 1)[-1]) in killset]
        with sc:
            sc.executemany("DELETE FROM documents WHERE identifier=?", drop)
        sc.execute("VACUUM")
        sc.close()
        print(f"deleted {len(drop)} rows from search.db")

    moved = 0
    for i in kill:
        for u in i["uuids"]:
            src = os.path.join(EXT, u)
            if os.path.exists(src):
                shutil.move(src, os.path.join(bdir, "ext", u))
                moved += 1
    print(f"moved {moved} external files to backup")
    print(f"\nrestore: cp '{bdir}/Paste.db' '{DB}' && cp '{bdir}/search.db' '{SEARCH}' && "
          f"rm -f '{SEARCH}-wal' '{SEARCH}-shm' && mv '{bdir}/ext/'* '{EXT}/'")
    verify()


def verify():
    con = connect(DB, readonly=True)
    q = lambda sql: con.execute(sql).fetchone()[0]
    snippets = q("SELECT count(*) FROM ZSNIPPET")
    refs = set(ext_uuid(b) for (b,) in con.execute("SELECT ZPASTEBOARDITEMS FROM ZSNIPPETDATA")
               if ext_uuid(b))
    files = set(os.listdir(EXT))
    print("\n=== verify ===")
    print(f"integrity_check:          {q('PRAGMA integrity_check')}")
    print(f"snippets:                 {snippets}")
    print(f"pinned snippets:          {len(pinned_pks(con))}")
    print(f"data rows w/o snippet:    {q('SELECT count(*) FROM ZSNIPPETDATA WHERE ZSNIPPET NOT IN (SELECT Z_PK FROM ZSNIPPET)')}")
    print(f"list rows w/o snippet:    {q('SELECT count(*) FROM Z_6LISTS WHERE Z_6SNIPPETS NOT IN (SELECT Z_PK FROM ZSNIPPET)')}")
    print(f"external refs missing:    {len(refs - files)}")
    print(f"external files unrefd:    {len(files - refs)}")
    con.close()
    if os.path.exists(SEARCH):
        sc = connect(SEARCH, readonly=True)
        print(f"search.db rows:           {sc.execute('SELECT count(*) FROM documents').fetchone()[0]}")
        sc.close()
    print(f"Paste.db size:            {os.path.getsize(DB) / MB:.0f} MB")
    print(f"external size:            {sum(os.path.getsize(os.path.join(EXT, f)) for f in files) / MB:.0f} MB")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    if cmd == "report":
        report()
    elif cmd == "apply":
        apply()
    elif cmd == "verify":
        verify()
    else:
        sys.exit(__doc__)
