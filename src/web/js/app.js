/* Alpine.js main application */

function app() {
    return {
        // State
        tab: 'overview',
        status: { collector_running: false, cycle_count: 0, total_pulls: 0, last_cycle: null, pull_counts: {} },
        evData: [],
        pulls: [],
        rankings: {},
        snapshots: {},
        activeAlerts: [],
        alertHistory: [],
        packs: [],
        evHistory: {},

        // Computed
        get topPack() {
            if (!this.evData.length) return null;
            var sorted = this.evData.slice().sort(function(a, b) {
                return b.conservative_score - a.conservative_score;
            });
            return sorted[0];
        },
        get buyUrl() { return 'https://magiceden.io/packs'; },

        // Init
        async init() {
            await this.fetchAll();
            this.initWebSocket();
            var self = this;
            setInterval(function() { self.fetchAll(); }, 60000);
        },

        async fetchAll() {
            await Promise.all([
                this.fetchStatus(),
                this.fetchEV(),
                this.fetchPulls(),
                this.fetchRankings(),
                this.fetchAlerts(),
                this.fetchPacks(),
            ]);
            var self = this;
            this.$nextTick(function() {
                self.buildCharts();
                self.fetchEvHistory();
                self.fetchSnapshots();
            });
        },

        async fetchStatus() {
            try { this.status = await (await fetch('/api/status')).json(); } catch(e) {}
        },
        async fetchEV() {
            try { this.evData = await (await fetch('/api/ev/all')).json(); } catch(e) {}
        },
        async fetchPulls() {
            try { this.pulls = await (await fetch('/api/pulls/recent?limit=50')).json(); } catch(e) {}
        },
        async fetchRankings() {
            try { this.rankings = await (await fetch('/api/rankings')).json(); } catch(e) {}
        },
        async fetchAlerts() {
            try {
                this.activeAlerts = await (await fetch('/api/alerts/active')).json();
                this.alertHistory = await (await fetch('/api/alerts/history?limit=50')).json();
            } catch(e) {}
        },
        async fetchPacks() {
            try { this.packs = await (await fetch('/api/packs')).json(); } catch(e) {}
        },
        async fetchEvHistory() {
            for (var p of this.packs) {
                try {
                    var data = await (await fetch('/api/ev/' + p.slug + '/history?limit=200')).json();
                    if (data.length) this.evHistory[p.slug] = data;
                } catch(e) {}
            }
            this.$nextTick(function() {
                buildEvTrendChart('evTrendChart', this.evHistory);
            }.bind(this));
        },
        async fetchSnapshots() {
            for (var p of this.packs) {
                try {
                    var data = await (await fetch('/api/snapshots/' + p.slug + '?limit=50')).json();
                    if (data.length > 1) {
                        this.snapshots[p.slug] = data;
                        var cid = 'oddsShift_' + p.slug;
                        this.$nextTick(function() {
                            buildOddsShiftChart(cid, data);
                        });
                    }
                } catch(e) {}
            }
        },

        buildCharts() {
            buildOddsChart('oddsChart', this.evData, this.snapshots);
        },

        initWebSocket() {
            var self = this;
            var ws = createWebSocket('/ws/live');
            ws.onEvent('new_pull', function(data) {
                self.pulls.unshift(data);
                if (self.pulls.length > 100) self.pulls.pop();
            });
            ws.onEvent('ev_update', function(data) {
                if (Array.isArray(data)) {
                    self.evData = data;
                } else {
                    var idx = self.evData.findIndex(function(e) { return e.pack_type === data.pack_type; });
                    if (idx >= 0) Object.assign(self.evData[idx], data);
                    else self.evData.push(data);
                }
                self.$nextTick(function() { self.buildCharts(); });
            });
            ws.onEvent('alert', function(data) {
                self.activeAlerts.unshift(data);
            });
            ws.onEvent('status', function(data) {
                Object.assign(self.status, data);
            });
        },

        async acknowledgeAlert(id) {
            await fetch('/api/alerts/' + id + '/acknowledge', { method: 'POST' });
            this.activeAlerts = this.activeAlerts.filter(function(a) { return a.id !== id; });
        },

        // CSS class helpers
        confidenceClass(tier) {
            var m = {
                'calibrated': 'bg-green-500/20 text-green-400',
                'partial': 'bg-yellow-500/20 text-yellow-400',
                'very_conservative': 'bg-red-500/20 text-red-400',
            };
            return m[tier] || 'bg-gray-500/20 text-gray-400';
        },
        rarityClass(rarity) {
            var m = {
                'holographic': 'bg-red-500/20 text-red-400',
                'gold': 'bg-yellow-500/20 text-yellow-400',
                'silver': 'bg-gray-400/20 text-gray-300',
                'gloss': 'bg-gray-600/20 text-gray-500',
            };
            return m[(rarity || '').toLowerCase()] || 'bg-gray-500/20 text-gray-400';
        },
        alertClass(severity) {
            var m = {
                'critical': 'bg-red-500/90 text-white',
                'warning': 'bg-orange-400/90 text-gray-900',
                'info': 'bg-blue-400/90 text-gray-900',
            };
            return m[severity] || 'bg-gray-600 text-white';
        },
        alertBadgeClass(severity) {
            var m = {
                'critical': 'bg-red-500/20 text-red-400',
                'warning': 'bg-orange-400/20 text-orange-400',
                'info': 'bg-blue-400/20 text-blue-400',
            };
            return m[severity] || '';
        },
        evRatioColor(ratio) {
            return ratio >= 1.0 ? 'text-green-400' : 'text-red-400';
        },
    };
}
