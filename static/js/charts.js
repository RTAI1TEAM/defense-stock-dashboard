/**
 * charts.js
 * chartjs-chart-financial 플러그인 없이 Chart.js 3.x 순수 기능으로 캔들스틱 구현
 * hitRadius / Cannot read 'x' 에러 근본 해결
 */

window.chartInstances = window.chartInstances || {};
window.chartRawData   = window.chartRawData   || {};

/* ────────────────────────────────────────────
   커스텀 캔들스틱 플러그인 (Chart.js 내장만 사용)
   x축: timestamp(ms), y축: price
   data 형식: [{ x, o, h, l, c }, ...]
──────────────────────────────────────────── */
const CandlestickPlugin = {
    id: "candlestickPlugin",
    afterDatasetsDraw(chart) {
        const meta = chart.getDatasetMeta(0);
        if (!meta || meta.type !== "_candlestick_custom") return;

        const ctx    = chart.ctx;
        const xScale = chart.scales.x;
        const yScale = chart.scales.y;
        const raw    = chart.data.datasets[0]._candleRaw || [];

        if (!raw.length) return;

        // 캔들 너비: 인접 두 점 간격의 60%
        let candleW = 8;
        if (raw.length > 1) {
            const x0 = xScale.getPixelForValue(raw[0].x);
            const x1 = xScale.getPixelForValue(raw[1].x);
            candleW = Math.max(2, Math.abs(x1 - x0) * 0.6);
        }

        ctx.save();
        raw.forEach(d => {
            if (d == null || d.o == null) return;
            const px = xScale.getPixelForValue(d.x);
            const po = yScale.getPixelForValue(d.o);
            const ph = yScale.getPixelForValue(d.h);
            const pl = yScale.getPixelForValue(d.l);
            const pc = yScale.getPixelForValue(d.c);

            const isUp    = d.c >= d.o;
            const color   = isUp ? "#e15759" : "#4e79a7";
            const bodyTop = isUp ? pc : po;
            const bodyH   = Math.max(1, Math.abs(pc - po));

            // 심지 (고저선)
            ctx.beginPath();
            ctx.strokeStyle = color;
            ctx.lineWidth   = 1;
            ctx.moveTo(px, ph);
            ctx.lineTo(px, pl);
            ctx.stroke();

            // 몸통
            ctx.fillStyle = color;
            ctx.fillRect(px - candleW / 2, bodyTop, candleW, bodyH);
        });
        ctx.restore();
    }
};

Chart.register(CandlestickPlugin);

/* ────────────────────────────────────────────
   유틸
──────────────────────────────────────────── */
function getLineSeriesFromCandle(rawData) {
    return rawData.map(item => ({ x: item.x, y: item.c }));
}

function setActiveChartButtons(canvasId, type) {
    const candleBtn = document.getElementById(`${canvasId}-btn-candle`);
    const lineBtn   = document.getElementById(`${canvasId}-btn-line`);
    if (!candleBtn || !lineBtn) return;

    if (type === "candle") {
        candleBtn.classList.replace("btn-outline-primary", "btn-primary");
        lineBtn.classList.replace("btn-primary", "btn-outline-primary");
    } else {
        lineBtn.classList.replace("btn-outline-primary", "btn-primary");
        candleBtn.classList.replace("btn-primary", "btn-outline-primary");
    }
}

/* ────────────────────────────────────────────
   라인 차트
──────────────────────────────────────────── */
window.renderLineChart = function ({ canvasId, rawData, datasetLabel = "종가" }) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    // Chart.js 3.x: getChart로 캔버스에 붙은 인스턴스 확실히 제거
    const _existingLine = Chart.getChart(canvas);
    if (_existingLine) _existingLine.destroy();
    if (window.chartInstances[canvasId]) {
        try { window.chartInstances[canvasId].destroy(); } catch(e) {}
        delete window.chartInstances[canvasId];
    }

    window.chartInstances[canvasId] = new Chart(ctx, {
        type: "line",
        data: {
            datasets: [{
                label: datasetLabel,
                data: getLineSeriesFromCandle(rawData),
                borderWidth: 2,
                fill: false,
                tension: 0.15,
                pointRadius: 0,
                pointHoverRadius: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            parsing: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true },
                tooltip: {
                    callbacks: {
                        title: items => items[0] ? new Date(items[0].raw.x).toLocaleDateString("ko-KR") : "",
                        label: ctx  => `${datasetLabel}: ${ctx.raw.y.toLocaleString()}원`
                    }
                },
                zoom: {
                    wheel: { enabled: true },
                    pinch: { enabled: true },
                    mode: "x"
                },
                pan: {
                    enabled: true,
                    mode: "x"
                }
            },
            scales: {
                x: { type: "time", time: { unit: "day" }, ticks: { maxTicksLimit: 8 } },
                y: { beginAtZero: false }
            }
        }
    });

    setActiveChartButtons(canvasId, "line");
};

/* ────────────────────────────────────────────
   캔들 차트 (커스텀 플러그인 사용, 외부 의존성 없음)
──────────────────────────────────────────── */
window.renderCandleChart = function ({ canvasId, rawData, datasetLabel = "주가" }) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    // Chart.js 3.x: getChart로 캔버스에 붙은 인스턴스 확실히 제거
    const _existingCandle = Chart.getChart(canvas);
    if (_existingCandle) _existingCandle.destroy();
    if (window.chartInstances[canvasId]) {
        try { window.chartInstances[canvasId].destroy(); } catch(e) {}
        delete window.chartInstances[canvasId];
    }

    // 플러그인이 그리기 위한 숨겨진 라인 데이터셋 (고가 기준 라인 — 축 범위 계산용)
    const allPrices = rawData.flatMap(d => [d.h, d.l]).filter(v => v != null);
    const yMin = Math.min(...allPrices) * 0.995;
    const yMax = Math.max(...allPrices) * 1.005;

    const chart = new Chart(ctx, {
        type: "line",            // 기본 타입 line (캔들은 플러그인이 직접 그림)
        data: {
            datasets: [{
                label: datasetLabel,
                data: rawData.map(d => ({ x: d.x, y: d.h })), // 축 범위용
                borderColor: "transparent",
                pointRadius: 0,
                fill: false,
                _candleRaw: rawData  // 플러그인에 원본 전달
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            parsing: false,
            animation: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true },
                candlestickPlugin: {},          // 플러그인 활성화
                zoom: {
                    wheel: { enabled: true },
                    pinch: { enabled: true },
                    mode: "x"
                },
                pan: {
                    enabled: true,
                    mode: "x"
                },
                tooltip: {
                    callbacks: {
                        title: items => {
                            if (!items[0]?.raw) return "";
                            return new Date(items[0].raw.x).toLocaleDateString("ko-KR");
                        },
                        label: ctx => {
                            const d = rawData.find(r => r.x === ctx.raw.x);
                            if (!d) return "";
                            return [
                                `시가: ${d.o.toLocaleString()}원`,
                                `고가: ${d.h.toLocaleString()}원`,
                                `저가: ${d.l.toLocaleString()}원`,
                                `종가: ${d.c.toLocaleString()}원`
                            ];
                        }
                    }
                }
            },
            scales: {
                x: { type: "time", time: { unit: "day" }, ticks: { maxTicksLimit: 8 } },
                y: { beginAtZero: false, min: yMin, max: yMax }
            }
        }
    });

    // 플러그인이 접근할 수 있도록 메타에 타입 표시
    chart.getDatasetMeta(0).type = "_candlestick_custom";
    chart.update("none");

    window.chartInstances[canvasId] = chart;
    setActiveChartButtons(canvasId, "candle");
};

/* ────────────────────────────────────────────
   Candle / Line 전환
──────────────────────────────────────────── */
window.switchChart = function (canvasId, type) {
    const chartInfo = window.chartRawData[canvasId];
    if (!chartInfo) return;

    if (type === "line") {
        window.renderLineChart({ canvasId, rawData: chartInfo.raw, datasetLabel: chartInfo.lineLabel });
    } else {
        window.renderCandleChart({ canvasId, rawData: chartInfo.raw, datasetLabel: chartInfo.candleLabel });
    }
};