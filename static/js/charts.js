/**
 * charts.js
 * Chart.js 3.x 순수 기능으로 캔들스틱 구현 (외부 플러그인 없음)
 */

window.chartInstances = window.chartInstances || {};
window.chartRawData   = window.chartRawData   || {};

/* ── 캔들 그리기 공통 함수 ───────────────────────────────────────── */
function drawCandles(chart, rawData) {
    if (!rawData || !rawData.length) return;
    const ctx    = chart.ctx;
    const xScale = chart.scales.x;
    const yScale = chart.scales.y;

    let candleW = 8;
    if (rawData.length > 1) {
        const x0 = xScale.getPixelForValue(rawData[0].x);
        const x1 = xScale.getPixelForValue(rawData[1].x);
        candleW = Math.max(2, Math.abs(x1 - x0) * 0.6);
    }

    ctx.save();
    rawData.forEach(d => {
        if (d == null || d.o == null) return;
        const px = xScale.getPixelForValue(d.x);
        const po = yScale.getPixelForValue(d.o);
        const ph = yScale.getPixelForValue(d.h);
        const pl = yScale.getPixelForValue(d.l);
        const pc = yScale.getPixelForValue(d.c);
        const color   = d.c >= d.o ? "#e15759" : "#4e79a7";
        const bodyTop = Math.min(po, pc);
        const bodyH   = Math.max(1, Math.abs(pc - po));

        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth   = 1;
        ctx.moveTo(px, ph);
        ctx.lineTo(px, pl);
        ctx.stroke();

        ctx.fillStyle = color;
        ctx.fillRect(px - candleW / 2, bodyTop, candleW, bodyH);
    });
    ctx.restore();
}

/* ── 버튼 상태 동기화 ───────────────────────────────────────────── */
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

/* ── 인스턴스 안전 제거 ─────────────────────────────────────────── */
function destroyChart(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const existing = Chart.getChart(canvas);
    if (existing) existing.destroy();
    if (window.chartInstances[canvasId]) {
        try { window.chartInstances[canvasId].destroy(); } catch(e) {}
        delete window.chartInstances[canvasId];
    }
}

/* ── 라인 차트 ──────────────────────────────────────────────────── */
window.renderLineChart = function ({ canvasId, rawData, datasetLabel = "종가" }) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    destroyChart(canvasId);

    window.chartInstances[canvasId] = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
            datasets: [{
                label: datasetLabel,
                data: rawData.map(d => ({ x: d.x, y: d.c })),
                borderColor: "#0d6efd",
                backgroundColor: "#0d6efd",
                borderWidth: 2,
                fill: false,
                tension: 0.15,
                pointRadius: 0,
                pointHoverRadius: 2,
                pointBackgroundColor: "#0d6efd",
                pointBorderColor: "#0d6efd",
                parsing: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            parsing: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: items => items[0] ? new Date(items[0].raw.x).toLocaleDateString("ko-KR") : "",
                        label: ctx  => `${datasetLabel}: ${ctx.raw.y.toLocaleString()}원`
                    }
                },
                zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: "x" },
                pan:  { enabled: true, mode: "x" }
            },
            scales: {
                x: { type: "time", time: { unit: "day" }, ticks: { maxTicksLimit: 8 } },
                y: { beginAtZero: false }
            }
        }
    });

    setActiveChartButtons(canvasId, "line");
};

/* ── 캔들 차트 (인라인 플러그인 방식) ──────────────────────────── */
window.renderCandleChart = function ({ canvasId, rawData, datasetLabel = "주가" }) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    destroyChart(canvasId);

    const allPrices = rawData.flatMap(d => [d.h, d.l]).filter(v => v != null);
    const yMin = Math.min(...allPrices) * 0.995;
    const yMax = Math.max(...allPrices) * 1.005;

    window.chartInstances[canvasId] = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
            datasets: [{
                label: datasetLabel,
                data: rawData.map(d => ({ x: d.x, y: d.h })), // 축 범위용
                borderColor: "transparent",
                backgroundColor: "transparent",
                pointRadius: 0,
                fill: false,
                parsing: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            parsing: false,
            animation: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: "x" },
                pan:  { enabled: true, mode: "x" },
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
        },
        // 인라인 플러그인: meta.type 체크 없이 rawData 직접 사용
        plugins: [{
            id: "inlineCandleMain",
            afterDatasetsDraw(chart) {
                drawCandles(chart, rawData);
            }
        }]
    });

    setActiveChartButtons(canvasId, "candle");
};

/* ── Candle / Line 전환 ─────────────────────────────────────────── */
window.switchChart = function (canvasId, type) {
    const chartInfo = window.chartRawData[canvasId];
    if (!chartInfo) return;
    if (type === "line") {
        window.renderLineChart({ canvasId, rawData: chartInfo.raw, datasetLabel: chartInfo.lineLabel });
    } else {
        window.renderCandleChart({ canvasId, rawData: chartInfo.raw, datasetLabel: chartInfo.candleLabel });
    }
};