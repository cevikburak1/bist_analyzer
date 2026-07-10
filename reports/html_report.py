"""
İnteraktif HTML Rapor (Plotly)

Filtrelenebilir tablo ve tıklanabilir hisse detay grafikleri içeren
tek sayfalık HTML raporu üretir.
"""

import logging
import json
from datetime import datetime
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from analysis.market_regime import MarketRegime
from analysis.signals import Signal
from config import OUTPUT_DIR, REPORT_DATE_FORMAT

logger = logging.getLogger(__name__)

SIGNAL_COLORS = {
    "GÜÇLÜ AL": "#00ff88",
    "AL": "#00ff88",
    "SAT": "#ff4444",
    "BEKLE": "#ffaa00",
    "KAR AL": "#d946ef",
}


def _build_summary_table(signals: list[Signal], regime: MarketRegime) -> str:
    """Sinyal özet tablosu HTML'i"""
    al = sum(1 for s in signals if s.signal == "AL")
    sat = sum(1 for s in signals if s.signal == "SAT")
    bekle = sum(1 for s in signals if s.signal == "BEKLE")
    avg_score = sum(s.score for s in signals) / len(signals) if signals else 0

    regime_colors = {"YUKSELIS": "#00ff88", "DUSUS": "#ff4444", "YATAY": "#ffaa00"}
    r_color = regime_colors.get(regime.regime, "#fff")

    return f"""
    <div style="display:flex; gap:20px; flex-wrap:wrap; margin-bottom:20px;">
        <div style="background:#16213e; padding:15px 25px; border-radius:10px; border-left:4px solid {r_color};">
            <div style="color:#aaa; font-size:12px;">Piyasa Rejimi</div>
            <div style="color:{r_color}; font-size:20px; font-weight:bold;">{regime.label}</div>
            <div style="color:#888; font-size:11px;">XU100: {regime.index_price:,.0f} | 20G: {regime.performance_20d:+.2f}%</div>
        </div>
        <div style="background:#16213e; padding:15px 25px; border-radius:10px; border-left:4px solid #00ff88;">
            <div style="color:#aaa; font-size:12px;">AL Sinyali</div>
            <div style="color:#00ff88; font-size:28px; font-weight:bold;">{al}</div>
        </div>
        <div style="background:#16213e; padding:15px 25px; border-radius:10px; border-left:4px solid #ff4444;">
            <div style="color:#aaa; font-size:12px;">SAT Sinyali</div>
            <div style="color:#ff4444; font-size:28px; font-weight:bold;">{sat}</div>
        </div>
        <div style="background:#16213e; padding:15px 25px; border-radius:10px; border-left:4px solid #ffaa00;">
            <div style="color:#aaa; font-size:12px;">BEKLE</div>
            <div style="color:#ffaa00; font-size:28px; font-weight:bold;">{bekle}</div>
        </div>
        <div style="background:#16213e; padding:15px 25px; border-radius:10px; border-left:4px solid #00d2ff;">
            <div style="color:#aaa; font-size:12px;">Ort. Skor</div>
            <div style="color:#00d2ff; font-size:28px; font-weight:bold;">{avg_score:.1f}</div>
        </div>
    </div>
    """


def _build_data_table(signals: list[Signal]) -> str:
    """Filtrelenebilir sinyal tablosu HTML'i (JavaScript ile)"""
    rows_js = []
    for sig in signals:
        price_str = f"{sig.price:,.2f}" if sig.price < 1000 else f"{sig.price:,.0f}"
        metrics = sig.score_breakdown
        target = sig.targets.short_target if sig.targets else sig.target
        rows_js.append([
            sig.symbol,
            price_str,
            round(sig.score, 1),
            sig.action or sig.signal,
            sig.reason,
            round(metrics.wr_pct, 1),
            round(metrics.adx, 1),
            round(metrics.v_kat, 2),
            "OK" if metrics.dzl_ok else "--",
            "OK" if metrics.sqz_ok else "--",
            f"{sig.stop_loss:.2f}",
            f"{target:.2f}",
        ])

    return f"""
    <div style="margin-bottom:15px;">
        <input type="text" id="searchBox" placeholder="Hisse ara..."
               style="padding:8px 15px; background:#16213e; border:1px solid #333;
                      color:#eee; border-radius:5px; width:200px; margin-right:10px;">
        <select id="signalFilter"
                style="padding:8px 15px; background:#16213e; border:1px solid #333;
                       color:#eee; border-radius:5px;">
            <option value="">Tüm Sinyaller</option>
            <option value="AL">AL</option>
            <option value="SAT">SAT</option>
            <option value="BEKLE">BEKLE</option>
        </select>
    </div>
    <table id="signalTable" style="width:100%; border-collapse:collapse; font-size:13px;">
        <thead>
            <tr style="background:#0f3460;">
                <th style="padding:10px; text-align:left; cursor:pointer;" onclick="sortTable(0)">Hisse ⇅</th>
                <th style="padding:10px; text-align:right; cursor:pointer;" onclick="sortTable(1)">Fiyat ⇅</th>
                <th style="padding:10px; text-align:center; cursor:pointer;" onclick="sortTable(2)">Skor ⇅</th>
                <th style="padding:10px; text-align:center;">Aksiyon</th>
                <th style="padding:10px; text-align:left;">Neden</th>
                <th title="3 bar sonraki maliyet tamponlu tarihsel kurulum başarı proxy'si; gerçek backtest değildir" style="padding:10px; text-align:right; cursor:pointer;" onclick="sortTable(5)">Kurulum% ⇅</th>
                <th style="padding:10px; text-align:right; cursor:pointer;" onclick="sortTable(6)">ADX ⇅</th>
                <th style="padding:10px; text-align:right; cursor:pointer;" onclick="sortTable(7)">V/K ⇅</th>
                <th style="padding:10px; text-align:center;">DZL</th>
                <th style="padding:10px; text-align:center;">SQZ</th>
                <th style="padding:10px; text-align:right;">Stop</th>
                <th style="padding:10px; text-align:right;">Hedef</th>
            </tr>
        </thead>
        <tbody id="tableBody"></tbody>
    </table>
    <script>
    const allRows = {json.dumps(rows_js, ensure_ascii=False)};
    const signalColors = {{"GÜÇLÜ AL": "#00ff88", "AL": "#00ff88", "SAT": "#ff4444", "BEKLE": "#ffaa00", "KAR AL": "#d946ef"}};

    function renderTable(data) {{
        const tbody = document.getElementById("tableBody");
        tbody.innerHTML = "";
        data.forEach((r, i) => {{
            const sigColor = signalColors[r[3]] || "#fff";
            const bgAlpha = i % 2 === 0 ? "0.03" : "0.06";
            const tr = document.createElement("tr");
            tr.style.background = `rgba(255,255,255,${{bgAlpha}})`;
            tr.style.cursor = "pointer";
            tr.onclick = () => scrollToChart(r[0]);
            tr.innerHTML = `
                <td style="padding:8px; font-weight:bold;">${{r[0]}}</td>
                <td style="padding:8px; text-align:right;">${{r[1]}}</td>
                <td style="padding:8px; text-align:center;">
                    <span style="background:${{sigColor}}22; color:${{sigColor}};
                                 padding:2px 10px; border-radius:12px;">${{r[2]}}</span>
                </td>
                <td style="padding:8px; text-align:center; color:${{sigColor}}; font-weight:bold;">${{r[3]}}</td>
                <td style="padding:8px; color:#888; font-size:11px;">${{r[4]}}</td>
                <td style="padding:8px; text-align:right;">${{r[5]}}</td>
                <td style="padding:8px; text-align:right;">${{r[6]}}</td>
                <td style="padding:8px; text-align:right;">${{r[7]}}</td>
                <td style="padding:8px; text-align:center;">${{r[8]}}</td>
                <td style="padding:8px; text-align:center;">${{r[9]}}</td>
                <td style="padding:8px; text-align:right;">${{r[10]}}</td>
                <td style="padding:8px; text-align:right;">${{r[11]}}</td>
            `;
            tbody.appendChild(tr);
        }});
    }}

    function filterRows() {{
        const search = document.getElementById("searchBox").value.toUpperCase();
        const signal = document.getElementById("signalFilter").value;
        const filtered = allRows.filter(r =>
            r[0].includes(search) && (signal === "" || r[3] === signal)
        );
        renderTable(filtered);
    }}

    let sortDir = 1;
    function sortTable(col) {{
        allRows.sort((a, b) => {{
            if (typeof a[col] === "number") return (a[col] - b[col]) * sortDir;
            return a[col].localeCompare(b[col]) * sortDir;
        }});
        sortDir *= -1;
        filterRows();
    }}

    function scrollToChart(symbol) {{
        const el = document.getElementById("chart-" + symbol);
        if (el) el.scrollIntoView({{ behavior: "smooth", block: "start" }});
    }}

    document.getElementById("searchBox").addEventListener("input", filterRows);
    document.getElementById("signalFilter").addEventListener("change", filterRows);
    renderTable(allRows);
    </script>
    """


def _build_commentary_box(sig: Signal) -> str:
    """Grafik altına yorum ve hedef bilgi kutusu."""
    comm = sig.commentary
    tgt = sig.targets
    fib = sig.fibonacci

    if not comm:
        return ""

    sig_color = SIGNAL_COLORS.get(sig.signal, "#fff")
    summary = comm.summary if comm else sig.signal

    # Hedef satırı
    targets_html = ""
    if tgt and tgt.short_target > 0:
        targets_html = f"""
        <div style="display:flex; gap:15px; margin:8px 0; flex-wrap:wrap;">
            <span style="color:#00ff88;">Kısa: {tgt.short_target:,.2f} (+{tgt.short_reward_pct:.1f}%)</span>
            <span style="color:#00ff88;">Orta: {tgt.medium_target:,.2f} (+{tgt.medium_reward_pct:.1f}%)</span>
            <span style="color:#00ff88;">Uzun: {tgt.long_target:,.2f} (+{tgt.long_reward_pct:.1f}%)</span>
            <span style="color:#ff4444;">Stop: {tgt.stop_loss:,.2f} (-{tgt.risk_pct:.1f}%)</span>
        </div>"""

    # Riskler
    risks_html = ""
    if comm.risks:
        risk_items = "".join(f"<li>{r}</li>" for r in comm.risks)
        risks_html = f'<div style="color:#ff6b6b; font-size:11px; margin-top:5px;"><b>Riskler:</b><ul style="margin:3px 0; padding-left:18px;">{risk_items}</ul></div>'

    return f"""
    <div style="background:#16213e; border-left:4px solid {sig_color}; padding:12px 18px;
                border-radius:0 8px 8px 0; margin-bottom:20px; font-size:12px;">
        <div style="font-size:15px; font-weight:bold; color:{sig_color}; margin-bottom:6px;">
            {sig.symbol} — {summary} (Skor: {sig.score:.0f})
        </div>
        {targets_html}
        <div style="color:#ccc; line-height:1.6; margin-top:6px;">{comm.paragraph if comm else ''}</div>
        {risks_html}
    </div>"""


def _build_stock_chart(symbol: str, df: pd.DataFrame, sig: Signal) -> str:
    """Tek bir hisse için Plotly grafik + Fibonacci + mum annotation + yorum kutusu."""
    plot_df = df.tail(120)

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.55, 0.25, 0.20],
        subplot_titles=(f"{symbol} — Fiyat", "Hacim", "RSI"),
    )

    # Fiyat
    fig.add_trace(
        go.Scatter(x=plot_df.index, y=plot_df["close"], name="Fiyat",
                   line=dict(color="#00d2ff", width=1.5)),
        row=1, col=1,
    )
    if "sma_short" in plot_df.columns:
        fig.add_trace(
            go.Scatter(x=plot_df.index, y=plot_df["sma_short"], name="SMA50",
                       line=dict(color="#ff6b6b", width=1, dash="dot")),
            row=1, col=1,
        )
    if "sma_long" in plot_df.columns:
        sma200 = plot_df["sma_long"].dropna()
        if len(sma200) > 0:
            fig.add_trace(
                go.Scatter(x=sma200.index, y=sma200, name="SMA200",
                           line=dict(color="#ffd93d", width=1, dash="dot")),
                row=1, col=1,
            )
    if "bb_upper" in plot_df.columns:
        fig.add_trace(
            go.Scatter(x=plot_df.index, y=plot_df["bb_upper"], name="BB Üst",
                       line=dict(color="#888", width=0.5), showlegend=False),
            row=1, col=1,
        )
        fig.add_trace(
            go.Scatter(x=plot_df.index, y=plot_df["bb_lower"], name="BB Alt",
                       line=dict(color="#888", width=0.5), fill="tonexty",
                       fillcolor="rgba(136,136,136,0.1)", showlegend=False),
            row=1, col=1,
        )

    # ── Fibonacci seviyeleri ──
    fib = sig.fibonacci
    if fib and fib.retracement_levels:
        y_min = plot_df["low"].min()
        y_max = plot_df["high"].max()
        for ratio, level in fib.retracement_levels.items():
            if y_min * 0.9 <= level <= y_max * 1.1:
                fig.add_hline(
                    y=level, line_dash="dot", line_color="#ff9800",
                    opacity=0.4, row=1, col=1,
                    annotation_text=f"Fib {ratio:.1%}",
                    annotation_position="right",
                    annotation_font_size=9,
                    annotation_font_color="#ff9800",
                )

    # ── Stop / Hedef yatay çizgileri ──
    tgt = sig.targets
    if tgt and tgt.stop_loss > 0:
        fig.add_hline(y=tgt.stop_loss, line_dash="dash", line_color="#ff4444",
                      opacity=0.6, row=1, col=1,
                      annotation_text="STOP", annotation_position="left",
                      annotation_font_size=9, annotation_font_color="#ff4444")
    if tgt and tgt.short_target > 0:
        fig.add_hline(y=tgt.short_target, line_dash="dash", line_color="#00ff88",
                      opacity=0.4, row=1, col=1,
                      annotation_text="K.Hedef", annotation_position="left",
                      annotation_font_size=9, annotation_font_color="#00ff88")
    if tgt and tgt.medium_target > 0:
        fig.add_hline(y=tgt.medium_target, line_dash="dash", line_color="#00cc66",
                      opacity=0.3, row=1, col=1,
                      annotation_text="O.Hedef", annotation_position="left",
                      annotation_font_size=9, annotation_font_color="#00cc66")

    # Hacim
    colors = ["#00ff88" if c >= o else "#ff4444"
              for c, o in zip(plot_df["close"], plot_df["open"])]
    fig.add_trace(
        go.Bar(x=plot_df.index, y=plot_df["volume"], name="Hacim",
               marker_color=colors, opacity=0.6, showlegend=False),
        row=2, col=1,
    )

    # RSI
    if "rsi" in plot_df.columns:
        fig.add_trace(
            go.Scatter(x=plot_df.index, y=plot_df["rsi"], name="RSI",
                       line=dict(color="#e94560", width=1.2)),
            row=3, col=1,
        )
        fig.add_hline(y=70, line_dash="dash", line_color="#ff4444",
                      opacity=0.5, row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#00ff88",
                      opacity=0.5, row=3, col=1)

    sig_color = SIGNAL_COLORS.get(sig.signal, "#fff")

    # Başlık: sinyal + mum + EW bilgisi
    ew = sig.elliott_wave
    ew_text = f" | EW: W{ew.current_wave}" if ew and ew.current_wave != "?" else ""
    candle_text = ""
    if sig.candle_patterns:
        candle_text = f" | Mum: {sig.candle_patterns[0].name}"

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        height=500,
        margin=dict(l=50, r=20, t=40, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        title=dict(
            text=f"{symbol} | {sig.signal} | Skor: {sig.score:.0f} | RSI: {sig.rsi:.0f}{ew_text}{candle_text}",
            font=dict(color=sig_color, size=14),
        ),
    )

    fig.update_yaxes(row=3, col=1, range=[0, 100])

    chart_html = fig.to_html(full_html=False, include_plotlyjs=False)
    commentary_html = _build_commentary_box(sig)

    return f'<div id="chart-{symbol}" style="margin-bottom:30px;">{chart_html}{commentary_html}</div>'


def generate_html_report(
    signals: list[Signal],
    stock_data: dict[str, pd.DataFrame],
    regime: MarketRegime,
) -> Path:
    """Tam interaktif HTML raporunu oluşturur."""
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime(REPORT_DATE_FORMAT)
    filepath = output_dir / f"bist_interactive_{date_str}.html"

    # Grafikleri oluştur (önce AL sinyalleri, sonra diğerleri)
    charts_html = ""
    sorted_signals = sorted(signals, key=lambda s: (
        0 if s.signal == "AL" else 1 if s.signal == "BEKLE" else 2,
        -s.score,
    ))

    for sig in sorted_signals:
        df = stock_data.get(sig.symbol)
        if df is not None and not df.empty:
            charts_html += _build_stock_chart(sig.symbol, df, sig)

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BIST Analiz Raporu — {datetime.now().strftime('%d.%m.%Y')}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e;
            color: #eee;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 25px;
            color: #00d2ff;
            font-size: 24px;
        }}
        table th {{
            position: sticky;
            top: 0;
            background: #0f3460;
            z-index: 10;
        }}
        table td, table th {{
            border-bottom: 1px solid #ffffff0a;
        }}
        table tr:hover {{
            background: rgba(0, 210, 255, 0.05) !important;
        }}
        input, select {{
            outline: none;
        }}
        input:focus, select:focus {{
            border-color: #00d2ff;
        }}
        .charts-section {{
            margin-top: 40px;
        }}
        .charts-section h2 {{
            color: #00d2ff;
            margin-bottom: 20px;
            font-size: 18px;
        }}
    </style>
</head>
<body>
    <h1>BIST Hisse Analiz Raporu</h1>
    {_build_summary_table(signals, regime)}
    {_build_data_table(signals)}
    <div class="charts-section">
        <h2>Detay Grafikleri</h2>
        {charts_html}
    </div>
    <div style="text-align:center; color:#555; padding:20px; font-size:11px;">
        Oluşturulma: {datetime.now().strftime('%d.%m.%Y %H:%M')} |
        Bu rapor yatırım tavsiyesi içermez.
    </div>
</body>
</html>"""

    filepath.write_text(html, encoding="utf-8")
    logger.info("İnteraktif HTML raporu kaydedildi: %s", filepath)
    return filepath
