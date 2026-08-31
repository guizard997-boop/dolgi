const express = require('express');
const fs = require('fs');
const path = require('path');
const cheerio = require('cheerio');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

const publicPath = path.join(__dirname, 'public');
app.use(express.static(publicPath));

const DATA_FILE = path.join(__dirname, 'data.json');

// Инициализация базы данных для организаций и долгов
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

// ПАРСИНГ ВСЕХ ТОВАРОВ С ОСНОВНОГО САЙТА
app.get('/api/products', async (req, res) => {
    try {
        const response = await fetch('https://mircancelyarii-production.up.railway.app/catalog.html');
        if (!response.ok) {
            throw new Error(`Ошибка загрузки каталога: ${response.statusText}`);
        }
        
        const html = await response.text();
        const $ = cheerio.load(html);
        const products = [];

        // Парсим карточки товаров из HTML вашего сайта
        $('.product-card, .card, .product-item').each((index, element) => {
            const title = $(element).find('h3, .product-title, .title, .card-title').text().trim();
            const priceText = $(element).find('.price, .product-price, p').text().trim();
            
            // Извлекаем только цифры цены
            const priceMatch = priceText.match(/\d+/);
            const price = priceMatch ? parseInt(priceMatch[0], 10) : 0;

            if (title) {
                products.push({
                    id: index + 1,
                    title: title,
                    price: price
                });
            }
        });

        // Если парсинг вернул список, отдаем его
        if (products.length > 0) {
            return res.json(products);
        }

        // Запасной ответ, если структура карточек отличается
        res.json([
            { id: 1, title: "Ошибка парсинга каталога (проверьте селекторы)", price: 0 }
        ]);

    } catch (error) {
        console.error("Ошибка при получении товаров:", error);
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
