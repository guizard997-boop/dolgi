const express = require('express');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

const publicPath = path.join(__dirname, 'public');
app.use(express.static(publicPath));

const DATA_FILE = path.join(__dirname, 'data.json');

// Инициализация локальной базы данных для организаций и долгов
function loadData() {
    if (!fs.existsSync(DATA_FILE)) {
        const initialData = {
            organizations: [{ id: 1, name: "ОсОО 'Школа №1'" }, { id: 2, name: "ИП Иванов" }],
            debts: []
        };
        fs.writeFileSync(DATA_FILE, JSON.stringify(initialData, null, 2));
        return initialData;
    }
    return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
}

function saveData(data) {
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2));
}

// ПАРСИНГ ТОВАРОВ ИЗ JS-КОДА catalog.html
app.get('/api/products', async (req, res) => {
    try {
        const response = await fetch('https://mircancelyarii-production.up.railway.app/catalog.html');
        if (!response.ok) {
            throw new Error(`Ошибка сети: ${response.statusText}`);
        }
        
        const html = await response.text();

        // Извлекаем массив products = [...] из скрипта внутри catalog.html
        const match = html.match(/const\s+products\s*=\s*(\[[\s\S]*?\]);/);

        if (match && match[1]) {
            let jsonString = match[1];

            // Форматируем JS-массив в строгий JSON
            jsonString = jsonString
                .replace(/([a-zA-Z0-9_]+)\s*:/g, '"$1":') // Добавляем кавычки ключам
                .replace(/'/g, '"')                       // Заменяем одинарные кавычки на двойные
                .replace(/,\s*([\]}])/g, '$1');           // Удаляем висячие запятые

            const products = JSON.parse(jsonString);
            return res.json(products);
        }

        res.status(404).json({ error: "Массив товаров не найден на сайте" });

    } catch (error) {
        console.error("Ошибка парсинга товаров:", error);
        res.status(500).json({ error: "Не удалось загрузить товары с основного сайта" });
    }
});

// API ОРГАНИЗАЦИЙ
app.get('/api/organizations', (req, res) => {
    const data = loadData();
    res.json(data.organizations);
});

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

// API ДОЛГОВ
app.get('/api/debts', (req, res) => {
    const data = loadData();
    res.json(data.debts);
});

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

app.delete('/api/debts/:id', (req, res) => {
    const id = parseInt(req.params.id);
    const data = loadData();
    data.debts = data.debts.filter(d => d.id !== id);
    saveData(data);
    res.json({ success: true });
});

app.get('*', (req, res) => {
    res.sendFile(path.join(publicPath, 'index.html'));
});

app.listen(PORT, () => {
    console.log(`Сервер запущен на порту ${PORT}`);
});
