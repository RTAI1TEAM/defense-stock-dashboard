/**
 * 주식 상세 페이지 통합 스크립트
 * 설명: 채팅 시스템, UI 전환, Chart.js를 이용한 주식 전략 시뮬레이션 시각화 포함
 */

// 1. 채팅 관련 및 페이지 초기화 로직

/**
 * 채팅 메시지 목록을 가장 아래로 스크롤하여 최신 메시지를 보여줌
 */
function scrollChatToBottom() {
    const chatList = document.getElementById("chat-msg-list");
    if (chatList) {
        chatList.scrollTop = chatList.scrollHeight;
    }
}

/**
 * 문서 로드 완료 시 초기화 작업 수행
 */
document.addEventListener("DOMContentLoaded", function () {
    // 채팅 박스 초기 데이터 로드: 서버에서 HTML 조각을 가져와 컨테이너에 삽입
    fetch("/stocks/" + STOCK_CONFIG.ticker + "/chat-box")
        .then(response => response.text())
        .then(html => {
            document.getElementById("stock-chat-container").innerHTML = html;
            setTimeout(scrollChatToBottom, 0); // DOM 렌더링 후 스크롤 하단 이동
        });

    // 투자 폼 전환 로직: AI 분석 화면과 투자 입력 폼 사이의 UI 스위칭
    const startBtn = document.getElementById('investStartBtn');
    const analysis = document.getElementById('ai-analysis-wrapper');
    const invest   = document.getElementById('invest-form-wrapper');
    
    // '투자 시작' 버튼 클릭 시 분석 영역 숨기고 폼 영역 표시
    if (startBtn && analysis && invest) {
        startBtn.addEventListener('click', function () {
            analysis.style.display = 'none';
            invest.style.display   = 'block';
        });
    }
    
    // 이전으로 돌아가기(goBack) 전역 함수 정의
    window.goBack = function () {
        if (analysis && invest) {
            invest.style.display   = 'none';
            analysis.style.display = 'block';
        }
    };
});

// 2. 전략 및 차트 분석 로직

const TICKER = STOCK_CONFIG.stockTicker;

// 화면에 보여줄 전략별 한 줄 요약 텍스트 정의
const ONE_LINER = {
    golden_cross: "📈 MA5(단기)가 MA20(장기)을 상향 돌파 시 매수 🔴B / 하향 돌파 시 매도 🔵S",
    breakout:     "🚀 종가가 20일 최고가(저항선) 돌파 시 매수 🔴B / MA20(지지선) 아래 이탈 시 매도 🔵S"
};

let _lastStrategyData = null; // 마지막으로 성공한 분석 데이터를 보관 (차트 타입 변경 시 사용)

/**
 * 전략 분석 결과를 초기화하고 일반 차트로 되돌림
 */
function resetBacktestCard() {
    const card = document.getElementById("backtestCard");
    if (card) card.style.display = "none";
    const oneLiner = document.getElementById("strategyOneLinerText");
    if (oneLiner) { oneLiner.textContent = ""; oneLiner.style.visibility = "hidden"; }
    _lastStrategyData = null;
    const strategy = document.getElementById("strategySelect").value;
    // 전략이 '없음'일 경우 기본 차트 렌더링 함수 호출
    if (strategy === "none" && typeof switchChart === "function") {
        switchChart("mainEtfChart", getCurrentChartType());
    }
}

/**
 * 기존에 렌더링된 Chart.js 인스턴스를 파괴하여 메모리 누수 방지 및 재렌더링 준비
 */
function destroyMainChart() {
    const canvas = document.getElementById("mainEtfChart");
    if (!canvas) return;
    // 줌 상태 초기화 (xMin0/xMax0 리셋 — 다음 차트 로드 시 새 범위로 저장됨)
    if (canvas._resetZoomState) canvas._resetZoomState();
    const existing = Chart.getChart(canvas);
    if (existing) existing.destroy();
    if (window.chartInstances && window.chartInstances["mainEtfChart"]) {
        try { window.chartInstances["mainEtfChart"].destroy(); } catch(e) {}
        delete window.chartInstances["mainEtfChart"];
    }
}

/**
 * 현재 UI에서 선택된 차트 종류(캔들/라인)를 반환
 */
function getCurrentChartType() {
    const candleBtn = document.getElementById("mainEtfChart-btn-candle");
    return candleBtn && candleBtn.classList.contains("btn-primary") ? "candle" : "line";
}

/**
 * 백테스트 통계 결과(수익률, 승률 등)를 카드 UI에 업데이트
 */
function updateBacktestCard(data) {
    document.getElementById("backtestCard").style.display = "";
    const profit = data.total_profit;
    const profitEl = document.getElementById("bt-profit");
    // 수익률 색상 및 텍스트 설정
    profitEl.textContent  = (profit >= 0 ? "+" : "") + profit + "%";
    profitEl.style.color  = profit >= 0 ? "#2e7d32" : "#c62828";
    document.getElementById("bt-winrate").textContent = data.win_rate + "%";
    document.getElementById("bt-count").textContent   = data.trade_count + "회";
    
    // 1,000만원 투자 기준 예상 최종 금액 계산
    const finalAmount = Math.round(10_000_000 * (1 + profit / 100));
    const finalEl = document.getElementById("bt-final");
    finalEl.textContent = finalAmount.toLocaleString() + "원";
    finalEl.style.color = profit >= 0 ? "#2e7d32" : "#c62828";
}

/**
 * 분석 데이터를 바탕으로 메인 차트에 전략 지표와 매매 지점 렌더링
 */
function renderStrategyOnMain(data) {
    const type   = getCurrentChartType();
    const canvas = document.getElementById("mainEtfChart");
    if (!canvas) return;

    destroyMainChart(); // 기존 차트 제거

    const tsLabels = data.labels.map(d => new Date(d).getTime());

    // 매수 및 매도 데이터 포인트 매핑
    const buyPoints  = data.labels.map((d, i) => {
        const t = data.backtest.find(x => x.date === d && x.type === 'BUY');
        return { x: tsLabels[i], y: t ? t.price : NaN };
    });
    const sellPoints = data.labels.map((d, i) => {
        const t = data.backtest.find(x => x.date === d && (x.type === 'SELL' || x.type === 'SELL (End)'));
        return { x: tsLabels[i], y: t ? t.price : NaN };
    });

    const datasets = [];

    // 배경 차트 데이터 세트 설정 (캔들 또는 라인)
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
            _candleRaw: filtered, // 커스텀 플러그인에서 사용할 원본 데이터 저장
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

    // 선택된 전략에 따라 보조 지표(MA5, MA20, 최고가 등) 추가
    if (data.strategy === "golden_cross") {
        datasets.push({ type:"line", label:"MA5",  data: tsLabels.map((ts,i) => ({ x:ts, y: data.ma_short[i] != null ? data.ma_short[i] : NaN })), borderColor:"#f28e2b", borderWidth:1.5, borderDash:[4,3], fill:false, tension:0.15, pointRadius:0, spanGaps:true, parsing:false, order:3 });
        datasets.push({ type:"line", label:"MA20", data: tsLabels.map((ts,i) => ({ x:ts, y: data.ma_long[i]  != null ? data.ma_long[i]  : NaN })), borderColor:"#59a14f", borderWidth:1.5, borderDash:[4,3], fill:false, tension:0.15, pointRadius:0, spanGaps:true, parsing:false, order:4 });
    } else {
        datasets.push({ type:"line", label:"20일 최고가", data: tsLabels.map((ts,i) => ({ x:ts, y: data.high20[i] != null ? data.high20[i] : NaN })), borderColor:"#e15759", borderWidth:1.5, borderDash:[6,3], fill:false, tension:0,     pointRadius:0, spanGaps:true, parsing:false, order:3 });
        datasets.push({ type:"line", label:"MA20",         data: tsLabels.map((ts,i) => ({ x:ts, y: data.ma20[i]   != null ? data.ma20[i]   : NaN })), borderColor:"#59a14f", borderWidth:1.5, borderDash:[4,3], fill:false, tension:0.15, pointRadius:0, spanGaps:true, parsing:false, order:4 });
    }

    // 매수(B)/매도(S) 포인트 지점 데이터 세트 추가
    const buyRadii  = buyPoints.map(p  => isNaN(p.y) ? 0 : 10);
    const sellRadii = sellPoints.map(p => isNaN(p.y) ? 0 : 10);
    datasets.push({ type:"line", label:"매수(B)", data: buyPoints,  borderColor:"#e15759", backgroundColor:"#e15759", pointRadius:buyRadii,  pointHoverRadius:buyRadii,  showLine:false, order:1, parsing:false });
    datasets.push({ type:"line", label:"매도(S)", data: sellPoints, borderColor:"#4e79a7", backgroundColor:"#4e79a7", pointRadius:sellRadii, pointHoverRadius:sellRadii, showLine:false, order:1, parsing:false });

    // 캔들 모드: 실제 고가/저가 기준으로 y축 범위 계산 (꼬리 잘림 방지)
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

    // Chart.js 인스턴스 생성 및 설정
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
                }
            },
            scales: {
                x: { type: "time", time: { unit: "day" }, ticks: { maxTicksLimit: 8 } },
                y: yScaleOpts
            }
        },
        plugins: [
            // [플러그인 1] 캔들을 캔버스에 직접 그리는 로직
            {
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
            // [플러그인 2] 매수/매도 포인트 원형 안에 'B'/'S' 텍스트를 그림
            {
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

    if (typeof setActiveChartButtons === "function") setActiveChartButtons("mainEtfChart", type);

    // 전략 차트용 줌 엔진 바인딩
    if (typeof bindZoomEngine === "function") bindZoomEngine("mainEtfChart");

    // 버튼 이벤트 리스너 중복 방지 및 캔들/라인 전환 처리
    if (!canvas._strategyBtnBound) {
        canvas._strategyBtnBound = true;
        const candleBtn = document.getElementById("mainEtfChart-btn-candle");
        const lineBtn   = document.getElementById("mainEtfChart-btn-line");
        if (candleBtn) candleBtn.addEventListener("click", () => { if (_lastStrategyData) renderStrategyOnMain(_lastStrategyData); });
        if (lineBtn)   lineBtn.addEventListener("click",   () => { if (_lastStrategyData) renderStrategyOnMain(_lastStrategyData); });
    }
}

/**
 * [API 호출] 사용자가 선택한 전략 및 기간으로 백테스트 요청 및 결과 업데이트
 */
function updateStrategyChart() {
    const strategy = document.getElementById("strategySelect").value;
    const days     = document.getElementById("periodSelect").value;
    const btn      = document.getElementById("analyzeBtn");

    if (strategy === "none") {
        resetBacktestCard();
        return;
    }

    // 전략 설명 한 줄 표시
    const oneLiner = document.getElementById("strategyOneLinerText");
    if (oneLiner) { oneLiner.textContent = ONE_LINER[strategy] || ""; oneLiner.style.visibility = "visible"; }

    btn.textContent = "⏳ 분석 중...";
    btn.disabled    = true;

    // 전략 데이터를 가져오는 서버 통신
    fetch(`/api/strategy/${TICKER}?strategy=${strategy}&days=${days}`)
        .then(r => r.json())
        .then(data => {
            btn.textContent = "🔍 분석하기";
            btn.disabled    = false;
            if (!data.success) { alert("전략 계산 오류: " + data.message); return; }
            _lastStrategyData = data;
            renderStrategyOnMain(data); // 차트에 전략 렌더링
            updateBacktestCard(data);    // 통계 카드 갱신
        })
        .catch(err => {
            btn.textContent = "🔍 분석하기";
            btn.disabled    = false;
            alert("서버 오류: " + err);
        });
}

// 3. 채팅 전송 및 새로고침 함수

/**
 * 1. 채팅 전송 함수: 입력된 메시지를 비동기(POST)로 전송
 */
function sendChat() {
    const ticker = STOCK_CONFIG.ticker;
    const msgInput = document.getElementById('chat-input-msg');
    const message = msgInput.value.trim();

    if (!message) return;

    const formData = new FormData();
    formData.append('ticker', ticker);
    formData.append('message', message);

    // 백엔드의 /chat/create 경로로 비동기 전송
    fetch(STOCK_CONFIG.chatCreateUrl, {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === "success") {
            msgInput.value = ''; // 입력창 비우기
            refreshChatList(ticker); // 채팅 목록만 새로고침
        } else {
            alert(data.error || "전송 실패");
        }
    })
    .catch(err => console.error("전송 에러:", err));
}

/**
 * 2. 채팅 목록 새로고침 함수: 서버에서 전체 채팅 HTML을 받아 메시지 목록 영역만 교체
 */
function refreshChatList(ticker) {
    fetch(`/stocks/${ticker}/chat-box`)
        .then(res => res.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            // 새로 받아온 HTML에서 메시지 리스트(#chat-msg-list) 내용만 추출하여 교체
            const newContent = doc.getElementById('chat-msg-list').innerHTML;
            const chatList = document.getElementById('chat-msg-list');
            
            if (chatList) {
                chatList.innerHTML = newContent;
                setTimeout(scrollChatToBottom, 0); // 새 메시지 추가 후 하단 이동
            }
        })
        .catch(err => console.error("새로고침 에러:", err));
}