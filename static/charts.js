'use strict';

const netmonCharts = [];

const palette = () => {
  const css = getComputedStyle(document.documentElement);
  return {
    text: css.getPropertyValue('--muted').trim(),
    grid: css.getPropertyValue('--chart-grid').trim(),
    blue: css.getPropertyValue('--plot-blue').trim(),
    green: css.getPropertyValue('--plot-teal').trim(),
    violet: css.getPropertyValue('--plot-violet').trim(),
    panel: css.getPropertyValue('--panel').trim(),
    title: css.getPropertyValue('--text').trim(),
    border: css.getPropertyValue('--line').trim(),
  };
};

const plotNumber = value => Number(value).toLocaleString('id-ID', { maximumFractionDigits: 1 });
const plotDate = value => new Intl.DateTimeFormat('id-ID', {
  day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
}).format(new Date(value));

function plotColors(type) {
  const colors = palette();
  return type === 'wan' ? [colors.green, colors.violet] : [colors.blue, colors.green];
}

function areaGradient(context) {
  const { chart, dataset } = context;
  const area = chart.chartArea;
  if (!area) return dataset.borderColor + '18';
  const gradient = chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
  gradient.addColorStop(0, dataset.borderColor + '55');
  gradient.addColorStop(.6, dataset.borderColor + '20');
  gradient.addColorStop(1, dataset.borderColor + '03');
  return gradient;
}

const chartGuide = {
  id: 'netmonGuide',
  afterDatasetsDraw(chart) {
    const active = chart.tooltip?.getActiveElements();
    if (!active?.length) return;
    const x = active[0].element.x;
    const { top, bottom } = chart.chartArea;
    const context = chart.ctx;
    context.save();
    context.beginPath();
    context.setLineDash([4, 5]);
    context.strokeStyle = palette().text + '70';
    context.lineWidth = 1;
    context.moveTo(x, top);
    context.lineTo(x, bottom);
    context.stroke();
    context.restore();
  },
};

const trafficLimitGuide = {
  id: 'netmonTrafficLimit',
  afterDatasetsDraw(chart) {
    const limit = Number(chart.options.plugins.netmonTrafficLimit?.value);
    if (!Number.isFinite(limit) || limit <= 0) return;
    const yScale = chart.scales.y;
    const y = yScale.getPixelForValue(limit);
    const { left, right, top, bottom } = chart.chartArea;
    if (y < top || y > bottom) return;

    const context = chart.ctx;
    context.save();
    context.beginPath();
    context.setLineDash([7, 5]);
    context.strokeStyle = '#e45b68';
    context.lineWidth = 2;
    context.moveTo(left, y);
    context.lineTo(right, y);
    context.stroke();
    context.setLineDash([]);
    context.font = '600 11px "Segoe UI", Arial, sans-serif';
    context.textAlign = 'right';
    context.textBaseline = y - top < 18 ? 'top' : 'bottom';
    context.fillStyle = '#e45b68';
    context.fillText(`Batas ${plotNumber(limit)} Mbps`, right - 5, y + (y - top < 18 ? 4 : -4));
    context.restore();
  },
};

function makeChart(canvas, points, type, compact, chartConfig = {}) {
  const colors = palette();
  const wan = type === 'wan';
  const seriesColors = plotColors(type);
  const unit = wan ? 'Mbps' : '%';
  const fields = wan
    ? [['Input', 'input_mbps'], ['Output', 'output_mbps']]
    : [['CPU', 'cpu_max'], ['Memory', 'mem_pct']];
  const times = points.map(point => new Date(point.timestamp).getTime());
  const validTimes = times.filter(Number.isFinite);
  const first = validTimes[0];
  const last = validTimes.at(-1);
  const sameDay = validTimes.length > 0 && new Date(first).toDateString() === new Date(last).toDateString();
  const peak = points.reduce((maximum, point) => Math.max(maximum, ...fields.map(([, key]) => (
    Number.isFinite(point[key]) ? point[key] : 0
  ))), 0);
  const requestedLimit = Number(chartConfig.wanLimit);
  const wanLimit = wan && Number.isFinite(requestedLimit) && requestedLimit > 0 ? requestedLimit : null;
  const ymax = wan
    ? (wanLimit ? Math.max(wanLimit * 1.1, Math.ceil(peak * 1.12 / 10) * 10) : undefined)
    : Math.max(20, Math.ceil(peak * 1.12 / 10) * 10);

  const chart = new Chart(canvas, {
    type: 'line',
    plugins: [chartGuide, trafficLimitGuide],
    data: {
      datasets: fields.map(([label, key], index) => ({
        label,
        data: points.map((point, pointIndex) => ({ x: times[pointIndex], y: point[key] }))
          .filter(point => Number.isFinite(point.x)),
        borderColor: seriesColors[index],
        backgroundColor: areaGradient,
        pointBackgroundColor: seriesColors[index],
        pointBorderColor: colors.panel,
        pointBorderWidth: 2,
        borderWidth: 2.5,
        pointRadius: points.length < 3 ? 3 : 0,
        pointHoverRadius: 5,
        pointHitRadius: 14,
        // Improve line continuity for display only; source samples remain unchanged.
        tension: .35,
        cubicInterpolationMode: 'default',
        borderCapStyle: 'round',
        borderJoinStyle: 'round',
        fill: 'origin',
        spanGaps: false,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      normalized: false,
      interaction: { mode: 'index', intersect: false },
      layout: { padding: { top: 10, right: 6, bottom: 0 } },
      plugins: {
        netmonTrafficLimit: { value: wanLimit },
        legend: {
          display: !compact,
          position: 'top',
          align: 'end',
          labels: {
            color: colors.text,
            usePointStyle: true,
            pointStyle: 'circle',
            boxWidth: 7,
            boxHeight: 7,
            padding: 22,
            font: { family: '"Segoe UI", Arial, sans-serif', size: 13, weight: 500 },
          },
        },
        tooltip: {
          backgroundColor: colors.panel,
          titleColor: colors.title,
          bodyColor: colors.text,
          borderColor: colors.border,
          borderWidth: 1,
          cornerRadius: 12,
          padding: 14,
          titleMarginBottom: 10,
          bodySpacing: 7,
          displayColors: true,
          usePointStyle: true,
          boxWidth: 8,
          boxHeight: 8,
          caretSize: 5,
          titleFont: { family: '"Segoe UI", Arial, sans-serif', size: 13, weight: 600 },
          bodyFont: { family: '"Segoe UI", Arial, sans-serif', size: 13 },
          callbacks: {
            title: items => items.length ? plotDate(items[0].parsed.x) : '',
            label: context => ` ${context.dataset.label}   ${plotNumber(context.parsed.y)} ${unit}`,
          },
        },
      },
      scales: {
        x: {
          type: 'linear',
          min: validTimes.length ? first - (first === last ? 60000 : 0) : undefined,
          max: validTimes.length ? last + (first === last ? 60000 : 0) : undefined,
          grid: { display: false },
          border: { display: false },
          ticks: {
            color: colors.text,
            maxTicksLimit: compact ? 3 : 6,
            maxRotation: 0,
            font: { family: '"Segoe UI", Arial, sans-serif', size: 12 },
            padding: 10,
            callback: value => new Intl.DateTimeFormat('id-ID', sameDay
              ? { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }
              : { day: '2-digit', month: 'short' }).format(new Date(value)),
          },
        },
        y: {
          beginAtZero: true,
          suggestedMax: ymax,
          border: { display: false, dash: [3, 5] },
          grid: { color: colors.grid, drawTicks: false },
          ticks: {
            color: colors.text,
            maxTicksLimit: compact ? 3 : 5,
            padding: 10,
            font: { family: '"Segoe UI", Arial, sans-serif', size: 12 },
            callback: value => plotNumber(value) + (wan ? '' : '%'),
          },
        },
      },
    },
  });
  chart.netmonType = type;
  netmonCharts.push(chart);
  return chart;
}

async function fetchHistory(label, days) {
  const response = await fetch('/api/history/' + encodeURIComponent(label) + '?days=' + days);
  if (response.status === 401) {
    window.location.href = '/login';
    throw new Error('Sesi berakhir. Silakan login kembali.');
  }
  if (!response.ok) throw new Error('Grafik gagal dimuat. Muat ulang halaman untuk mencoba kembali.');
  return response.json();
}

function dataMessage(points, type) {
  if (!points.length) return 'Belum ada data pada rentang waktu ini.';
  const keys = type === 'wan' ? ['input_mbps', 'output_mbps'] : ['cpu_max', 'mem_pct'];
  if (!points.some(point => keys.some(key => Number.isFinite(point[key])))) return 'Data penggunaan belum berhasil terbaca.';
  return '';
}

for (const canvas of document.querySelectorAll('.wan-chart')) {
  const message = canvas.closest('.wan-card').querySelector('.chart-message');
  fetchHistory(canvas.dataset.label, 7)
    .then(points => {
      makeChart(canvas, points, 'wan', true);
      message.textContent = dataMessage(points, 'wan');
    })
    .catch(error => { message.textContent = error.message; });
}

window.addEventListener('netmon-theme-change', () => {
  const colors = palette();
  for (const chart of netmonCharts) {
    const seriesColors = plotColors(chart.netmonType);
    chart.data.datasets.forEach((dataset, index) => {
      dataset.borderColor = seriesColors[index];
      dataset.pointBackgroundColor = seriesColors[index];
      dataset.pointBorderColor = colors.panel;
    });
    for (const axis of ['x', 'y']) chart.options.scales[axis].ticks.color = colors.text;
    chart.options.scales.y.grid.color = colors.grid;
    chart.options.plugins.legend.labels.color = colors.text;
    Object.assign(chart.options.plugins.tooltip, {
      backgroundColor: colors.panel,
      titleColor: colors.title,
      bodyColor: colors.text,
      borderColor: colors.border,
    });
    chart.update('none');
  }
});
