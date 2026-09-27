document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    document.querySelectorAll('form[data-confirm]').forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });

    document.querySelectorAll('.auto-submit-on-change').forEach(element => {
        element.addEventListener('change', function() {
            this.closest('form').submit();
        });
    });

    const searchInputs = document.querySelectorAll('.search-input');
    searchInputs.forEach(input => {
        let timeout;
        input.addEventListener('input', function() {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                this.closest('form').submit();
            }, 500);
        });
    });

    document.querySelectorAll('[data-auto-focus]').forEach(el => {
        el.focus();
    });

    window.formatNumber = function(num, decimals = 0) {
        if (num === null || num === undefined) return '';
        return Number(num).toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    };

    window.formatCurrency = function(num) {
        return formatNumber(num, 2);
    };

    window.parseNumber = function(str) {
        return parseFloat(str.replace(/,/g, '')) || 0;
    };

    window.calculateTotal = function(qty, price) {
        return (parseNumber(qty) * parseNumber(price)).toFixed(2);
    };
});

function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
    bsToast.show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    document.body.appendChild(container);
    return container;
}

function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

function ajaxRequest(url, options = {}) {
    const defaults = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    };
    const config = { ...defaults, ...options };
    if (config.body && typeof config.body === 'object') {
        config.body = JSON.stringify(config.body);
    }
    return fetch(url, config)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .catch(error => {
            console.error('AJAX Error:', error);
            showToast('An error occurred. Please try again.', 'danger');
            throw error;
        });
}