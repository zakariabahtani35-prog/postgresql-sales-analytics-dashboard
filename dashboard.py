import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


st.set_page_config(
    page_title="Superstore Dashboard",
    page_icon="🛒",
    layout="wide"
)

# Database credentials — store these in st.secrets or environment variables
# in a real production environment.
DB_CONFIG = {
    "user":     "postgres",
    "password": "1234",
    "host":     "localhost",
    "port":     "5432",
    "name":     "superstore_db_1",
}

# Shared chart style applied globally
sns.set_theme(style="whitegrid", font_scale=1.0)



def get_engine():
    """
    Build and return a SQLAlchemy engine from DB_CONFIG.
    Raises SQLAlchemyError if the connection cannot be established.
    """
    url = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['name']}"
    )
    engine = create_engine(url, pool_pre_ping=True)
    # Verify the connection is alive before returning
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine


def read_table(engine, table_name: str) -> pd.DataFrame:
    """Safely read a full table from the database."""
    return pd.read_sql(f"SELECT * FROM {table_name}", engine)

@st.cache_data
def load_data() -> pd.DataFrame:
    """
    Connect to PostgreSQL, load all tables, merge them into one flat
    DataFrame, and return it.  Results are cached by Streamlit so the
    database is only queried once per session.
    """
    engine = get_engine()

    # Load raw tables
    tables = {
        "orders":        read_table(engine, "orders"),
        "order_details": read_table(engine, "order_details"),
        "products":      read_table(engine, "products"),
        "customers":     read_table(engine, "customers"),
        "categories":    read_table(engine, "categories"),
        "regions":       read_table(engine, "regions"),
    }

    # Build one flat DataFrame through sequential left-joins
    df = (
        tables["order_details"]
        .merge(tables["orders"],     on="order_id",    how="left")
        .merge(tables["products"],   on="product_id",  how="left")
        .merge(tables["categories"], on="category_id", how="left")
        .merge(tables["customers"],  on="customer_id", how="left")
        .merge(tables["regions"],    on="postal_code", how="left")
    )

    return df

def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse dates, add derived time columns, and compute profit_margin.
    This is kept separate from load_data so transformations are easy to test.
    """
    df = df.copy()

    # Parse date columns
    df["order_date"] = pd.to_datetime(df["order_date"])
    df["ship_date"]  = pd.to_datetime(df["ship_date"])

    # Time granularity columns used in charts
    df["year"]       = df["order_date"].dt.year
    df["year_month"] = df["order_date"].dt.to_period("M").astype(str)

    # Profit margin — guard against division by zero
    df["profit_margin"] = (df["profit"] / df["sales"].replace(0, np.nan)) * 100

    return df

def render_sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Render sidebar multiselect filters for Region, Category, and Year.
    Returns the filtered DataFrame.
    """
    st.sidebar.title("🔍 Filters")
    st.sidebar.markdown("Use the filters below to explore the data.")

    def multiselect(label: str, column: str) -> list:
        """Helper that builds a multiselect defaulting to all options."""
        options = sorted(df[column].dropna().unique().tolist())
        return st.sidebar.multiselect(label, options=options, default=options)

    selected_regions    = multiselect("Region",   "region")
    selected_categories = multiselect("Category", "category_name")
    selected_years      = multiselect("Year",     "year")

    mask = (
        df["region"].isin(selected_regions) &
        df["category_name"].isin(selected_categories) &
        df["year"].isin(selected_years)
    )
    return df[mask]


def compute_kpis(df: pd.DataFrame) -> dict:
    """
    Compute the four headline KPIs and return them as a dictionary.
    Isolating this logic makes unit-testing straightforward.
    """
    return {
        "total_sales":   df["sales"].sum(),
        "total_profit":  df["profit"].sum(),
        "avg_margin":    df["profit_margin"].mean(),
        "total_orders":  df["order_id"].nunique(),
    }


def render_kpis(kpis: dict) -> None:
    """Display the four KPI metric cards in a single row."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(" Total Sales",       f"${kpis['total_sales']:,.0f}")
    col2.metric(" Total Profit",      f"${kpis['total_profit']:,.0f}")
    col3.metric(" Avg Profit Margin", f"{kpis['avg_margin']:.1f}%")
    col4.metric(" Total Orders",      f"{kpis['total_orders']:,}")


def _render_figure(fig) -> None:
    """Helper: display a matplotlib figure in Streamlit, then close it."""
    st.pyplot(fig)
    plt.close(fig)


def plot_monthly_sales_trend(df: pd.DataFrame) -> None:
    """Line chart of total sales aggregated by calendar month."""
    monthly = (
        df.groupby("year_month")["sales"]
        .sum()
        .reset_index()
        .sort_values("year_month")
    )

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(
        monthly["year_month"], monthly["sales"],
        marker="o", linewidth=2, markersize=4, color="steelblue"
    )
    ax.set(title="Monthly Sales Trend", xlabel="Month", ylabel="Total Sales ($)")
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.tight_layout()
    _render_figure(fig)


def plot_sales_by_category(df: pd.DataFrame) -> None:
    """
    Bar chart of total sales per category.
    Each bar is labelled with its dollar value.
    """
    data = (
        df.groupby("category_name")["sales"]
        .sum()
        .reset_index()
        .sort_values("sales", ascending=False)
    )

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(
        data["category_name"], data["sales"],
        color=["#66c2a5", "#fc8d62", "#8da0cb"]
    )
    for bar in bars:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 500,
            f"${bar.get_height():,.0f}",
            ha="center", fontsize=9
        )
    ax.set(title="Sales by Category", xlabel="Category", ylabel="Total Sales ($)")
    plt.tight_layout()
    _render_figure(fig)


def plot_profit_by_category(df: pd.DataFrame) -> None:
    """
    Bar chart of total profit per category.
    Bars are green for positive profit and red for negative.
    """
    data = (
        df.groupby("category_name")["profit"]
        .sum()
        .reset_index()
        .sort_values("profit", ascending=False)
    )

    colors = ["green" if p > 0 else "red" for p in data["profit"]]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(data["category_name"], data["profit"], color=colors)
    ax.set(title="Profit by Category", xlabel="Category", ylabel="Total Profit ($)")
    plt.tight_layout()
    _render_figure(fig)


def plot_top10_products(df: pd.DataFrame) -> None:
    """Horizontal bar chart showing the top 10 products by total sales."""
    top10 = (
        df.groupby("product_name")["sales"]
        .sum()
        .reset_index()
        .sort_values("sales", ascending=True)
        .tail(10)
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(top10["product_name"], top10["sales"], color="coral")
    ax.set(title="Top 10 Products by Sales", xlabel="Total Sales ($)")
    plt.tight_layout()
    _render_figure(fig)


def plot_sales_heatmap(df: pd.DataFrame) -> None:
    """Heatmap of total sales broken down by Region (rows) × Category (cols)."""
    pivot = df.pivot_table(
        index="region", columns="category_name",
        values="sales", aggfunc="sum"
    ).fillna(0)

    fig, ax = plt.subplots(figsize=(8, 4))
    sns.heatmap(pivot, annot=True, fmt=".0f", cmap="YlOrRd", ax=ax, linewidths=0.5)
    ax.set(title="Sales by Region and Category", xlabel="Category", ylabel="Region")
    plt.tight_layout()
    _render_figure(fig)


def plot_profit_distribution(df: pd.DataFrame) -> None:
    """
    Histogram + KDE of the profit column.
    A vertical dashed line marks the mean profit value.
    """
    mean_profit = df["profit"].mean()

    fig, ax = plt.subplots(figsize=(9, 4))
    sns.histplot(df["profit"], bins=60, kde=True, color="mediumseagreen", ax=ax)
    ax.axvline(mean_profit, color="red", linestyle="--",
               label=f"Mean: ${mean_profit:.0f}")
    ax.set(title="Distribution of Profit", xlabel="Profit ($)", ylabel="Count")
    ax.legend()
    plt.tight_layout()
    _render_figure(fig)

def main() -> None:
    """
    Entry point: wire everything together and render the full dashboard.
    All sections follow the same pattern:
        1. Subheader
        2. Chart / widget
        3. Divider
    """

    # Load & prepare data 
    try:
        raw_df = load_data()
    except SQLAlchemyError as e:
        st.error(f"Database connection error: {e}")
        st.info(
            "Please update the DB_CONFIG dictionary at the top of dashboard.py "
            "with your PostgreSQL credentials."
        )
        st.stop()
    except Exception as e:
        st.error(f"Unexpected error while loading data: {e}")
        st.stop()

    df = prepare_data(raw_df)

    #  Sidebar filters
    filtered_df = render_sidebar_filters(df)

    if filtered_df.empty:
        st.warning(" No data matches the selected filters. Please adjust your selection.")
        st.stop()

    # Page header 
    st.title(" Superstore Sales Dashboard")
    st.markdown(f"Showing **{filtered_df.shape[0]:,}** records based on current filters.")
    st.markdown("---")

    # KPIs 
    st.subheader(" Key Performance Indicators")
    render_kpis(compute_kpis(filtered_df))
    st.markdown("---")

    #  Monthly Sales Trend 
    st.subheader(" Monthly Sales Trend")
    plot_monthly_sales_trend(filtered_df)
    st.markdown("---")

    # --- Performance by Category (two charts side by side) 
    st.subheader(" Performance by Category")
    col_left, col_right = st.columns(2)
    with col_left:
        plot_sales_by_category(filtered_df)
    with col_right:
        plot_profit_by_category(filtered_df)
    st.markdown("---")

    #  Top 10 Products 
    st.subheader(" Top 10 Products by Sales")
    plot_top10_products(filtered_df)
    st.markdown("---")

    # --- Heatmap ---
    st.subheader(" Sales Heatmap: Region × Category")
    plot_sales_heatmap(filtered_df)
    st.markdown("---")

    #  Profit Distribution 
    st.subheader(" Profit Distribution")
    plot_profit_distribution(filtered_df)
    st.markdown("---")

    # Footer 
    st.caption(" Superstore Analytics Dashboard — Built with Streamlit · Data from PostgreSQL")


# Run the dashboard
if __name__ == "__main__":
    main()
