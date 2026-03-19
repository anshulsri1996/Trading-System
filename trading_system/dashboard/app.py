# dashboard/app.py

import sys, os
import json
import threading
from datetime import datetime, date
from flask import Flask, jsonify, render_template

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from data.data_manager import DataManager
from strategies.strategy_generator import (
    EMACrossoverStrategy,
    BollingerBandsStrategy,
    RSIStrategy
)
from risk_engine.risk_engine import RiskEngine
from execution.execution_engine import ExecutionEngine
from logger.logger import TradingLogger

app = Flask(__name__)

# ── Global state — shared between trading thread and dashboard ─────────────
state = {
    'portfolio_value' : config.CAPITAL,
    'total_pnl'       : 0.0,
    'daily_pnl'       : 0.0,
    'position'        : 0,
    'entry_price'     : 0.0,
    'stop_loss'       : 0.0,
    'last_signal'     : 'NONE',
    'last_price'      : 0.0,
    'kill_switch'     : False,
    'trades'          : [],
    'equity_curve'    : [],
    'signals'         : [],
    'engine_running'  : False,
    'last_update'     : datetime.now().isoformat()
}

# ── Routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/state')
def get_state():
    """Returns current trading state as JSON — polled by the dashboard."""
    return jsonify(state)

@app.route('/api/kill_switch', methods=['POST'])
def toggle_kill_switch():
    """Manually activate/deactivate the kill switch from the dashboard."""
    state['kill_switch'] = not state['kill_switch']
    action = "activated" if state['kill_switch'] else "deactivated"
    return jsonify({'status': f'Kill switch {action}'})


# ── Trading thread — runs in background ───────────────────────────────────
def run_trading_engine():
    """
    Runs the trading engine in a background thread so the
    Flask dashboard stays responsive.
    """
    strategy = EMACrossoverStrategy(fast_period=20, slow_period=50)
    risk     = RiskEngine(
                   capital            = config.CAPITAL,
                   max_risk_per_trade = config.MAX_RISK_PER_TRADE,
                   daily_loss_limit   = config.DAILY_LOSS_LIMIT,
                   stop_loss_pct      = 0.02
               )
    logger   = TradingLogger(strategy_name=strategy.name)
    dm       = DataManager(symbol=config.DEFAULT_SYMBOL)

    # Paper trading state
    capital      = float(config.CAPITAL)
    position     = 0
    entry_price  = 0.0
    stop_loss_p  = 0.0

    state['engine_running'] = True

    import time
    while state['engine_running']:
        try:
            # Fetch latest data
            df = dm.get_recent_data(days=120, interval="1d")
            if df is None or len(df) < 20:
                time.sleep(60)
                continue

            # Generate signals
            df       = strategy.generate_signals(df)
            last     = df.iloc[-2]
            signal   = int(last['signal'])
            price    = float(last['close'])
            sig_name = {1:'BUY', -1:'SELL', 0:'HOLD'}.get(signal, 'HOLD')

            # Log signal
            logger.log_signal(sig_name, price, config.DEFAULT_SYMBOL)

            # Check stop loss
            if position > 0 and price <= stop_loss_p:
                proceeds    = position * price * 0.999
                pnl         = (price - entry_price) * position
                capital    += proceeds
                logger.log_trade("SELL", config.DEFAULT_SYMBOL,
                                 position, price, pnl, reason="STOP_LOSS")
                risk.update_pnl(pnl)
                state['trades'].append({
                    'time'   : datetime.now().strftime('%H:%M:%S'),
                    'action' : 'SELL',
                    'price'  : price,
                    'pnl'    : round(pnl, 2),
                    'reason' : 'STOP LOSS'
                })
                position    = 0
                entry_price = 0.0
                stop_loss_p = 0.0

            # Apply kill switch from dashboard
            if state['kill_switch']:
                risk.kill_switch = True

            # Process signal
            check = risk.can_trade(signal, 1 if position > 0 else 0)

            if check['allowed']:
                if signal == 1 and position == 0:
                    sizing      = risk.calculate_position_size(price, capital)
                    shares      = sizing['shares']
                    capital    -= shares * price * 1.001
                    position    = shares
                    entry_price = price
                    stop_loss_p = sizing['stop_loss_price']
                    logger.log_trade("BUY", config.DEFAULT_SYMBOL,
                                     shares, price,
                                     stop_loss=stop_loss_p)
                    state['trades'].append({
                        'time'   : datetime.now().strftime('%H:%M:%S'),
                        'action' : 'BUY',
                        'price'  : price,
                        'pnl'    : None,
                        'reason' : 'SIGNAL'
                    })

                elif signal == -1 and position > 0:
                    proceeds    = position * price * 0.999
                    pnl         = (price - entry_price) * position
                    capital    += proceeds
                    logger.log_trade("SELL", config.DEFAULT_SYMBOL,
                                     position, price, pnl, reason="SIGNAL")
                    risk.update_pnl(pnl)
                    state['trades'].append({
                        'time'   : datetime.now().strftime('%H:%M:%S'),
                        'action' : 'SELL',
                        'price'  : price,
                        'pnl'    : round(pnl, 2),
                        'reason' : 'SIGNAL'
                    })
                    position    = 0
                    entry_price = 0.0
                    stop_loss_p = 0.0

            # Update dashboard state
            market_val = capital + position * price
            total_pnl  = market_val - config.CAPITAL

            logger.log_pnl(capital, position, price,
                           risk.daily_pnl)

            state.update({
                'portfolio_value' : round(market_val, 2),
                'total_pnl'       : round(total_pnl, 2),
                'daily_pnl'       : round(risk.daily_pnl, 2),
                'position'        : position,
                'entry_price'     : entry_price,
                'stop_loss'       : stop_loss_p,
                'last_signal'     : sig_name,
                'last_price'      : price,
                'kill_switch'     : risk.kill_switch,
                'last_update'     : datetime.now().strftime('%H:%M:%S')
            })

            # Keep equity curve at max 200 points
            state['equity_curve'].append({
                'time'  : datetime.now().strftime('%H:%M'),
                'value' : round(market_val, 2)
            })
            if len(state['equity_curve']) > 200:
                state['equity_curve'].pop(0)

            state['signals'].append({
                'time'   : datetime.now().strftime('%H:%M:%S'),
                'signal' : sig_name,
                'price'  : price
            })
            if len(state['signals']) > 50:
                state['signals'].pop(0)

        except Exception as e:
            logger.log_error("TradingEngine", str(e))
            print(f"[Dashboard] Engine error: {e}")

        time.sleep(60)  # refresh every 60 seconds


# ── Start ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Start trading engine in background thread
    t = threading.Thread(target=run_trading_engine, daemon=True)
    t.start()
    print("\n[Dashboard] Trading engine started in background")
    print("[Dashboard] Open your browser at: http://localhost:5000\n")
    app.run(debug=False, port=5000, use_reloader=False)