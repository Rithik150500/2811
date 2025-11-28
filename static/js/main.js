// Main JavaScript for Legal Risk Analysis System - Index Page

document.addEventListener('DOMContentLoaded', function() {
    const analysisForm = document.getElementById('analysisForm');
    const formStatus = document.getElementById('formStatus');

    // Handle analysis form submission
    if (analysisForm) {
        analysisForm.addEventListener('submit', async function(e) {
            e.preventDefault();

            // Get form data
            const formData = new FormData(analysisForm);

            // Show loading state
            const submitButton = analysisForm.querySelector('button[type="submit"]');
            const originalText = submitButton.textContent;
            submitButton.textContent = '⏳ Starting Analysis...';
            submitButton.disabled = true;

            formStatus.style.display = 'none';

            try {
                const response = await fetch('/api/analysis/start', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (response.ok) {
                    // Success - show message and redirect
                    formStatus.className = 'status-message success';
                    formStatus.textContent = `✓ Analysis started successfully! Redirecting to session...`;
                    formStatus.style.display = 'block';

                    // Redirect to session page after 2 seconds
                    setTimeout(() => {
                        window.location.href = `/session/${result.session_id}`;
                    }, 2000);
                } else {
                    // Error
                    formStatus.className = 'status-message error';
                    formStatus.textContent = `✗ Error: ${result.detail || 'Failed to start analysis'}`;
                    formStatus.style.display = 'block';

                    submitButton.textContent = originalText;
                    submitButton.disabled = false;
                }
            } catch (error) {
                formStatus.className = 'status-message error';
                formStatus.textContent = `✗ Network error: ${error.message}`;
                formStatus.style.display = 'block';

                submitButton.textContent = originalText;
                submitButton.disabled = false;
            }
        });
    }

    // Auto-refresh sessions list every 10 seconds
    setInterval(async () => {
        try {
            const response = await fetch('/api/sessions');
            if (response.ok) {
                const data = await response.json();
                updateSessionsDisplay(data.sessions);
            }
        } catch (error) {
            console.error('Failed to refresh sessions:', error);
        }
    }, 10000);
});

function updateSessionsDisplay(sessions) {
    // Update session cards with latest status
    sessions.forEach(session => {
        const sessionCard = document.querySelector(`[data-session-id="${session.session_id}"]`);
        if (sessionCard) {
            const statusBadge = sessionCard.querySelector('.status-badge');
            const iterationText = sessionCard.querySelector('.iteration-text');

            if (statusBadge) {
                statusBadge.className = `status-badge status-${session.status}`;
                statusBadge.textContent = session.status;
            }

            if (iterationText) {
                iterationText.textContent = session.current_iteration;
            }
        }
    });
}
