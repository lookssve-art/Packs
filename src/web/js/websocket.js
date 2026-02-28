/* WebSocket client with auto-reconnect */

function createWebSocket(path) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = protocol + '//' + location.host + path;

    let ws = null;
    let reconnectDelay = 1000;
    const maxDelay = 30000;
    const handlers = {};
    let pingInterval = null;

    function connect() {
        ws = new WebSocket(url);

        ws.onopen = function() {
            console.log('[WS] Connected');
            reconnectDelay = 1000;
            pingInterval = setInterval(function() {
                if (ws.readyState === WebSocket.OPEN) {
                    ws.send('ping');
                }
            }, 30000);
        };

        ws.onmessage = function(event) {
            try {
                var msg = JSON.parse(event.data);
                var eventName = msg.event;
                var data = msg.data;
                if (handlers[eventName]) {
                    handlers[eventName].forEach(function(fn) { fn(data); });
                }
            } catch (e) {
                console.warn('[WS] Parse error:', e);
            }
        };

        ws.onclose = function() {
            console.log('[WS] Disconnected, reconnecting in ' + reconnectDelay + 'ms');
            clearInterval(pingInterval);
            setTimeout(connect, reconnectDelay);
            reconnectDelay = Math.min(reconnectDelay * 2, maxDelay);
        };

        ws.onerror = function(err) {
            console.error('[WS] Error:', err);
            ws.close();
        };
    }

    connect();

    return {
        onEvent: function(eventName, callback) {
            if (!handlers[eventName]) handlers[eventName] = [];
            handlers[eventName].push(callback);
        }
    };
}
