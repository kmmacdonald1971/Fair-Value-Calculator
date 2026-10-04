import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Fair Value Calculator", layout="wide", page_icon="📈")

st.title("Fair Value Calculator")
st.caption("Estimate stock worth based on EPS, expected growth rates, and exit P/E multiples.")

# --- SIDEBAR INPUTS ---
st.sidebar.header("Stock Search")
symbol_input = st.sidebar.text_input("Ticker Symbol (e.g., ATZ.TO for TSX, AAPL for NASDAQ)", value="ATZ.TO").upper().strip()

# Fetch stock data using yfinance
@st.cache_data(ttl=3600)
def load_stock_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0.0)
        trailing_eps = info.get("trailingEps", 0.0)
        trailing_pe = info.get("trailingPE", 0.0)
        currency = info.get("currency", "USD")
        short_name = info.get("shortName", ticker_symbol)
        
        expected_growth = info.get("earningsGrowth", 0.15)
        if expected_growth is not None and expected_growth > 0:
            expected_growth = round(expected_growth * 100, 2)
        else:
            expected_growth = 15.0

        return {
            "name": short_name,
            "price": float(current_price),
            "eps": float(trailing_eps),
            "pe": float(trailing_pe),
            "currency": "C$" if currency == "CAD" else "$",
            "growth": float(expected_growth)
        }
    except Exception as e:
        return None

stock_data = load_stock_data(symbol_input)

if stock_data is None or stock_data["price"] == 0:
    st.error(f"Unable to fetch data for ticker '{symbol_input}'. For TSX stocks, append '.TO' (e.g., ATZ.TO).")
    st.stop()

st.sidebar.subheader("Assumptions")
eps_input = st.sidebar.number_input(f"Earnings per Share ({stock_data['currency']})", value=stock_data["eps"], step=0.10)
initial_growth = st.sidebar.number_input("EPS Growth Rate (%)", value=stock_data["growth"], step=0.5)
terminal_growth = st.sidebar.number_input("Terminal EPS Growth Rate (%)", value=4.0, step=0.5)
years = st.sidebar.slider("Projection Horizon (Years)", min_value=1, max_value=20, value=10)
exit_pe = st.sidebar.number_input("Exit P/E Ratio", value=20.0, step=1.0)
required_return = st.sidebar.number_input("Required Annual Return (%)", value=10.0, step=0.5)
margin_of_safety = st.sidebar.number_input("Margin of Safety (%)", value=0.0, step=1.0)

# --- CALCULATION LOGIC ---
if years > 1:
    growth_rates = np.linspace(initial_growth / 100.0, terminal_growth / 100.0, years)
else:
    growth_rates = np.array([initial_growth / 100.0])

eps_projections = [eps_input]
for rate in growth_rates:
    eps_projections.append(eps_projections[-1] * (1 + rate))

final_eps = eps_projections[-1]
final_stock_price = final_eps * exit_pe
fair_value = final_stock_price / ((1 + required_return / 100.0) ** years)
buy_price = fair_value * (1.0 - margin_of_safety / 100.0)

curr_price = stock_data["price"]
upside = ((fair_value - curr_price) / curr_price) * 100.0
cagr_return = (((final_stock_price / curr_price) ** (1 / years)) - 1) * 100.0

# --- DISPLAY TOP SUMMARY ---
curr_symbol = stock_data["currency"]
st.info(f"**{stock_data['name']} ({symbol_input})** trades at **{curr_symbol}{curr_price:.2f}**, with trailing EPS of **{curr_symbol}{stock_data['eps']:.2f}**, expected EPS growth of **{initial_growth:.1f}%**, and a P/E ratio of **{stock_data['pe']:.2f}**.")

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"EPS in Year {years}", f"{curr_symbol}{final_eps:.2f}", f"+{((final_eps/eps_input)-1)*100:.1f}%")
col2.metric(f"Stock Price in Year {years}", f"{curr_symbol}{final_stock_price:.2f}", f"+{((final_stock_price/curr_price)-1)*100:.1f}%")
col3.metric("Projected Annual Return", f"{cagr_return:.1f}%")
col4.metric("Current P/E Ratio", f"{stock_data['pe']:.2f}")

st.markdown("---")

# --- FAIR VALUE & BUY ZONE ---
fv_col1, fv_col2 = st.columns([1, 2])

with fv_col1:
    st.markdown("#### Fair Value (Earnings Multiple)")
    st.markdown(f"# {curr_symbol}{fair_value:.2f}")
    if upside >= 0:
        st.success(f"**+{upside:.1f}% Upside** to Fair Value")
    else:
        st.error(f"**{upside:.1f}% Downside** to Fair Value")

with fv_col2:
    st.markdown("#### Valuation Status")
    progress = min(max(curr_price / (fair_value * 1.5 if fair_value > 0 else 1.0), 0.0), 1.0)
    st.progress(progress)
    if curr_price <= buy_price:
        st.success(f"**BUY ZONE** (Current Price {curr_symbol}{curr_price:.2f} <= Fair Value {curr_symbol}{fair_value:.2f})")
    else:
        st.warning(f"**OVERVALUED / ABOVE FAIR VALUE** (Current Price {curr_symbol}{curr_price:.2f} > Fair Value {curr_symbol}{fair_value:.2f})")

st.markdown("---")

# --- PROJECTION CHART ---
st.subheader("Projected EPS and Stock Price")

years_axis = [f"Year {i}" for i in range(years + 1)]
projected_prices = [eps * (stock_data["pe"] if i == 0 else exit_pe) for i, eps in enumerate(eps_projections)]

fig = go.Figure()
fig.add_trace(go.Bar(x=years_axis, y=eps_projections, name="Earnings Per Share", yaxis="y1", marker_color="#00875A"))
fig.add_trace(go.Scatter(x=years_axis, y=projected_prices, name="Projected Stock Price", yaxis="y2", mode="lines+markers", line=dict(color="#172B4D", width=3)))

fig.update_layout(
    yaxis=dict(title="EPS", showgrid=False),
    yaxis2=dict(title="Stock Price", overlaying="y", side="right", showgrid=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=20, r=20, t=30, b=20),
    height=400
)
st.plotly_chart(fig, use_container_width=True)

# --- SENSITIVITY MATRIX ---
st.subheader("Fair Value by EPS Growth and Exit P/E")
st.caption("Green cells indicate fair value is above current price. Red cells indicate below current price.")

growth_variations = [round(initial_growth + i, 1) for i in [-5.0, -2.5, 0.0, 2.5, 5.0]]
pe_variations = [round(exit_pe + i, 1) for i in [-4.0, -2.0, 0.0, 2.0]]

matrix_data = []
for g in growth_variations:
    row = []
    g_rates = np.linspace(g / 100.0, terminal_growth / 100.0, years) if years > 1 else np.array([g / 100.0])
    cell_eps = eps_input
    for r in g_rates:
        cell_eps *= (1 + r)
    for p in pe_variations:
        cell_fv = (cell_eps * p) / ((1 + required_return / 100.0) ** years)
        row.append(f"{curr_symbol}{cell_fv:.2f}")
    matrix_data.append(row)

matrix_df = pd.DataFrame(
    matrix_data, 
    index=[f"{g}%" for g in growth_variations], 
    columns=[f"{p}x" for p in pe_variations]
)

st.dataframe(matrix_df, use_container_width=True)
