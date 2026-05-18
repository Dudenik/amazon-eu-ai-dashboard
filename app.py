import streamlit as st
import pandas as pd
import plotly.express as px
import os

# =========================================================
# НАЛАШТУВАННЯ СТОРІНКИ
# =========================================================
st.set_page_config(
    page_title="TESLYAR Amazon EU Dashboard",
    layout="wide",
    page_icon="📊"
)

st.title("📊 TESLYAR Amazon EU AI Дашборд")
st.caption("Операційна аналітика на базі штучного інтелекту для маркетплейсів Amazon у ЄС")

# =========================================================
# БОКОВА ПАНЕЛЬ КЕРУВАННЯ
# =========================================================
st.sidebar.header("Керування дашбордом")
top_n = st.sidebar.slider("Топ-N товарів (SKU) за падінням", 5, 20, 10)

# =========================================================
# АВТОМАТИЧНЕ ЗАВАНТАЖЕННЯ / ІМПОРТ ФАЙЛІВ
# =========================================================
march_path = "march 2026.csv"
april_path = "april 2026.csv"

if os.path.exists(march_path) and os.path.exists(april_path):
    st.sidebar.success("✅ Локальні файли (Березень та Квітень) завантажено автоматично!")
    march_file = march_path
    april_file = april_path
else:
    st.header("📁 Завантаження місячних P&L звітів вручну")
    col1, col2 = st.columns(2)
    with col1:
        march_file = st.file_uploader("Завантажити файл за Березень 2026", type=["csv"])
    with col2:
        april_file = st.file_uploader("Завантажити файл за Квітень 2026", type=["csv"])

if not march_file or not april_file:
    st.info("Будь ласка, переконайтеся, що файли 'march 2026.csv' та 'april 2026.csv' лежать у папці з проєктом, або завантажте їх вручну.")
    st.stop()

# =========================================================
# ФУНКЦІЯ ОБРОБКИ ТА ОЧИЩЕННЯ ДАНИХ
# =========================================================
def process_amazon_pl(file_buffer):
    df = pd.read_csv(file_buffer, sep=';')
    cleaned_rows = []
    current_market = "Невідомо"
    
    def clean_num(val):
        if pd.isna(val) or val == '-':
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).replace('\xa0', '').replace(' ', '').replace('%', '').replace(',', '.')
        try:
            return float(s)
        except:
            return 0.0

    for _, row in df.iterrows():
        p_val = str(row['Marketplace / Product']).strip()
        asin_val = row['ASIN']
        sku_val = row['SKU']
        
        if pd.isna(asin_val) and pd.isna(sku_val):
            if p_val and p_val != 'nan':
                current_market = p_val
        else:
            r_dict = row.to_dict()
            r_dict['Marketplace_Cleaned'] = current_market
            cleaned_rows.append(r_dict)
            
    df_res = pd.DataFrame(cleaned_rows)
    
    cols_to_clean = ['Units', 'Sales', 'Net profit', 'Margin', 'ROI']
    for col in cols_to_clean:
        if col in df_res.columns:
            df_res[col] = df_res[col].apply(clean_num)
            
    if 'SKU' in df_res.columns:
        df_res['SKU'] = df_res['SKU'].astype(str).str.strip()
        
    return df_res

march_df = process_amazon_pl(march_file)
april_df = process_amazon_pl(april_file)

# Зведення даних
merged_df = pd.merge(
    march_df[['SKU', 'Marketplace_Cleaned', 'Sales', 'Net profit']],
    april_df[['SKU', 'Marketplace_Cleaned', 'Sales', 'Net profit']],
    on=['SKU', 'Marketplace_Cleaned'],
    suffixes=("_March", "_April")
)

merged_df["Difference"] = merged_df["Net profit_April"] - merged_df["Net profit_March"]

sales_march = merged_df["Sales_March"].sum()
sales_april = merged_df["Sales_April"].sum()
profit_march = merged_df["Net profit_March"].sum()
profit_april = merged_df["Net profit_April"].sum()

margin_march = (profit_march / sales_march * 100) if sales_march != 0 else 0
margin_april = (profit_april / sales_april * 100) if sales_april != 0 else 0

# =========================================================
# БЛОК 1: СТРАТЕГІЧНИЙ ОГЛЯД ПОРТФЕЛЯ
# =========================================================
st.header("📈 1.  Стратегічний огляд портфеля")
kpi1, kpi2, kpi3 = st.columns(3)

with kpi1:
    st.metric("Загальні продажі (Sales)", f"€{sales_april:,.2f}", f"{((sales_april - sales_march)/sales_march)*100:+.1f}%")
with kpi2:
    st.metric("Чистий прибуток (Net Profit)", f"€{profit_april:,.2f}", f"{((profit_april - profit_march)/profit_march)*100:+.1f}%")
with kpi3:
    st.metric("Маржинальність (Margin)", f"{margin_april:.1f}%", f"{margin_april - margin_march:+.1f}% (abs.)")

chart_df = pd.DataFrame({
    "Місяць": ["Березень", "Березень", "Квітень", "Квітень"],
    "Метрика": ["Продажі (€)", "Чистий прибуток (€)", "Продажі (€)", "Чистий прибуток (€)"],
    "Значення": [sales_march, profit_march, sales_april, profit_april]
})
fig = px.bar(chart_df, x="Місяць", y="Значення", color="Метрика", barmode="group", title="Глобальна динаміка продажів та прибутку")
st.plotly_chart(fig, use_container_width=True)

# =========================================================
# БЛОК 2: АНАЛІТИКА ПРОБЛЕМНИХ ТОВАРІВ
# =========================================================
st.header("🔻 2. Проблемні позиції (Падіння прибутку)")

worst_skus = merged_df.sort_values("Difference").head(top_n)
worst_skus["Display_Name"] = worst_skus["SKU"] + " (" + worst_skus["Marketplace_Cleaned"] + ")"

fig_sku = px.bar(
    worst_skus.sort_values("Difference", ascending=True), 
    x="Difference", y="Display_Name", orientation="h",
    title=f"Топ-{top_n} SKU з найбільшим просіданням прибутку",
    color="Difference", color_continuous_scale="Reds_r"
)
st.plotly_chart(fig_sku, use_container_width=True)

st.dataframe(
    worst_skus[['SKU', 'Marketplace_Cleaned', 'Net profit_March', 'Net profit_April', 'Difference']].rename(
        columns={"Marketplace_Cleaned": "Маркетплейс", "Net profit_March": "Прибуток Березень", "Net profit_April": "Прибуток Квітень", "Difference": "Зміна прибутку"}
    ), use_container_width=True
)

# =========================================================
# БЛОК 3: СТРАТЕГІЧНИЙ AI-АНАЛІТИЧНИЙ РУШІЙ
# =========================================================
st.header("🧠 3. Стратегічний AI-аналіз портфеля")

sales_change_pct = ((sales_april - sales_march) / sales_march) * 100 if sales_march != 0 else 0
profit_change_pct = ((profit_april - profit_march) / profit_march) * 100 if profit_march != 0 else 0

top_decline_sku = worst_skus.iloc[0]['SKU']
top_decline_market = worst_skus.iloc[0]['Marketplace_Cleaned']
top_decline_val = worst_skus.iloc[0]['Difference']

m_mar = march_df.groupby('Marketplace_Cleaned')['Net profit'].sum().to_frame()
m_apr = april_df.groupby('Marketplace_Cleaned')['Net profit'].sum().to_frame()
m_comp = m_mar.join(m_apr, lsuffix='_Mar', rsuffix='_Apr').fillna(0)
m_comp['Change'] = m_comp['Net profit_Apr'] - m_comp['Net profit_Mar']

worst_market = m_comp.sort_values('Change').index[0]
worst_market_change = m_comp.sort_values('Change')['Change'].iloc[0]

unprofitable_april = merged_df[merged_df["Net profit_April"] < 0].shape[0]

# Безпечне зшивання тексту через круглі дужки (100% захист від IndentationError)
insights_text = (
    "### 📊 Головні висновки на основі аналізу завантажених даних:\n\n"
    f"• **Динаміка виручки:** Загальні продажі змінилися на **{sales_change_pct:.1f}%** (з €{sales_march:,.2f} до €{sales_april:,.2f}).\n"
    f"• **Динаміка прибутку:** Чистий прибуток змінився на **{profit_change_pct:.1f}%** (з €{profit_march:,.2f} до €{profit_april:,.2f}).\n"
    f"• **Найбільш проблемний регіон:** Маркетплейс **{worst_market}** показав найгіршу фінансову динаміку портфеля, втративши **€{abs(worst_market_change):,.2f}** чистого прибутку порівняно з попереднім місяцем.\n"
    f"• **Головна точка падіння серед товарів:** Найбільше просідання зафіксовано за артикулом **{top_decline_sku}** на маркетплейсі **{top_decline_market}** (втрата €{abs(top_decline_val):,.2f}).\n"
    f"• **Зона ризику:** Наразі **{unprofitable_april}** SKU перетнули поріг рентабельності та зафіксували чистий збиток.\n\n"
    "---\n"
    "### ⚠ Автоматичні антикризисні рекомендації для менеджменту:\n"
    f"1. **Оптимізація витрат для {worst_market}:** Оскільки цей маркетплейс продемонстрував найгірший результат, необхідно терміново перевірити структуру локальних витрат (комісії Amazon FBA, вартість зберігання або нюанси локального ПДВ/VAT) саме в **{worst_market}**.\n"
    f"2. **Аудит маркетингового бюджету по SKU {top_decline_sku}:** Необхідно стабілізувати маржинальність головного продукту-аутсайдера шляхом оновлення ціноутворення або перегляду ефективності рекламних ставок (PPC)."
)

st.info(insights_text)