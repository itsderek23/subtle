function isUserInputMessage(msg) {
    if (msg.type !== 'user') return false;
    if (!msg.text_content || !msg.text_content.trim()) return false;
    if (msg.tool_results && msg.tool_results.length > 0) return false;
    return true;
}

function hasToolResults(msg) {
    return msg.type === 'user' && msg.tool_results && msg.tool_results.length > 0;
}

function extractUserEvent(timestamp) {
    return { type: 'user', timestamp: timestamp, duration: 0 };
}

function extractAiEvent(timestamp, durationSeconds) {
    return {
        type: 'ai',
        timestamp: timestamp - (durationSeconds * 1000),
        duration: durationSeconds * 1000
    };
}

function extractToolEvents(timestamp, toolUses) {
    return toolUses.map(toolUse => ({
        type: 'tool',
        toolId: toolUse.id,
        toolName: toolUse.name,
        timestamp: timestamp,
        duration: 0
    }));
}

function attachToolResultDurations(events, resultTimestamp, toolResults) {
    for (const result of toolResults) {
        const toolEvent = events.find(e => e.type === 'tool' && e.toolId === result.tool_use_id);
        if (toolEvent) {
            toolEvent.duration = resultTimestamp - toolEvent.timestamp;
        }
    }
}

function extractAssistantEvents(timestamp, msg) {
    const events = [];
    if (msg.duration_seconds > 0) {
        events.push(extractAiEvent(timestamp, msg.duration_seconds));
    }
    if (msg.tool_uses && msg.tool_uses.length > 0) {
        events.push(...extractToolEvents(timestamp, msg.tool_uses));
    }
    return events;
}

function extractTimelineEvents(messages) {
    const events = [];

    for (const msg of messages) {
        if (!msg.timestamp) continue;

        const timestamp = new Date(msg.timestamp).getTime();

        if (isUserInputMessage(msg)) {
            events.push(extractUserEvent(timestamp));
        }

        if (msg.type === 'assistant') {
            events.push(...extractAssistantEvents(timestamp, msg));
        }

        if (hasToolResults(msg)) {
            attachToolResultDurations(events, timestamp, msg.tool_results);
        }
    }

    return events.sort((a, b) => a.timestamp - b.timestamp);
}

function mergeConsecutiveEvents(events) {
    if (events.length === 0) return [];

    const maxGapMs = 60 * 1000;
    const merged = [];
    let current = { ...events[0] };

    for (let i = 1; i < events.length; i++) {
        const event = events[i];
        const currentEnd = current.timestamp + (current.duration || 0);
        const gap = event.timestamp - currentEnd;

        if (event.type === current.type && gap <= maxGapMs) {
            const eventEnd = event.timestamp + (event.duration || 0);
            current.duration = Math.max(eventEnd, currentEnd) - current.timestamp;
        } else {
            merged.push(current);
            current = { ...event };
        }
    }

    merged.push(current);
    return merged;
}

function calculateTimelineScale(events) {
    if (events.length === 0) {
        return { startTime: 0, endTime: 1000, totalDuration: 1000 };
    }

    let startTime = Infinity;
    let endTime = -Infinity;

    for (const event of events) {
        if (event.timestamp < startTime) {
            startTime = event.timestamp;
        }
        const eventEnd = event.timestamp + (event.duration || 0);
        if (eventEnd > endTime) {
            endTime = eventEnd;
        }
    }

    const totalDuration = endTime - startTime;

    return { startTime, endTime, totalDuration: totalDuration || 1000 };
}

function createTimelineElement(event, scale, containerWidth) {
    const { startTime, totalDuration } = scale;
    const minWidthPx = 1;
    const userCircleSize = 10;
    const barHeight = 30;

    const leftPercent = ((event.timestamp - startTime) / totalDuration) * 100;

    const el = document.createElement('div');
    el.style.position = 'absolute';
    el.style.top = '50%';
    el.style.transform = 'translateY(-50%)';

    if (event.type === 'user') {
        el.style.left = `calc(${leftPercent}% - ${userCircleSize / 2}px)`;
        el.style.width = `${userCircleSize}px`;
        el.style.height = `${userCircleSize}px`;
        el.style.borderRadius = '50%';
        el.className = 'bg-green-500';
    } else {
        let widthPercent = (event.duration / totalDuration) * 100;
        let widthPx = (widthPercent / 100) * containerWidth;

        if (widthPx < minWidthPx) {
            widthPx = minWidthPx;
            widthPercent = (minWidthPx / containerWidth) * 100;
        }

        el.style.left = `${leftPercent}%`;
        el.style.width = `${widthPercent}%`;
        el.style.minWidth = `${minWidthPx}px`;
        el.style.height = `${barHeight}px`;
        el.style.borderRadius = '3px';

        if (event.type === 'ai') {
            el.className = 'bg-cyan-500';
        } else if (event.type === 'tool') {
            el.className = 'bg-amber-500';
        }
    }

    return el;
}

function renderSessionTimeline(messages, containerElement) {
    if (!containerElement) return;

    containerElement.innerHTML = '';

    const rawEvents = extractTimelineEvents(messages);
    const events = mergeConsecutiveEvents(rawEvents);

    if (events.length === 0) {
        containerElement.innerHTML = '<div class="text-white/30 text-xs text-center py-2">No timeline data available</div>';
        return;
    }

    const scale = calculateTimelineScale(events);
    const containerWidth = containerElement.offsetWidth;

    for (const event of events) {
        const el = createTimelineElement(event, scale, containerWidth);
        containerElement.appendChild(el);
    }
}
