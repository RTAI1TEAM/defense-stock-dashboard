window.chartInstances = window.chartInstances || {};
window.chartRawData = window.chartRawData || {};

function getLineSeriesFromCandle(rawData) {
    return rawData.map(item => ({
        x: item.x,
        y: item.c
    }));
}

function setActiveChartButtons(canvasId, type) {
    const candleBtn = document.getElementById(`${canvasId}-btn-candle`);
    const lineBtn = document.getElementById(`${canvasId}-btn-line`);

    if (!candleBtn || !lineBtn) return;

    if (type === "candle") {
        candleBtn.classList.remove("btn-outline-primary");
        candleBtn.classList.add("btn-primary");

        lineBtn.classList.remove("btn-primary");
        lineBtn.classList.add("btn-outline-primary");
    } else {
        lineBtn.classList.remove("btn-outline-primary");
        lineBtn.classList.add("btn-primary");

        candleBtn.classList.remove("btn-primary");
        candleBtn.classList.add("btn-outline-primary");
    }
}

window.renderLineChart = function ({
    canvasId,
    rawData,
    datasetLabel = "종가"
}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    if (window.chartInstances[canvasId]) {
        window.chartInstances[canvasId].destroy();
    }

    const lineData = getLineSeriesFromCandle(rawData);

    window.chartInstances[canvasId] = new Chart(ctx, {
        type: "line",
        data: {
            datasets: [{
                label: datasetLabel,
                data: lineData,
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
            interaction: {
                mode: "index",
                intersect: false
            },
            plugins: {
                legend: {
                    display: true
                }
            },
                tooltip: {
                    enabled: true,
                    callbacks: {
                        title: function (tooltipItems) {
                            const item = tooltipItems[0];
                            if (!item) return "";

                            const date = new Date(item.raw.x);
                            return date.toLocaleDateString("ko-KR");
                        },
                        label: function (context) {
                            const value = context.raw.y;
                            return `${datasetLabel}: ${value.toLocaleString()}원`;
                        }
                    }
                },
            scales: {
                x: {
                    type: "time",
                    time: {
                        unit: "day"
                    },
                    ticks: {
                        maxTicksLimit: 8
                    }
                },
                y: {
                    beginAtZero: false
                }
            }
        }
    });

    setActiveChartButtons(canvasId, "line");
};

window.renderCandleChart = function ({
    canvasId,
    rawData,
    datasetLabel = "주가"
}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    if (window.chartInstances[canvasId]) {
        window.chartInstances[canvasId].destroy();
    }

    window.chartInstances[canvasId] = new Chart(ctx, {
        type: "candlestick",
        data: {
            datasets: [{
                label: datasetLabel,
                data: rawData
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            parsing: false,
            plugins: {
                legend: {
                    display: true
                }
            },
            scales: {
                x: {
                    type: "time",
                    time: {
                        unit: "day"
                    },
                    ticks: {
                        maxTicksLimit: 8
                    }
                },
                y: {
                    beginAtZero: false
                }
            }
        }
    });

    setActiveChartButtons(canvasId, "candle");
};

window.switchChart = function (canvasId, type) {
    const chartInfo = window.chartRawData[canvasId];
    if (!chartInfo) return;

    if (type === "line") {
        window.renderLineChart({
            canvasId: canvasId,
            rawData: chartInfo.raw,
            datasetLabel: chartInfo.lineLabel
        });
    } else {
        window.renderCandleChart({
            canvasId: canvasId,
            rawData: chartInfo.raw,
            datasetLabel: chartInfo.candleLabel
        });
    }
};