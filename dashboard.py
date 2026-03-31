import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine

st.set_page_config(
    page_title="Superstore Dashboard",
    page_icon="https://wa9tna.wordpress.com/wp-content/uploads/2026/03/76d97a05-c24b-493f-873a-5bc5545026a4.png",
    layout="wide"
)

DB_USER     = "postgres"
DB_PASSWORD = "1234"
DB_HOST     = "localhost"
DB_PORT     = "5432"
DB_NAME     = "superstore_db"


@st.cache_data
def load_data():
    """
    Connect to PostgreSQL, load all tables, merge them into one DataFrame,
    and compute extra columns needed for the dashboard.
    """
    engine = create_engine(
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    # Load each table
    orders        = pd.read_sql("SELECT * FROM orders",        engine)
    order_details = pd.read_sql("SELECT * FROM order_details", engine)
    products      = pd.read_sql("SELECT * FROM products",      engine)
    customers     = pd.read_sql("SELECT * FROM customers",     engine)
    categories    = pd.read_sql("SELECT * FROM categories",    engine)
    regions       = pd.read_sql("SELECT * FROM regions",       engine)

    df = (order_details
          .merge(orders,     on="order_id",    how="left")
          .merge(products,   on="product_id",  how="left")
          .merge(categories, on="category_id", how="left")
          .merge(customers,  on="customer_id", how="left")
          .merge(regions,    on="postal_code", how="left"))


    df["order_date"] = pd.to_datetime(df["order_date"])
    df["ship_date"]  = pd.to_datetime(df["ship_date"])


    df["year"]       = df["order_date"].dt.year
    df["year_month"] = df["order_date"].dt.to_period("M").astype(str)

    df["profit_margin"] = (df["profit"] / df["sales"].replace(0, np.nan)) * 100

    return df


try:
    df = load_data()
except Exception as e:
    st.error(f"Could not connect to PostgreSQL: {e}")
    st.info("Please update DB_USER, DB_PASSWORD, DB_HOST, DB_PORT and DB_NAME in dashboard.py")
    st.stop()

st.sidebar.title("🔍 Filters")
st.sidebar.markdown("Use the filters below to explore the data.")

def multiselect_all(label, series):
    options = sorted(series.dropna().unique().tolist())
    return st.sidebar.multiselect(label, options=options, default=options)

selected_regions    = multiselect_all("Region",   df["region"])
selected_categories = multiselect_all("Category", df["category_name"])
selected_years      = multiselect_all("Year",     df["year"])

filtered_df = df[
    df["region"].isin(selected_regions) &
    df["category_name"].isin(selected_categories) &
    df["year"].isin(selected_years)
]

if filtered_df.empty:
    st.warning("No data matches the selected filters. Please adjust your selection.")
    st.stop()

st.title("🛒 Superstore Sales Dashboard")
st.markdown(f"Showing **{filtered_df.shape[0]:,}** records based on current filters.")
st.markdown("---")


st.subheader("📊 Key Performance Indicators")

col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 Total Sales",       f"${filtered_df['sales'].sum():,.0f}")
col2.metric("📈 Total Profit",      f"${filtered_df['profit'].sum():,.0f}")
col3.metric("📉 Avg Profit Margin", f"{filtered_df['profit_margin'].mean():.1f}%")
col4.metric("🧾 Total Orders",      f"{filtered_df['order_id'].nunique():,}")

st.markdown("---")


st.subheader(" Monthly Sales Trend")

monthly = (filtered_df
           .groupby("year_month")["sales"]
           .sum()
           .reset_index()
           .sort_values("year_month"))

fig, ax = plt.subplots(figsize=(12, 4))
ax.plot(monthly["year_month"], monthly["sales"],
        marker="o", linewidth=2, markersize=4, color="steelblue")
ax.set(xlabel="Month", ylabel="Total Sales ($)", title="Monthly Sales Trend")
plt.xticks(rotation=45, ha="right", fontsize=8)
plt.tight_layout()
st.pyplot(fig)
plt.close()

st.markdown("---")

st.subheader("📦 Performance by Category")

col_a, col_b = st.columns(2)

def bar_chart(ax, data, x_col, y_col, title, ylabel, colors):
    """Generic helper to draw a bar chart on a given axes."""
    ax.bar(data[x_col], data[y_col], color=colors)
    ax.set(title=title, xlabel="Category", ylabel=ylabel)

with col_a:
   
    sales_cat = (filtered_df.groupby("category_name")["sales"]
                 .sum().reset_index().sort_values("sales", ascending=False))

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(sales_cat["category_name"], sales_cat["sales"],
                  color=["#66c2a5", "#fc8d62", "#8da0cb"])
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 500,
                f"${bar.get_height():,.0f}",
                ha="center", fontsize=9)
    ax.set(title="Sales by Category", xlabel="Category", ylabel="Total Sales ($)")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

with col_b:
    profit_cat = (filtered_df.groupby("category_name")["profit"]
                  .sum().reset_index().sort_values("profit", ascending=False))

    colors = ["green" if p > 0 else "red" for p in profit_cat["profit"]]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(profit_cat["category_name"], profit_cat["profit"], color=colors)
    ax.set(title="Profit by Category", xlabel="Category", ylabel="Total Profit ($)")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()

st.markdown("---")

st.subheader("🏆 Top 10 Products by Sales")

top10 = (filtered_df.groupby("product_name")["sales"]
         .sum().reset_index()
         .sort_values("sales", ascending=True)
         .tail(10))

fig, ax = plt.subplots(figsize=(10, 5))
ax.barh(top10["product_name"], top10["sales"], color="coral")
ax.set(xlabel="Total Sales ($)", title="Top 10 Products by Sales")
plt.tight_layout()
st.pyplot(fig)
plt.close()

st.markdown("---")

st.subheader("🗺️ Sales Heatmap: Region × Category")

pivot = filtered_df.pivot_table(
    index="region", columns="category_name",
    values="sales", aggfunc="sum"
).fillna(0)

fig, ax = plt.subplots(figsize=(8, 4))
sns.heatmap(pivot, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax, linewidths=0.5)
ax.set(title="Sales by Region and Category", xlabel="Category", ylabel="Region")
plt.tight_layout()
st.pyplot(fig)
plt.close()

st.markdown("---")

st.subheader(" Profit Distribution")

mean_profit = filtered_df["profit"].mean()
fig, ax = plt.subplots(figsize=(9, 4))
sns.histplot(filtered_df["profit"], bins=60, kde=True, color="mediumseagreen", ax=ax)
ax.axvline(mean_profit, color="red", linestyle="--", label=f"Mean: ${mean_profit:.0f}")
ax.set(xlabel="Profit ($)", ylabel="Count", title="Distribution of Profit")
ax.legend()
plt.tight_layout()
st.pyplot(fig)
plt.close()

st.markdown("---")
st.caption(" Superstore Analytics Dashboard — Built with Streamlit · Data from PostgreSQL")
