/**
 * 주식 상세 페이지 통합 스크립트입니다.
 * 이 파일은 채팅 UI 제어, 투자 폼 전환, 그리고 전략별 차트 시각화를 담당합니다.
 */

// [1. 채팅 관련 및 페이지 초기화 로직]

// 채팅 메시지 목록의 스크롤을 가장 아래로 이동시켜 최신 메시지를 사용자에게 보여주는 함수입니다.
function scrollChatToBottom() {
    const chatList = document.getElementById("chat-msg-list");
    if (chatList) {
        chatList.scrollTop = chatList.scrollHeight;
    }
}

// 페이지의 HTML 구조가 완전히 로드된 후 실행되는 초기화 블록입니다.
document.addEventListener("DOMContentLoaded", function () {
    // 페이지 로드 직후 해당 종목의 채팅 박스 내용을 서버에서 비동기적으로 가져옵니다.
    fetch("/stocks/" + STOCK_CONFIG.ticker + "/chat-box")
        .then(response => response.text())
        .then(html => {
            // 받아온 HTML을 채팅 컨테이너 영역에 삽입합니다.
            document.getElementById("stock-chat-container").innerHTML = html;
            // 메시지가 로드된 후 스크롤 위치를 최하단으로 조정합니다.
            setTimeout(scrollChatToBottom, 0);
        });

    // 화면 우측의 'AI 분석' 영역과 '모의투자 입력 폼'을 서로 전환하는 로직입니다.
    const startBtn = document.getElementById('investStartBtn');
    const analysis = document.getElementById('ai-analysis-wrapper');
    const invest   = document.getElementById('invest-form-wrapper');
    
    // '모의투자 시작하기' 버튼 클릭 시 분석 카드를 숨기고 투자 폼을 보여줍니다.
    if (startBtn && analysis && invest) {
        startBtn.addEventListener('click', function () {
            analysis.style.display = 'none';
            invest.style.display   = 'block';
        });
    }
    
    // 투자 폼에서 '취소' 또는 '뒤로가기'를 눌렀을 때 다시 AI 분석 카드로 돌아가는 전역 함수입니다.
    window.goBack = function () {
        if (analysis && invest) {
            invest.style.display   = 'none';
            analysis.style.display = 'block';
        }
    };
});

// [2. 전략 및 차트 분석 로직]

// 서버에서 전달받은 종목의 고유 티커 정보를 상수로 저장합니다.
const TICKER = STOCK_CONFIG.stockTicker;

// 각 투자 전략의 핵심 매매 공식을 사용자에게 한 줄로 설명하기 위한 정의문입니다.
const ONE_LINER = {
    golden_cross: "📈 MA5(단기)가 MA20(장기)을 상향 돌파 시 매수 🔴B / 하향 돌파 시 매도 🔵S",
    breakout:     "🚀 종가가 20일 최고가(저항선) 돌파 시 매수 🔴B / MA20(지지선) 아래 이탈 시 매도 🔵S"
};

// 마지막으로 수신한 백테스트 및 전략 데이터를 저장하여 화면 갱신 시 활용합니다.
let _lastStrategyData = null;

// 전략 선택을 취소했을 때 백테스트 결과 카드를 숨기고 차트를 기본 상태로 되돌리는 함수입니다.
function resetBacktestCard() {
    const card = document.getElementById("backtestCard");
    if (card) card.style.display = "none";
    const oneLiner = document.getElementById("strategyOneLinerText");
    if (oneLiner) { oneLiner.textContent = ""; oneLiner.style.visibility = "hidden"; }
    _lastStrategyData = null;
    const strategy = document.getElementById("strategySelect").value;
    // '전략 없음' 선택 시 차트를 기본 종가 차트로 다시 그립니다.
    if (strategy === "none" && typeof switchChart === "function") {
        switchChart("mainEtfChart", getCurrentChartType());
    }
}

// 새로운 차트를 렌더링하기 전, 기존에 생성된 Chart.js 인스턴스를 파괴하여 메모리 누수를 방지합니다.
function destroyMainChart() {
    const canvas = document.getElementById("mainEtfChart");
    if (!canvas) return;
    // 차트의 줌(Zoom) 상태를 초기화합니다.
    if (canvas._resetZoomState) canvas._resetZoomState();
    const existing = Chart.getChart(canvas);
    if (existing) existing.destroy();
    // 전역 객체에 저장된 인스턴스 기록을 삭제합니다.
    if (window.chartInstances && window.chartInstances["mainEtfChart"]) {
        try { window.chartInstances["mainEtfChart"].destroy(); } catch(e) {}
        delete window.chartInstances["mainEtfChart"];
    }
}

// 현재 화면에 표시 중인 차트의 종류가 '캔들'인지 '라인'인지 확인하여 반환합니다.
function getCurrentChartType() {
    const candleBtn = document.getElementById("mainEtfChart-btn-candle");
    return candleBtn && candleBtn.classList.contains("btn-primary") ? "candle" : "line";
}

// 서버에서 계산된 백테스트 결과 데이터를 우측 카드 UI에 반영하는 함수입니다.
function updateBacktestCard(data) {
    document.getElementById("backtestCard").style.display = "";
    const profit = data.total_profit;
    const profitEl = document.getElementById("bt-profit");
    
    // 수익률이 양수이면 빨간색, 음수이면 파란색으로 표시합니다.
    profitEl.textContent  = (profit >= 0 ? "+" : "") + profit + "%";
    profitEl.style.color  = profit >= 0 ? "#2e7d32" : "#c62828";
    document.getElementById("bt-winrate").textContent = data.win_rate + "%";
    document.getElementById("bt-count").textContent   = data.trade_count + "회";
    
    // 가상 시드머니 1,000만원을 기준으로 최종 예상 자산을 계산하여 보여줍니다.
    const finalAmount = Math.round(10_000_000 * (1 + profit / 100));
    const finalEl = document.getElementById("bt-final");
    finalEl.textContent = finalAmount.toLocaleString() + "원";
    finalEl.style.color = profit >= 0 ? "#2e7d32" : "#c62828";
}

// [핵심 기능] 전략 지표와 매수/매도 마커를 메인 차트 위에 렌더링하는 함수입니다.
function renderStrategyOnMain(data) {
    const type   = getCurrentChartType();
    const canvas = document.getElementById("mainEtfChart");
    if (!canvas) return;

    destroyMainChart(); // 기존 차트를 초기화합니다.

    // 날짜 데이터를 시계열 차트에서 인식 가능한 타임스탬프로 변환합니다.
    const tsLabels = data.labels.map(d => new Date(d).getTime());

    // 전략에 따른 매수(BUY) 및 매도(SELL) 좌표를 설정합니다.
    const buyPoints  = data.labels.map((d, i) => {
        const t = data.backtest.find(x => x.date === d && x.type === 'BUY');
        return { x: tsLabels[i], y: t ? t.price : NaN };
    });
    const sellPoints = data.labels.map((d, i) => {
        const t = data.backtest.find(x => x.date === d && (x.type === 'SELL' || x.type === 'SELL (End)'));
        return { x: tsLabels[i], y: t ? t.price : NaN };
    });

    const datasets = [];

    // 사용자의 선택에 따라 캔들 데이터 또는 종가 라인 데이터를 데이터셋에 추가합니다.
    if (type === "candle") {
        const rawAll   = (window.chartRawData && window.chartRawData["mainEtfChart"])
            ? window.chartRawData["mainEtfChart"].raw : [];
        const labelSet = new Set(data.labels);
        const filtered = rawAll.filter(c => {
            if (!c || c.x == null) return false;
            return labelSet.has(new Date(c.x).toISOString().slice(0, 10));
        });
        datasets.push({
            type: "line", label: "캔들",
            data: filtered.map(c => ({ x: c.x, y: c.c })),
            _candleRaw: filtered,
            borderColor: "transparent", backgroundColor: "transparent",
            pointRadius: 0, showLine: false, order: 2, parsing: false
        });
    } else {
        datasets.push({
            type: "line", label: "종가",
            data: tsLabels.map((ts, i) => ({ x: ts, y: data.close[i] })),
            borderColor: "#4e79a7", borderWidth: 2, fill: false,
            tension: 0.15, pointRadius: 0, order: 2, parsing: false
        });
    }

    // 선택된 전략에 맞는 보조지표(이평선, 전고점선 등)를 데이터셋에 추가합니다.
    if (data.strategy === "golden_cross") {
        datasets.push({ type:"line", label:"MA5",  data: tsLabels.map((ts,i) => ({ x:ts, y: data.ma_short[i] != null ? data.ma_short[i] : NaN })), borderColor:"#f28e2b", borderWidth:1.5, borderDash:[4,3], fill:false, tension:0.15, pointRadius:0, spanGaps:true, parsing:false, order:3 });
        datasets.push({ type:"line", label:"MA20", data: tsLabels.map((ts,i) => ({ x:ts, y: data.ma_long[i]  != null ? data.ma_long[i]  : NaN })), borderColor:"#59a14f", borderWidth:1.5, borderDash:[4,3], fill:false, tension:0.15, pointRadius:0, spanGaps:true, parsing:false, order:4 });
    } else {
        datasets.push({ type:"line", label:"20일 최고가", data: tsLabels.map((ts,i) => ({ x:ts, y: data.high20[i] != null ? data.high20[i] : NaN })), borderColor:"#e15759", borderWidth:1.5, borderDash:[6,3], fill:false, tension:0,     pointRadius:0, spanGaps:true, parsing:false, order:3 });
        datasets.push({ type:"line", label:"MA20",         data: tsLabels.map((ts,i) => ({ x:ts, y: data.ma20[i]   != null ? data.ma20[i]   : NaN })), borderColor:"#59a14f", borderWidth:1.5, borderDash:[4,3], fill:false, tension:0.15, pointRadius:0, spanGaps:true, parsing:false, order:4 });
    }

    // 매수 및 매도 지점에 표시될 동그란 마커들을 추가합니다.
    const buyRadii  = buyPoints.map(p  => isNaN(p.y) ? 0 : 10);
    const sellRadii = sellPoints.map(p => isNaN(p.y) ? 0 : 10);
    datasets.push({ type:"line", label:"매수(B)", data: buyPoints,  borderColor:"#e15759", backgroundColor:"#e15759", pointRadius:buyRadii,  pointHoverRadius:buyRadii,  showLine:false, order:1, parsing:false });
    datasets.push({ type:"line", label:"매도(S)", data: sellPoints, borderColor:"#4e79a7", backgroundColor:"#4e79a7", pointRadius:sellRadii, pointHoverRadius:sellRadii, showLine:false, order:1, parsing:false });

    // 차트의 Y축 범위를 데이터에 맞춰 동적으로 계산합니다.
    let yScaleOpts = { beginAtZero: false };
    if (type === "candle") {
        const candleDs = datasets.find(d => d._candleRaw && d._candleRaw.length);
        if (candleDs) {
            const highs = candleDs._candleRaw.map(c => c.h).filter(v => v != null);
            const lows  = candleDs._candleRaw.map(c => c.l).filter(v => v != null);
            if (highs.length && lows.length) {
                const range = Math.max(...highs) - Math.min(...lows);
                yScaleOpts.max = Math.max(...highs) + range * 0.03;
                yScaleOpts.min = Math.min(...lows)  - range * 0.03;
            }
        }
    }

    // Chart.js 인스턴스를 생성하여 캔버스에 렌더링합니다.
    window.chartInstances = window.chartInstances || {};
    window.chartInstances["mainEtfChart"] = new Chart(canvas.getContext("2d"), {
        type: "line",
        data: { datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            parsing: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: true },
                tooltip: {
                    filter: item => item.raw != null && !isNaN(item.raw.y),
                    callbacks: {
                        title: function(items) {
                            if (!items[0]?.raw) return "";
                            return new Date(items[0].raw.x).toLocaleDateString("ko-KR");
                        },
                        label: function(ctx) {
                            if (!ctx.raw || isNaN(ctx.raw.y)) return null;
                            if (ctx.dataset.label === "매수(B)") {
                                const t = data.backtest.find(x => x.type === 'BUY' && new Date(x.date).getTime() === ctx.raw.x);
                                return t ? `▲ 매수: ${t.price.toLocaleString()}원 (${t.shares}주)` : "▲ 매수";
                            }
                            if (ctx.dataset.label === "매도(S)") {
                                const t = data.backtest.find(x => (x.type==='SELL'||x.type==='SELL (End)') && new Date(x.date).getTime() === ctx.raw.x);
                                return t ? `▼ 매도: ${t.price.toLocaleString()}원 ${t.profit_rate>=0?'+':''}${t.profit_rate}%` : "▼ 매도";
                            }
                            const val = typeof ctx.raw === 'object' ? (ctx.raw.y ?? ctx.raw.c) : ctx.raw;
                            return val != null ? `${ctx.dataset.label}: ${val.toLocaleString()}원` : null;
                        }
                    }
                },
            },
            scales: {
                x: { type: "time", time: { unit: "day" }, ticks: { maxTicksLimit: 8 } },
                y: yScaleOpts
            }
        },
        plugins: [
            {
                // [플러그인] 캔들 차트를 캔버스 위에 직접 그리는 로직입니다.
                id: "inlineCandle",
                afterDatasetsDraw(chart) {
                    chart.data.datasets.forEach(ds => {
                        if (!ds._candleRaw || !ds._candleRaw.length) return;
                        const ctx2 = chart.ctx, xScale = chart.scales.x, yScale = chart.scales.y;
                        const raw = ds._candleRaw;
                        let candleW = 8;
                        if (raw.length >= 2) candleW = Math.max(2, Math.abs(xScale.getPixelForValue(raw[1].x) - xScale.getPixelForValue(raw[0].x)) * 0.6);
                        raw.forEach(c => {
                            if (!c) return;
                            const px = xScale.getPixelForValue(c.x);
                            const color = c.c >= c.o ? "#e15759" : "#4e79a7";
                            ctx2.save();
                            ctx2.beginPath(); ctx2.strokeStyle = color; ctx2.lineWidth = 1;
                            ctx2.moveTo(px, yScale.getPixelForValue(c.h));
                            ctx2.lineTo(px, yScale.getPixelForValue(c.l));
                            ctx2.stroke();
                            const bodyTop = Math.min(yScale.getPixelForValue(c.o), yScale.getPixelForValue(c.c));
                            const bodyH = Math.max(1, Math.abs(yScale.getPixelForValue(c.o) - yScale.getPixelForValue(c.c)));
                            ctx2.fillStyle = color;
                            ctx2.fillRect(px - candleW / 2, bodyTop, candleW, bodyH);
                            ctx2.restore();
                        });
                    });
                }
            },
            {
                // [플러그인] 매매 포인트 위에 B(Buy)와 S(Sell) 라벨을 텍스트로 표시합니다.
                id: "bsLabels",
                afterDatasetsDraw(chart) {
                    const ctx2 = chart.ctx;
                    chart.data.datasets.forEach((ds, di) => {
                        if (ds.label !== "매수(B)" && ds.label !== "매도(S)") return;
                        const isBuy = ds.label === "매수(B)";
                        chart.getDatasetMeta(di).data.forEach((pt, idx) => {
                            if (!ds.data[idx] || isNaN(ds.data[idx].y)) return;
                            ctx2.save();
                            ctx2.font = "bold 9px Arial"; ctx2.fillStyle = "#fff";
                            ctx2.textAlign = "center"; ctx2.textBaseline = "middle";
                            ctx2.fillText(isBuy ? "B" : "S", pt.x, pt.y);
                            ctx2.restore();
                        });
                    });
                }
            }
        ]
    });

    // 차트 형태 전환 버튼의 활성화 상태를 업데이트합니다.
    if (typeof setActiveChartButtons === "function") setActiveChartButtons("mainEtfChart", type);

    // 차트의 줌(Zoom) 엔진을 활성화합니다.
    if (typeof bindZoomEngine === "function") bindZoomEngine("mainEtfChart");

    // 버튼 클릭 시 현재 보고 있는 전략 데이터를 바탕으로 차트를 다시 그리도록 이벤트를 바인딩합니다.
    if (!canvas._strategyBtnBound) {
        canvas._strategyBtnBound = true;
        const candleBtn = document.getElementById("mainEtfChart-btn-candle");
        const lineBtn   = document.getElementById("mainEtfChart-btn-line");
        if (candleBtn) candleBtn.addEventListener("click", () => { if (_lastStrategyData) renderStrategyOnMain(_lastStrategyData); });
        if (lineBtn)   lineBtn.addEventListener("click",   () => { if (_lastStrategyData) renderStrategyOnMain(_lastStrategyData); });
    }
}

// 사용자가 전략이나 분석 기간을 변경했을 때 서버에 데이터를 요청하여 차트를 업데이트하는 함수입니다.
function updateStrategyChart() {
    const strategy = document.getElementById("strategySelect").value;
    const days     = document.getElementById("periodSelect").value;
    const btn      = document.getElementById("analyzeBtn");

    // 전략을 선택하지 않았을 경우 초기화합니다.
    if (strategy === "none") {
        resetBacktestCard();
        return;
    }

    // 선택한 전략에 대한 설명을 화면에 표시합니다.
    const oneLiner = document.getElementById("strategyOneLinerText");
    if (oneLiner) { oneLiner.textContent = ONE_LINER[strategy] || ""; oneLiner.style.visibility = "visible"; }

    // 분석 중 버튼 상태를 변경하여 중복 클릭을 방지합니다.
    btn.textContent = "⏳ 분석 중...";
    btn.disabled    = true;

    // 서버의 전략 API를 통해 백테스트 결과를 가져옵니다.
    fetch(`/api/strategy/${TICKER}?strategy=${strategy}&days=${days}`)
        .then(r => r.json())
        .then(data => {
            btn.textContent = "🔍 분석하기";
            btn.disabled    = false;
            if (!data.success) { alert("전략 계산 오류: " + data.message); return; }
            // 데이터를 저장하고 차트와 결과 카드를 업데이트합니다.
            _lastStrategyData = data;
            renderStrategyOnMain(data);
            updateBacktestCard(data);
        })
        .catch(err => {
            btn.textContent = "🔍 분석하기";
            btn.disabled    = false;
            alert("서버 오류: " + err);
        });
}

// [3. 채팅 전송 및 새로고침 함수]

// 사용자가 입력한 메시지를 서버로 전송하고 채팅 목록을 갱신하는 함수입니다.
function sendChat() {
    const ticker = STOCK_CONFIG.ticker;
    const msgInput = document.getElementById('chat-input-msg');
    const message = msgInput.value.trim();

    if (!message) return; // 메시지가 비어있으면 전송하지 않습니다.

    const formData = new FormData();
    formData.append('ticker', ticker);
    formData.append('message', message);

    // 메시지를 DB에 저장하기 위해 백엔드로 전송합니다.
    fetch(STOCK_CONFIG.chatCreateUrl, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "success") {
            msgInput.value = ''; // 입력창을 비웁니다.
            refreshChatList(ticker); // 채팅 목록만 부분적으로 새로고침합니다.
        } else {
            alert(data.error || "전송 실패");
        }
    })
    .catch(err => console.error("전송 에러:", err));
}

// 페이지 전체 새로고침 없이 채팅 메시지 영역만 최신 데이터로 교체하는 함수입니다.
function refreshChatList(ticker) {
    fetch(`/stocks/${ticker}/chat-box`)
        .then(res => res.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            // 새로 받아온 HTML에서 메시지 리스트 부분만 추출하여 교체합니다.
            const newContent = doc.getElementById('chat-msg-list').innerHTML;
            const chatList = document.getElementById('chat-msg-list');
            
            if (chatList) {
                chatList.innerHTML = newContent;
                // 새로운 메시지가 추가되었으므로 다시 하단으로 스크롤합니다.
                setTimeout(scrollChatToBottom, 0);
            }
        })
        .catch(err => console.error("새로고침 에러:", err));
}