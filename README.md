# 🛒 Superstore Sales Analytics Dashboard
### Data Engineering · Business Intelligence · Interactive Analytics

> A production-style, end-to-end data analytics project that ingests retail transactional data from a normalized PostgreSQL database, processes it with Pandas, and exposes actionable business intelligence through a fully interactive Streamlit dashboard.

---

## 📋 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Business Context](#2-business-context)
3. [Project Architecture](#3-project-architecture)
4. [Data Pipeline](#4-data-pipeline)
5. [Database Design](#5-database-design-data-model)
6. [Data Preparation & Feature Engineering](#6-data-preparation--feature-engineering)
7. [Key Performance Indicators (KPIs)](#7-key-performance-indicators-kpis)
8. [Dashboard Features](#8-dashboard-features)
9. [Data Visualizations](#9-data-visualizations)
10. [Technologies Used](#10-technologies-used)
11. [Project Structure](#11-project-structure)
12. [Installation Guide](#12-installation-guide)
13. [How to Run the Dashboard](#13-how-to-run-the-dashboard)
14. [Example Business Insights](#14-example-business-insights)
15. [Performance Considerations](#15-performance-considerations)
16. [Limitations](#16-limitations)
17. [Future Improvements](#17-future-improvements)
18. [Author](#18-author)

---

## 1. Project Overview

This project delivers a **fully interactive Business Intelligence dashboard** for a fictional retail company — *Superstore* — built entirely in Python and powered by a PostgreSQL relational database.

**Objective:** Transform raw transactional retail data into a real-time, filterable analytics dashboard that enables business stakeholders to monitor sales performance, profitability, and product trends across regions and categories — without writing a single line of SQL.

**Business Problem Solved:**
- Sales managers lack a unified view of performance across regions and product lines.
- Finance teams cannot quickly assess profit margins at the category or product level.
- Leadership has no tool to detect seasonal trends or regional underperformance.

This dashboard solves all three problems in a single, self-service interface.

---

## 2. Business Context

**Superstore** is a mid-sized retail company operating across multiple U.S. regions, selling products across three major categories: **Furniture**, **Office Supplies**, and **Technology**.

The business faces the following analytical challenges:
- Sales and profit data are spread across multiple operational database tables.
- Stakeholders need to slice performance by **region**, **product category**, and **time period** without relying on data engineering teams.
- Monthly revenue fluctuations and thin profit margins in certain categories require close monitoring.

This project addresses these challenges by building a **BI-grade analytics layer** on top of the existing transactional PostgreSQL database, surfacing KPIs and visualizations in a web-accessible dashboard.

---

## 3. Project Architecture

The system follows a **linear data flow** from storage to visualization:

```
PostgreSQL Database
        │
        │  SQLAlchemy (connection + query layer)
        ▼
  Raw DataFrames (6 tables)
        │
        │  Pandas (merge + feature engineering)
        ▼
  Flat Analytical DataFrame
        │
        │  Streamlit (interactive filters)
        ▼
  Filtered DataFrame
        │
        │  Matplotlib / Seaborn (charting)
        ▼
  Interactive Web Dashboard
```

The architecture deliberately keeps all layers **decoupled** — the database layer, transformation layer, and presentation layer each have their own functions — making each component independently testable and replaceable.

---

## 4. Data Pipeline

The pipeline executes the following steps end-to-end:

1. **Data Ingestion** — Six PostgreSQL tables are read into memory using `pd.read_sql()` via a SQLAlchemy engine.

2. **Data Validation** — A `SELECT 1` health check confirms the database connection is alive before any data is loaded.

3. **Data Merging** — The six normalized tables are joined into a single flat analytical DataFrame using a chain of left merges.

4. **Data Cleaning** — Date columns are parsed from strings to `datetime64` objects; `NaN` guards prevent division-by-zero errors.

5. **Feature Engineering** — Derived columns (`year`, `year_month`, `profit_margin`) are computed from base columns.

6. **Caching** — The merged and cleaned DataFrame is cached in Streamlit session memory using `@st.cache_data`, eliminating redundant database round-trips.

7. **Interactive Filtering** — Users filter the dataset dynamically in the sidebar by region, category, and year.

8. **KPI Aggregation** — Four headline metrics are computed on the filtered slice using Pandas aggregations.

9. **Visualization** — Six charts render from the filtered dataset using Matplotlib and Seaborn.

---

## 5. Database Design (Data Model)

The PostgreSQL database uses a **normalized star-schema-like design** where `order_details` acts as the central fact table, linked to five dimension tables.

```
customers ──────────────────────────────┐
                                        │
categories ──────────────┐              │
                         ▼              ▼
regions ──── orders ◄── order_details ──► products
              │
              └── (postal_code joins regions)
```

### Table Descriptions

| Table | Role | Key Columns |
|---|---|---|
| `order_details` | **Fact table** — one row per line item | `order_id`, `product_id`, `sales`, `profit`, `quantity`, `discount` |
| `orders` | Order header — date, ship mode | `order_id`, `customer_id`, `order_date`, `ship_date`, `ship_mode` |
| `products` | Product master data | `product_id`, `category_id`, `product_name` |
| `categories` | Category reference | `category_id`, `category_name`, `sub_category` |
| `customers` | Customer profiles | `customer_id`, `customer_name`, `segment` |
| `regions` | Geographic data | `postal_code`, `city`, `state`, `region`, `country` |

### Join Logic

```
order_details  →  orders        (on order_id)
             →  products       (on product_id)
             →  categories     (on category_id)
             →  customers      (on customer_id)
             →  regions        (on postal_code via orders)
```

All joins are `LEFT JOIN` to preserve every line item even if a dimension record is missing.

---

## 6. Data Preparation & Feature Engineering

All transformations are handled in the `prepare_data()` function, which operates on the merged flat DataFrame:

### Date Parsing
```python
df["order_date"] = pd.to_datetime(df["order_date"])
df["ship_date"]  = pd.to_datetime(df["ship_date"])
```
Converts string dates to proper `datetime64` objects, enabling time-based grouping and sorting.

### Time Granularity Columns
```python
df["year"]       = df["order_date"].dt.year         # For year filter
df["year_month"] = df["order_date"].dt.to_period("M").astype(str)  # For trend chart
```
Pre-computes time columns to avoid repeated derivation during chart rendering.

### Profit Margin Calculation
```python
df["profit_margin"] = (df["profit"] / df["sales"].replace(0, np.nan)) * 100
```
Computes per-row profit margin as a percentage. `.replace(0, np.nan)` prevents division-by-zero errors on zero-revenue rows, which would otherwise produce `Inf` values and corrupt KPI aggregations.

---

## 7. Key Performance Indicators (KPIs)

The dashboard surfaces four headline KPIs computed from the current filter selection:

| KPI | Formula | Business Purpose |
|---|---|---|
| **Total Sales** | `sum(sales)` | Measures top-line revenue performance |
| **Total Profit** | `sum(profit)` | Reveals net profitability after costs |
| **Avg Profit Margin** | `mean(profit_margin)` | Indicates pricing and cost efficiency |
| **Total Orders** | `nunique(order_id)` | Tracks order volume and customer demand |

These four metrics give a leadership team a **30-second health check** on business performance across any combination of region, category, and time period.

**Decision-making use cases:**
- A drop in **profit margin** alongside stable **total sales** signals rising costs or excessive discounting.
- A spike in **total orders** with flat **total sales** may indicate a shift toward lower-ticket items.
- Regional filtering isolates whether underperformance is systemic or geographic.

---

## 8. Dashboard Features

The dashboard is designed for **self-service analytics** — no SQL or coding knowledge required.

### Interactive Filters (Sidebar)
- **Region** — filter by one or more U.S. geographic regions
- **Category** — isolate specific product categories
- **Year** — compare performance across individual years or custom ranges

All filters default to **select all**, ensuring the full dataset is visible on first load. Every chart and KPI card updates **instantly** when filters change.

### Dynamic Data Exploration
- Filter combinations update all six charts and four KPI cards simultaneously.
- An empty-filter guard displays a warning and halts rendering if no records match the selection.
- A record counter confirms exactly how many rows are driving the current view.

---

## 9. Data Visualizations

### 📅 Monthly Sales Trend
**Type:** Line chart  
**Aggregation:** Total sales grouped by `year_month`  
**Business Insight:** Reveals seasonality, growth trajectories, and revenue dips. Useful for identifying Q4 peaks or post-holiday slowdowns, enabling better inventory and staffing decisions.

---

### 📦 Sales by Category
**Type:** Bar chart with value labels  
**Aggregation:** Total sales grouped by `category_name`  
**Business Insight:** Compares revenue contribution across Furniture, Office Supplies, and Technology. Guides marketing spend and category expansion decisions.

---

### 📦 Profit by Category
**Type:** Bar chart (green = profit, red = loss)  
**Aggregation:** Total profit grouped by `category_name`  
**Business Insight:** A category generating high sales but negative profit (red bar) signals a pricing or cost problem requiring immediate attention. Separates revenue leaders from margin leaders.

---

### 🏆 Top 10 Products by Sales
**Type:** Horizontal bar chart  
**Aggregation:** Total sales grouped by `product_name`, top 10  
**Business Insight:** Identifies the revenue-driving products that should be prioritized in stock replenishment, promotions, and supplier negotiations.

---

### 🗺️ Sales Heatmap (Region × Category)
**Type:** Annotated heatmap  
**Aggregation:** Pivot table of total sales by region and category  
**Business Insight:** Instantly exposes geographic concentration of revenue. A region with low Technology sales but high Office Supplies may represent an untapped cross-selling opportunity.

---

### 📊 Profit Distribution
**Type:** Histogram with KDE overlay and mean line  
**Aggregation:** Per-row `profit` values  
**Business Insight:** Reveals the shape of profitability — whether most transactions are profitable, whether losses are rare outliers or systemic, and whether the profit distribution is skewed. The mean reference line anchors the distribution visually.

---

## 10. Technologies Used

| Technology | Version | Role |
|---|---|---|
| **Python** | 3.9+ | Core programming language |
| **Streamlit** | ≥ 1.30 | Web dashboard framework |
| **Pandas** | ≥ 2.0 | Data manipulation and aggregation |
| **NumPy** | ≥ 1.24 | Numerical operations and NaN handling |
| **PostgreSQL** | ≥ 13 | Relational database and data storage |
| **SQLAlchemy** | ≥ 2.0 | Database connection and ORM layer |
| **Matplotlib** | ≥ 3.7 | Low-level charting engine |
| **Seaborn** | ≥ 0.12 | Statistical visualization (heatmap, histogram) |

---

## 11. Project Structure

```
superstore-dashboard/
│
├── dashboard.py          # Main application — all dashboard logic
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation (this file)
```

### File Descriptions

| File | Purpose |
|---|---|
| `dashboard.py` | Complete Streamlit application: DB connection, data loading, feature engineering, filters, KPIs, and all six visualization functions |
| `requirements.txt` | Pinned Python dependencies for reproducible environment setup |
| `README.md` | Project documentation for portfolio and onboarding |

---

## 12. Installation Guide

### Prerequisites
- Python 3.9 or higher
- PostgreSQL 13 or higher (running locally or remotely)
- The Superstore dataset loaded into your PostgreSQL instance

### Step 1 — Clone the Repository
```bash
git clone https://github.com/your-username/superstore-dashboard.git
cd superstore-dashboard
```

### Step 2 — Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### Step 3 — Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Configure PostgreSQL

Ensure PostgreSQL is running and your Superstore database is populated. Then update the `DB_CONFIG` dictionary at the top of `dashboard.py`:

```python
DB_CONFIG = {
    "user":     "your_postgres_user",
    "password": "your_password",
    "host":     "localhost",          # or remote host
    "port":     "5432",
    "name":     "your_database_name",
}
```

> **Security note:** For production use, replace hardcoded credentials with `st.secrets` or environment variables.

### Step 5 — Verify the Database Connection
```bash
psql -U your_postgres_user -d your_database_name -c "SELECT COUNT(*) FROM orders;"
```
A non-zero row count confirms the database is ready.

---

## 13. How to Run the Dashboard

```bash
streamlit run dashboard.py
```

Streamlit will open your default browser automatically at:

```
http://localhost:8501
```

**What you will see:**
1. A sidebar with three interactive filters (Region, Category, Year)
2. Four KPI metric cards (Sales, Profit, Margin, Orders)
3. Six analytical charts updating in real time as you adjust filters
4. A record counter confirming how many rows drive the current view

---

## 14. Example Business Insights

The following insights are representative of what this dashboard can surface on a typical Superstore dataset:

- **Technology** drives the highest revenue but **Office Supplies** often delivers the highest profit margin — a common retail pattern where high-volume, low-ticket items outperform on margin.
- The **West** region consistently ranks as the top revenue-generating territory; the **South** region frequently shows the weakest performance, suggesting an expansion opportunity.
- A clear **Q4 sales spike** appears in the Monthly Sales Trend, confirming seasonal demand driven by back-to-school and year-end purchasing cycles.
- Several **Furniture** subcategories post negative profit despite strong sales, indicating discounting practices that erode margin.
- The **Profit Distribution** chart reveals a right-skewed distribution: most transactions are modestly profitable, but a small number of high-value Technology orders account for a disproportionate share of total profit.

---

## 15. Performance Considerations

### Streamlit Caching (`@st.cache_data`)
The `load_data()` function is decorated with `@st.cache_data`. This means the six PostgreSQL queries and all merge operations execute **only once per session**. Subsequent filter changes operate entirely on the in-memory DataFrame, eliminating latency from repeated database round-trips.

### Efficient Database Queries
- `pool_pre_ping=True` on the SQLAlchemy engine ensures stale connections are detected and recycled automatically, preventing silent failures on long-running sessions.
- A lightweight `SELECT 1` health check validates connectivity before loading data, providing a fast-fail with a clear error message.

### Pandas Transformations
- All feature engineering (date parsing, derived columns, profit margin) is performed in `prepare_data()`, which runs once on the full dataset. Filtering then operates on pre-computed columns rather than recalculating on each render.
- `df.copy()` in `prepare_data()` prevents in-place mutations of the cached DataFrame, ensuring cache integrity across sessions.

---

## 16. Limitations

| Limitation | Description |
|---|---|
| **Static dataset** | The dashboard reflects data as of the last database load. There is no live ingestion or real-time streaming. |
| **Manual credential configuration** | Database credentials are stored in plain text in `dashboard.py`. Production deployments require `st.secrets` or environment variable injection. |
| **No predictive analytics** | The dashboard is descriptive and diagnostic only. It does not forecast future sales or flag anomalies automatically. |
| **Single-file architecture** | All logic resides in `dashboard.py`. Larger projects would benefit from separating database, transformation, and visualization layers into distinct modules. |
| **No user authentication** | The dashboard has no login layer. Anyone with network access to the Streamlit server can view the data. |

---

## 17. Future Improvements

| Improvement | Description |
|---|---|
| **Sales Forecasting** | Integrate `Prophet` or `scikit-learn` to add a time-series sales forecast panel, enabling proactive inventory planning. |
| **Customer Segmentation** | Apply RFM (Recency, Frequency, Monetary) analysis or K-Means clustering to identify high-value customer cohorts. |
| **Automated ETL Pipeline** | Replace manual data loading with an Apache Airflow or Prefect DAG that refreshes the database on a schedule. |
| **Cloud Deployment** | Deploy the dashboard to Streamlit Community Cloud, AWS, or GCP to make it accessible without a local setup. |
| **Multi-page Dashboard** | Refactor into a multi-page Streamlit app with dedicated pages for Sales, Profitability, Products, and Customer Analytics. |
| **Secrets Management** | Migrate credentials to `st.secrets` or AWS Secrets Manager for secure, production-grade credential handling. |
| **Unit Tests** | Add a `tests/` directory with `pytest` coverage for `compute_kpis()`, `prepare_data()`, and the filter logic. |
| **Export Functionality** | Add CSV/Excel download buttons so stakeholders can extract filtered data directly from the dashboard. |

---

## 18. Author

**[zakaria bahtani]**  
Data Analyst · Data Engineer · Python Developer

- 🔗 [LinkedIn](https://www.linkedin.com/in/zakaria-bahtani-b64251390/)
- 📧 zakariabahtani35@gmail.com

---

*Built with Python · PostgreSQL · Streamlit · Pandas · Matplotlib · Seaborn · SQLAlchemy*
