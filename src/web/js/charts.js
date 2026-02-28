/* Chart.js configurations for dark theme */

Chart.defaults.color = '#a6adc8';
Chart.defaults.borderColor = '#313244';
Chart.defaults.font.family = 'ui-monospace, monospace';

var CAT = {
    blue: '#89b4fa', green: '#a6e3a1', yellow: '#f9e2af',
    red: '#f38ba8', mauve: '#cba6f7', peach: '#fab387',
    overlay: '#6c7086', surface: '#313244', text: '#cdd6f4',
};

var _charts = {};

function buildOddsChart(canvasId, evData, snapshots) {
    var ctx = document.getElementById(canvasId);
    if (!ctx || !evData || !evData.length) return;

    var ev = evData[0];
    var rarities = ['holographic', 'gold', 'silver', 'gloss'];
    var labels = rarities.map(function(r) { return capitalize(r); });

    var observed = rarities.map(function(r) {
        var p = ev.rarity_posteriors[r];
        return p ? p[0] * 100 : 0;
    });

    var datasets = [];

    // Published rates from snapshots
    var packSnaps = snapshots && snapshots[ev.pack_type];
    if (packSnaps && packSnaps.length > 0) {
        var published = rarities.map(function(r) {
            return (packSnaps[0].rates[r] || 0) * 100;
        });
        datasets.push({
            label: 'Published', data: published,
            backgroundColor: CAT.blue + '99', borderColor: CAT.blue, borderWidth: 1,
        });
    }

    datasets.push({
        label: 'Observed (posterior)', data: observed,
        backgroundColor: CAT.green + '99', borderColor: CAT.green, borderWidth: 1,
    });

    if (_charts[canvasId]) _charts[canvasId].destroy();
    _charts[canvasId] = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Probability (%)' },
                     grid: { color: CAT.surface } },
                x: { grid: { display: false } },
            },
        },
    });
}

function buildEvTrendChart(canvasId, evHistory) {
    var ctx = document.getElementById(canvasId);
    if (!ctx || !evHistory || !Object.keys(evHistory).length) return;

    var colors = [CAT.blue, CAT.green, CAT.yellow, CAT.red, CAT.mauve];
    var datasets = [];
    var i = 0;

    for (var packType in evHistory) {
        var points = evHistory[packType];
        if (!points || !points.length) continue;
        var sorted = points.slice().sort(function(a, b) {
            return a.timestamp.localeCompare(b.timestamp);
        });
        datasets.push({
            label: capitalize(packType) + ' EV Ratio',
            data: sorted.map(function(p) { return { x: p.timestamp, y: p.ev_ratio }; }),
            borderColor: colors[i % colors.length],
            backgroundColor: 'transparent',
            tension: 0.3, pointRadius: 2, borderWidth: 2,
        });
        i++;
    }

    if (_charts[canvasId]) _charts[canvasId].destroy();
    _charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: { datasets: datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'top' } },
            scales: {
                x: { type: 'time', time: { unit: 'hour' }, grid: { color: CAT.surface } },
                y: { title: { display: true, text: 'EV Ratio' }, grid: { color: CAT.surface } },
            },
        },
    });
}

function buildOddsShiftChart(canvasId, snapshots) {
    var ctx = document.getElementById(canvasId);
    if (!ctx || !snapshots || snapshots.length < 2) return;

    var rarityColors = {
        holographic: CAT.red, gold: CAT.yellow,
        silver: '#a6adc8', gloss: '#585b70',
    };
    var sorted = snapshots.slice().sort(function(a, b) {
        return a.timestamp.localeCompare(b.timestamp);
    });
    var rarities = ['holographic', 'gold', 'silver', 'gloss'];
    var datasets = rarities.map(function(r) {
        return {
            label: capitalize(r),
            data: sorted.map(function(s) { return { x: s.timestamp, y: (s.rates[r] || 0) * 100 }; }),
            borderColor: rarityColors[r], backgroundColor: 'transparent',
            tension: 0.2, pointRadius: 4, borderWidth: 2,
        };
    });

    if (_charts[canvasId]) _charts[canvasId].destroy();
    _charts[canvasId] = new Chart(ctx, {
        type: 'line',
        data: { datasets: datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                x: { type: 'time', time: { unit: 'hour' }, grid: { color: CAT.surface } },
                y: { title: { display: true, text: 'Drop Rate (%)' }, grid: { color: CAT.surface } },
            },
        },
    });
}
