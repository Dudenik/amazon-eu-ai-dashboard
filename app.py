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

st.title("📊 TESLYAR Amazon EU Професійний AI-Дашборд")
st.caption("Операційна фінансова аналітика на базі штучного інтелекту | ТОВ ТЕСЛЯР")

# =========================================================
# БОКОВА ПАНЕЛЬ КЕРУВАННЯ
# =========================================================
st.sidebar.header("Керування дашбордом")
top_n = st.sidebar.slider("Топ-N товарів за падінням прибутку", 5, 20, 10)

# =========================================================
# АВТОМАТИЧНЕ ЗАВАНТАЖЕННЯ / ІМПОРТ ФАЙЛІВ P&L
# =========================================================
march_path = "march 2026.csv"
april_path = "april 2026.csv"

if os.path.exists(march_path) and os.path.exists(april_path):
    st.sidebar.success("✅ Локальні P&L звіти (Березень/Квітень) завантажено автоматично!")
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
    st.info("Будь ласка, переконайтеся, що файли 'march 2026.csv' та 'april 2026.csv' лежать у папці з проєктом.")
    st.stop()

# =========================================================
# БЕЗПЕЧНИЙ ПАРСЕР P&L (ТОЧНИЙ ФІНАНСОВИЙ РОЗРАХУНОК)
# =========================================================
def process_amazon_advanced(file_buffer):
    # Захист буфера Streamlit від порожнього читання
    if hasattr(file_buffer, 'seek'): file_buffer.seek(0)
    
    try:
        df = pd.read_csv(file_buffer, sep=';')
        if len(df.columns) < 5: 
            if hasattr(file_buffer, 'seek'): file_buffer.seek(0)
            df = pd.read_csv(file_buffer, sep=',')
    except:
        if hasattr(file_buffer, 'seek'): file_buffer.seek(0)
        df = pd.read_csv(file_buffer, sep=',')
        
    df.columns = [str(c).strip() for c in df.columns]
    
    # Гарантуємо наявність потрібних колонок
    for col in ['Marketplace / Product', 'Sales', 'Net profit', 'ASIN', 'SKU']:
        if col not in df.columns:
            df[col] = None if col in ['ASIN', 'SKU'] else (0.0 if col in ['Sales', 'Net profit'] else "Невідомо")

    def clean_num(val):
        if pd.isna(val) or val == '-': return 0.0
        if isinstance(val, (int, float)): return float(val)
        s = str(val).replace('\xa0', '').replace(' ', '').replace('%', '').replace(',', '.')
        try: return float(s)
        except: return 0.0

    # 1. Загальні цифри беремо із заголовків країн (там враховані всі кости аккаунта)
    headers = df[df['ASIN'].isna() & df['SKU'].isna()].copy()
    headers['Sales_Clean'] = headers['Sales'].apply(clean_num)
    headers['Profit_Clean'] = headers['Net profit'].apply(clean_num)
    
    total_sales = headers['Sales_Clean'].sum() if not headers.empty else 0.0
    total_profit = headers['Profit_Clean'].sum() if not headers.empty else 0.0
    
    # 2. Детальні рядки для аналізу товарів (SKU)
    cleaned_rows = []
    current_market = "Невідомо"
    
    for _, row in df.iterrows():
        p_val = str(row.get('Marketplace / Product', '')).strip()
        asin_val = row.get('ASIN')
        sku_val = row.get('SKU')
        
        if pd.isna(asin_val) and pd.isna(sku_val):
            if p_val and p_val != 'nan': current_market = p_val
        else:
            r_dict = row.to_dict()
            r_dict['Marketplace_Cleaned'] = current_market
            r_dict['Product_Name'] = p_val if (p_val and p_val != 'nan') else str(sku_val)
            cleaned_rows.append(r_dict)
            
    df_items = pd.DataFrame(cleaned_rows)
    
    for col in ['SKU', 'Marketplace_Cleaned', 'Product_Name', 'Sales', 'Net profit']:
        if col not in df_items.columns:
            df_items[col] = 0.0 if 'profit' in col or col == 'Sales' else "Невідомо"
            
    for col in ['Units', 'Sales', 'Net profit', 'Margin', 'ROI']:
        if col in df_items.columns: df_items[col] = df_items[col].apply(clean_num)
    if 'SKU' in df_items.columns: df_items['SKU'] = df_items['SKU'].astype(str).str.strip()
        
    return total_sales, total_profit, headers, df_items

# Виклик функції парсингу
sales_march, profit_march, headers_march, items_march = process_amazon_advanced(march_file)
sales_april, profit_april, headers_april, items_april = process_amazon_advanced(april_file)

margin_march = (profit_march / sales_march * 100) if sales_march != 0 else 0
margin_april = (profit_april / sales_april * 100) if sales_april != 0 else 0

# =========================================================
# СКЛЕЮВАННЯ ДАНИХ (БЕЗПЕЧНЕ)
# =========================================================
# 1. По товарах
merged_items = pd.merge(
    items_march[['SKU', 'Marketplace_Cleaned', 'Product_Name', 'Sales', 'Net profit']],
    items_april[['SKU', 'Marketplace_Cleaned', 'Sales', 'Net profit']],
    on=['SKU', 'Marketplace_Cleaned'], suffixes=("_March", "_April"), how='inner'
)

if not merged_items.empty:
    merged_items["Difference"] = merged_items["Net profit_April"] - merged_items["Net profit_March"]
else:
    merged_items = pd.DataFrame(columns=['SKU', 'Marketplace_Cleaned', 'Product_Name', 'Sales_March', 'Net profit_March', 'Sales_April', 'Net profit_April', 'Difference'])

# 2. По регіонах (для пошуку найгіршого маркетплейсу)
h_mar = headers_march[['Marketplace / Product', 'Sales_Clean', 'Profit_Clean']].rename(columns={'Sales_Clean': 'Sales_March', 'Profit_Clean': 'Net profit_March'})
h_apr = headers_april[['Marketplace / Product', 'Sales_Clean', 'Profit_Clean']].rename(columns={'Sales_Clean': 'Sales_April', 'Profit_Clean': 'Net profit_April'})
region_perf = pd.merge(h_mar, h_apr, on='Marketplace / Product', how='outer').fillna(0)
region_perf['Profit_Change'] = region_perf['Net profit_April'] - region_perf['Net profit_March']

# =========================================================
# БЛОК 1: СТРАТЕГІЧНИЙ ОГЛЯД ФІНАНСІВ
# =========================================================
st.header("📈 1. Стратегічний огляд фінансів")
kpi1, kpi2, kpi3 = st.columns(3)

with kpi1: 
    st.metric("Загальні продажі (Sales)", f"€{sales_april:,.2f}", f"{((sales_april - sales_march)/sales_march)*100:+.1f}%" if sales_march else "0%")
with kpi2: 
    st.metric("Чистий прибуток (Net Profit)", f"€{profit_april:,.2f}", f"{((profit_april - profit_march)/profit_march)*100:+.1f}%" if profit_march else "0%")
with kpi3: 
    st.metric("Маржинальність (Margin)", f"{margin_april:.1f}%", f"{margin_april - margin_march:+.1f}% (abs.)")

chart_df = pd.DataFrame({
    "Місяць": ["Березень", "Березень", "Квітень", "Квітень"], 
    "Метрика": ["Продажі (€)", "Чистий прибуток (€)", "Продажі (€)", "Чистий прибуток (€)"], 
    "Значення": [sales_march, profit_march, sales_april, profit_april]
})
st.plotly_chart(px.bar(chart_df, x="Місяць", y="Значення", color="Метрика", barmode="group", title="Глобальна динаміка"), use_container_width=True)

# =========================================================
# БЛОК 2: АНАЛІТИКА ПРОБЛЕМНИХ ТОВАРІВ
# =========================================================
st.header("🔻 2. Проблемні позиції (Падіння прибутку)")
worst_skus = merged_items.sort_values("Difference").head(top_n) if not merged_items.empty else pd.DataFrame()

if not worst_skus.empty and "Difference" in worst_skus.columns:
    worst_skus["Display_Name"] = worst_skus["Product_Name"].astype(str).str.slice(0, 35) + "... (" + worst_skus["Marketplace_Cleaned"] + ")"
    
    fig_sku = px.bar(worst_skus.sort_values("Difference", ascending=True), x="Difference", y="Display_Name", orientation="h", title=f"Топ-{top_n} товарів з найбільшим просіданням прибутку", color="Difference", color_continuous_scale="Reds_r")
    st.plotly_chart(fig_sku, use_container_width=True)
    
    st.dataframe(
        worst_skus[['Product_Name', 'SKU', 'Marketplace_Cleaned', 'Net profit_March', 'Net profit_April', 'Difference']].rename(
            columns={
                "Product_Name": "Назва товару",
                "SKU": "Артикул (SKU)",
                "Marketplace_Cleaned": "Маркетплейс",
                "Net profit_March": "Прибуток Березень (€)",
                "Net profit_April": "Прибуток Квітень (€)",
                "Difference": "Зміна прибутку (€)"
            }
        ), use_container_width=True
    )
else:
    st.info("Недостатньо даних для побудови графіка товарів.")

# =========================================================
# БЛОК 3: СТРАТЕГІЧНИЙ AI-АНАЛІЗ
# =========================================================
st.header("🧠 3. Комплексний AI-аналіз портфеля")

if not region_perf.empty:
    worst_market = region_perf.sort_values('Profit_Change').iloc[0]['Marketplace / Product']
    worst_market_change = region_perf.sort_values('Profit_Change').iloc[0]['Profit_Change']
else:
    worst_market = "Невідомо"
    worst_market_change = 0.0

if not worst_skus.empty:
    top_decline_product = worst_skus.iloc[0].get('Product_Name', 'Невідомо')
    top_decline_sku = worst_skus.iloc[0].get('SKU', 'Невідомо')
    top_decline_market = worst_skus.iloc[0].get('Marketplace_Cleaned', 'Невідомо')
    top_decline_val = worst_skus.iloc[0].get('Difference', 0.0)
else:
    top_decline_product, top_decline_sku, top_decline_market, top_decline_val = "Невідомо", "Невідомо", "Невідомо", 0.0

unprofitable_april = items_april[items_april["Net profit"] < 0].shape[0] if not items_april.empty else 0
profit_pct = ((profit_april - profit_march)/profit_march)*100 if profit_march != 0 else 0

ai_text = (
    "### 📊 Головні висновки на основі фінансового аналізу:\n\n"
    f"• **Динаміка прибутку:** Чистий прибуток компанії змінився на {profit_pct:.1f}% (з €{profit_march:,.2f} до €{profit_april:,.2f}).\n"
    f"• **Найбільш проблемний регіон:** Маркетплейс **{worst_market}** показав найгіршу фінансову динаміку (втрата/ріст прибутку на €{abs(worst_market_change):,.2f}).\n"
    f"• **Артикул-аутсайдер:** Головним чинником падіння прибутку серед товарів став продукт **\"{top_decline_product}\"** (SKU: `{top_decline_sku}`) на маркетплейсі **{top_decline_market}** (чиста зміна на €{abs(top_decline_val):,.2f}).\n"
    f"• **Операційний ризик:** Одразу **{unprofitable_april}** товарних позицій не показали рентабельності у квітні й зафіксували чистий збиток.\n\n"
    "---\n"
    "### ⚠ Автоматичні антикризисні рекомендації:\n"
    f"1. **Аудит регіону {worst_market}:** З огляду на різке падіння прибутку, необхідно терміново перевірити структуру витрат (Amazon FBA, комісії, повернення) на цьому маркетплейсі.\n"
    f"2. **Точкова оптимізація \"{top_decline_product}\":** Необхідно перевірити кости даної картки на {top_decline_market} (SKU: `{top_decline_sku}`) та переглянути ціноутворення."
)

st.info(ai_text)