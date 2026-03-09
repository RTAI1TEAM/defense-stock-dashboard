window.chartInstances = window.chartInstances || {};

window.renderLineChart = function ({
    canvasId,
    labels,
    values,
    datasetLabel = "종가"
}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext("2d");

    if (window.chartInstances[canvasId]) {
        window.chartInstances[canvasId].destroy();
    }

    window.chartInstances[canvasId] = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: datasetLabel,
                data: values,
                borderWidth: 2,
                fill: false,
                tension: 0.15
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true
                }
            },
            scales: {
                x: {
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
};