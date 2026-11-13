import re
import sqlite3
import traceback
import uuid
from datetime import datetime

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
DEFAULT_SOURCE = "mangadex"

TABLES_V2 = {
        "author": {
                "uid":        {"pri":True,  "type":"varchar", "def":""},
                "name":       {"pri":False, "type":"varchar", "def":""},
                "ignore":     {"pri":False, "type":"boolean", "def":0},
        },
        "author_ref": {
                "plugin":     {"pri":True,  "type":"varchar", "def":DEFAULT_SOURCE},
                "ext_id":     {"pri":True,  "type":"varchar", "def":""},
                "author_uid": {"pri":False, "type":"varchar", "def":None},
                "favorite":   {"pri":False, "type":"boolean", "def":0},
                "deleted":    {"pri":False, "type":"boolean", "def":0},
        },
        "tgroup": {
                "uid":        {"pri":True,  "type":"varchar", "def":""},
                "name":       {"pri":False, "type":"varchar", "def":""},
                "ignore":     {"pri":False, "type":"boolean", "def":0},
        },
        "tgroup_ref": {
                "plugin":     {"pri":True,  "type":"varchar", "def":DEFAULT_SOURCE},
                "ext_id":     {"pri":True,  "type":"varchar", "def":""},
                "tgroup_uid": {"pri":False, "type":"varchar", "def":None},
                "fake":       {"pri":False, "type":"boolean", "def":0},
                "deleted":    {"pri":False, "type":"boolean", "def":0},
        },
        "series": {
                "uid":        {"pri":True,  "type":"varchar", "def":""},
                "name":       {"pri":False, "type":"varchar", "def":""},
                "forceName":  {"pri":False, "type":"varchar", "def":None},
                "image":      {"pri":False, "type":"blob",    "def":None},
                "imageName":  {"pri":False, "type":"varchar", "def":""},
                "fixedImage": {"pri":False, "type":"boolean", "def":0},
                "priority":   {"pri":False, "type":"integer", "def":""},
                "h":          {"pri":False, "type":"boolean", "def":0},
                "nameWarn":   {"pri":False, "type":"boolean", "def":0},
        },
        "series_ref": {
                "plugin":     {"pri":True,  "type":"varchar", "def":DEFAULT_SOURCE},
                "ext_id":     {"pri":True,  "type":"varchar", "def":""},
                "series_uid": {"pri":False, "type":"varchar", "def":None},
                "favorite":   {"pri":False, "type":"boolean", "def":0},
                "lastUpdate": {"pri":False, "type":"varchar", "def":""},
                "lastCheck":  {"pri":False, "type":"varchar", "def":""},
        },
        "series_author": {
                "series_uid": {"pri":True,  "type":"varchar", "def":None},
                "author_uid": {"pri":True,  "type":"varchar", "def":None},
                "role":       {"pri":True,  "type":"varchar", "def":"author"},
        },
        "chapter": {
                "uid":        {"pri":True,  "type":"varchar", "def":""},
                "series_uid": {"pri":False, "type":"varchar", "def":None},
                "title":      {"pri":False, "type":"varchar", "def":""},
                "volume":     {"pri":False, "type":"varchar", "def":""},
                "chapter":    {"pri":False, "type":"varchar", "def":""},
                "language":   {"pri":False, "type":"varchar", "def":""},
                "time":       {"pri":False, "type":"varchar", "def":""},
                "got":        {"pri":False, "type":"boolean", "def":0},
        },
        "chapter_ref": {
                "plugin":      {"pri":True,  "type":"varchar", "def":DEFAULT_SOURCE},
                "ext_id":      {"pri":True,  "type":"varchar", "def":""},
                "chapter_uid": {"pri":False, "type":"varchar", "def":None},
        },
        "chapter_tgroup": {
                "chapter_uid": {"pri":True, "type":"varchar", "def":None},
                "tgroup_uid":  {"pri":True, "type":"varchar", "def":None},
        },
        "queue": {
                "ext_id":     {"pri":True,  "type":"varchar", "def":""},
                "plugin":     {"pri":True,  "type":"varchar", "def":DEFAULT_SOURCE},
                "type":       {"pri":True,  "type":"varchar", "def":""},
                "name":       {"pri":False, "type":"varchar", "def":""},
                "parent_uid": {"pri":False, "type":"varchar", "def":None},
                "status":     {"pri":False, "type":"varchar", "def":"pending"},
                "statusText": {"pri":False, "type":"varchar", "def":"pending"},
        },
        "merged": {
                "old_uid":    {"pri":True,  "type":"varchar", "def":""},
                "new_uid":    {"pri":False, "type":"varchar", "def":""},
        },
}

REF_TABLES_V2 = {
        "author_ref":     {"author_uid":  {"table":"author",  "col":"uid"}},
        "tgroup_ref":     {"tgroup_uid":  {"table":"tgroup",  "col":"uid"}},
        "series_ref":     {"series_uid":  {"table":"series",  "col":"uid"}},
        "series_author":  {"series_uid":  {"table":"series",  "col":"uid"},
                           "author_uid":  {"table":"author",  "col":"uid"}},
        "chapter":        {"series_uid":  {"table":"series",  "col":"uid"}},
        "chapter_ref":    {"chapter_uid": {"table":"chapter", "col":"uid"}},
        "chapter_tgroup": {"chapter_uid": {"table":"chapter", "col":"uid"},
                           "tgroup_uid":  {"table":"tgroup",  "col":"uid"}},
}

def newUid() -> str:
        return str(getattr(uuid, "uuid7", uuid.uuid4)())

def normSource(v) -> str:
        v = "" if v is None else str(v).strip()
        return DEFAULT_SOURCE if v in ("", "0", "1", "None", "null") else v

def rowSource(r, default=DEFAULT_SOURCE) -> str:
        return normSource(r["source"]) if "source" in r.keys() else default

def splitIds(v) -> list:
        return [] if v is None else [i.strip() for i in str(v).split(",") if i.strip()]

def createSql(table:str, tables:dict, refTables:dict) -> str:
        cols, pri = [], []
        for col, d in tables[table].items():
                c = f"{col} {d['type'].upper()} " + ("DEFAULT NULL" if d.get("def") is None else f"DEFAULT '{d['def']}'")
                ref = refTables.get(table, {}).get(col)
                if ref:
                        c += f" REFERENCES {ref['table']}({ref['col']})"
                cols.append(c)
                if d["pri"]:
                        pri.append(col)
        if pri:
                cols.append(f"PRIMARY KEY({','.join(pri)})")
        return f"CREATE TABLE {table} ({', '.join(cols)})"

def backupDB(dbPath:str, logged) -> None:
        loc = f"{dbPath}_{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
        logged(f"Backing up database to {loc}...")
        try:
                src, dst = sqlite3.connect(dbPath), sqlite3.connect(loc)
                with dst:
                        src.backup(dst)
                src.close()
                dst.close()
        except Exception as e:
                logged(traceback.format_exc())
                raise RuntimeError(f"Cannot backup database, aborting update: {e}")
        logged("Backup completed")

def migrateV1toV2(db, logged, keepOld=False) -> None:
        cur = db.cursor()
        cur.row_factory = sqlite3.Row
        changed = ["series", "author", "tgroup", "chapter", "queue"]
        for t in changed:
                logged(f"Renaming table {t} to {t}_old...")
                cur.execute(f"ALTER TABLE {t} RENAME TO {t}_old")
        for t in TABLES_V2:
                logged(f"Creating table {t}...")
                cur.execute(createSql(t, TABLES_V2, REF_TABLES_V2))

        maps = {k: {} for k in ("author", "tgroup", "series", "chapter")}
        dup = {k: 0 for k in maps}
        stub = {k: 0 for k in maps}
        alias = {k: 0 for k in maps}
        stats = {"named": 0, "srcFixed": 0}
        extSources = {"author": {}, "tgroup": {}}

        def ensure(kind, src, ext):
                uid = maps[kind].get((src, ext))
                if uid is not None:
                        return uid
                cand = extSources.get(kind, {}).get(ext, set())
                if len(cand) == 1:
                        uid = maps[kind][(next(iter(cand)), ext)]
                        maps[kind][(src, ext)] = uid
                        alias[kind] += 1
                        if kind == "tgroup":
                                other = next(iter(cand))
                                cur.execute("INSERT INTO tgroup_ref (plugin,ext_id,tgroup_uid,fake,deleted) SELECT ?,?,tgroup_uid,fake,deleted FROM tgroup_ref WHERE plugin=? AND ext_id=?", (src, ext, other, ext))
                                return uid
                else:
                        uid = newUid()
                        maps[kind][(src, ext)] = uid
                        stub[kind] += 1
                        if kind == "tgroup" and src == "mangadex" and not UUID_RE.match(ext):
                                stats["named"] += 1
                                cur.execute("INSERT INTO tgroup (uid, name) VALUES (?,?)", (uid, ext))
                        else:
                                cur.execute(f"INSERT INTO {kind} (uid) VALUES (?)", (uid,))
                cur.execute(f"INSERT INTO {kind}_ref (plugin, ext_id, {kind}_uid) VALUES (?,?,?)", (src, ext, uid))
                return uid

        def isDup(kind, key):
                if key in maps[kind]:
                        dup[kind] += 1
                        return True
                return False

        logged("Converting author...")
        for r in cur.execute("SELECT * FROM author_old").fetchall():
                src = rowSource(r); key = (src, r["id"])
                if isDup("author", key): continue
                uid = maps["author"][key] = newUid()
                cur.execute("INSERT INTO author (uid,name,ignore) VALUES (?,?,?)", (uid, r["name"], r["ignore"]))
                cur.execute("INSERT INTO author_ref (plugin,ext_id,author_uid,favorite,deleted) VALUES (?,?,?,?,?)", (src, r["id"], uid, r["favorite"], r["deleted"]))

        logged("Converting tgroup...")
        for r in cur.execute("SELECT * FROM tgroup_old").fetchall():
                src = rowSource(r); key = (src, r["id"])
                if isDup("tgroup", key): continue
                uid = maps["tgroup"][key] = newUid()
                cur.execute("INSERT INTO tgroup (uid,name,ignore) VALUES (?,?,?)", (uid, r["name"], r["ignore"]))
                cur.execute("INSERT INTO tgroup_ref (plugin,ext_id,tgroup_uid,fake,deleted) VALUES (?,?,?,?,?)", (src, r["id"], uid, r["fake"], r["deleted"]))

        for k in extSources:
                for (sc, ex) in maps[k]:
                        extSources[k].setdefault(ex, set()).add(sc)

        logged("Converting series...")
        altIds = 0
        for r in cur.execute("SELECT * FROM series_old").fetchall():
                src = normSource(r["source"]); key = (src, r["id"])
                if isDup("series", key): continue
                uid = maps["series"][key] = newUid()
                altIds += 1 if r["altId"] else 0
                cur.execute("INSERT INTO series (uid,name,forceName,image,imageName,fixedImage,priority,h,nameWarn) VALUES (?,?,?,?,?,?,?,?,?)",
                            (uid, r["name"], r["forceName"], r["image"], r["imageName"], r["fixedImage"], r["priority"], r["h"], r["nameWarn"]))
                cur.execute("INSERT INTO series_ref (plugin,ext_id,series_uid,favorite,lastUpdate,lastCheck) VALUES (?,?,?,?,?,?)",
                            (src, r["id"], uid, r["favorite"], r["lastUpdate"], r["lastCheck"]))
                for role in ("author", "artist"):
                        for aid in splitIds(r[role]):
                                cur.execute("INSERT OR IGNORE INTO series_author (series_uid,author_uid,role) VALUES (?,?,?)",
                                            (uid, ensure("author", src, aid), role))
        if altIds:
                logged(f"{altIds} series had altId; it is dropped (kept in series_old if keepOld is set)")

        logged("Converting chapter...")
        seriesSources = {}
        for (sc, ex) in maps["series"]:
                seriesSources.setdefault(ex, set()).add(sc)
        orphans = 0
        chHasSource = "source" in [c[1] for c in cur.execute("PRAGMA table_info(chapter_old)")]
        seriesSrc = {}
        if not chHasSource:
                for sr in cur.execute("SELECT id, source FROM series_old").fetchall():
                        seriesSrc.setdefault(sr["id"], set()).add(normSource(sr["source"]))
        ambiguous = 0
        def chapterSource(r):
                nonlocal ambiguous
                if chHasSource:
                        return normSource(r["source"])
                found = seriesSrc.get(r["series"], set())
                if len(found) > 1:
                        ambiguous += 1
                return next(iter(found)) if len(found) == 1 else DEFAULT_SOURCE
        for r in cur.execute("SELECT * FROM chapter_old").fetchall():
                src = chapterSource(r)
                if r["series"] and (src, r["series"]) not in maps["series"]:
                        cand = seriesSources.get(r["series"], set())
                        if len(cand) == 1:
                                src = next(iter(cand)); stats["srcFixed"] += 1
                key = (src, r["id"])
                if isDup("chapter", key): continue
                uid = maps["chapter"][key] = newUid()
                suid = ensure("series", src, r["series"]) if r["series"] else None
                orphans += 1 if suid is None else 0
                cur.execute("INSERT INTO chapter (uid,series_uid,title,volume,chapter,language,time,got) VALUES (?,?,?,?,?,?,?,?)",
                            (uid, suid, r["title"], r["volume"], r["chapter"], r["language"], r["time"], r["got"]))
                cur.execute("INSERT INTO chapter_ref (plugin,ext_id,chapter_uid) VALUES (?,?,?)", (src, r["id"], uid))
                for gid in splitIds(r["tgroup"]):
                        cur.execute("INSERT OR IGNORE INTO chapter_tgroup (chapter_uid,tgroup_uid) VALUES (?,?)", (uid, ensure("tgroup", src, gid)))
        if orphans:
                logged(f"{orphans} chapters have no series id (series_uid left empty)")
        if ambiguous:
                logged(f"{ambiguous} chapters belong to a series id that exists under several sources; used {DEFAULT_SOURCE}")

        logged("Converting queue...")
        unresolved = 0
        for r in cur.execute("SELECT * FROM queue_old").fetchall():
                src = normSource(r["source"])
                puid = maps["series"].get((src, r["parent"])) if r["parent"] else None
                unresolved += 1 if r["parent"] and puid is None else 0
                cur.execute("INSERT OR IGNORE INTO queue (ext_id,plugin,type,name,parent_uid,status,statusText) VALUES (?,?,?,?,?,?,?)",
                            (r["id"], src, r["type"], r["name"], puid, r["status"], r["statusText"]))
        if unresolved:
                logged(f"{unresolved} queue rows have a parent that is not a known series (parent_uid left empty)")

        logged("Converting settings...")
        row = cur.execute("SELECT value FROM settings WHERE key='appBGCover'").fetchone()
        if row and row["value"]:
                m = cur.execute("SELECT series_uid FROM series_ref WHERE ext_id=? ORDER BY plugin=? DESC LIMIT 1", (row["value"], DEFAULT_SOURCE)).fetchone()
                cur.execute("UPDATE settings SET value=? WHERE key='appBGCover'", (m["series_uid"] if m else "",))

        logged("Normalising boolean columns...")
        for t, cols in TABLES_V2.items():
                for c, d in cols.items():
                        if d["type"] == "boolean":
                                cur.execute(f"UPDATE {t} SET {c} = CASE WHEN {c} IN (1,'1','true','True','TRUE') THEN 1 ELSE 0 END "
                                            f"WHERE typeof({c}) != 'integer' OR {c} NOT IN (0,1)")

        logged("Verifying...")
        for kind in maps:
                old = cur.execute(f"SELECT COUNT(*) FROM {kind}_old").fetchone()[0] if kind != "chapter" else cur.execute("SELECT COUNT(*) FROM chapter_old").fetchone()[0]
                new = cur.execute(f"SELECT COUNT(*) FROM {kind}_ref").fetchone()[0]
                if new != old - dup[kind] + stub[kind] + alias[kind]:
                        raise AssertionError(f"{kind}: expected {old - dup[kind] + stub[kind] + alias[kind]} rows but found {new}")
                if alias[kind]:
                        logged(f"{alias[kind]} {kind} ids were stored under a different source in the old data; linked to the existing row")
                if dup[kind]:
                        logged(f"{dup[kind]} duplicate {kind} rows merged after source cleanup")
                if stub[kind]:
                        logged(f"{stub[kind]} placeholder {kind} rows created for ids that were referenced but missing")
        if stats["srcFixed"]:
                logged(f"{stats['srcFixed']} chapters had a source different from their series; source taken from the series")
        if stats["named"]:
                logged(f"{stats['named']} placeholder tgroup rows use the stored id as name (mangadex group ids are UUIDs, these were names)")
        for t in TABLES_V2:
                if cur.execute(f"PRAGMA foreign_key_check({t})").fetchall():
                        raise AssertionError(f"foreign key check failed on {t}")

        if not keepOld:
                for t in changed:
                        logged(f"Dropping old table {t}_old...")
                        cur.execute(f"DROP TABLE {t}_old")

def updateDB(dbPath:str, logged=print, autoBackup:bool=True, keepOld:bool=False, newVersion:str|None=None) -> None:
        if autoBackup:
                backupDB(dbPath, logged)

        db = sqlite3.connect(dbPath, isolation_level=None)
        db.execute("PRAGMA journal_mode=WAL;")
        db.execute("PRAGMA foreign_keys=OFF;")
        try:
                db.execute("BEGIN")
                migrateV1toV2(db, logged, keepOld)
                if newVersion is not None:
                        db.execute("UPDATE settings SET value=? WHERE key='dbVersion'", (newVersion,))
                db.execute("COMMIT")
        except Exception as e:
                logged(traceback.format_exc())
                logged(f"Database update failed, rolling back: {e}")
                try:
                        db.execute("ROLLBACK")
                except sqlite3.Error:
                        pass
                db.close()
                raise
        db.execute("PRAGMA foreign_keys=ON;")
        db.close()
        logged("Database update completed")