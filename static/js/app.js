function formatDuration(seconds) {
    if (seconds === null || seconds === undefined) return '–';
    if (seconds === 0) return '0ms';

    if (seconds < 1) {
        return `${Math.round(seconds * 1000)}ms`;
    }
    if (seconds < 60) {
        return `${seconds.toFixed(1)}s`;
    }
    if (seconds < 3600) {
        const m = Math.floor(seconds / 60);
        const s = Math.round(seconds % 60);
        return s > 0 ? `${m}m ${s}s` : `${m}m`;
    }
    if (seconds < 86400) {
        const h = Math.floor(seconds / 3600);
        const m = Math.round((seconds % 3600) / 60);
        return m > 0 ? `${h}h ${m}m` : `${h}h`;
    }
    const d = Math.floor(seconds / 86400);
    const h = Math.round((seconds % 86400) / 3600);
    return h > 0 ? `${d}d ${h}h` : `${d}d`;
}

function formatTokens(count) {
    if (!count) return '0';
    if (count >= 1000000) {
        return (count / 1000000).toFixed(1) + 'M';
    }
    if (count >= 1000) {
        return (count / 1000).toFixed(1) + 'K';
    }
    return count.toString();
}

function formatHours(hours) {
    if (hours === null || hours === undefined) return '0';
    return hours.toFixed(1);
}

function formatPercentChange(percent) {
    if (percent === null || percent === undefined) return '';
    const sign = percent >= 0 ? '+' : '';
    return ` ${sign}${Math.round(percent)}%`;
}

function sessionsListApp() {
    return {
        sessions: [],
        loading: true,
        searchQuery: '',
        searchResults: null,
        searchLoading: false,
        debounceTimer: null,
        dailyUsage: null,
        dailyUsageLoading: true,
        chart: null,

        get filteredSessions() {
            if (this.searchResults === null) {
                return this.sessions;
            }
            return this.sessions.filter(s => this.searchResults.includes(s.session_id));
        },

        get totalHours() {
            if (!this.dailyUsage || !this.dailyUsage.current_week) return 0;
            const lastDay = this.dailyUsage.current_week[this.dailyUsage.current_week.length - 1];
            if (!lastDay) return 0;
            return lastDay.cumulative_total || 0;
        },

        get percentChange() {
            if (!this.dailyUsage || !this.dailyUsage.current_week || !this.dailyUsage.previous_week) return null;
            const currentTotal = this.totalHours;
            const prevLastDay = this.dailyUsage.previous_week[this.dailyUsage.previous_week.length - 1];
            if (!prevLastDay) return null;
            const prevTotal = prevLastDay.cumulative_total || 0;
            if (prevTotal === 0) return currentTotal > 0 ? 100 : null;
            return ((currentTotal - prevTotal) / prevTotal) * 100;
        },

        handleSearchInput() {
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }

            if (!this.searchQuery.trim()) {
                this.searchResults = null;
                this.searchLoading = false;
                return;
            }

            this.searchLoading = true;
            this.debounceTimer = setTimeout(() => this.performSearch(), 300);
        },

        async performSearch() {
            try {
                const response = await fetch(`/api/sessions/search?q=${encodeURIComponent(this.searchQuery)}`);
                const data = await response.json();
                this.searchResults = data.matching_session_ids;
            } catch (error) {
                console.error('Search failed:', error);
                this.searchResults = [];
            } finally {
                this.searchLoading = false;
            }
        },

        clearSearch() {
            this.searchQuery = '';
            this.searchResults = null;
            this.searchLoading = false;
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }
        },

        async init() {
            try {
                const [sessionsRes, dailyRes] = await Promise.all([
                    fetch('/api/sessions'),
                    fetch('/api/sessions/daily-usage')
                ]);
                this.sessions = await sessionsRes.json();
                if (dailyRes.ok) {
                    this.dailyUsage = await dailyRes.json();
                }
            } catch (error) {
                console.error('Failed to load sessions:', error);
            } finally {
                this.loading = false;
                this.dailyUsageLoading = false;
                this.$nextTick(() => this.initChart());
            }
        },

        initChart() {
            if (!this.dailyUsage || !this.dailyUsage.current_week) return;

            const ctx = this.$refs.chartCanvas;
            if (!ctx) return;

            const currentWeek = this.dailyUsage.current_week;
            const previousWeek = this.dailyUsage.previous_week;

            const labels = currentWeek.map(d => d.weekday);
            const currentData = currentWeek.map(d => d.cumulative_total);
            const prevWeekData = previousWeek.map(d => d.cumulative_total);

            this.chart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Current 7D',
                            data: currentData,
                            backgroundColor: '#d97706',
                            borderRadius: 2,
                            barPercentage: 0.95,
                            categoryPercentage: 0.95,
                            order: 2,
                        },
                        {
                            label: 'Previous 7D',
                            data: prevWeekData,
                            type: 'line',
                            borderColor: '#6b7280',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            pointBackgroundColor: '#6b7280',
                            pointRadius: 0,
                            pointHoverRadius: 4,
                            tension: 0,
                            order: 1,
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index',
                    },
                    plugins: {
                        legend: {
                            display: false,
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.9)',
                            titleColor: 'rgba(255, 255, 255, 0.6)',
                            bodyColor: 'rgba(255, 255, 255, 0.8)',
                            titleFont: { family: 'Geist Mono, monospace', size: 10 },
                            bodyFont: { family: 'Geist Mono, monospace', size: 10 },
                            padding: 10,
                            borderColor: 'rgba(255, 255, 255, 0.1)',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    const value = context.parsed.y || 0;
                                    return `${context.dataset.label}: ${value.toFixed(1)} hrs`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: { display: false },
                            ticks: {
                                color: 'rgba(255, 255, 255, 0.3)',
                                font: { size: 9, family: 'Geist Mono, monospace' }
                            }
                        },
                        y: {
                            display: false,
                        }
                    }
                }
            });
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

        formatDuration,
        formatTokens,
        formatHours,
        formatPercentChange,

        formatLoc(loc) {
            if (!loc) return '–';
            const added = loc.added || 0;
            const removed = loc.removed || 0;
            if (added === 0 && removed === 0) return '–';
            return `+${added}/-${removed}`;
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
        },

        formatDuration
    };
}

function classifyMessage(msg) {
    const isToolResult = msg.type === 'user' && msg.tool_results && msg.tool_results.length > 0;
    const isUserMessage = msg.type === 'user' && msg.text_content && msg.text_content.trim() && !isToolResult;
    const isAssistantMessage = msg.type === 'assistant';
    return { isUserMessage, isAssistantMessage, isToolResult };
}

function createUserTurn(msg) {
    return {
        type: 'user',
        content: msg.text_content,
        messageIndices: [msg.index],
        timestamp: msg.timestamp,
    };
}

function createAssistantTurn(msg) {
    return {
        type: 'assistant',
        segments: [],
        messageIndices: [],
        totalInputTokens: 0,
        totalOutputTokens: 0,
        totalDuration: 0,
        timestamp: msg.timestamp,
        model: msg.model,
    };
}

function addTextSegment(turn, msg) {
    if (msg.text_content && msg.text_content.trim()) {
        turn.segments.push({
            type: 'text',
            content: msg.text_content,
            thinking: msg.thinking,
            messageIndex: msg.index,
        });
    }
}

function addToolSegments(turn, msg) {
    if (msg.tool_uses && msg.tool_uses.length > 0) {
        for (const tool of msg.tool_uses) {
            turn.segments.push({
                type: 'tool',
                tool: tool,
                result: null,
                messageIndex: msg.index,
            });
        }
    }
}

function updateAssistantTurnStats(turn, msg) {
    turn.messageIndices.push(msg.index);
    turn.totalInputTokens += msg.input_tokens || 0;
    turn.totalOutputTokens += msg.output_tokens || 0;
    if (msg.duration_seconds) {
        turn.totalDuration += msg.duration_seconds;
    }
    if (msg.is_commit) {
        turn.hasCommit = true;
        turn.commitInfo = msg.commit_info;
    }
}

function attachToolResults(turn, msg) {
    for (const result of msg.tool_results) {
        const toolSegment = turn.segments.find(
            s => s.type === 'tool' && s.tool && s.tool.id === result.tool_use_id
        );
        if (toolSegment) {
            toolSegment.result = result;
            toolSegment.resultMessageIndex = msg.index;
        }
    }
    turn.messageIndices.push(msg.index);
}

function segmentMatchesSearch(seg, searchResults) {
    if (seg.messageIndex !== undefined && searchResults.includes(seg.messageIndex)) return true;
    if (seg.resultMessageIndex !== undefined && searchResults.includes(seg.resultMessageIndex)) return true;
    return false;
}

function filterUserTurn(turn, searchResults) {
    if (turn.messageIndices.some(idx => searchResults.includes(idx))) {
        return turn;
    }
    return null;
}

function filterAssistantTurn(turn, searchResults) {
    const filteredSegments = turn.segments.filter(seg => segmentMatchesSearch(seg, searchResults));
    if (filteredSegments.length > 0) {
        return { ...turn, segments: filteredSegments };
    }
    return null;
}

async function fetchMessagePanel(sessionId, messageIndex) {
    const response = await fetch(`/api/messages/${sessionId}/${messageIndex}`);
    return response.json();
}

function sessionDetailApp(sessionId) {
    return {
        sessionId: sessionId,
        messages: [],
        turns: [],
        loading: true,
        selectedTurnIndex: null,
        selectedMessageIndex: null,
        selectedIndex: null,
        panelOpen: false,
        panelLoading: false,
        rawMessage: null,
        searchQuery: '',
        searchResults: null,
        searchLoading: false,
        debounceTimer: null,
        expandedTurns: {},
        expandedTools: {},
        summary: {
            durationSeconds: null,
            agentTimeSeconds: null,
            toolTimeSeconds: null,
            errorCount: 0,
            commits: 0,
            toolLoc: { added: 0, removed: 0 },
            gitLoc: { added: 0, removed: 0, found: false }
        },

        get filteredTurns() {
            if (this.searchResults === null) {
                return this.turns;
            }
            return this.turns
                .map(turn => {
                    if (turn.type === 'user') return filterUserTurn(turn, this.searchResults);
                    if (turn.type === 'assistant') return filterAssistantTurn(turn, this.searchResults);
                    return null;
                })
                .filter(Boolean);
        },

        get filteredMessages() {
            if (this.searchResults === null) {
                return this.messages;
            }
            return this.messages.filter(m => this.searchResults.includes(m.index));
        },

        handleSearchInput() {
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }

            if (!this.searchQuery.trim()) {
                this.searchResults = null;
                this.searchLoading = false;
                return;
            }

            this.searchLoading = true;
            this.debounceTimer = setTimeout(() => this.performSearch(), 300);
        },

        async performSearch() {
            try {
                const response = await fetch(`/api/sessions/${this.sessionId}/messages/search?q=${encodeURIComponent(this.searchQuery)}`);
                const data = await response.json();
                this.searchResults = data.matching_indices;
            } catch (error) {
                console.error('Search failed:', error);
                this.searchResults = [];
            } finally {
                this.searchLoading = false;
            }
        },

        clearSearch() {
            this.searchQuery = '';
            this.searchResults = null;
            this.searchLoading = false;
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }
        },

        async init() {
            window.addEventListener('keydown', (e) => this.handleKeydown(e));

            try {
                const [messagesRes, sessionRes] = await Promise.all([
                    fetch(`/api/sessions/${this.sessionId}/messages`),
                    fetch(`/api/sessions/${this.sessionId}`)
                ]);
                this.messages = await messagesRes.json();
                const session = await sessionRes.json();
                this.computeSummary(session);
                this.groupMessagesIntoTurns();
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
                agentTimeSeconds: session.agent_time_seconds,
                toolTimeSeconds: session.tool_time_seconds,
                errorCount: session.error_count,
                commits,
                toolLoc: { added: toolAdded, removed: toolRemoved },
                gitLoc: { added: gitAdded, removed: gitRemoved, found: gitFound }
            };
        },

        groupMessagesIntoTurns() {
            const turns = [];
            let currentTurn = null;

            for (const msg of this.messages) {
                const { isUserMessage, isAssistantMessage, isToolResult } = classifyMessage(msg);

                if (isUserMessage) {
                    if (currentTurn) turns.push(currentTurn);
                    turns.push(createUserTurn(msg));
                    currentTurn = null;
                } else if (isAssistantMessage) {
                    if (!currentTurn || currentTurn.type !== 'assistant') {
                        if (currentTurn) turns.push(currentTurn);
                        currentTurn = createAssistantTurn(msg);
                    }
                    addTextSegment(currentTurn, msg);
                    addToolSegments(currentTurn, msg);
                    updateAssistantTurnStats(currentTurn, msg);
                } else if (isToolResult && currentTurn && currentTurn.type === 'assistant') {
                    attachToolResults(currentTurn, msg);
                }
            }

            if (currentTurn) turns.push(currentTurn);
            this.turns = turns;
        },

        isExpanded(turnIndex) {
            return this.expandedTurns[turnIndex] === true;
        },

        toggleExpand(turnIndex) {
            this.expandedTurns[turnIndex] = !this.expandedTurns[turnIndex];
        },

        isToolExpanded(turnIndex, toolIndex) {
            const key = `${turnIndex}-${toolIndex}`;
            return this.expandedTools[key] === true;
        },

        toggleToolExpand(turnIndex, toolIndex) {
            const key = `${turnIndex}-${toolIndex}`;
            this.expandedTools[key] = !this.expandedTools[key];
        },

        truncateText(text, maxLength = 300) {
            if (!text || text.length <= maxLength) return text;
            return text.substring(0, maxLength);
        },

        needsTruncation(text, maxLength = 300) {
            return text && text.length > maxLength;
        },

        renderMarkdown(text) {
            if (!text) return '';
            if (typeof marked !== 'undefined') {
                return marked.parse(text);
            }
            return text.replace(/\n/g, '<br>');
        },

        formatUserContent(content) {
            if (!content) return '';
            let text = content
                .replace(/<command-message>.*?<\/command-message>\s*/g, '')
                .replace(/<command-name>(.*?)<\/command-name>/g, '$1')
                .replace(/<command-args>(.*?)<\/command-args>/g, ' $1')
                .replace(/<[^>]+>/g, '')
                .trim();
            return text;
        },

        getToolArgs(tool) {
            const name = tool.name;
            if (name === 'Bash' && tool.command) {
                const cmd = tool.command.length > 60 ? tool.command.substring(0, 60) + '…' : tool.command;
                return cmd;
            }
            if (tool.file_path) {
                return tool.file_path;
            }
            if (tool.pattern) {
                return tool.pattern;
            }
            if (tool.query) {
                return tool.query;
            }
            return '';
        },

        truncateResult(text) {
            if (!text) return '(No content)';
            const firstLine = text.split('\n')[0];
            const lineCount = text.split('\n').length;
            if (lineCount > 1) {
                const preview = firstLine.length > 80 ? firstLine.substring(0, 80) + '…' : firstLine;
                return `${preview} … +${lineCount - 1} lines`;
            }
            return firstLine.length > 100 ? firstLine.substring(0, 100) + '…' : firstLine;
        },

        getToolSummary(tool) {
            const name = tool.name;
            const fileName = tool.file_path ? tool.file_path.split('/').pop() : null;

            const handlers = {
                Edit: () => {
                    if (!fileName) return null;
                    if (tool.edit_summary) {
                        const diff = tool.edit_summary.new_lines - tool.edit_summary.old_lines;
                        return `Edited ${fileName} (${diff >= 0 ? '+' : ''}${diff} lines)`;
                    }
                    return `Edited ${fileName}`;
                },
                Write: () => fileName ? `Wrote ${fileName}${tool.write_lines ? ` (${tool.write_lines} lines)` : ''}` : null,
                Read: () => fileName ? `Read ${fileName}` : null,
                Bash: () => tool.command ? `Ran: ${tool.command}` : null,
                Glob: () => tool.pattern ? `Searched files: ${tool.pattern}` : null,
                Grep: () => tool.pattern ? `Searched for: ${tool.pattern}` : null,
                WebSearch: () => tool.query ? `Web search: ${tool.query}` : null,
                Task: () => 'Launched agent task',
            };

            const handler = handlers[name];
            return (handler && handler()) || name;
        },

        getToolIcon(toolName) {
            const icons = {
                'Edit': '\u270F\uFE0F',
                'Write': '\u{1F4DD}',
                'Read': '\u{1F4D6}',
                'Bash': '\u26A1',
                'Glob': '\u{1F50D}',
                'Grep': '\u{1F50E}',
                'WebSearch': '\u{1F310}',
                'WebFetch': '\u{1F310}',
                'Task': '\u{1F916}',
            };
            return icons[toolName] || '\u{1F527}';
        },

        async loadMessagePanel(messageIndex) {
            this.panelOpen = true;
            this.panelLoading = true;
            this.rawMessage = null;

            try {
                this.rawMessage = await fetchMessagePanel(this.sessionId, messageIndex);
            } catch (error) {
                console.error('Failed to load message:', error);
            } finally {
                this.panelLoading = false;
            }
        },

        async selectTurn(turnIndex, messageIndex) {
            this.selectedTurnIndex = turnIndex;
            this.selectedMessageIndex = messageIndex;
            await this.loadMessagePanel(messageIndex);
        },

        async selectMessage(index) {
            this.selectedIndex = index;
            await this.loadMessagePanel(index);
        },

        closePanel() {
            this.panelOpen = false;
            this.selectedIndex = null;
            this.rawMessage = null;
        },

        handleKeydown(event) {
            if (!this.panelOpen) return;

            if (event.key === 'Escape') {
                this.closePanel();
                return;
            }

            if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
                event.preventDefault();
                const filtered = this.filteredMessages;
                const currentIdx = filtered.findIndex(m => m.index === this.selectedIndex);
                if (currentIdx === -1) return;

                let newIdx;
                if (event.key === 'ArrowUp') {
                    newIdx = currentIdx > 0 ? currentIdx - 1 : currentIdx;
                } else {
                    newIdx = currentIdx < filtered.length - 1 ? currentIdx + 1 : currentIdx;
                }

                if (newIdx !== currentIdx) {
                    this.selectMessage(filtered[newIdx].index);
                }
            }
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

        formatDuration
    };
}
