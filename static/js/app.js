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
        },

        formatLoc(loc) {
            if (!loc) return '<span class="text-white/30">–</span>';
            const added = loc.added || 0;
            const removed = loc.removed || 0;
            if (added === 0 && removed === 0) return '<span class="text-white/30">–</span>';
            return `<span class="text-green-400">+${added}</span><span class="text-white/30">/</span><span class="text-red-400">-${removed}</span>`;
        }
    };
}

function messageBreakdownApp(sessionId) {
    return {
        sessionId: sessionId,
        breakdown: [],
        total: 0,
        loading: true,

        async init() {
            try {
                const response = await fetch(`/api/sessions/${this.sessionId}/message_breakdown`);
                const data = await response.json();
                this.breakdown = data.breakdown;
                this.total = data.total;
            } catch (error) {
                console.error('Failed to load message breakdown:', error);
            } finally {
                this.loading = false;
            }
        },

        getColor(type) {
            const colors = {
                'tool': '#f59e0b',
                'assistant': '#06b6d4',
                'user': '#10b981'
            };
            return colors[type] || '#6b7280';
        },

        getPercentage(count) {
            if (this.total === 0) return 0;
            return (count / this.total) * 100;
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
        summary: {
            durationSeconds: null,
            executionTimeSeconds: null,
            errorCount: 0,
            commits: 0,
            toolLoc: { added: 0, removed: 0 },
            gitLoc: { added: 0, removed: 0, found: false }
        },

        async init() {
            try {
                const [messagesRes, sessionRes] = await Promise.all([
                    fetch(`/api/sessions/${this.sessionId}/messages`),
                    fetch(`/api/sessions/${this.sessionId}`)
                ]);
                this.messages = await messagesRes.json();
                const session = await sessionRes.json();
                this.computeSummary(session);
            } catch (error) {
                console.error('Failed to load messages:', error);
            } finally {
                this.loading = false;
            }
        },

        computeSummary(session) {
            let commits = 0;
            let toolAdded = 0, toolRemoved = 0;
            let gitAdded = 0, gitRemoved = 0, gitFound = false;

            for (const msg of this.messages) {
                if (msg.is_commit) commits++;
                if (msg.edit_loc) {
                    toolAdded += msg.edit_loc.added || 0;
                    toolRemoved += msg.edit_loc.removed || 0;
                }
                if (msg.write_loc) {
                    toolAdded += msg.write_loc || 0;
                }
                if (msg.git_diff_loc) {
                    gitFound = true;
                    gitAdded += msg.git_diff_loc.added || 0;
                    gitRemoved += msg.git_diff_loc.removed || 0;
                }
            }

            this.summary = {
                durationSeconds: session.duration_seconds,
                executionTimeSeconds: session.execution_time_seconds,
                errorCount: session.error_count,
                commits,
                toolLoc: { added: toolAdded, removed: toolRemoved },
                gitLoc: { added: gitAdded, removed: gitRemoved, found: gitFound }
            };
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
        },

        formatDuration(seconds) {
            if (!seconds) return '–';
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            }
            return `${minutes}m`;
        }
    };
}
