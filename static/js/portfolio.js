// [파일 역할] 포트폴리오 페이지의 동적 UI 제어 및 데이터 시각화 스크립트
// - Chart.js를 이용한 자산 비중 도넛 차트 생성
// - 보유 종목 상세 보기(아코디언) 및 매도/전략 변경 모달 제어
// - AJAX(fetch)를 이용한 거래 내역 비동기 로딩 및 페이지네이션 구현

document.addEventListener("DOMContentLoaded", function () {
    // 페이지 진입 시 데이터 로드 및 차트 초기화 수행
    const pageRoot = document.getElementById("portfolioPage");
    if (!pageRoot) return;

    // Chart.js 플러그인 등록 (차트 내 숫자/라벨 표시용)
    Chart.register(ChartDataLabels);

    // [데이터 파싱] HTML dataset에 저장된 서버 데이터를 JS 변수로 변환
    const labels = JSON.parse(pageRoot.dataset.pieLabels || "[]");
    const values = JSON.parse(pageRoot.dataset.pieValues || "[]");
    const cashBalance = parseFloat(pageRoot.dataset.cashBalance || "0");
    const initialPage = parseInt(pageRoot.dataset.page || "1", 10);
    const initialTotalPages = parseInt(pageRoot.dataset.totalPages || "1", 10);

    // 초기 페이지네이션 UI 렌더링
    if (initialTotalPages > 1) {
        renderPagination(initialPage, initialTotalPages);
    }

    // [차트 데이터 가공] 보유 종목 데이터 뒤에 '현금' 비중 추가
    const allLabels = labels.length > 0 ? [...labels, "현금"] : ["현금"];
    const allValues = labels.length > 0 ? [...values, cashBalance] : [cashBalance];
    const colors = ['#3b82f6','#f87171','#34d399','#fbbf24','#a78bfa','#93c5fd','#fca5a5'];
    const bgColors = allLabels.map((_, i) => colors[i % colors.length]);
    bgColors[bgColors.length - 1] = '#d1d5db'; // 마지막 '현금' 영역은 회색으로 고정

    // [도넛 차트 생성] 자산 구성비를 시각화
    const chartEl = document.getElementById("portfolioPieChart");
    if (chartEl) {
        new Chart(chartEl, {
            type: "doughnut",
            data: {
                labels: allLabels,
                datasets: [{
                    data: allValues,
                    backgroundColor: bgColors,
                    borderWidth: 2,
                    borderColor: "#fff"
                }]
            },
            options: {
                cutout: "55%", // 중앙 구멍 크기
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }, // 범례는 별도 커스텀 UI 사용 권장
                    datalabels: {
                        color: "#fff",
                        font: { weight: "bold", size: 11 },
                        formatter: (val, ctx) => {
                            // 전체 합계 대비 백분율(%) 계산 및 5% 이상인 경우만 라벨 표시
                            const sum = ctx.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                            const pct = (val * 100 / sum).toFixed(1);
                            if (pct < 5) return "";
                            return ctx.chart.data.labels[ctx.dataIndex] + "\n" + pct + "%";
                        }
                    }
                }
            }
        });
    }
});

// ── UI 상호작용: 아코디언 토글 ─────────────────────────────────────────────

function toggleGroup(gid, summaryRow) {
    // 특정 종목의 상세 전략별 보유 현황(tr)을 숨기거나 표시
    const rows = document.querySelectorAll(".detail-" + gid);
    const icon = summaryRow.querySelector(".toggle-icon");
    const isOpen = rows.length > 0 && rows[0].style.display !== "none";

    // 열려있으면 닫고, 닫혀있으면 여는 토글 로직
    rows.forEach(r => r.style.display = isOpen ? "none" : "table-row");

    // 상태에 따른 아이콘 및 배경색 변경
    if (icon) icon.textContent = isOpen ? "▶" : "▼";
    summaryRow.style.background = isOpen ? "" : "#eef2ff";
}

// ── 모달 관리 로직 ─────────────────────────────────────────────────

let currentHoldingId = null; // 현재 작업 중인 보유 종목 ID 저장
let currentMaxQty = 0;      // 매도 가능한 최대 수량 저장

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.style.display = "none";
}

// [매도 모달 오픈] 매도 수량 및 종목 정보 세팅
function openSellModal(holdingId, maxQty, stockName, strategy) {
    currentHoldingId = holdingId;
    currentMaxQty = maxQty;

    document.getElementById("sellModalTitle").innerText = `${stockName} 매도`;
    document.getElementById("sellModalDesc").innerText = `전략: ${strategy} | 최대 매도 가능: ${maxQty}주`;

    const q = document.getElementById("sellQtyInput");
    q.value = maxQty; // 기본값을 최대 수량으로 설정
    q.max = maxQty;

    document.getElementById("sellModal").style.display = "block";
}

// [전략 변경 모달 오픈] 현재 적용된 전략 확인 및 선택창 세팅
function openStrategyModal(holdingId, currentStrategy, stockName) {
    currentHoldingId = holdingId;

    document.getElementById("strategyModalTitle").innerText = `${stockName} 전략 변경`;
    document.getElementById("strategyModalDesc").innerText = `현재 적용된 전략: ${currentStrategy}`;

    const sel = document.getElementById("strategySelectModal");
    // 현재 전략이 옵션에 존재하면 선택, 없으면 '수동 운용' 기본값
    sel.value = Array.from(sel.options).some(o => o.value === currentStrategy)
        ? currentStrategy
        : "수동 운용";

    document.getElementById("strategyModal").style.display = "block";
}

// ── API 통신: 서버 요청 실행 ────────────────────────────────────────────

// [매도 실행] 입력된 수량 검증 후 서버에 매도 요청(POST)
function executeSell() {
    const sellQty = parseInt(document.getElementById("sellQtyInput").value, 10);

    if (isNaN(sellQty) || sellQty <= 0 || sellQty > currentMaxQty) {
        alert("올바른 수량을 입력해 주세요.");
        return;
    }

    fetch("/api/sell_stock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            holding_id: currentHoldingId,
            sell_qty: sellQty
        })
    })
    .then(r => r.json())
    .then(data => {
        alert(data.message);
        if (data.success) {
            location.reload(); // 성공 시 자산 현황 갱신을 위해 페이지 새로고침
        } else {
            closeModal("sellModal");
        }
    })
    .catch(err => {
        console.error(err);
        alert("매도 요청 중 오류가 발생했습니다.");
    });
}

// [전략 변경 실행] 선택된 새로운 전략을 서버에 업데이트 요청(POST)
function executeStrategyChange() {
    const newStrategy = document.getElementById("strategySelectModal").value;

    fetch("/api/change_strategy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            holding_id: currentHoldingId,
            strategy: newStrategy
        })
    })
    .then(r => r.json())
    .then(data => {
        alert(data.message);
        if (data.success) {
            location.reload();
        } else {
            closeModal("strategyModal");
        }
    })
    .catch(err => {
        console.error(err);
        alert("전략 변경 중 오류가 발생했습니다.");
    });
}

// ── 거래 내역 비동기 로딩 및 페이지네이션 ────────────────────────────────────────

// [거래 내역 로드] 특정 페이지의 거래 내역을 서버에서 가져와 테이블 갱신
function loadTrades(page) {
    const tbody = document.querySelector("#tradeTableBody");
    if (!tbody) return;

    // 로딩 중임을 시각적으로 표시 (투명도 조절)
    tbody.style.opacity = "0.5";

    fetch(`/api/trades?page=${page}`)
        .then(response => response.json())
        .then(data => {
            tbody.style.opacity = "1";
            if (!data.success) return;

            tbody.innerHTML = ""; // 기존 목록 초기화

            if (data.trades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="py-5 text-muted">거래 내역이 없습니다.</td></tr>';
            } else {
                // 새로운 거래 데이터로 테이블 행(row) 생성
                data.trades.forEach(trade => {
                    const badgeClass = trade.trade_type === "BUY" ? "bg-danger" : "bg-primary";
                    const typeText = trade.trade_type === "BUY" ? "매수" : "매도";
                    const formatNum = (num) => Number(num).toLocaleString();

                    // 매도 시 수익금/수익률 계산 결과 표시 (매수는 '-' 처리)
                    let profitCell = '<td class="text-end"><span class="text-muted">-</span></td>';
                    if (trade.profit_amount !== null && trade.profit_amount !== undefined) {
                        const color = trade.profit_amount > 0 ? "#f23645" : "#0062ff";
                        const sign = trade.profit_amount > 0 ? "+" : "";
                        const amount = formatNum(Math.round(trade.profit_amount));
                        const rate = Number(trade.profit_rate).toFixed(1);

                        profitCell = `
                            <td class="text-end">
                                <span style="color:${color}; font-weight:600; white-space:nowrap;">
                                    ${sign}${amount}원 (${sign}${rate}%)
                                </span>
                            </td>
                        `;
                    }

                    const row = `
                        <tr>
                            <td>${trade.traded_at}</td>
                            <td><span class="badge ${badgeClass}">${typeText}</span></td>
                            <td class="text-start fw-bold">
                                <a href="/stocks/${trade.ticker}" class="stock-link">${trade.name_kr}</a>
                                (${trade.quantity}주)
                            </td>
                            <td class="text-end">${formatNum(trade.price)}원</td>
                            <td class="text-end fw-bold">${formatNum(trade.total_amount)}원</td>
                            ${profitCell}
                        </tr>
                    `;
                    tbody.insertAdjacentHTML("beforeend", row);
                });
            }

            // 하단 페이지네이션 번호 갱신
            renderPagination(data.current_page, data.total_pages);
        })
        .catch(err => {
            console.error("데이터 로드 실패:", err);
            tbody.style.opacity = "1";
        });
}

// [페이지네이션 렌더링] 전체 페이지 수에 맞춰 하단 번호 UI 생성
function renderPagination(currentPage, totalPages) {
    const paginationUl = document.querySelector("#tradePagination");
    if (!paginationUl || totalPages <= 1) {
        if (paginationUl) paginationUl.innerHTML = "";
        return;
    }

    let html = "";

    // '이전' 버튼 생성
    const prevDisabled = currentPage === 1 ? "disabled" : "";
    html += `
        <li class="page-item ${prevDisabled}">
            <a class="page-link" href="javascript:void(0);" onclick="loadTrades(${currentPage - 1})" aria-label="Previous">
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
    `;

    // 한 번에 표시할 페이지 번호 범위 계산 (최대 5개)
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);

    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }

    // 숫자 페이지 번호 생성
    for (let p = startPage; p <= endPage; p++) {
        const activeClass = p === currentPage ? "active" : "";
        html += `
            <li class="page-item ${activeClass}" data-page="${p}">
                <a class="page-link" href="javascript:void(0);" onclick="loadTrades(${p})">${p}</a>
            </li>
        `;
    }

    // '다음' 버튼 생성
    const nextDisabled = currentPage === totalPages ? "disabled" : "";
    html += `
        <li class="page-item ${nextDisabled}">
            <a class="page-link" href="javascript:void(0);" onclick="loadTrades(${currentPage + 1})" aria-label="Next">
                <span aria-hidden="true">&raquo;</span>
            </a>
        </li>
    `;

    paginationUl.innerHTML = html;
}