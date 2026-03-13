// chart.js : 다양한 종류의 차트를 생성할 수 있는 데이터 시각화 라이브러리 https://www.chartjs.org/docs/latest/
//  Chart.js 3.x — 캔들스틱 + 순수 Canvas 이벤트 줌/팬 (플러그인 불필요)

// 캔버스 ID 별 Chart.js 인스턴스 저장
window.chartInstances = window.chartInstances || {};
// 차트 원본 데이터 저장. 차트 타입을 line<->candle로 바꿀 때 사용
window.chartRawData   = window.chartRawData   || {};

// 특정 canvas에 대해 휠 줌, 더블클릭 리셋, 마우스 드래그 팬 이벤트를 붙여주는 엔진
function bindZoomEngine(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // 이미 바인딩됨 → 줌 상태만 리셋하고 종료 (이벤트 중복 방지)
    if (canvas._zoomBound) {
        if (canvas._resetZoomState) canvas._resetZoomState();
        return;
    }
    canvas._zoomBound = true;
    // 초기 전체 차트 범위 저장
    let xMin0 = null, xMax0 = null;
    // 드래그 팬 여부 저장, 드래그 시작한 마우스 위치, 팬 시작 시의 x축 범위
    let isPanning = false, panStartX = 0, panStartMin, panStartMax;
    
    // 현재 canvasId에 해당하는 차트 객체를 꺼내는 함수
    function getChart() { 
        return window.chartInstances?.[canvasId]; 
    }
    // 최초 전체 범위 저장
    // 현재 캔버스의 차트 객체를 꺼내와서 x범위 저장
    function saveOriginal() {
        if (xMin0 !== null) return;
        const ch = getChart(); 
        if (!ch) return;
        xMin0 = ch.scales.x.min;
        xMax0 = ch.scales.x.max;
    }
    // 차트 x 범위 초기화
    canvas._resetZoomState = function () { xMin0 = null; xMax0 = null; };

    // 휠 줌
    canvas.addEventListener("wheel", function (e) {
        e.preventDefault();
        const ch = getChart(); if (!ch) return;
        saveOriginal();     // 최초 전체 범위 저장
        const sc = ch.scales.x;     // 현재 스케일 저장
        const curRange = sc.max - sc.min;   // 현재 보이는 x축 구간 길이
        const factor   = e.deltaY < 0 ? 0.8 : 1.25; // 확대/축소 배율
        const newRange = Math.min(Math.max(curRange * factor, 5 * 86400000), xMax0 - xMin0);    // 새 범위 제한
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

    // 더블클릭 시 원래 저장해둔 전체 x축 범위로 복귀
    canvas.addEventListener("dblclick", function () {
        const ch = getChart(); if (!ch || xMin0 === null) return;
        ch.options.scales.x.min = xMin0;
        ch.options.scales.x.max = xMax0;
        ch.update("none");
    });

    // 드래그 팬
    canvas.addEventListener("mousedown", function (e) {
        if (e.button !== 0) return;
        const ch = getChart(); if (!ch) return;
        saveOriginal();
        isPanning = true; panStartX = e.clientX;
        panStartMin = ch.scales.x.min; panStartMax = ch.scales.x.max;
        canvas.style.cursor = "grabbing";   // 커서를 grabbing으로 변경
    });
    window.addEventListener("mousemove", function (e) {
        if (!isPanning) return;
        const ch = getChart(); if (!ch) return;
        const sc = ch.scales.x;
        const range = panStartMax - panStartMin;    // 현재 보여지는 날짜 축
        const pxPer = range / sc.width;     // 1 픽셀 이동이 x축 값으로 얼마나 되는지 계산
        const delta = (e.clientX - panStartX) * pxPer;  // 마우스 움직인 범위를 x축 단위로 환산
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


// 캔들차트 그리기
function drawCandles(chart, rawData) {
    if (!rawData || !rawData.length) return;
    const ctx = chart.ctx, xScale = chart.scales.x, yScale = chart.scales.y;
    // 캔들 폭 계산
    let candleW = 8;
    if (rawData.length > 1) {
        const x0 = xScale.getPixelForValue(rawData[0].x);
        const x1 = xScale.getPixelForValue(rawData[1].x);
        candleW = Math.max(2, Math.abs(x1 - x0) * 0.6);
    }
    ctx.save();
    rawData.forEach(d => {
        // 데이터 유효성 체크
        if (!d || d.o == null || d.h == null || d.l == null || d.c == null) return;
        // 고가나 저가가 0이면 스킵
        if (d.h === 0 || d.l === 0) return;
        // canvas 픽셀 좌표로 변환
        const px = xScale.getPixelForValue(d.x);
        const po = yScale.getPixelForValue(d.o), ph = yScale.getPixelForValue(d.h);
        const pl = yScale.getPixelForValue(d.l), pc = yScale.getPixelForValue(d.c);
        // 상승/하락 색상
        const color = d.c >= d.o ? "#e15759" : "#4e79a7";
        // 캔들 그리기
        ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = 1;
        ctx.moveTo(px, ph); ctx.lineTo(px, pl); ctx.stroke();
        ctx.fillStyle = color;
        ctx.fillRect(px - candleW / 2, Math.min(po, pc), candleW, Math.max(1, Math.abs(pc - po)));
    });
    ctx.restore();
}

// 어떤 버튼이 활성 상태인지 시각적으로 보여주는 부분
// 활성화 된 버튼의 부트스트랩 클래스를 btn-primary로 바꾸는 함수
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

// 새 차트를 그리기 전 기존 차트를 지우는 함수
function destroyChart(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    if (canvas._resetZoomState) canvas._resetZoomState();   // 줌 추기화
    const existing = Chart.getChart(canvas);    // chart.js가 관리하는 기존 차트 제거
    if (existing) existing.destroy();
    if (window.chartInstances[canvasId]) {
        try { window.chartInstances[canvasId].destroy(); } catch(e) {}
        delete window.chartInstances[canvasId];
    }
}

// 라인 차트 렌더링하는 함수
window.renderLineChart = function ({ canvasId, rawData, datasetLabel = "종가" }) {
    const canvas = document.getElementById(canvasId);
    // 기존 차트 제거
    if (!canvas) return;
    destroyChart(canvasId);
    // chart.js의 line차트 생성
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


// 캔들차트 렌더링하는 함수
window.renderCandleChart = function ({ canvasId, rawData, datasetLabel = "주가" }) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    destroyChart(canvasId);

    const allPrices = rawData.flatMap(d => [d.h, d.l]).filter(v => v != null);
    const yMin = Math.min(...allPrices) * 0.995;
    const yMax = Math.max(...allPrices) * 1.005;

    window.chartInstances[canvasId] = new Chart(canvas.getContext("2d"), {
        type: "line",   // chart.js의 시간축/툴팁/축 시스템만 빌려오고 실제 캔들은 drawCandles()로 직접 그림
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
        plugins: [{     // chart.js의 커스텀 플러그인 훅
            id: "inlineCandleMain",
            afterDatasetsDraw(chart) { drawCandles(chart, rawData); }   
        }]
    });

    bindZoomEngine(canvasId);
    setActiveChartButtons(canvasId, "candle");
};

// 라인 <-> 캔들 전환 함수
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