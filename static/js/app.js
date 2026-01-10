function sessionsListApp() {
    return {
        sessions: [],
        loading: true,

        async init() {
            try {
                const response = await fetch('/api/sessions');
                this.sessions = await response.json();
            } catch (error) {
                console.error('Failed to load sessions:', error);
            } finally {
                this.loading = false;
            }
        },

        goToSession(sessionId) {
            window.location.href = `/session/${sessionId}`;
        },

        formatTime(isoString) {
            if (!isoString) return '–';
            const date = new Date(isoString);
            return date.toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });
        },

        formatDuration(seconds) {
            if (!seconds) return '–';
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            }
            return `${minutes}m`;
        },

        formatTokens(count) {
            if (!count) return '0';
            if (count >= 1000000) {
                return (count / 1000000).toFixed(1) + 'M';
            }
            if (count >= 1000) {
                return (count / 1000).toFixed(0) + 'K';
            }
            return count.toString();
        }
    };
}
