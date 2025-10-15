<h1 align="center">🤖 Smart Warehouse RTK</h1>

<p align="center">
  <i>"Умный склад - система управления
складской логистикой с использованием автономных
роботов"</i><br><br>
  <img src="https://img.shields.io/badge/Python-3.10-blue?logo=python" />
  <img src="https://img.shields.io/badge/React-18.2.0-61DAFB?logo=react" />
  <img src="https://img.shields.io/badge/Redux%20Toolkit-RTK%20Query-764ABC?logo=redux" />
  <img src="https://img.shields.io/badge/License-MIT-green" />
</p>

---

## 🧭 О проекте

**Smart Warehouse RTK** — это инновационное решение, созданное для участия в кейс-чемпионате  
[📂 Ссылка на кейс](https://drive.google.com/drive/u/0/folders/16xJ4XcN_ipFjO-VJEkBTMvxk1MhP9xqA)

Система объединяет **данные RTK-устройств**, **машинное обучение** и **умный интерфейс**, чтобы:
- 📦 Оптимизировать хранение и перемещение товаров  
- 🚜 Повысить точность позиционирования техники и персонала  
- 📊 Предсказывать загрузку и узкие места склада  
- ⚙️ Автоматизировать управленческие решения  

---

## 🧠 Концепция

> “Наш подход — объединить физическое позиционирование и цифровой интеллект,  
> чтобы склад стал по-настоящему умным.”

---

## 🏗 Архитектура системы

<p align="center">
  <img src="./docs/architecture.png" width="800" alt="System Architecture">
</p>

**Компоненты проекта:**
1. **Backend** — API на FastAPI / Flask  
2. **Frontend** — React + Redux Toolkit (RTK Query)  
3. **AI Module** — прогнозирование и аналитика  
4. **Database** — PostgreSQL  
5. **Integration Layer** — обработка RTK-данных от внешних устройств  

---

## ⚙️ Технологический стек

| Категория | Технологии |
|------------|-------------|
| 💻 Frontend | React, Redux Toolkit, RTK Query, Tailwind |
| ⚙️ Backend | FastAPI, SQLAlchemy |
| 🧠 Data & ML | Pandas, Scikit-learn, PyTorch |
| 🗄 Database | PostgreSQL |
| 🧰 DevOps | Docker, GitHub Actions, Render / Railway |
| 📊 Visuals | Plotly, Chart.js |

---

## 🚀 Быстрый старт

```bash
# 1️⃣ Клонируем репозиторий
git clone https://github.com/nikBaben/smart-warehouse-rtk.git
cd smart-warehouse-rtk

# 2️⃣ Устанавливаем зависимости
pip install -r requirements.txt

# 3️⃣ Запускаем backend
python src/backend/main.py

# 4️⃣ Запускаем frontend
cd src/frontend
npm install
npm start
