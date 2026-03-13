document.addEventListener("DOMContentLoaded", function () {
    const pageRoot = document.getElementById("portfolioPage");
    if (!pageRoot) return;

    Chart.register(ChartDataLabels);

    const labels = JSON.parse(pageRoot.dataset.pieLabels || "[]");
    const values = JSON.parse(pageRoot.dataset.pieValues || "[]");
    const cashBalance = parseFloat(pageRoot.dataset.cashBalance || "0");
    const initialPage = parseInt(pageRoot.dataset.page || "1", 10);
    const initialTotalPages = parseInt(pageRoot.dataset.totalPages || "1", 10);

    if (initialTotalPages > 1) {
        renderPagination(initialPage, initialTotalPages);
    }

    const allLabels = labels.length > 0 ? [...labels, "현금"] : ["현금"];
    const allValues = labels.length > 0 ? [...values, cashBalance] : [cashBalance];
    const colors = ['#3b82f6','#f87171','#34d399','#fbbf24','#a78bfa','#93c5fd','#fca5a5'];
    const bgColors = allLabels.map((_, i) => colors[i % colors.length]);
    bgColors[bgColors.length - 1] = '#d1d5db';

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
                cutout: "55%",
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    datalabels: {
                        color: "#fff",
                        font: { weight: "bold", size: 11 },
                        formatter: (val, ctx) => {
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

// ── 아코디언 토글 ─────────────────────────────────────────────
function toggleGroup(gid, summaryRow) {
    const rows = document.querySelectorAll(".detail-" + gid);
    const icon = summaryRow.querySelector(".toggle-icon");
    const isOpen = rows.length > 0 && rows[0].style.display !== "none";

    rows.forEach(r => r.style.display = isOpen ? "none" : "table-row");

    if (icon) icon.textContent = isOpen ? "▶" : "▼";
    summaryRow.style.background = isOpen ? "" : "#eef2ff";
}

// ── 모달 공통 ─────────────────────────────────────────────────
let currentHoldingId = null;
let currentMaxQty = 0;

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.style.display = "none";
}

// ── 매도 모달 ─────────────────────────────────────────────────
function openSellModal(holdingId, maxQty, stockName, strategy) {
    currentHoldingId = holdingId;
    currentMaxQty = maxQty;

    document.getElementById("sellModalTitle").innerText = `${stockName} 매도`;
    document.getElementById("sellModalDesc").innerText = `전략: ${strategy} | 최대 매도 가능: ${maxQty}주`;

    const q = document.getElementById("sellQtyInput");
    q.value = maxQty;
    q.max = maxQty;

    document.getElementById("sellModal").style.display = "block";
}

// ── 전략 변경 모달 ────────────────────────────────────────────
function openStrategyModal(holdingId, currentStrategy, stockName) {
    currentHoldingId = holdingId;

    document.getElementById("strategyModalTitle").innerText = `${stockName} 전략 변경`;
    document.getElementById("strategyModalDesc").innerText = `현재 적용된 전략: ${currentStrategy}`;

    const sel = document.getElementById("strategySelectModal");
    sel.value = Array.from(sel.options).some(o => o.value === currentStrategy)
        ? currentStrategy
        : "수동 운용";

    document.getElementById("strategyModal").style.display = "block";
}

// ── 매도 실행 ─────────────────────────────────────────────────
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
            location.reload();
        } else {
            closeModal("sellModal");
        }
    })
    .catch(err => {
        console.error(err);
        alert("매도 요청 중 오류가 발생했습니다.");
    });
}

// ── 전략 변경 실행 ────────────────────────────────────────────
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

function loadTrades(page) {
    const tbody = document.querySelector("#tradeTableBody");
    if (!tbody) return;

    tbody.style.opacity = "0.5";

    fetch(`/api/trades?page=${page}`)
        .then(response => response.json())
        .then(data => {
            tbody.style.opacity = "1";

            if (!data.success) return;

            tbody.innerHTML = "";

            if (data.trades.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="py-5 text-muted">거래 내역이 없습니다.</td></tr>';
            } else {
                data.trades.forEach(trade => {
                    const badgeClass = trade.trade_type === "BUY" ? "bg-danger" : "bg-primary";
                    const typeText = trade.trade_type === "BUY" ? "매수" : "매도";
                    const formatNum = (num) => Number(num).toLocaleString();

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

            renderPagination(data.current_page, data.total_pages);
        })
        .catch(err => {
            console.error("데이터 로드 실패:", err);
            tbody.style.opacity = "1";
        });
}

function renderPagination(currentPage, totalPages) {
    const paginationUl = document.querySelector("#tradePagination");
    if (!paginationUl || totalPages <= 1) {
        if (paginationUl) paginationUl.innerHTML = "";
        return;
    }

    let html = "";

    const prevDisabled = currentPage === 1 ? "disabled" : "";
    html += `
        <li class="page-item ${prevDisabled}">
            <a class="page-link" href="javascript:void(0);" onclick="loadTrades(${currentPage - 1})" aria-label="Previous">
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
    `;

    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);

    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }

    for (let p = startPage; p <= endPage; p++) {
        const activeClass = p === currentPage ? "active" : "";
        html += `
            <li class="page-item ${activeClass}" data-page="${p}">
                <a class="page-link" href="javascript:void(0);" onclick="loadTrades(${p})">${p}</a>
            </li>
        `;
    }

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