import os
from functools import wraps
from datetime import datetime

from flask import Flask, request, redirect, url_for, session, render_template_string, flash, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dolgi-secret-key-2026")

# SQLite рядом с приложением (или DATA_DIR / Volume)
_BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", _BASE)
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    DATA_DIR = _BASE

DB_PATH = os.path.join(DATA_DIR, "debts.db")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + DB_PATH
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
MAIN_SITE = os.environ.get(
    "MAIN_SITE_URL", "https://mircancelyarii-production.up.railway.app"
).rstrip("/")

# SQLAlchemy
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy(app)


class Organization(db.Model):
    __tablename__ = "organization"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), default="")
    note = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Debt(db.Model):
    __tablename__ = "debt"
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="open")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)


def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("ok"):
            return redirect(url_for("login"))
        return f(*a, **k)

    return w


def layout(title, body):
    return f"""<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font-family:system-ui,sans-serif;background:#f0fdfa;margin:0;color:#134e4a}}
header{{background:#fff;border-bottom:1px solid #ccfbf1;padding:12px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}}
header a{{color:#0f766e;text-decoration:none;font-size:14px}}
header .logo{{font-weight:800;color:#0f766e}}
main{{max-width:720px;margin:0 auto;padding:20px 16px}}
.card{{background:#fff;border:1px solid #99f6e4;border-radius:14px;padding:16px;margin-bottom:14px}}
.btn{{background:#0f766e;color:#fff;border:0;border-radius:10px;padding:10px 16px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-block;font-size:14px}}
.btn2{{background:#fff;color:#0f766e;border:1px solid #0f766e}}
input,select,textarea{{width:100%;padding:10px;border:1px solid #99f6e4;border-radius:10px;margin:6px 0 12px;box-sizing:border-box}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{text-align:left;padding:8px;border-bottom:1px solid #e2e8f0}}
.red{{color:#dc2626;font-weight:800}}
.muted{{color:#64748b;font-size:13px}}
.flash{{background:#ecfdf5;border:1px solid #6ee7b7;padding:10px;border-radius:10px;margin-bottom:12px}}
</style></head><body>
<header>
<a class="logo" href="/">Учёт долгов</a>
<a href="/orgs">Организации</a>
<a href="/debts">Долги</a>
<a href="/products">Товары</a>
<a href="/logout" style="margin-left:auto;color:#dc2626">Выйти</a>
</header>
<main>{body}</main>
</body></html>"""


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
<form method="post">
<input type="password" name="password" placeholder="Пароль" required>
<button class="btn" type="submit">Войти</button>
</form></div>"""
    return layout("Вход", body)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
def index():
    orgs = Organization.query.count()
    open_list = Debt.query.filter_by(status="open").all()
    total = sum(d.amount or 0 for d in open_list)
    body = f"""
<div class="card"><div class="muted">Организации</div><div style="font-size:28px;font-weight:800">{orgs}</div></div>
<div class="card"><div class="muted">Открытые долги</div><div class="red" style="font-size:28px">{total:,.0f} сом</div></div>
<p>
<a class="btn" href="/debts/add">+ Долг</a>
<a class="btn btn2" href="/orgs/add">+ Организация</a>
</p>"""
    return layout("Главная", body)


@app.route("/orgs")
@login_required
def orgs():
    items = Organization.query.order_by(Organization.name).all()
    rows = ""
    for o in items:
        debt_sum = sum(
            d.amount or 0
            for d in Debt.query.filter_by(organization_id=o.id, status="open").all()
        )
        rows += f"""<tr>
<td>{o.name}</td><td>{o.phone or "—"}</td>
<td class="{"red" if debt_sum else ""}">{debt_sum:,.0f}</td>
<td>
<a href="/debts?org={o.id}">Долги</a> ·
<a href="/orgs/edit/{o.id}">Изм.</a> ·
<form style="display:inline" method="post" action="/orgs/delete/{o.id}" onsubmit="return confirm('Удалить?')">
<button type="submit" style="background:none;border:0;color:#dc2626;cursor:pointer">Удал.</button>
</form>
</td></tr>"""
    body = f"""
<div style="display:flex;justify-content:space-between;align-items:center">
<h2>Организации</h2>
<a class="btn" href="/orgs/add">+ Добавить</a>
</div>
<div class="card">
<table><tr><th>Название</th><th>Телефон</th><th>Долг</th><th></th></tr>
{rows or '<tr><td colspan="4" class="muted">Пока пусто</td></tr>'}
</table></div>"""
    return layout("Организации", body)


@app.route("/orgs/add", methods=["GET", "POST"])
@app.route("/orgs/edit/<int:oid>", methods=["GET", "POST"])
@login_required
def org_form(oid=None):
    o = db.session.get(Organization, oid) if oid else None
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            return redirect(request.url)
        if o:
            o.name = name
            o.phone = (request.form.get("phone") or "").strip()
            o.note = (request.form.get("note") or "").strip()
        else:
            db.session.add(
                Organization(
                    name=name,
                    phone=(request.form.get("phone") or "").strip(),
                    note=(request.form.get("note") or "").strip(),
                )
            )
        db.session.commit()
        return redirect("/orgs")
    body = f"""
<h2>{"Изменить" if o else "Новая"} организация</h2>
<div class="card">
<form method="post">
<label>Название</label>
<input name="name" required value="{o.name if o else ""}">
<label>Телефон</label>
<input name="phone" value="{o.phone if o else ""}">
<label>Заметка</label>
<textarea name="note" rows="2">{o.note if o else ""}</textarea>
<button class="btn" type="submit">Сохранить</button>
</form></div>"""
    return layout("Организация", body)


@app.route("/orgs/delete/<int:oid>", methods=["POST"])
@login_required
def org_delete(oid):
    o = db.session.get(Organization, oid)
    if o:
        Debt.query.filter_by(organization_id=oid).delete()
        db.session.delete(o)
        db.session.commit()
    return redirect("/orgs")


@app.route("/debts")
@login_required
def debts():
    org_id = request.args.get("org", type=int)
    status = request.args.get("status", "open")
    q = Debt.query
    if org_id:
        q = q.filter_by(organization_id=org_id)
    if status in ("open", "paid"):
        q = q.filter_by(status=status)
    items = q.order_by(Debt.created_at.desc()).all()
    org_map = {x.id: x.name for x in Organization.query.all()}
    rows = ""
    for d in items:
        name = org_map.get(d.organization_id, "—")
        st = "Открыт" if d.status == "open" else "Погашен"
        act = ""
        if d.status == "open":
            act = f'<form style="display:inline" method="post" action="/debts/pay/{d.id}"><button class="btn" type="submit" style="padding:4px 8px;font-size:12px">Погасить</button></form> '
        act += f'<form style="display:inline" method="post" action="/debts/delete/{d.id}" onsubmit="return confirm(\'Удалить?\')"><button type="submit" style="background:none;border:0;color:#dc2626;cursor:pointer">Удал.</button></form>'
        rows += f"<tr><td>{name}</td><td>{d.amount:,.0f}</td><td>{(d.description or '—')[:40]}</td><td>{st}</td><td>{act}</td></tr>"
    total = sum(d.amount or 0 for d in Debt.query.filter_by(status="open").all())
    body = f"""
<div style="display:flex;justify-content:space-between;align-items:center">
<h2>Долги</h2>
<a class="btn" href="/debts/add">+ Долг</a>
</div>
<p class="muted">Открытых: <span class="red">{total:,.0f} сом</span></p>
<p>
<a href="/debts?status=open">Открытые</a> ·
<a href="/debts?status=paid">Погашенные</a> ·
<a href="/debts?status=all">Все</a>
</p>
<div class="card">
<table>
<tr><th>Организация</th><th>Сумма</th><th>Описание</th><th>Статус</th><th></th></tr>
{rows or '<tr><td colspan="5" class="muted">Нет записей</td></tr>'}
</table></div>"""
    return layout("Долги", body)


@app.route("/debts/add", methods=["GET", "POST"])
@login_required
def debt_add():
    orgs = Organization.query.order_by(Organization.name).all()
    if request.method == "POST":
        try:
            oid = int(request.form.get("organization_id") or 0)
            amount = float(str(request.form.get("amount", "0")).replace(",", "."))
        except ValueError:
            return redirect("/debts/add")
        if oid and amount > 0 and db.session.get(Organization, oid):
            db.session.add(
                Debt(
                    organization_id=oid,
                    amount=amount,
                    description=(request.form.get("description") or "").strip(),
                    status="open",
                )
            )
            db.session.commit()
            return redirect("/debts")
        return redirect("/debts/add")
    if not orgs:
        return layout(
            "Долг",
            '<div class="card"><p>Сначала добавьте организацию.</p><a class="btn" href="/orgs/add">+ Организация</a></div>',
        )
    opts = "".join(f'<option value="{o.id}">{o.name}</option>' for o in orgs)
    body = f"""
<h2>Новый долг</h2>
<div class="card">
<form method="post">
<label>Организация</label>
<select name="organization_id" required>{opts}</select>
<label>Сумма (сом)</label>
<input name="amount" type="number" step="0.01" min="0.01" required>
<label>Описание</label>
<textarea name="description" rows="2"></textarea>
<button class="btn" type="submit">Сохранить</button>
</form></div>"""
    return layout("Новый долг", body)


@app.route("/debts/pay/<int:did>", methods=["POST"])
@login_required
def debt_pay(did):
    d = db.session.get(Debt, did)
    if d:
        d.status = "paid"
        d.paid_at = datetime.utcnow()
        db.session.commit()
    return redirect(request.referrer or "/debts")


@app.route("/debts/delete/<int:did>", methods=["POST"])
@login_required
def debt_delete(did):
    d = db.session.get(Debt, did)
    if d:
        db.session.delete(d)
        db.session.commit()
    return redirect("/debts")


@app.route("/products")
@login_required
def products():
    items = []
    try:
        import requests

        r = requests.get(MAIN_SITE + "/api/products", timeout=12)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("items") or data.get("products") or []
    except Exception as e:
        print("products error", e)
    rows = ""
    for p in items:
        if not isinstance(p, dict):
            continue
        name = p.get("name") or p.get("title") or "—"
        price = p.get("price", 0)
        img = p.get("image_url") or p.get("image") or ""
        img_html = (
            f'<img src="{img}" width="40" height="40" style="border-radius:8px;object-fit:cover" onerror="this.style.display=\'none\'">'
            if img
            else ""
        )
        rows += f'<div style="display:flex;gap:10px;align-items:center;padding:8px 0;border-bottom:1px solid #e2e8f0">{img_html}<div><b>{name}</b><div class="muted">{price} сом</div></div></div>'
    body = f"""
<h2>Товары магазина</h2>
<p class="muted">Источник: {MAIN_SITE}</p>
<div class="card">{rows or '<p class="muted">Не удалось загрузить. Нужен /api/products на магазине.</p>'}</div>"""
    return layout("Товары", body)


@app.route("/health")
def health():
    return jsonify({"ok": True})


# Создаём таблицы при импорте (безопасно)
try:
    with app.app_context():
        db.create_all()
except Exception as e:
    print("create_all error:", e)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
