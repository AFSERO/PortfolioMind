# NetWorth — Phase 1 Specification: Investment Portfolio Tracker

## 1. Overview
A web application where users register, add their investment assets (stocks, forex, gold, crypto, funds, real estate/custom), and view a real-time dashboard showing portfolio allocation, profit/loss, and historical performance.

## 2. User Stories

### Authentication
- As a user, I can register with email and password
- As a user, I can log in and receive a JWT token
- As a user, I can stay logged in via refresh tokens
- As a user, I can log out and invalidate my session

### Asset Management
- As a user, I can add an investment asset with: type, name, purchase price, quantity, purchase date, currency
- As a user, I can edit or delete any of my assets
- As a user, I can add multiple positions in the same asset (e.g., bought AAPL twice)
- As a user, I can add custom/manual assets (real estate, funds) where I set the current value myself
- As a user, I can see the current market price of tracked assets (auto-updated)

### Dashboard
- As a user, I see my total portfolio value in TRY and USD
- As a user, I see a pie chart showing allocation by asset type (stocks %, crypto %, etc.)
- As a user, I see a pie chart showing allocation by individual asset
- As a user, I see total profit/loss (amount and percentage) per asset
- As a user, I see a line chart of portfolio value over time
- As a user, I can filter dashboard by asset type
- As a user, I see a summary card for each asset type with total value and P/L

## 3. Data Models

### User
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| email | String | Unique, indexed |
| password_hash | String | bcrypt hashed |
| display_name | String | Optional |
| base_currency | String | Default: "TRY" |
| created_at | DateTime | Auto |
| updated_at | DateTime | Auto |

### Asset
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| user_id | UUID | FK → User |
| asset_type | Enum | STOCK, FOREX, GOLD, CRYPTO, FUND, REAL_ESTATE, CUSTOM |
| symbol | String | e.g., "AAPL", "USD/TRY", "BTC". Nullable for custom |
| name | String | Display name, e.g., "Apple Inc.", "Ev - Kadıköy" |
| purchase_price | Decimal(18,6) | Per unit price at purchase |
| quantity | Decimal(18,6) | Number of units |
| purchase_currency | String | "TRY", "USD", "EUR" |
| purchase_date | Date | When acquired |
| current_price | Decimal(18,6) | Latest fetched or manual price |
| current_price_currency | String | Currency of current price |
| is_manual_price | Boolean | True for real estate, custom |
| notes | Text | Optional user notes |
| created_at | DateTime | Auto |
| updated_at | DateTime | Auto |

### PriceHistory (for portfolio timeline chart)
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| asset_id | UUID | FK → Asset |
| price | Decimal(18,6) | |
| currency | String | |
| recorded_at | DateTime | |

### PortfolioSnapshot (daily total value for line chart)
| Field | Type | Notes |
|-------|------|-------|
| id | UUID | Primary key |
| user_id | UUID | FK → User |
| total_value_try | Decimal(18,2) | |
| total_value_usd | Decimal(18,2) | |
| snapshot_date | Date | Unique per user per day |

## 4. API Endpoints

### Auth
```
POST   /api/auth/register        → Register new user
POST   /api/auth/login            → Login, return JWT
POST   /api/auth/refresh          → Refresh access token
POST   /api/auth/logout           → Invalidate token
```

### Assets
```
GET    /api/assets                 → List all user assets
POST   /api/assets                 → Add new asset
GET    /api/assets/{id}            → Get asset detail
PUT    /api/assets/{id}            → Update asset
DELETE /api/assets/{id}            → Delete asset
POST   /api/assets/{id}/update-price → Manual price update (for custom assets)
```

### Dashboard
```
GET    /api/dashboard/summary      → Total value, P/L, allocation data
GET    /api/dashboard/timeline     → Portfolio value over time (for line chart)
GET    /api/dashboard/allocation   → Allocation breakdown by type and asset
```

### Prices
```
GET    /api/prices/live/{symbol}   → Get current price for a symbol
POST   /api/prices/refresh         → Refresh all user asset prices
```

## 5. External Price APIs

| Asset Type | API | Notes |
|-----------|-----|-------|
| Forex (USD, EUR) | ExchangeRate-API (free tier) | 1500 req/month free |
| Crypto (BTC, ETH) | CoinGecko API | Free, no key needed |
| Gold | MetalPriceAPI or CollectAPI | Free tier available |
| BIST Stocks | Yahoo Finance (yfinance) | Free, add ".IS" suffix (e.g., THYAO.IS) |
| Funds/Real Estate | Manual entry | User provides current value |

Price refresh strategy:
- On dashboard load: fetch prices for all user assets (with 5-min cache)
- Background job: daily snapshot of portfolio value for timeline chart
- Fallback: if API fails, use last known price and show "last updated" timestamp

## 6. Frontend Pages

### `/login` and `/register`
- Simple forms with email/password
- Redirect to dashboard on success

### `/dashboard` (main page)
- Summary cards at top: Total Value (TRY/USD), Total P/L, Number of Assets
- Pie chart: allocation by asset type
- Pie chart: allocation by individual asset
- Line chart: portfolio value over time
- Asset type filter tabs
- Quick-add asset button

### `/assets`
- Table listing all assets with: name, type, quantity, purchase price, current price, P/L, actions
- Sortable columns
- Add/Edit asset modal or drawer
- Delete with confirmation

### `/assets/{id}`
- Detailed view of single asset
- Price history chart
- Edit button, delete button

### `/settings`
- Change base currency
- Update display name
- Change password

## 7. UI/UX Guidelines
- Use shadcn/ui components exclusively
- Dark mode support from day one (shadcn handles this)
- Responsive: mobile-first, works on all screen sizes
- Color coding: green for profit, red for loss
- Loading skeletons while data fetches
- Toast notifications for success/error actions
- Currency formatting: proper locale-based number formatting (1.234,56 for TRY)

## 8. Security
- Passwords hashed with bcrypt (min 12 rounds)
- JWT access tokens expire in 15 minutes
- Refresh tokens expire in 7 days, stored in httpOnly cookie
- All asset endpoints verify user ownership
- Rate limiting on auth endpoints (5 req/min)
- Input validation on all endpoints (Pydantic)
- CORS restricted to frontend origin only

## 9. Non-functional Requirements
- API response time < 500ms for dashboard (excluding external price fetches)
- Price cache: 5-minute TTL to avoid excessive API calls
- Database indexes on: user_id, asset_type, symbol, snapshot_date
- Docker Compose for local development (backend + frontend + postgres)
- Environment-based config (.env files, never committed)

## 10. Out of Scope (Phase 1)
- Income/expense tracking (Phase 2)
- Credit card statement parsing (Phase 2)
- AI chatbot (Phase 3)
- Mobile app
- Multi-user sharing / family accounts
- Tax calculations
- Transaction history (buy/sell log)
