// Session Detail Page JavaScript

let ws = null;
const updatesContainer = document.getElementById('updates');

// Initialize WebSocket connection for real-time updates
function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${sessionId}`;

    ws = new WebSocket(wsUrl);

    ws.onopen = function() {
        console.log('WebSocket connected');
        addUpdate('info', 'Real-time updates connected');
    };

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
    };

    ws.onerror = function(error) {
        console.error('WebSocket error:', error);
        addUpdate('error', 'Connection error - updates may be delayed');
    };

    ws.onclose = function() {
        console.log('WebSocket disconnected');
        // Attempt to reconnect after 5 seconds
        setTimeout(initWebSocket, 5000);
    };
}

// Handle incoming WebSocket messages
function handleWebSocketMessage(data) {
    console.log('WebSocket message:', data);

    switch (data.type) {
        case 'status':
            updateStatus(data.status, data.message);
            addUpdate('info', data.message);
            break;

        case 'approval_required':
            addUpdate('warning', `Approval required (Iteration ${data.iteration})`);
            // Reload page to show approval form
            setTimeout(() => window.location.reload(), 1000);
            break;

        case 'completed':
            updateStatus('completed', 'Analysis completed');
            addUpdate('success', 'Analysis completed successfully');
            // Reload to show extracted files
            setTimeout(() => window.location.reload(), 2000);
            break;

        case 'error':
            updateStatus('error', 'Error occurred');
            addUpdate('error', data.message);
            break;

        case 'files_extracted':
            addUpdate('success', `${data.file_count} files extracted`);
            setTimeout(() => window.location.reload(), 1000);
            break;

        case 'session_state':
            // Initial state received
            if (data.session) {
                updateStatus(data.session.status, `Session status: ${data.session.status}`);
            }
            break;

        default:
            console.log('Unknown message type:', data.type);
    }
}

// Update status display
function updateStatus(status, message) {
    const statusBadge = document.getElementById('currentStatus');
    if (statusBadge) {
        statusBadge.className = `status-badge status-${status}`;
        statusBadge.textContent = status;
    }

    if (message) {
        addUpdate('info', message);
    }
}

// Add update to the updates log
function addUpdate(type, message) {
    if (!updatesContainer) return;

    const updateDiv = document.createElement('div');
    updateDiv.className = `update-item update-${type}`;

    const time = new Date().toLocaleTimeString();
    updateDiv.innerHTML = `
        <span class="update-time">${time}</span>
        <span class="update-message">${message}</span>
    `;

    updatesContainer.insertBefore(updateDiv, updatesContainer.firstChild);

    // Keep only last 50 updates
    while (updatesContainer.children.length > 50) {
        updatesContainer.removeChild(updatesContainer.lastChild);
    }
}

// Handle approval form
const approvalForm = document.getElementById('approvalForm');
if (approvalForm) {
    // Handle decision radio button changes
    const approvalItems = document.querySelectorAll('.approval-item');

    approvalItems.forEach((item, index) => {
        const radios = item.querySelectorAll(`input[name="decision_${index}"]`);
        const modificationArea = item.querySelector('.modification-area');

        radios.forEach(radio => {
            radio.addEventListener('change', function() {
                if (this.value === 'modify') {
                    modificationArea.style.display = 'block';
                } else {
                    modificationArea.style.display = 'none';
                }
            });
        });
    });

    // Handle form submission
    approvalForm.addEventListener('submit', async function(e) {
        e.preventDefault();

        const formData = new FormData(approvalForm);
        const approvalCount = parseInt(formData.get('approval_count'));

        // Build decisions array
        const decisions = [];

        for (let i = 0; i < approvalCount; i++) {
            const decision = formData.get(`decision_${i}`);
            const toolCallId = formData.get(`tool_call_id_${i}`);
            const toolName = formData.get(`tool_name_${i}`);

            const decisionObj = {
                tool_call_id: toolCallId,
                tool_name: toolName,
                decision: decision
            };

            if (decision === 'modify') {
                const modifiedArgs = formData.get(`modified_args_${i}`);
                try {
                    decisionObj.modified_args = JSON.parse(modifiedArgs);
                } catch (error) {
                    alert(`Error parsing modified arguments for ${toolName}: ${error.message}`);
                    return;
                }
            }

            decisions.push(decisionObj);
        }

        // Submit decisions
        const submitButton = approvalForm.querySelector('button[type="submit"]');
        const originalText = submitButton.textContent;
        submitButton.textContent = '⏳ Submitting...';
        submitButton.disabled = true;

        try {
            const response = await fetch('/api/approval/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    session_id: sessionId,
                    decisions_json: JSON.stringify(decisions)
                })
            });

            if (response.ok) {
                addUpdate('success', 'Approvals submitted - resuming analysis');
                // Reload page after a short delay
                setTimeout(() => window.location.reload(), 1500);
            } else {
                const error = await response.json();
                alert(`Error submitting approvals: ${error.detail}`);
                submitButton.textContent = originalText;
                submitButton.disabled = false;
            }
        } catch (error) {
            alert(`Network error: ${error.message}`);
            submitButton.textContent = originalText;
            submitButton.disabled = false;
        }
    });
}

// Refresh session data
async function refreshSession() {
    try {
        const response = await fetch(`/api/session/${sessionId}`);
        if (response.ok) {
            addUpdate('info', 'Session data refreshed');
            setTimeout(() => window.location.reload(), 500);
        }
    } catch (error) {
        addUpdate('error', `Failed to refresh: ${error.message}`);
    }
}

// Delete session
async function deleteSession() {
    if (!confirm('Are you sure you want to delete this session? All data will be lost.')) {
        return;
    }

    try {
        const response = await fetch(`/api/session/${sessionId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            alert('Session deleted successfully');
            window.location.href = '/';
        } else {
            const error = await response.json();
            alert(`Error deleting session: ${error.detail}`);
        }
    } catch (error) {
        alert(`Network error: ${error.message}`);
    }
}

// Initialize WebSocket on page load
document.addEventListener('DOMContentLoaded', function() {
    initWebSocket();

    // Auto-refresh iteration count every 5 seconds
    setInterval(async () => {
        try {
            const response = await fetch(`/api/session/${sessionId}`);
            if (response.ok) {
                const session = await response.json();
                const iterationElement = document.getElementById('currentIteration');
                if (iterationElement && session.current_iteration) {
                    iterationElement.textContent = session.current_iteration;
                }
            }
        } catch (error) {
            console.error('Failed to update iteration:', error);
        }
    }, 5000);
});
