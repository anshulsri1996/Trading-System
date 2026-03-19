# streamlit_app.py
# Run with: streamlit run streamlit_app.py

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import time
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from data.data_manager import DataManager
from strategies.strategy_generator import (
    EMACrossoverStrategy,
    BollingerBandsStrategy,
    RSIStrategy,
    StrategyGenerator
)
from backtester.backtester import Backtester
from analyser.analyser import StrategyAnalyser
from risk_engine.risk_engine import RiskEngine
from logger.logger import TradingLogger

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title  = "Algo Trading System",
    page_icon   = "📈",
    layout      = "wide",
    initial_sidebar_state = "expanded"
)

# ── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0D1017; }
    .stApp { background-color: #0D1017; }
    
    .metric-card {
        background: #131720;
        border: 1px solid #2A2520;
        border-radius: 10px;
        padding: 18px 20px;
        text-align: center;
        margin: 4px;
    }
    .metric-label {
        font-size: 11px;
        color: #6B6963;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 28px;
        font-weight: 700;
    }
    .metric-green  { color: #4CAF82; }
    .metric-red    { color: #E05555; }
    .metric-gold   { color: #C9A84C; }
    .metric-blue   { color: #5B8FD4; }
    .metric-white  { color: #E8E4DC; }

    .grade-badge {
        display: inline-block;
        padding: 6px 20px;
        border-radius: 20px;
        font-size: 16px;
        font-weight: 700;
    }
    .grade-A { background: #1A3A1A; color: #4CAF82; }
    .grade-B { background: #1A2A3A; color: #5B8FD4; }
    .grade-C { background: #2A2A1A; color: #C9A84C; }
    .grade-D { background: #2A1A1A; color: #E07030; }
    .grade-F { background: #2A1010; color: #E05555; }

    .signal-buy  { background: #1A3A1A; color: #4CAF82; 
                   padding: 8px 20px; border-radius: 20px; 
                   font-weight: 700; font-size: 18px; }
    .signal-sell { background: #2A1010; color: #E05555;
                   padding: 8px 20px; border-radius: 20px;
                   font-weight: 700; font-size: 18px; }
    .signal-hold { background: #1A1E2A; color: #5B8FD4;
                   padding: 8px 20px; border-radius: 20px;
                   font-weight: 700; font-size: 18px; }

    .weakness-box {
        background: #1A1410;
        border-left: 3px solid #C9A84C;
        padding: 10px 14px;
        border-radius: 0 8px 8px 0;
        margin: 6px 0;
        font-size: 13px;
        color: #C8C4BC;
    }
    .suggestion-high   { border-left: 3px solid #E05555; }
    .suggestion-medium { border-left: 3px solid #C9A84C; }
    .suggestion-low    { border-left: 3px solid #4CAF82; }

    .section-header {
        font-size: 11px;
        letter-spacing: 2px;
        color: #C9A84C;
        text-transform: uppercase;
        margin-bottom: 8px;
        font-weight: 600;
    }
    .trade-win  { color: #4CAF82; font-weight: 600; }
    .trade-loss { color: #E05555; font-weight: 600; }

    div[data-testid="stSidebar"] {
        background: #111418;
        border-right: 1px solid #2A2520;
    }
    .stButton > button {
        background: #C9A84C;
        color: #0D1017;
        font-weight: 700;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-size: 14px;
        width: 100%;
        transition: opacity 0.2s;
    }
    .stButton > button:hover { opacity: 0.85; }
    h1, h2, h3 { color: #E8E4DC !important; }
    p, li { color: #C8C4BC; }
</style>
""", unsafe_allow_html=True)


# ── Session state init ─────────────────────────────────────────────────────
if 'backtest_results' not in st.session_state:
    st.session_state.backtest_results = None
if 'analysis'         not in st.session_state:
    st.session_state.analysis = None
if 'signals_df'       not in st.session_state:
    st.session_state.signals_df = None
if 'paper_trades'     not in st.session_state:
    st.session_state.paper_trades = []
if 'paper_running'    not in st.session_state:
    st.session_state.paper_running = False
if 'paper_capital'    not in st.session_state:
    st.session_state.paper_capital = float(config.CAPITAL)
if 'paper_position'   not in st.session_state:
    st.session_state.paper_position = 0
if 'paper_entry'      not in st.session_state:
    st.session_state.paper_entry = 0.0
if 'paper_equity'     not in st.session_state:
    st.session_state.paper_equity = []
if 'strategy_obj'     not in st.session_state:
    st.session_state.strategy_obj = None
if 'stop_loss_price'  not in st.session_state:
    st.session_state.stop_loss_price = 0.0


# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR — Settings
# ══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚡ Trading System")
    st.markdown("---")

    st.markdown('<div class="section-header">Market Settings</div>',
                unsafe_allow_html=True)

    NIFTY_50 = {
        "Reliance Industries"       : "RELIANCE.NS",
        "TCS"                       : "TCS.NS",
        "HDFC Bank"                 : "HDFCBANK.NS",
        "Infosys"                   : "INFY.NS",
        "ICICI Bank"                : "ICICIBANK.NS",
        "Hindustan Unilever"        : "HINDUNILVR.NS",
        "ITC"                       : "ITC.NS",
        "State Bank of India"       : "SBIN.NS",
        "Bharti Airtel"             : "BHARTIARTL.NS",
        "Kotak Mahindra Bank"       : "KOTAKBANK.NS",
        "Bajaj Finance"             : "BAJFINANCE.NS",
        "LT (Larsen & Toubro)"      : "LT.NS",
        "HCL Technologies"          : "HCLTECH.NS",
        "Asian Paints"              : "ASIANPAINT.NS",
        "Axis Bank"                 : "AXISBANK.NS",
        "Maruti Suzuki"             : "MARUTI.NS",
        "Sun Pharma"                : "SUNPHARMA.NS",
        "Titan Company"             : "TITAN.NS",
        "Wipro"                     : "WIPRO.NS",
        "Nestle India"              : "NESTLEIND.NS",
        "UltraTech Cement"          : "ULTRACEMCO.NS",
        "Power Grid Corp"           : "POWERGRID.NS",
        "NTPC"                      : "NTPC.NS",
        "Tech Mahindra"             : "TECHM.NS",
        "Mahindra & Mahindra"       : "M&M.NS",
        "IndusInd Bank"             : "INDUSINDBK.NS",
        "JSW Steel"                 : "JSWSTEEL.NS",
        "Tata Steel"                : "TATASTEEL.NS",
        "Bajaj Finserv"             : "BAJAJFINSV.NS",
        "ONGC"                      : "ONGC.NS",
        "Tata Motors"               : "TATAMOTORS.NS",
        "Cipla"                     : "CIPLA.NS",
        "Adani Ports"               : "ADANIPORTS.NS",
        "Adani Enterprises"         : "ADANIENT.NS",
        "Coal India"                : "COALINDIA.NS",
        "Dr Reddys Labs"            : "DRREDDY.NS",
        "Eicher Motors"             : "EICHERMOT.NS",
        "Hero MotoCorp"             : "HEROMOTOCO.NS",
        "Hindalco"                  : "HINDALCO.NS",
        "Britannia"                 : "BRITANNIA.NS",
        "Divis Laboratories"        : "DIVISLAB.NS",
        "Grasim Industries"         : "GRASIM.NS",
        "SBI Life Insurance"        : "SBILIFE.NS",
        "HDFC Life Insurance"       : "HDFCLIFE.NS",
        "Bajaj Auto"                : "BAJAJ-AUTO.NS",
        "Apollo Hospitals"          : "APOLLOHOSP.NS",
        "Tata Consumer Products"    : "TATACONSUM.NS",
        "BEL"                       : "BEL.NS",
        "Shriram Finance"           : "SHRIRAMFIN.NS",
        "Trent"                     : "TRENT.NS",
    }

    selected_name = st.selectbox(
        "Select Nifty 50 stock",
        options = list(NIFTY_50.keys()),
        index   = 0,
        help    = "Type to search by company name"
    )
    symbol = NIFTY_50[selected_name]
    st.caption(f"NSE Symbol: `{symbol}`")
    capital = st.number_input("Capital (₹)", value=100_000,
                              step=10_000, min_value=10_000)
    start_date = st.date_input("Backtest start",
                               value=pd.to_datetime("2022-01-01"))
    end_date   = st.date_input("Backtest end",
                               value=pd.to_datetime("2024-12-31"))

    st.markdown("---")
    st.markdown('<div class="section-header">Risk Settings</div>',
                unsafe_allow_html=True)

    stop_loss_pct    = st.slider("Stop loss %",    1, 5,  2) / 100
    max_risk_trade   = st.slider("Max risk/trade %", 1, 5, 2) / 100
    daily_loss_limit = st.slider("Daily loss limit %", 1, 10, 5) / 100

    st.markdown("---")
    st.markdown(
        '<p style="font-size:11px;color:#6B6963;text-align:center;">'
        'Paper Trading Mode<br>No real money at risk</p>',
        unsafe_allow_html=True
    )


# ══════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("# 📈 Algorithmic Trading System")
    st.markdown(
        f'<p style="color:#6B6963;font-size:14px;">'
        f'Symbol: <b style="color:#C9A84C">{symbol}</b> &nbsp;|&nbsp; '
        f'Capital: <b style="color:#C9A84C">₹{capital:,.0f}</b> &nbsp;|&nbsp; '
        f'Mode: <b style="color:#4CAF82">Paper Trading</b></p>',
        unsafe_allow_html=True
    )
with col_h2:
    st.markdown(
        f'<p style="text-align:right;color:#6B6963;font-size:12px;">'
        f'{datetime.now().strftime("%d %b %Y, %H:%M")}</p>',
        unsafe_allow_html=True
    )

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════
# TAB LAYOUT
# ══════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "🧪 Strategy & Backtest",
    "📊 Analysis & Score",
    "🔴 Live Paper Trading",
    "📋 Reports & Logs"
])


# ══════════════════════════════════════════════════════════════════════════
# TAB 1 — STRATEGY & BACKTEST
# ══════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Choose your strategy")

    strategy_choice = st.radio(
        "Strategy type",
        ["EMA Crossover", "Bollinger Bands",
         "RSI Mean Reversion", "AI Generator (Custom)"],
        horizontal=True,
        label_visibility="collapsed"
    )

    col_p1, col_p2 = st.columns(2)

    strategy_obj = None

    if strategy_choice == "EMA Crossover":
        with col_p1:
            fast = st.slider("Fast EMA period", 5,  50, 20)
        with col_p2:
            slow = st.slider("Slow EMA period", 20, 200, 50)
        strategy_obj = EMACrossoverStrategy(
            fast_period=fast, slow_period=slow)

    elif strategy_choice == "Bollinger Bands":
        with col_p1:
            period = st.slider("Period", 10, 50, 20)
        with col_p2:
            std_dev = st.slider("Standard deviations", 1.0, 3.0, 2.0, 0.5)
        strategy_obj = BollingerBandsStrategy(
            period=period, std_dev=std_dev)

    elif strategy_choice == "RSI Mean Reversion":
        with col_p1:
            rsi_period   = st.slider("RSI period", 7, 28, 14)
            oversold     = st.slider("Oversold level", 20, 40, 30)
        with col_p2:
            overbought   = st.slider("Overbought level", 60, 80, 70)
        strategy_obj = RSIStrategy(
            period=rsi_period,
            oversold=oversold,
            overbought=overbought
        )

    else:
        idea = st.text_area(
            "Describe your strategy in plain English",
            placeholder=(
                "Example: Buy when RSI drops below 35 and price is above "
                "the 200 day moving average and volume is greater than the "
                "20 day average. Sell when RSI rises above 65 or price "
                "crosses below the 50 day moving average."
            ),
            height=120
        )
        if idea.strip():
            gen = StrategyGenerator()
            with st.spinner("Claude AI is writing your strategy..."):
                strategy_obj = gen.from_text(idea)
            st.success(f"Strategy generated: {strategy_obj.name}")
        else:
            st.info("Type your strategy idea above to continue.")

    st.markdown("---")

    # ── Run Backtest button ────────────────────────────────────────────
    if strategy_obj and st.button("▶ Run Backtest", key="run_bt"):
        with st.spinner("Fetching data and running backtest..."):
            dm = DataManager(symbol=symbol)
            df = dm.get_historical_data(
                start    = str(start_date),
                end      = str(end_date),
                interval = "1d"
            )

            if df.empty:
                st.error("No data returned. Check the symbol.")
            else:
                bt      = Backtester(capital=capital)
                signals = strategy_obj.generate_signals(df)
                results = bt.run(signals, strategy_name=strategy_obj.name)

                ana      = StrategyAnalyser()
                analysis = ana.analyse(results, df=df)

                st.session_state.backtest_results = results
                st.session_state.analysis         = analysis
                st.session_state.signals_df       = signals
                st.session_state.strategy_obj     = strategy_obj

        st.success("Backtest complete! See the Analysis tab for full results.")

    # ── Quick results preview ──────────────────────────────────────────
    if st.session_state.backtest_results:
        r = st.session_state.backtest_results
        st.markdown("### Quick results")
        c1, c2, c3, c4 = st.columns(4)
        color_ret = "green" if r['total_return'] >= 0 else "red"
        c1.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Total return</div>'
            f'<div class="metric-value metric-{color_ret}">'
            f'{r["total_return"]:+.1f}%</div></div>',
            unsafe_allow_html=True)
        c2.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Win rate</div>'
            f'<div class="metric-value metric-gold">'
            f'{r["win_rate"]:.1f}%</div></div>',
            unsafe_allow_html=True)
        c3.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Total trades</div>'
            f'<div class="metric-value metric-white">'
            f'{r["total_trades"]}</div></div>',
            unsafe_allow_html=True)
        c4.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-label">Max drawdown</div>'
            f'<div class="metric-value metric-red">'
            f'{r["max_drawdown"]:.1f}%</div></div>',
            unsafe_allow_html=True)

        # Equity curve chart
        if not r['equity_curve'].empty:
            st.markdown("### Equity curve")
            eq_df = r['equity_curve']
            fig   = go.Figure()
            color = "#4CAF82" if r['total_return'] >= 0 else "#E05555"
            fig.add_trace(go.Scatter(
                x    = eq_df['date'],
                y    = eq_df['equity'],
                mode = 'lines',
                line = dict(color=color, width=2),
                fill = 'tozeroy',
                fillcolor = color.replace(")", ",0.08)").replace("rgb", "rgba")
            ))
            fig.update_layout(
                plot_bgcolor  = "#131720",
                paper_bgcolor = "#0D1017",
                font_color    = "#C8C4BC",
                height        = 280,
                margin        = dict(l=40, r=20, t=20, b=40),
                xaxis = dict(gridcolor="#2A2520", showgrid=True),
                yaxis = dict(gridcolor="#2A2520", showgrid=True,
                             tickprefix="₹")
            )
            st.plotly_chart(fig, use_container_width=True)

        # Trade log
        st.markdown("### Trade log")
        trades = r['trades'][
            ['entry_date','exit_date','entry_price',
             'exit_price','pnl','pnl_pct','result']
        ].copy()
        trades['pnl'] = trades['pnl'].apply(
            lambda x: f"₹{x:+,.0f}")
        trades['pnl_pct'] = trades['pnl_pct'].apply(
            lambda x: f"{x:+.2f}%")
        st.dataframe(trades, use_container_width=True, height=250)


# ══════════════════════════════════════════════════════════════════════════
# TAB 2 — ANALYSIS
# ══════════════════════════════════════════════════════════════════════════
with tab2:
    if not st.session_state.analysis:
        st.info("Run a backtest first to see the analysis.")
    else:
        a = st.session_state.analysis
        r = st.session_state.backtest_results
        sc = a['score']
        grade = sc['grade']

        # Overall score
        col_sc, col_gr = st.columns([2, 1])
        with col_sc:
            st.markdown("### Strategy score")
            fig_gauge = go.Figure(go.Indicator(
                mode  = "gauge+number",
                value = sc['total'],
                number= {'suffix': '/100', 'font': {'color': '#C9A84C', 'size': 36}},
                gauge = {
                    'axis' : {'range': [0, 100], 'tickcolor': '#6B6963'},
                    'bar'  : {'color': '#C9A84C'},
                    'bgcolor': '#131720',
                    'steps': [
                        {'range': [0,  30], 'color': '#2A1010'},
                        {'range': [30, 45], 'color': '#2A1A10'},
                        {'range': [45, 60], 'color': '#2A2A10'},
                        {'range': [60, 75], 'color': '#102A10'},
                        {'range': [75, 100],'color': '#0A1F0A'},
                    ],
                    'threshold': {
                        'line' : {'color': '#C9A84C', 'width': 3},
                        'value': sc['total']
                    }
                }
            ))
            fig_gauge.update_layout(
                paper_bgcolor = "#0D1017",
                font_color    = "#C8C4BC",
                height        = 220,
                margin        = dict(l=20, r=20, t=20, b=10)
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_gr:
            st.markdown("### Grade")
            st.markdown(
                f'<div style="margin-top:40px;text-align:center;">'
                f'<span class="grade-badge grade-{grade}">{grade}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
            st.markdown("### Score breakdown")
            st.markdown(
                f"Win rate: **{sc['win_rate']:.1f}**/25  \n"
                f"Profit factor: **{sc['profit_factor']:.1f}**/25  \n"
                f"Drawdown: **{sc['drawdown']:.1f}**/25  \n"
                f"Returns: **{sc['returns']:.1f}**/25"
            )

        # Benchmark comparison
        if a['benchmark']:
            st.markdown("### vs Buy and Hold")
            col_b1, col_b2, col_b3 = st.columns(3)
            alpha = r['total_return'] - a['benchmark']
            col_b1.metric("Strategy return",
                          f"{r['total_return']:+.1f}%")
            col_b2.metric("Buy and hold return",
                          f"{a['benchmark']:+.1f}%")
            col_b3.metric("Alpha generated",
                          f"{alpha:+.1f}%",
                          delta=f"{alpha:+.1f}%")

        # Weaknesses
        st.markdown("### Weaknesses found")
        if not a['weaknesses']:
            st.success("No major weaknesses detected.")
        else:
            for w in a['weaknesses']:
                st.markdown(
                    f'<div class="weakness-box">'
                    f'<b>[{w["type"]}]</b><br/>{w["detail"]}'
                    f'</div>',
                    unsafe_allow_html=True
                )

        # Suggestions
        st.markdown("### Improvement suggestions")
        priority_colors = {
            'HIGH':   ('suggestion-high',   '🔴 HIGH'),
            'MEDIUM': ('suggestion-medium', '🟡 MEDIUM'),
            'LOW':    ('suggestion-low',    '🟢 LOW'),
        }
        for sug in a['suggestions']:
            cls, label = priority_colors.get(
                sug['priority'], ('', sug['priority']))
            st.markdown(
                f'<div class="weakness-box {cls}">'
                f'<b>{label} — {sug["action"]}</b><br/>'
                f'{sug["detail"]}</div>',
                unsafe_allow_html=True
            )


# ══════════════════════════════════════════════════════════════════════════
# TAB 3 — LIVE PAPER TRADING
# ══════════════════════════════════════════════════════════════════════════
with tab3:
    if not st.session_state.analysis:
        st.info("Run a backtest and check the Analysis tab first.")
    else:
        grade = st.session_state.analysis['score']['grade']
        score = st.session_state.analysis['score']['total']

        # Grade gate
        if grade == 'F':
            st.error(
                f"Grade F strategy (score: {score:.0f}/100) — "
                f"hard blocked. Fix the weaknesses shown in the "
                f"Analysis tab and re-run the backtest."
            )
        else:
            if grade in ['A', 'B']:
                st.success(f"Grade {grade} strategy approved automatically.")
            elif grade == 'C':
                st.warning(f"Grade C — acceptable but not ideal.")
            elif grade == 'D':
                confirm = st.checkbox(
                    "Grade D strategy — I understand the risks and want to proceed"
                )
                if not confirm:
                    st.stop()

            st.markdown("### Live paper trading engine")

            col_start, col_stop = st.columns(2)
            with col_start:
                start_paper = st.button("▶ Start Paper Trading", key="start_pt")
            with col_stop:
                stop_paper  = st.button("⏹ Stop", key="stop_pt")

            if start_paper:
                st.session_state.paper_running  = True
                st.session_state.paper_trades   = []
                st.session_state.paper_capital  = float(capital)
                st.session_state.paper_position = 0
                st.session_state.paper_entry    = 0.0
                st.session_state.paper_equity   = []

            if stop_paper:
                st.session_state.paper_running = False

            # ── Live loop ──────────────────────────────────────────────
            if st.session_state.paper_running:
                strategy = st.session_state.strategy_obj
                risk     = RiskEngine(
                    capital            = capital,
                    max_risk_per_trade = max_risk_trade,
                    daily_loss_limit   = daily_loss_limit,
                    stop_loss_pct      = stop_loss_pct
                )

                dm  = DataManager(symbol=symbol)
                df  = dm.get_recent_data(days=120, interval="1d")
                df  = strategy.generate_signals(df)
                last        = df.iloc[-2]
                signal      = int(last['signal'])
                price       = float(last['close'])
                signal_name = {1:'BUY',-1:'SELL',0:'HOLD'}.get(signal,'HOLD')
                sig_class   = signal_name.lower()

                # Stop loss check
                if (st.session_state.paper_position > 0 and
                        price <= st.session_state.stop_loss_price):
                    proceeds = st.session_state.paper_position * price * 0.999
                    pnl      = ((price - st.session_state.paper_entry)
                                * st.session_state.paper_position)
                    st.session_state.paper_capital += proceeds
                    st.session_state.paper_trades.append({
                        'time'  : datetime.now().strftime('%H:%M:%S'),
                        'action': 'SELL',
                        'price' : price,
                        'pnl'   : round(pnl, 2),
                        'reason': 'STOP LOSS'
                    })
                    st.session_state.paper_position   = 0
                    st.session_state.paper_entry      = 0.0
                    st.session_state.stop_loss_price  = 0.0

                # Process signal
                check = risk.can_trade(
                    signal,
                    1 if st.session_state.paper_position > 0 else 0
                )
                if check['allowed']:
                    if signal == 1 and st.session_state.paper_position == 0:
                        sizing = risk.calculate_position_size(
                            price, st.session_state.paper_capital)
                        shares = sizing['shares']
                        st.session_state.paper_capital -= (
                            shares * price * 1.001)
                        st.session_state.paper_position  = shares
                        st.session_state.paper_entry     = price
                        st.session_state.stop_loss_price = (
                            sizing['stop_loss_price'])
                        st.session_state.paper_trades.append({
                            'time'  : datetime.now().strftime('%H:%M:%S'),
                            'action': 'BUY',
                            'price' : price,
                            'pnl'   : None,
                            'reason': 'SIGNAL'
                        })

                    elif (signal == -1 and
                          st.session_state.paper_position > 0):
                        proceeds = (st.session_state.paper_position
                                    * price * 0.999)
                        pnl = ((price - st.session_state.paper_entry)
                               * st.session_state.paper_position)
                        st.session_state.paper_capital += proceeds
                        st.session_state.paper_trades.append({
                            'time'  : datetime.now().strftime('%H:%M:%S'),
                            'action': 'SELL',
                            'price' : price,
                            'pnl'   : round(pnl, 2),
                            'reason': 'SIGNAL'
                        })
                        st.session_state.paper_position  = 0
                        st.session_state.paper_entry     = 0.0
                        st.session_state.stop_loss_price = 0.0

                # Update equity
                mv = (st.session_state.paper_capital
                      + st.session_state.paper_position * price)
                st.session_state.paper_equity.append({
                    'time'  : datetime.now().strftime('%H:%M:%S'),
                    'equity': round(mv, 2)
                })

                # ── Dashboard metrics ──────────────────────────────────
                total_pnl = mv - capital
                pnl_pct   = total_pnl / capital * 100
                pnl_color = "green" if total_pnl >= 0 else "red"

                st.markdown(
                    f'<div style="text-align:center;margin:10px 0;">'
                    f'<span class="signal-{sig_class}">{signal_name}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                m1, m2, m3, m4 = st.columns(4)
                m1.markdown(
                    f'<div class="metric-card"><div class="metric-label">'
                    f'Portfolio value</div>'
                    f'<div class="metric-value metric-white">'
                    f'₹{mv:,.0f}</div></div>',
                    unsafe_allow_html=True)
                m2.markdown(
                    f'<div class="metric-card"><div class="metric-label">'
                    f'Total PnL</div>'
                    f'<div class="metric-value metric-{pnl_color}">'
                    f'₹{total_pnl:+,.0f}</div></div>',
                    unsafe_allow_html=True)
                m3.markdown(
                    f'<div class="metric-card"><div class="metric-label">'
                    f'Return</div>'
                    f'<div class="metric-value metric-{pnl_color}">'
                    f'{pnl_pct:+.2f}%</div></div>',
                    unsafe_allow_html=True)
                m4.markdown(
                    f'<div class="metric-card"><div class="metric-label">'
                    f'Last price</div>'
                    f'<div class="metric-value metric-gold">'
                    f'₹{price:,.2f}</div></div>',
                    unsafe_allow_html=True)

                # Open position
                if st.session_state.paper_position > 0:
                    unreal = ((price - st.session_state.paper_entry)
                              / st.session_state.paper_entry * 100)
                    ur_col = "green" if unreal >= 0 else "red"
                    st.markdown(
                        f'<div class="weakness-box" style="margin-top:12px;">'
                        f'<b>Open Position</b><br/>'
                        f'Shares: {st.session_state.paper_position} &nbsp;|&nbsp; '
                        f'Entry: ₹{st.session_state.paper_entry:,.2f} &nbsp;|&nbsp; '
                        f'Stop: ₹{st.session_state.stop_loss_price:,.2f} &nbsp;|&nbsp; '
                        f'Unrealised: '
                        f'<span style="color:{"#4CAF82" if unreal>=0 else "#E05555"}">'
                        f'{unreal:+.2f}%</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

                # Equity chart
                if len(st.session_state.paper_equity) > 1:
                    eq_df = pd.DataFrame(st.session_state.paper_equity)
                    fig2  = go.Figure()
                    clr   = "#4CAF82" if total_pnl >= 0 else "#E05555"
                    fig2.add_trace(go.Scatter(
                        x    = eq_df['time'],
                        y    = eq_df['equity'],
                        mode = 'lines',
                        line = dict(color=clr, width=2),
                        fill = 'tozeroy'
                    ))
                    fig2.update_layout(
                        plot_bgcolor  = "#131720",
                        paper_bgcolor = "#0D1017",
                        font_color    = "#C8C4BC",
                        height        = 200,
                        margin        = dict(l=40,r=20,t=10,b=30),
                        xaxis = dict(gridcolor="#2A2520"),
                        yaxis = dict(gridcolor="#2A2520",
                                     tickprefix="₹")
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                # Trade history
                if st.session_state.paper_trades:
                    st.markdown("### Trade history")
                    trades_df = pd.DataFrame(
                        reversed(st.session_state.paper_trades))
                    trades_df['pnl'] = trades_df['pnl'].apply(
                        lambda x: f"₹{x:+,.0f}" if x is not None else "—")
                    st.dataframe(trades_df, use_container_width=True,
                                 height=200)

                # Auto refresh
                time.sleep(1)
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# TAB 4 — REPORTS
# ══════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### Session report")

    if not st.session_state.paper_trades:
        st.info("No trades yet. Run paper trading to generate data.")
    else:
        trades = [t for t in st.session_state.paper_trades
                  if t['pnl'] is not None]
        if trades:
            trades_df  = pd.DataFrame(trades)
            total_pnl  = trades_df['pnl'].sum()
            wins       = (trades_df['pnl'] > 0).sum()
            losses     = (trades_df['pnl'] <= 0).sum()
            win_rate   = wins / len(trades_df) * 100
            avg_win    = trades_df[trades_df['pnl']>0]['pnl'].mean() if wins  else 0
            avg_loss   = trades_df[trades_df['pnl']<=0]['pnl'].mean() if losses else 0

            c1,c2,c3,c4 = st.columns(4)
            pnl_col = "green" if total_pnl >= 0 else "red"
            c1.markdown(
                f'<div class="metric-card"><div class="metric-label">'
                f'Total PnL</div>'
                f'<div class="metric-value metric-{pnl_col}">'
                f'₹{total_pnl:+,.0f}</div></div>',
                unsafe_allow_html=True)
            c2.markdown(
                f'<div class="metric-card"><div class="metric-label">'
                f'Win rate</div>'
                f'<div class="metric-value metric-gold">'
                f'{win_rate:.1f}%</div></div>',
                unsafe_allow_html=True)
            c3.markdown(
                f'<div class="metric-card"><div class="metric-label">'
                f'Avg win</div>'
                f'<div class="metric-value metric-green">'
                f'₹{avg_win:+,.0f}</div></div>',
                unsafe_allow_html=True)
            c4.markdown(
                f'<div class="metric-card"><div class="metric-label">'
                f'Avg loss</div>'
                f'<div class="metric-value metric-red">'
                f'₹{avg_loss:+,.0f}</div></div>',
                unsafe_allow_html=True)

            # PnL bar chart per trade
            st.markdown("### PnL per trade")
            colors_bar = [
                "#4CAF82" if p > 0 else "#E05555"
                for p in trades_df['pnl']
            ]
            fig_bar = go.Figure(go.Bar(
                x     = list(range(1, len(trades_df)+1)),
                y     = trades_df['pnl'],
                marker_color = colors_bar
            ))
            fig_bar.update_layout(
                plot_bgcolor  = "#131720",
                paper_bgcolor = "#0D1017",
                font_color    = "#C8C4BC",
                height        = 250,
                margin        = dict(l=40,r=20,t=10,b=30),
                xaxis = dict(title="Trade #",
                             gridcolor="#2A2520"),
                yaxis = dict(title="PnL (₹)",
                             gridcolor="#2A2520",
                             tickprefix="₹")
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # Log files viewer
        st.markdown("### Log files")
        log_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "logs")
        if os.path.exists(log_dir):
            log_files = os.listdir(log_dir)
            if log_files:
                selected = st.selectbox("View log file", log_files)
                log_path = os.path.join(log_dir, selected)
                with open(log_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                st.code(content[-3000:], language="text")
            else:
                st.info("No log files yet.")
        else:
            st.info("Logs folder not found.")

        # EOD Report viewer
        st.markdown("### End of day reports")
        rep_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "reports")
        if os.path.exists(rep_dir):
            reports = os.listdir(rep_dir)
            if reports:
                selected_rep = st.selectbox("View report", reports)
                rep_path = os.path.join(rep_dir, selected_rep)
                with open(rep_path, 'r', encoding='utf-8') as f:
                    rep_content = f.read()
                st.code(rep_content, language="text")
            else:
                st.info("No reports yet.")