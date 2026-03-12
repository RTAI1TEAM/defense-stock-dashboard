/**
 * charts.js
 * Chart.js 3.x — 캔들스틱 + 순수 Canvas 이벤트 줌/팬 (플러그인 불필요)
 */

window.chartInstances = window.chartInstances || {};
window.chartRawData   = window.chartRawData   || {};

/* ══════════════════════════════════════════════════════════════════
   순수 Canvas 줌/팬 엔진
   휠: 줌인/아웃  |  드래그: 팬  |  더블클릭: 전체 리셋
   ══════════════════════════════════════════════════════════════════ */
function bindZoomEngine(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // 이미 바인딩됨 → 줌 상태만 리셋하고 종료 (이벤트 중복 방지)
    if (canvas._zoomBound) {
        if (canvas._resetZoomState) canvas._resetZoomState();
        return;
    }
    canvas._zoomBound = true;

    let xMin0 = null, xMax0 = null;
    let isPanning = false, panStartX = 0, panStartMin, panStartMax;

    function getChart() { return window.chartInstances?.[canvasId]; }

    function saveOriginal() {
        if (xMin0 !== null) return;
        const ch = getChart(); if (!ch) return;
        xMin0 = ch.scales.x.min;
        xMax0 = ch.scales.x.max;
    }

    canvas._resetZoomState = function () { xMin0 = null; xMax0 = null; };

    /* 휠 줌 */
    canvas.addEventListener("wheel", function (e) {
        e.preventDefault();
        const ch = getChart(); if (!ch) return;
        saveOriginal();
        const sc = ch.scales.x;
        const curRange = sc.max - sc.min;
        const factor   = e.deltaY < 0 ? 0.8 : 1.25;
        const newRange = Math.min(Math.max(curRange * factor, 5 * 86400000), xMax0 - xMin0);
        const rect  = canvas.getBoundingClientRect();
        const ratio = (e.clientX - rect.left - sc.left) / sc.width;
        const pivot = sc.min + ratio * curRange;
        let newMin  = pivot - ratio * newRange;
        let newMax  = pivot + (1 - ratio) * newRange;
        if (newMin < xMin0) { newMax += xMin0 - newMin; newMin = xMin0; }
        if (newMax > xMax0) { newMin -= newMax - xMax0; newMax = xMax0; }
        ch.options.scales.x.min = newMin;
        ch.options.scales.x.max = newMax;
        ch.update("none");
    }, { passive: false });

    /* 더블클릭 리셋 */
    canvas.addEventListener("dblclick", function () {
        const ch = getChart(); if (!ch || xMin0 === null) return;
        ch.options.scales.x.min = xMin0;
        ch.options.scales.x.max = xMax0;
        ch.update("none");
    });

    /* 드래그 팬 */
    canvas.addEventListener("mousedown", function (e) {
        if (e.button !== 0) return;
        const ch = getChart(); if (!ch) return;
        saveOriginal();
        isPanning = true; panStartX = e.clientX;
        panStartMin = ch.scales.x.min; panStartMax = ch.scales.x.max;
        canvas.style.cursor = "grabbing";
    });
    window.addEventListener("mousemove", function (e) {
        if (!isPanning) return;
        const ch = getChart(); if (!ch) return;
        const sc = ch.scales.x;
        const range = panStartMax - panStartMin;
        const pxPer = range / sc.width;
        const delta = (e.clientX - panStartX) * pxPer;
        let newMin = panStartMin - delta, newMax = panStartMax - delta;
        if (newMin < xMin0) { newMin = xMin0; newMax = xMin0 + range; }
        if (newMax > xMax0) { newMax = xMax0; newMin = xMax0 - range; }
        ch.options.scales.x.min = newMin;
        ch.options.scales.x.max = newMax;
        ch.update("none");
    });
    window.addEventListener("mouseup", function () {
        if (isPanning) { isPanning = false; canvas.style.cursor = "default"; }
    });
}

/* ══════════════════════════════════════════════════════════════════
   캔들 그리기
   ══════════════════════════════════════════════════════════════════ */
function drawCandles(chart, rawData) {
    if (!rawData || !rawData.length) return;
    const ctx = chart.ctx, xScale = chart.scales.x, yScale = chart.scales.y;
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
        const po = yScale.getPixelForValue(d.o), ph = yScale.getPixelForValue(d.h);
        const pl = yScale.getPixelForValue(d.l), pc = yScale.getPixelForValue(d.c);
        const color = d.c >= d.o ? "#e15759" : "#4e79a7";
        ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = 1;
        ctx.moveTo(px, ph); ctx.lineTo(px, pl); ctx.stroke();
        ctx.fillStyle = color;
        ctx.fillRect(px - candleW / 2, Math.min(po, pc), candleW, Math.max(1, Math.abs(pc - po)));
    });
    ctx.restore();
}

/* ══════════════════════════════════════════════════════════════════
   버튼 상태 동기화
   ══════════════════════════════════════════════════════════════════ */
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

/* ══════════════════════════════════════════════════════════════════
   인스턴스 안전 제거
   ══════════════════════════════════════════════════════════════════ */
function destroyChart(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    if (canvas._resetZoomState) canvas._resetZoomState();
    const existing = Chart.getChart(canvas);
    if (existing) existing.destroy();
    if (window.chartInstances[canvasId]) {
        try { window.chartInstances[canvasId].destroy(); } catch(e) {}
        delete window.chartInstances[canvasId];
    }
}

/* ══════════════════════════════════════════════════════════════════
   라인 차트
   ══════════════════════════════════════════════════════════════════ */
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
                borderColor: "#0d6efd", backgroundColor: "#0d6efd",
                borderWidth: 2, fill: false, tension: 0.15,
                pointRadius: 0, pointHoverRadius: 2, parsing: false
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false, parsing: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: items => items[0] ? new Date(items[0].raw.x).toLocaleDateString("ko-KR") : "",
                        label: ctx  => `${datasetLabel}: ${ctx.raw.y.toLocaleString()}원`
                    }
                }
            },
            scales: {
                x: { type: "time", time: { unit: "day" }, ticks: { maxTicksLimit: 8 } },
                y: { beginAtZero: false }
            }
        }
    });

    bindZoomEngine(canvasId);
    setActiveChartButtons(canvasId, "line");
};

/* ══════════════════════════════════════════════════════════════════
   캔들 차트
   ══════════════════════════════════════════════════════════════════ */
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
                data: rawData.map(d => ({ x: d.x, y: d.h })),
                borderColor: "transparent", backgroundColor: "transparent",
                pointRadius: 0, fill: false, parsing: false
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false, parsing: false, animation: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: items => items[0]?.raw ? new Date(items[0].raw.x).toLocaleDateString("ko-KR") : "",
                        label: ctx => {
                            const d = rawData.find(r => r.x === ctx.raw.x);
                            if (!d) return "";
                            return [`시가: ${d.o.toLocaleString()}원`, `고가: ${d.h.toLocaleString()}원`,
                                    `저가: ${d.l.toLocaleString()}원`, `종가: ${d.c.toLocaleString()}원`];
                        }
                    }
                }
            },
            scales: {
                x: { type: "time", time: { unit: "day" }, ticks: { maxTicksLimit: 8 } },
                y: { beginAtZero: false, min: yMin, max: yMax }
            }
        },
        plugins: [{
            id: "inlineCandleMain",
            afterDatasetsDraw(chart) { drawCandles(chart, rawData); }
        }]
    });

    bindZoomEngine(canvasId);
    setActiveChartButtons(canvasId, "candle");
};

/* ══════════════════════════════════════════════════════════════════
   Candle / Line 전환
   ══════════════════════════════════════════════════════════════════ */
window.switchChart = function (canvasId, type) {
    const chartInfo = window.chartRawData[canvasId];
    if (!chartInfo) return;
    const canvas = document.getElementById(canvasId);
    if (canvas && canvas._resetZoomState) canvas._resetZoomState();
    if (type === "line") {
        window.renderLineChart({ canvasId, rawData: chartInfo.raw, datasetLabel: chartInfo.lineLabel });
    } else {
        window.renderCandleChart({ canvasId, rawData: chartInfo.raw, datasetLabel: chartInfo.candleLabel });
    }
};