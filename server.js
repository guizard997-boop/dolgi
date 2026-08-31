const express = require('express');
const fs = require('fs');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const DATA_FILE = path.join(__dirname, 'data.json');

// Инициализация базы данных
function loadData() {
    if (!fs.existsSync(DATA_FILE)) {
        const initialData = {
            organizations: [{ id: 1, name: "ОсОО 'Школа №1'" }, { id: 2, name: "ИП Иванов" }],
            debts: [],
            products: [
                { id: 1, title: "Тетрадь 48 листов", price: 35 },
                { id: 2, title: "Ручка шариковая синяя", price: 15 },
                { id: 3, title: "Набор карандашей 12 цв.", price: 120 },
                { id: 4, title: "Бумага А4 500 л.", price: 450 },
                { id: 5, title: "Маркер черный", price: 40 },
                { id: 6, title: "Папка-регистратор", price: 180 },
                { id: 7, title: "Клей-карандаш 15г", price: 30 },
                { id: 8, title: "Ножницы канцелярские", price: 85 }
            ]
        };
        fs.writeFileSync(DATA_FILE, JSON.stringify(initialData, null, 2));
        return initialData;
    }
    return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
}

function saveData(data) {
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

// Эндпоинты API

// Получить товары
app.get('/api/products', (req, res) => {
    const data = loadData();
    res.json(data.products);
});

// Получить список организаций
app.get('/api/organizations', (req, res) => {
    const data = loadData();
    res.json(data.organizations);
});

// Добавить новую организацию
app.post('/api/organizations', (req, res) => {
    const { name } = req.body;
    if (!name) return res.status(400).json({ error: "Название обязательно" });

    const data = loadData();
    if (data.organizations.some(o => o.name.toLowerCase() === name.toLowerCase())) {
        return res.status(400).json({ error: "Организация уже существует" });
    }

    const newOrg = { id: Date.now(), name };
    data.organizations.push(newOrg);
    saveData(data);
    res.status(201).json(newOrg);
});

// Получить историю долгов
app.get('/api/debts', (req, res) => {
    const data = loadData();
    res.json(data.debts);
});

// Добавить новую запись о долге
app.post('/api/debts', (req, res) => {
    const { org, items, total } = req.body;
    if (!org || !items || !total) return res.status(400).json({ error: "Все поля обязательны" });

    const data = loadData();
    const newDebt = {
        id: Date.now(),
        date: new Date().toLocaleString('ru-RU'),
        org,
        items,
        total
    };
    data.debts.unshift(newDebt);
    saveData(data);
    res.status(201).json(newDebt);
});

// Удалить запись о долге
app.delete('/api/debts/:id', (req, res) => {
    const id = parseInt(req.params.id);
    const data = loadData();
    data.debts = data.debts.filter(d => d.id !== id);
    saveData(data);
    res.json({ success: true });
});

// Главный роут
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
    console.log(`Сервер запущен на порту ${PORT}`);
});
