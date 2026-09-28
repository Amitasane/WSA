document.addEventListener("DOMContentLoaded", function () {

    // Counter animation
    document.querySelectorAll(".counter").forEach(counter => {
        const target = Number(counter.dataset.target || 0);
        let current = 0;
        const duration = 700;
        const start = performance.now();

        function tick(now) {
            const progress = Math.min((now - start) / duration, 1);

            current = Math.floor(
                target * (1 - Math.pow(1 - progress, 3))
            );

            counter.textContent = current.toLocaleString();

            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        }

        requestAnimationFrame(tick);
    });

    // Get dashboard data
    if (!window.WSA_DASHBOARD || typeof Chart === "undefined") {
        return;
    }

    const data = window.WSA_DASHBOARD;


   // ================= MONTHLY RECORDS VS OK VS NOK =================

const trendCanvas = document.getElementById("dailyTrendChart");

if (trendCanvas) {
    new Chart(trendCanvas.getContext("2d"), {
        type: "bar",

        data: {
            labels: data.dailyLabels,

            datasets: [
                {
                    type: "bar",
                    label: "Records",
                    data: data.dailyRecords,
                    backgroundColor: "rgba(10, 31, 68, 0.75)",
                    borderColor: "#0A1F44",
                    borderWidth: 1,
                    borderRadius: 4
                },

                {
                    type: "line",
                    label: "OK",
                    data: data.dailyOk || [],
                    borderColor: "#17824B",
                    backgroundColor: "#17824B",
                    borderWidth: 3,
                    tension: 0.3,
                    pointRadius: 3,
                    pointHoverRadius: 6,
                    fill: false
                },

                {
                    type: "line",
                    label: "NOK",
                    data: data.dailyNok,
                    borderColor: "#DC3545",
                    backgroundColor: "#DC3545",
                    borderWidth: 3,
                    tension: 0.3,
                    pointRadius: 3,
                    pointHoverRadius: 6,
                    fill: false
                }
            ]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false,

            interaction: {
                mode: "index",
                intersect: false
            },

            plugins: {
                legend: {
                    position: "top"
                },

                tooltip: {
                    mode: "index",
                    intersect: false
                }
            },

            scales: {
                y: {
                    beginAtZero: true,

                    ticks: {
                        precision: 0
                    },

                    title: {
                        display: true,
                        text: "Number of Records"
                    }
                },

                x: {
                    grid: {
                        display: false
                    },

                    ticks: {
                        display: false
                    },

                    title: {
                        display: false
                    }
                }
            }
        }
    });
}


    // ================= SHIFT-WISE NOK =================

    const shiftCanvas = document.getElementById("shiftChart");

    if (shiftCanvas) {
        new Chart(shiftCanvas.getContext("2d"), {
            type: "doughnut",

            data: {
                labels: data.shiftLabels,

                datasets: [
                    {
                        data: data.shiftNok,
                        backgroundColor: [
                            "#0A1F44",
                            "#2F80ED",
                            "#6C63FF",
                            "#6B7280"
                        ],
                        borderWidth: 0
                    }
                ]
            },

            options: {
                responsive: true,
                maintainAspectRatio: false,

                cutout: "65%",

                plugins: {
                    legend: {
                        position: "bottom"
                    }
                }
            }
        });
    }


    // ================= STATION-WISE NOK =================

    const stationCanvas = document.getElementById("stationChart");

    if (stationCanvas) {
        new Chart(stationCanvas.getContext("2d"), {
            type: "bar",

            data: {
                labels: data.stationLabels,

                datasets: [
                    {
                        label: "NOK Records",
                        data: data.stationNok,
                        backgroundColor: "rgba(0,82,212,0.78)",
                        borderRadius: 8
                    }
                ]
            },

            options: {
                responsive: true,
                maintainAspectRatio: false,

                plugins: {
                    legend: {
                        display: false
                    }
                },

                scales: {
                    y: {
                        beginAtZero: true,

                        ticks: {
                            precision: 0
                        }
                    },

                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }

});