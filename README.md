<p align="center">
  <img src="./docs/RostelecomLogo (2).png" alt="Smart Warehouse RTK banner" width="100%" />
</p>

<h1 align="center">Rostelecom Smart Warehouse</h1>

<p align="center">
  <i>"Умный склад - система управления
складской логистикой с использованием автономных
роботов"</i><br><br>
</p>

---

## 🧭 О проекте

**Ростелеком Умный склад** — это решение для кейс-чемпионата "Расти в ИТ".  
Проект направлен на автоматизацию и повышение эффективности управления складом с использованием **RTK-технологий, анализа данных** и **AI-моделей** для прогнозирования и оптимизации логистических процессов. 
[📂 Ссылка на кейс](https://drive.google.com/drive/u/0/folders/16xJ4XcN_ipFjO-VJEkBTMvxk1MhP9xqA)

Система объединяет **данные RTK-устройств**, **машинное обучение** и **умный интерфейс**, чтобы:
- 📦 Оптимизировать хранение и перемещение товаров  
- 🚜 Повысить точность позиционирования техники и персонала  
- 📊 Предсказывать загрузку и узкие места склада  
- ⚙️ Автоматизировать управленческие решения  

---


## 🏗 Архитектура проекта

flowchart TB
    %% Пользователи
    subgraph CLIENT["🌐 Клиентская часть"]
        U[👤 Пользователь]
        FE[🖥️ Frontend (React/Vue)]
        U --> FE
    end

    %% Реверс-прокси
    subgraph PROXY["🔁 Reverse Proxy Layer"]
        Caddy[Caddy Server<br/>TLS / Proxy / Routing]
    end

    %% Backend Layer
    subgraph BACKEND["⚙️ Backend Layer (FastAPI services)"]
        API[🚀 FastAPI API<br/>Основной сервис]
        EMU[🧩 Emulator<br/>Обработка команд]
        SCH[⏰ Scheduler<br/>Фоновые задачи / cron]
    end

    %% Auth
    subgraph AUTH["🔐 Аутентификация и безопасность"]
        KC[🛡️ Keycloak<br/>OAuth2 / OpenID / JWT]
    end

    %% Infrastructure
    subgraph INFRA["🗄️ Инфраструктура / Данные"]
        PG[(🐘 PostgreSQL Database)]
        REDIS[(🧠 Redis Pub/Sub)]
    end

    %% Cloud Layer
    subgraph CLOUD["☁️ Yandex Cloud"]
        PROXY --> BACKEND
        PROXY --> AUTH
        BACKEND --> INFRA
        AUTH --> PG
    end

    %% Взаимосвязи
    FE -->|HTTP/HTTPS| Caddy
    Caddy -->|Routes / Proxy| API
    Caddy -->|Static / SPA| FE

    %% API взаимодействия
    API -->|JWT Validation| KC
    API -->|SQLAlchemy ORM| PG
    API -->|Pub/Sub| REDIS
    EMU -->|Подписка на каналы| REDIS
    SCH -->|Планировщик задач| API

    %% Emulator взаимодействие
    EMU -->|Результаты в БД| PG

    %% Keycloak взаимодействие
    KC -->|User Tokens| API
    FE -->|OAuth2 Flow / JWT| KC

    %% Docker
    subgraph DOCKER["🐳 Docker Compose / Containers"]
        Caddy
        FE
        API
        EMU
        SCH
        KC
        PG
        REDIS
    end

**Компоненты проекта:**
1. **Backend** — API на FastAPI   
2. **Frontend** — React + Redux Toolkit (RTK Query)  
3. **AI Module** — прогнозирование и аналитика  
4. **Database** — PostgreSQL  
5. **Integration Layer** — обработка RTK-данных от внешних устройств  

---

## ⚙️ Технологический стек

| Категория | Технологии |
|------------|-------------|
| 💻 Frontend | React, TypeScript, Vite, shadcn |
| ⚙️ Backend | FastAPI, SQLAlchemy |
| 🧠 Data & ML | Pandas, PyTorch |
| 🗄 Database | PostgreSQL, Redis, Keyclock |
| 🧰 DevOps | Docker, GitHub Actions, YandexCloud|

---

## 🧠 Команда проекта

| Участник | Роль | Контакты |
|-----------|------|-----------|
| Никита  | Backend Developer | [GitHub](https://github.com/nikBaben),[Telegram](@bab3n) |
| Матвей | Frontend Developer & UX/UI Designer | [GitHub](https://github.com/o2cloud) |
| Вадим | Frontend Developer | [GitHub](https://github.com/tailorsky) |
| Александр | Backend Developer | [GitHub](https://github.com/RikiTikiTavee17) |
| Захар | Backend Developer | [GitHub](https://github.com/ZaharPavlikov) |
| Евгений | Data Science Engineer | [GitHub](https://github.com/Mmm-max) |

---

