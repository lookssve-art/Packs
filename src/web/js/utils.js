/* Formatting helpers */

function formatTimeAgo(isoString) {
    if (!isoString) return '---';
    const now = new Date();
    const then = new Date(isoString);
    const seconds = Math.floor((now - then) / 1000);
    if (seconds < 0) return 'just now';
    if (seconds < 60) return seconds + 's ago';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
    return Math.floor(seconds / 86400) + 'd ago';
}

function formatCurrency(value) {
    if (value === null || value === undefined) return '---';
    return '$' + Number(value).toFixed(2);
}

function formatPct(value) {
    if (value === null || value === undefined) return '---';
    return (value * 100).toFixed(2) + '%';
}

function capitalize(s) {
    if (!s) return '';
    return s.charAt(0).toUpperCase() + s.slice(1);
}
