(async function () {
  const canvas = document.getElementById("progressChart");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");

  // show a simple loading state on canvas
  function drawMessage(msg) {
    const w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.font = "14px sans-serif";
    ctx.fillStyle = "#6c757d";
    ctx.textAlign = "center";
    ctx.fillText(msg, w / 2, h / 2);
    ctx.restore();
  }

  drawMessage("Loading chart...");

  let data;
  try {
    const res = await fetch("/api/progress/chart");
    if (!res.ok) throw new Error("API error");
    data = await res.json();
  } catch (e) {
    drawMessage("Could not load chart.");
    return;
  }

  if (!data || !data.labels || data.labels.length === 0) {
    drawMessage("No chart data yet.");
    return;
  }

  new Chart(ctx, {
    type: "line",
    data: {
      labels: data.labels,
      datasets: [
        {
          label: "Distance (m)",
          data: data.distances,
          tension: 0.25,
          borderWidth: 2,
          pointRadius: 3,
          yAxisID: "yDist",
        },
        {
          label: "Time (sec)",
          data: data.times_sec,
          tension: 0.25,
          borderWidth: 2,
          pointRadius: 3,
          yAxisID: "yTime",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "top" },
        tooltip: {
          callbacks: {
            label: function (ctx) {
              const label = ctx.dataset.label || "";
              const v = ctx.parsed.y;
              if (label.includes("Distance")) return `${label}: ${Math.round(v)} m`;
              if (label.includes("Time")) return `${label}: ${v.toFixed(2)} sec`;
              return `${label}: ${v}`;
            },
          },
        },
      },
      scales: {
        yDist: {
          type: "linear",
          position: "left",
          beginAtZero: true,
          title: { display: true, text: "Distance (m)" },
        },
        yTime: {
          type: "linear",
          position: "right",
          beginAtZero: true,
          grid: { drawOnChartArea: false },
          title: { display: true, text: "Time (sec)" },
        },
        x: {
          ticks: { maxRotation: 0 },
        },
      },
    },
  });
})();