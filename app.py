from flask import Flask, request, redirect, url_for, flash, session, render_template_string, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from functools import wraps
import os
import requests

_BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR', _BASE)
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'debts-secret-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(DATA_DIR, 'debts.db')
)
uri = app.config['SQLALCHEMY_DATABASE_URI']
if uri.startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
MAIN_SITE = os.environ.get('MAIN_SITE_URL', 'https://mircancelyarii-production.up.railway.app').rstrip('/')


class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), default='')
    note = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    debts = db.relationship('Debt', backref='organization', lazy=True, cascade='all, delete-orphan')


class Debt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(30), default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped


def fetch_products():
    """Товары с основного сайта магазина (без обновления магазина — только чтение)."""
    items = []
    for path in ('/api/products', '/catalog'):
        try:
            r = requests.get(MAIN_SITE + path, timeout=12)
            if r.status_code != 200:
                continue
            if path == '/api/products':
                data = r.json()
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get('items') or data.get('products') or []
                if items:
                    return items
        except Exception as e:
            print('fetch products', e)
    return items


LAYOUT = '''<!DOCTYPE html>
<html lang="ru"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }} — Учёт долгов</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>tailwind.config={theme:{extend:{colors:{brand:'#0F766E',soft:'#F0FDFA'}}}}</script>
<style>@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
body{font-family:'Nunito',system-ui,sans-serif}.btn{background:linear-gradient(135deg,#0F766E,#14B8A6)}</style>
</head><body class="bg-soft min-h-screen">
<header class="bg-white border-b sticky top-0 z-40">
<div class="max-w-3xl mx-auto px-4 h-14 flex items-center gap-3 flex-wrap">
<a href="/" class="font-extrabold text-brand">Учёт долгов</a>
{% if session.get('admin') %}
<a href="/orgs" class="text-sm text-gray-600">Организации</a>
<a href="/debts" class="text-sm text-gray-600">Долги</a>
<a href="/products" class="text-sm text-gray-600">Товары</a>
<a href="/logout" class="text-sm text-red-500 ml-auto">Выйти</a>
{% endif %}
</div></header>
<main class="max-w-3xl mx-auto px-4 py-8">
{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}{% for c,m in messages %}
<div class="mb-3 p-3 rounded-xl text-sm {% if c=='success' %}bg-green-50 text-green-700{% else %}bg-red-50 text-red-700{% endif %}">{{ m }}</div>
{% endfor %}{% endif %}{% endwith %}
{{ content|safe }}
</main>
</body></html>'''


def page(title, content):
    from flask import get_flashed_messages
    return render_template_string(
        LAYOUT, title=title, content=content,
        get_flashed_messages=get_flashed_messages, session=session
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin'):
        return redirect('/')
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/')
        flash('Неверный пароль', 'danger')
    content = '''<div class="max-w-xs mx-auto border bg-white rounded-2xl p-6 text-center space-y-3">
<h1 class="font-extrabold text-lg">Вход</h1>
<form method="post" class="space-y-3">
<input type="password" name="password" required placeholder="Пароль" class="w-full border rounded-xl px-4 py-2 text-center">
<button class="btn text-white font-bold w-full py-2.5 rounded-xl">Войти</button>
</form></div>'''
    return page('Вход', content)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/')
@login_required
def index():
    orgs = Organization.query.count()
    open_debts = Debt.query.filter_by(status='open').all()
    total = sum(d.amount for d in open_debts)
    content = f'''
<div class="grid grid-cols-2 gap-3 mb-6">
<div class="bg-white border rounded-2xl p-4"><div class="text-xs text-gray-400">Организации</div><div class="text-3xl font-extrabold text-brand">{orgs}</div></div>
<div class="bg-white border rounded-2xl p-4"><div class="text-xs text-gray-400">Открытые долги</div><div class="text-3xl font-extrabold text-red-500">{total:,.0f} <span class="text-sm">сом</span></div></div>
</div>
<div class="flex flex-wrap gap-2">
<a href="/debts/add" class="btn text-white font-bold px-4 py-2.5 rounded-xl text-sm">+ Добавить долг</a>
<a href="/orgs/add" class="bg-white border font-bold px-4 py-2.5 rounded-xl text-sm text-brand">+ Организация</a>
<a href="/products" class="bg-white border font-bold px-4 py-2.5 rounded-xl text-sm">Товары магазина</a>
</div>'''
    return page('Главная', content)


@app.route('/orgs')
@login_required
def orgs_list():
    orgs = Organization.query.order_by(Organization.name).all()
    rows = []
    for o in orgs:
        s = sum(d.amount for d in o.debts if d.status == 'open')
        rows.append(
            f'<tr class="border-t"><td class="px-3 py-2 font-semibold">{o.name}</td>'
            f'<td class="px-3 py-2 text-sm text-gray-500">{o.phone or "—"}</td>'
            f'<td class="px-3 py-2 font-bold {"text-red-500" if s else "text-gray-300"}">{s:,.0f}</td>'
            f'<td class="px-3 py-2 text-sm">'
            f'<a href="/debts?org={o.id}" class="text-brand">Долги</a> · '
            f'<a href="/orgs/edit/{o.id}" class="text-brand">Изм.</a> · '
            f'<form action="/orgs/delete/{o.id}" method="post" class="inline" '
            f'onsubmit="return confirm(\'Удалить?\')">'
            f'<button class="text-red-400">Удал.</button></form></td></tr>'
        )
    content = f'''
<div class="flex justify-between mb-4"><h1 class="text-xl font-extrabold">Организации</h1>
<a href="/orgs/add" class="btn text-white text-sm font-bold px-3 py-1.5 rounded-xl">+ Добавить</a></div>
<div class="bg-white border rounded-2xl overflow-hidden">
<table class="w-full text-sm"><thead class="bg-gray-50 text-left"><tr>
<th class="px-3 py-2">Название</th><th class="px-3 py-2">Телефон</th><th class="px-3 py-2">Долг</th><th></th>
</tr></thead><tbody>{''.join(rows) or '<tr><td colspan="4" class="p-6 text-center text-gray-400">Пусто</td></tr>'}</tbody></table></div>'''
    return page('Организации', content)


@app.route('/orgs/add', methods=['GET', 'POST'])
@app.route('/orgs/edit/<int:oid>', methods=['GET', 'POST'])
@login_required
def org_form(oid=None):
    o = db.session.get(Organization, oid) if oid else None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Укажите название', 'danger')
            return redirect(request.url)
        if o:
            o.name = name
            o.phone = request.form.get('phone', '').strip()
            o.note = request.form.get('note', '').strip()
        else:
            db.session.add(Organization(
                name=name,
                phone=request.form.get('phone', '').strip(),
                note=request.form.get('note', '').strip(),
            ))
        db.session.commit()
        flash('Сохранено', 'success')
        return redirect(url_for('orgs_list'))
    content = f'''
<h1 class="text-xl font-extrabold mb-4">{'Изменить' if o else 'Новая'} организация</h1>
<form method="post" class="bg-white border rounded-2xl p-5 space-y-3">
<input name="name" required value="{o.name if o else ''}" placeholder="Название" class="w-full border rounded-xl px-4 py-2">
<input name="phone" value="{o.phone if o else ''}" placeholder="Телефон" class="w-full border rounded-xl px-4 py-2">
<textarea name="note" rows="2" placeholder="Заметка" class="w-full border rounded-xl px-4 py-2">{o.note if o else ''}</textarea>
<button class="btn text-white font-bold px-5 py-2 rounded-xl">Сохранить</button>
</form>'''
    return page('Организация', content)


@app.route('/orgs/delete/<int:oid>', methods=['POST'])
@login_required
def org_delete(oid):
    o = db.session.get(Organization, oid)
    if o:
        db.session.delete(o)
        db.session.commit()
        flash('Удалено', 'success')
    return redirect(url_for('orgs_list'))


@app.route('/debts')
@login_required
def debts_list():
    org_id = request.args.get('org', type=int)
    status = request.args.get('status', 'open')
    q = Debt.query
    if org_id:
        q = q.filter_by(organization_id=org_id)
    if status in ('open', 'paid'):
        q = q.filter_by(status=status)
    debts = q.order_by(Debt.created_at.desc()).all()
    orgs = {x.id: x for x in Organization.query.all()}
    rows = []
    for d in debts:
        name = orgs[d.organization_id].name if d.organization_id in orgs else '—'
        st = 'Открыт' if d.status == 'open' else 'Погашен'
        stc = 'text-red-500' if d.status == 'open' else 'text-green-600'
        act = ''
        if d.status == 'open':
            act = f'<form action="/debts/pay/{d.id}" method="post" class="inline"><button class="text-green-600">Погасить</button></form> · '
        act += f'<form action="/debts/delete/{d.id}" method="post" class="inline" onsubmit="return confirm(\'Удалить?\')"><button class="text-red-400">Удал.</button></form>'
        rows.append(
            f'<tr class="border-t"><td class="px-3 py-2 text-sm">{name}</td>'
            f'<td class="px-3 py-2 font-bold">{d.amount:,.0f}</td>'
            f'<td class="px-3 py-2 text-sm text-gray-500">{(d.description or "—")[:40]}</td>'
            f'<td class="px-3 py-2 text-sm {stc}">{st}</td>'
            f'<td class="px-3 py-2 text-sm">{act}</td></tr>'
        )
    total = sum(d.amount for d in Debt.query.filter_by(status='open').all())
    content = f'''
<div class="flex justify-between mb-2"><h1 class="text-xl font-extrabold">Долги</h1>
<a href="/debts/add" class="btn text-white text-sm font-bold px-3 py-1.5 rounded-xl">+ Долг</a></div>
<p class="text-sm text-gray-500 mb-3">Открытых: <b class="text-red-500">{total:,.0f} сом</b></p>
<div class="flex gap-2 mb-4 text-sm">
<a href="/debts?status=open" class="px-3 py-1 rounded-full border {'bg-brand text-white' if status=='open' else 'bg-white'}">Открытые</a>
<a href="/debts?status=paid" class="px-3 py-1 rounded-full border {'bg-brand text-white' if status=='paid' else 'bg-white'}">Погашенные</a>
<a href="/debts?status=all" class="px-3 py-1 rounded-full border {'bg-brand text-white' if status=='all' else 'bg-white'}">Все</a>
</div>
<div class="bg-white border rounded-2xl overflow-hidden">
<table class="w-full text-sm"><thead class="bg-gray-50 text-left"><tr>
<th class="px-3 py-2">Организация</th><th class="px-3 py-2">Сумма</th><th class="px-3 py-2">Описание</th><th class="px-3 py-2">Статус</th><th></th>
</tr></thead><tbody>{''.join(rows) or '<tr><td colspan="5" class="p-6 text-center text-gray-400">Нет записей</td></tr>'}</tbody></table></div>'''
    return page('Долги', content)


@app.route('/debts/add', methods=['GET', 'POST'])
@login_required
def debt_add():
    orgs = Organization.query.order_by(Organization.name).all()
    if request.method == 'POST':
        try:
            oid = int(request.form.get('organization_id') or 0)
            amount = float(str(request.form.get('amount', '0')).replace(',', '.'))
        except ValueError:
            flash('Проверьте данные', 'danger')
            return redirect(url_for('debt_add'))
        if not oid or amount <= 0 or not db.session.get(Organization, oid):
            flash('Выберите организацию и сумму', 'danger')
            return redirect(url_for('debt_add'))
        db.session.add(Debt(
            organization_id=oid,
            amount=amount,
            description=request.form.get('description', '').strip(),
            status='open',
        ))
        db.session.commit()
        flash('Долг добавлен', 'success')
        return redirect(url_for('debts_list'))
    if not orgs:
        return page('Долг', '<p class="text-gray-500 mb-4">Сначала добавьте организацию.</p><a href="/orgs/add" class="btn text-white font-bold px-4 py-2 rounded-xl">+ Организация</a>')
    opts = ''.join(f'<option value="{o.id}">{o.name}</option>' for o in orgs)
    content = f'''
<h1 class="text-xl font-extrabold mb-4">Новый долг</h1>
<form method="post" class="bg-white border rounded-2xl p-5 space-y-3">
<label class="text-sm text-gray-500">Организация</label>
<select name="organization_id" required class="w-full border rounded-xl px-4 py-2">{opts}</select>
<input name="amount" type="number" step="0.01" min="0.01" required placeholder="Сумма (сом)" class="w-full border rounded-xl px-4 py-2">
<textarea name="description" rows="2" placeholder="За что" class="w-full border rounded-xl px-4 py-2"></textarea>
<button class="btn text-white font-bold w-full py-2.5 rounded-xl">Сохранить</button>
</form>'''
    return page('Новый долг', content)


@app.route('/debts/pay/<int:did>', methods=['POST'])
@login_required
def debt_pay(did):
    d = db.session.get(Debt, did)
    if d:
        d.status = 'paid'
        d.paid_at = datetime.utcnow()
        db.session.commit()
        flash('Погашено', 'success')
    return redirect(request.referrer or url_for('debts_list'))


@app.route('/debts/delete/<int:did>', methods=['POST'])
@login_required
def debt_delete(did):
    d = db.session.get(Debt, did)
    if d:
        db.session.delete(d)
        db.session.commit()
        flash('Удалено', 'success')
    return redirect(url_for('debts_list'))


@app.route('/products')
@login_required
def products_page():
    products = fetch_products()
    rows = []
    for p in products:
        if isinstance(p, dict):
            name = p.get('name') or p.get('title') or '—'
            price = p.get('price', 0)
            img = p.get('image_url') or p.get('image') or ''
            cat = p.get('category') or p.get('category_name') or ''
            if isinstance(cat, dict):
                cat = cat.get('name', '')
            img_html = f'<img src="{img}" class="w-12 h-12 rounded-lg object-cover bg-gray-100" onerror="this.style.display=\'none\'">' if img else ''
            rows.append(
                f'<div class="flex gap-3 items-center border-b py-2">{img_html}'
                f'<div class="flex-1"><div class="font-semibold text-sm">{name}</div>'
                f'<div class="text-xs text-gray-500">{price} сом{" · " + str(cat) if cat else ""}</div></div></div>'
            )
    content = f'''
<h1 class="text-xl font-extrabold mb-2">Товары магазина</h1>
<p class="text-sm text-gray-500 mb-4">С сайта: {MAIN_SITE}</p>
<div class="bg-white border rounded-2xl p-4">
{''.join(rows) or '<p class="text-gray-400 text-center py-8">Товары не загрузились. Проверьте MAIN_SITE_URL или что на магазине есть /api/products</p>'}
</div>'''
    return page('Товары', content)


@app.route('/health')
def health():
    return jsonify({'ok': True, 'main_site': MAIN_SITE})


with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print('db init', e)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)
