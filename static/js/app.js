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

function sessionDetailApp(sessionId) {
    return {
        sessionId: sessionId,
        messages: [],
        loading: true,
        selectedIndex: null,
        panelOpen: false,
        panelLoading: false,
        rawMessage: null,

        async init() {
            try {
                const response = await fetch(`/api/sessions/${this.sessionId}/messages`);
                this.messages = await response.json();
            } catch (error) {
                console.error('Failed to load messages:', error);
            } finally {
                this.loading = false;
            }
        },

        async selectMessage(index) {
            this.selectedIndex = index;
            this.panelOpen = true;
            this.panelLoading = true;
            this.rawMessage = null;

            try {
                const response = await fetch(`/api/messages/${this.sessionId}/${index}`);
                this.rawMessage = await response.json();
            } catch (error) {
                console.error('Failed to load message:', error);
            } finally {
                this.panelLoading = false;
            }
        },

        closePanel() {
            this.panelOpen = false;
            this.selectedIndex = null;
            this.rawMessage = null;
        },

        typeClass(type) {
            const classes = {
                'assistant': 'text-amber-400',
                'user': 'text-blue-400',
                'tool_result': 'text-green-400',
            };
            return classes[type] || 'text-white/50';
        },

        formatTime(isoString) {
            if (!isoString) return '–';
            const date = new Date(isoString);
            return date.toLocaleTimeString('en-US', {
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });
        },

        formatModel(model) {
            if (!model) return '–';
            if (model.includes('opus')) return 'opus';
            if (model.includes('sonnet')) return 'sonnet';
            if (model.includes('haiku')) return 'haiku';
            return model.slice(0, 10);
        }
    };
}
