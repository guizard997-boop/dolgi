# -*- coding: utf-8 -*-
"""Учёт долгов — минимальный Flask без SQLAlchemy."""
import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, request, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dolgi-fix-2026")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
MAIN_SITE = os.environ.get(
    "MAIN_SITE_URL", "https://mircancelyarii-production.up.railway.app"
).rstrip("/")

_BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", _BASE)
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    DATA_DIR = _BASE
DB = os.path.join(DATA_DIR, "debts.db")


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS organization (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS debt (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            created_at TEXT,
            paid_at TEXT
        )"""
        )
        c.commit()


try:
    init_db()
except Exception as e:
    print("init_db:", e)


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("ok"):
            return redirect("/login")
        return f(*a, **k)

    return w


def page(title, body, nav=True):
    nav_html = ""
    if nav and session.get("ok"):
        nav_html = """<header style="background:#fff;border-bottom:1px solid #ccfbf1;padding:12px 16px;display:flex;gap:12px;flex-wrap:wrap;align-items:center">
<a href="/" style="font-weight:800;color:#0f766e;text-decoration:none">Учёт долгов</a>
<a href="/orgs" style="color:#0f766e;text-decoration:none;font-size:14px">Организации</a>
<a href="/debts" style="color:#0f766e;text-decoration:none;font-size:14px">Долги</a>
<a href="/products" style="color:#0f766e;text-decoration:none;font-size:14px">Товары</a>
<a href="/logout" style="margin-left:auto;color:#dc2626;text-decoration:none;font-size:14px">Выйти</a>
</header>"""
    return f"""<!DOCTYPE html><html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f0fdfa;margin:0;color:#134e4a}}
main{{max-width:720px;margin:0 auto;padding:20px 16px}}
.card{{background:#fff;border:1px solid #99f6e4;border-radius:14px;padding:16px;margin-bottom:14px}}
.btn{{background:#0f766e;color:#fff;border:0;border-radius:10px;padding:10px 16px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block;font-size:14px}}
.btn2{{background:#fff;color:#0f766e;border:1px solid #0f766e}}
input,select,textarea{{width:100%;padding:10px;border:1px solid #99f6e4;border-radius:10px;margin:6px 0 12px;box-sizing:border-box}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{text-align:left;padding:8px;border-bottom:1px solid #e2e8f0}}
.red{{color:#dc2626;font-weight:800}}
.muted{{color:#64748b;font-size:13px}}
</style></head><body>{nav_html}<main>{body}</main></body></html>"""


@app.route("/health")
def health():
    return jsonify(ok=True)


@app.route("/login", methods=["GET", "POST"])
def login():
    err = ""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["ok"] = True
            return redirect("/")
        err = '<p class="red">Неверный пароль</p>'
    body = f"""<div class="card" style="max-width:320px;margin:40px auto;text-align:center">
<h2>Вход</h2>{err}
<form method="post"><input type="password" name="password" placeholder="Пароль" required>
<button class="btn" type="submit">Войти</button></form></div>"""
    return page("Вход", body, nav=False)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
def index():
    with conn() as c:
        orgs = c.execute("SELECT COUNT(*) FROM organization").fetchone()[0]
        total = c.execute(
            "SELECT COALESCE(SUM(amount),0) FROM debt WHERE status='open'"
        ).fetchone()[0]
    body = f"""
<div class="card"><div class="muted">Организации</div><div style="font-size:28px;font-weight:800">{orgs}</div></div>
<div class="card"><div class="muted">Открытые долги</div><div class="red" style="font-size:28px">{total:,.0f} сом</div></div>
<p><a class="btn" href="/debts/add">+ Долг</a>
<a class="btn btn2" href="/orgs/add">+ Организация</a></p>"""
    return page("Главная", body)


@app.route("/orgs")
@login_required
def orgs():
    with conn() as c:
        items = c.execute("SELECT * FROM organization ORDER BY name").fetchall()
        rows = ""
        for o in items:
            s = c.execute(
                "SELECT COALESCE(SUM(amount),0) FROM debt WHERE organization_id=? AND status='open'",
                (o["id"],),
            ).fetchone()[0]
            rows += f"""<tr><td>{o['name']}</td><td>{o['phone'] or '—'}</td>
<td class="{'red' if s else ''}">{s:,.0f}</td>
<td><a href="/debts?org={o['id']}">Долги</a> ·
<a href="/orgs/edit/{o['id']}">Изм.</a> ·
<form style="display:inline" method="post" action="/orgs/delete/{o['id']}" onsubmit="return confirm('Удалить?')">
<button type="submit" style="background:none;border:0;color:#dc2626;cursor:pointer">Удал.</button></form></td></tr>"""
    body = f"""
<div style="display:flex;justify-content:space-between;align-items:center">
<h2>Организации</h2><a class="btn" href="/orgs/add">+ Добавить</a></div>
<div class="card"><table><tr><th>Название</th><th>Телефон</th><th>Долг</th><th></th></tr>
{rows or '<tr><td colspan="4" class="muted">Пусто</td></tr>'}</table></div>"""
    return page("Организации", body)


@app.route("/orgs/add", methods=["GET", "POST"])
@app.route("/orgs/edit/<int:oid>", methods=["GET", "POST"])
@login_required
def org_form(oid=None):
    o = None
    if oid:
        with conn() as c:
            o = c.execute("SELECT * FROM organization WHERE id=?", (oid,)).fetchone()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        note = (request.form.get("note") or "").strip()
        if name:
            with conn() as c:
                if oid and o:
                    c.execute(
                        "UPDATE organization SET name=?,phone=?,note=? WHERE id=?",
                        (name, phone, note, oid),
                    )
                else:
                    c.execute(
                        "INSERT INTO organization(name,phone,note) VALUES(?,?,?)",
                        (name, phone, note),
                    )
                c.commit()
        return redirect("/orgs")
    name = o["name"] if o else ""
    phone = o["phone"] if o else ""
    note = o["note"] if o else ""
    body = f"""
<h2>{"Изменить" if o else "Новая"} организация</h2>
<div class="card"><form method="post">
<label>Название</label><input name="name" required value="{name}">
<label>Телефон</label><input name="phone" value="{phone}">
<label>Заметка</label><textarea name="note" rows="2">{note}</textarea>
<button class="btn" type="submit">Сохранить</button>
</form></div>"""
    return page("Организация", body)


@app.route("/orgs/delete/<int:oid>", methods=["POST"])
@login_required
def org_delete(oid):
    with conn() as c:
        c.execute("DELETE FROM debt WHERE organization_id=?", (oid,))
        c.execute("DELETE FROM organization WHERE id=?", (oid,))
        c.commit()
    return redirect("/orgs")


@app.route("/debts")
@login_required
def debts():
    org_id = request.args.get("org", type=int)
    status = request.args.get("status", "open")
    with conn() as c:
        sql = "SELECT d.*, o.name as org_name FROM debt d LEFT JOIN organization o ON o.id=d.organization_id WHERE 1=1"
        params = []
        if org_id:
            sql += " AND d.organization_id=?"
            params.append(org_id)
        if status in ("open", "paid"):
            sql += " AND d.status=?"
            params.append(status)
        sql += " ORDER BY d.id DESC"
        items = c.execute(sql, params).fetchall()
        total = c.execute(
            "SELECT COALESCE(SUM(amount),0) FROM debt WHERE status='open'"
        ).fetchone()[0]
    rows = ""
    for d in items:
        st = "Открыт" if d["status"] == "open" else "Погашен"
        act = ""
        if d["status"] == "open":
            act = f'<form style="display:inline" method="post" action="/debts/pay/{d["id"]}"><button class="btn" style="padding:4px 8px;font-size:12px" type="submit">Погасить</button></form> '
        act += f'<form style="display:inline" method="post" action="/debts/delete/{d["id"]}" onsubmit="return confirm(\'Удалить?\')"><button type="submit" style="background:none;border:0;color:#dc2626;cursor:pointer">Удал.</button></form>'
        desc = (d["description"] or "—")[:40]
        rows += f"<tr><td>{d['org_name'] or '—'}</td><td>{d['amount']:,.0f}</td><td>{desc}</td><td>{st}</td><td>{act}</td></tr>"
    body = f"""
<div style="display:flex;justify-content:space-between;align-items:center">
<h2>Долги</h2><a class="btn" href="/debts/add">+ Долг</a></div>
<p class="muted">Открытых: <span class="red">{total:,.0f} сом</span></p>
<p><a href="/debts?status=open">Открытые</a> · <a href="/debts?status=paid">Погашенные</a> · <a href="/debts?status=all">Все</a></p>
<div class="card"><table>
<tr><th>Организация</th><th>Сумма</th><th>Описание</th><th>Статус</th><th></th></tr>
{rows or '<tr><td colspan="5" class="muted">Нет записей</td></tr>'}
</table></div>"""
    return page("Долги", body)


@app.route("/debts/add", methods=["GET", "POST"])
@login_required
def debt_add():
    with conn() as c:
        orgs = c.execute("SELECT * FROM organization ORDER BY name").fetchall()
    if request.method == "POST":
        try:
            oid = int(request.form.get("organization_id") or 0)
            amount = float(str(request.form.get("amount", "0")).replace(",", "."))
        except ValueError:
            return redirect("/debts/add")
        desc = (request.form.get("description") or "").strip()
        if oid and amount > 0:
            with conn() as c:
                c.execute(
                    "INSERT INTO debt(organization_id,amount,description,status,created_at) VALUES(?,?,?,?,?)",
                    (oid, amount, desc, "open", datetime.utcnow().isoformat()),
                )
                c.commit()
            return redirect("/debts")
        return redirect("/debts/add")
    if not orgs:
        return page(
            "Долг",
            '<div class="card"><p>Сначала добавьте организацию.</p><a class="btn" href="/orgs/add">+ Организация</a></div>',
        )
    opts = "".join(f'<option value="{o["id"]}">{o["name"]}</option>' for o in orgs)
    body = f"""
<h2>Новый долг</h2>
<div class="card"><form method="post">
<label>Организация</label><select name="organization_id" required>{opts}</select>
<label>Сумма (сом)</label><input name="amount" type="number" step="0.01" min="0.01" required>
<label>Описание</label><textarea name="description" rows="2"></textarea>
<button class="btn" type="submit">Сохранить</button>
</form></div>"""
    return page("Новый долг", body)


@app.route("/debts/pay/<int:did>", methods=["POST"])
@login_required
def debt_pay(did):
    with conn() as c:
        c.execute(
            "UPDATE debt SET status='paid', paid_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), did),
        )
        c.commit()
    return redirect(request.referrer or "/debts")


@app.route("/debts/delete/<int:did>", methods=["POST"])
@login_required
def debt_delete(did):
    with conn() as c:
        c.execute("DELETE FROM debt WHERE id=?", (did,))
        c.commit()
    return redirect("/debts")


@app.route("/products")
@login_required
def products():
    items = []
    err = ""
    try:
        import urllib.request
        import json

        req = urllib.request.Request(
            MAIN_SITE + "/api/products", headers={"User-Agent": "dolgi/1.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode())
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("items") or data.get("products") or []
    except Exception as e:
        err = str(e)
    rows = ""
    for p in items:
        if not isinstance(p, dict):
            continue
        name = p.get("name") or p.get("title") or "—"
        price = p.get("price", 0)
        rows += f'<div style="padding:8px 0;border-bottom:1px solid #e2e8f0"><b>{name}</b><div class="muted">{price} сом</div></div>'
    body = f"""
<h2>Товары магазина</h2>
<p class="muted">{MAIN_SITE}</p>
<div class="card">{rows or f'<p class="muted">Не загрузилось. {err}</p>'}</div>"""
    return page("Товары", body)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
