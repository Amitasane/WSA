document.addEventListener("DOMContentLoaded", function () {

    // Number counter animation
    document.querySelectorAll(".counter").forEach(counter => {
        const target = Number(counter.dataset.target || 0);
        let current = 0;
        const duration = 600;
        const start = performance.now();

        function tick(now) {
            const progress = Math.min((now - start) / duration, 1);
            current = Math.floor(target * (1 - Math.pow(1 - progress, 3)));
            counter.textContent = current.toLocaleString();

            if (progress < 1) {
                requestAnimationFrame(tick);
            } else {
                counter.textContent = target.toLocaleString();
            }
        }

        requestAnimationFrame(tick);
    });

    if (!window.INVESTIGATION_DASHBOARD || typeof Chart === "undefined") {
        return;
    }

    const d = window.INVESTIGATION_DASHBOARD;

    // ================= 1. MONTHLY INVESTIGATION TREND =================
    const trendEl = document.getElementById("trendChart");
    if (trendEl) {
        new Chart(trendEl.getContext("2d"), {
            type: "bar",
            data: {
                labels: d.trendLabels,
                datasets: [
                    {
                        type: "bar",
                        label: "Total Investigations",
                        data: d.trendTotal,
                        backgroundColor: "rgba(10, 31, 68, 0.75)",
                        borderColor: "#0A1F44",
                        borderWidth: 1,
                        borderRadius: 4
                    },
                    {
                        type: "line",
                        label: "Defect Identified",
                        data: d.trendDefect,
                        borderColor: "#C93446",
                        backgroundColor: "#C93446",
                        borderWidth: 2.5,
                        tension: 0.25,
                        pointRadius: 4,
                        fill: false
                    },
                    {
                        type: "line",
                        label: "Conforming (OK)",
                        data: d.trendConforming,
                        borderColor: "#17824B",
                        backgroundColor: "#17824B",
                        borderWidth: 2.5,
                        tension: 0.25,
                        pointRadius: 4,
                        fill: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { position: "top", labels: { boxWidth: 12, font: { family: "Poppins", size: 11 } } },
                    tooltip: { mode: "index", intersect: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { precision: 0, font: { family: "Poppins", size: 11 } },
                        title: { display: true, text: "Number of Investigations", font: { size: 11 } }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { font: { family: "Poppins", size: 11 } }
                    }
                }
            }
        });
    }

    // ================= 2. DEFECT PARETO CHART =================
    const paretoEl = document.getElementById("paretoChart");
    if (paretoEl && d.paretoLabels && d.paretoLabels.length > 0) {
        new Chart(paretoEl.getContext("2d"), {
            data: {
                labels: d.paretoLabels,
                datasets: [
                    {
                        type: "line",
                        label: "Cumulative %",
                        data: d.paretoCumulative,
                        borderColor: "#C93446",
                        backgroundColor: "rgba(201, 52, 70, 0.1)",
                        borderWidth: 2,
                        pointRadius: 4,
                        yAxisID: "yPct",
                        tension: 0.2
                    },
                    {
                        type: "bar",
                        label: "Frequency",
                        data: d.paretoCounts,
                        backgroundColor: "rgba(0, 82, 212, 0.8)",
                        borderColor: "#0052D4",
                        borderWidth: 1,
                        borderRadius: 4,
                        yAxisID: "yCount"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top", labels: { boxWidth: 12, font: { family: "Poppins", size: 11 } } },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                if (ctx.datasetIndex === 0) {
                                    return `Cumulative: ${ctx.parsed.y}%`;
                                }
                                return `Defects: ${ctx.parsed.y}`;
                            }
                        }
                    }
                },
                scales: {
                    yCount: {
                        type: "linear",
                        position: "left",
                        beginAtZero: true,
                        title: { display: true, text: "Failure Count", font: { size: 11 } },
                        ticks: { precision: 0 }
                    },
                    yPct: {
                        type: "linear",
                        position: "right",
                        min: 0,
                        max: 100,
                        grid: { drawOnChartArea: false },
                        title: { display: true, text: "Cumulative %", font: { size: 11 } },
                        ticks: {
                            callback: function(val) { return val + "%"; }
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: {
                            font: { family: "Poppins", size: 10 },
                            maxRotation: 40,
                            minRotation: 20
                        }
                    }
                }
            }
        });
    }

    // ================= 3. CUSTOMER DISTRIBUTION =================
    const custEl = document.getElementById("customerChart");
    if (custEl && d.customerLabels) {
        new Chart(custEl.getContext("2d"), {
            type: "bar",
            data: {
                labels: d.customerLabels,
                datasets: [
                    {
                        label: "Total Cases",
                        data: d.customerTotal,
                        backgroundColor: "rgba(10, 31, 68, 0.75)",
                        borderRadius: 4
                    },
                    {
                        label: "Defects",
                        data: d.customerDefect,
                        backgroundColor: "rgba(201, 52, 70, 0.8)",
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: "top", labels: { boxWidth: 12, font: { family: "Poppins", size: 11 } } }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { precision: 0 }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { font: { family: "Poppins", size: 11 } }
                    }
                }
            }
        });
    }

    // ================= 4. PRODUCT LINE SHARE DOUGHNUT =================
    const prodEl = document.getElementById("productShareChart");
    if (prodEl && d.productShareLabels) {
        new Chart(prodEl.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: d.productShareLabels,
                datasets: [
                    {
                        data: d.productShareCases,
                        backgroundColor: ["#0A1F44", "#0052D4"],
                        borderWidth: 2,
                        borderColor: "#ffffff"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                plugins: {
                    legend: { position: "bottom", labels: { boxWidth: 12, font: { family: "Poppins", size: 11 } } },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const val = ctx.parsed;
                                const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                                return ` ${ctx.label}: ${val} cases (${pct}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

});