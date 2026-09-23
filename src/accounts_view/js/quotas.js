// Quota rendering and visual telemetry logic (100% self-contained)

function renderQuotaBar(modelName, percentage, resetTime) {
  let tierClass = 'high';
  if (percentage < 25) {
    tierClass = 'low';
  } else if (percentage < 55) {
    tierClass = 'medium';
  }

  // Format reset countdown
  let resetStr = '';
  if (resetTime) {
    try {
      const resetDate = new Date(resetTime);
      const now = new Date();
      const diffMs = resetDate.getTime() - now.getTime();
      if (diffMs > 0) {
        const hours = Math.floor(diffMs / (1000 * 60 * 60));
        const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
        resetStr = `Resets in ${hours}h ${mins}m`;
      } else {
        resetStr = 'Resetting soon';
      }
    } catch {
      resetStr = '';
    }
  }

  return `
    <div class="quota-item">
      <div class="quota-item-header">
        <span class="quota-model-name">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
          </svg>
          ${modelName}
        </span>
        <div class="quota-meta">
          ${resetStr ? `<span class="quota-reset">${resetStr}</span>` : ''}
          <span class="quota-pct ${tierClass}">${percentage}%</span>
        </div>
      </div>
      <div class="progress-track">
        <div class="progress-fill ${tierClass}" style="width: ${Math.min(Math.max(percentage, 0), 100)}%"></div>
      </div>
    </div>
  `;
}
