// Global utility functions and event handlers

// Show alert messages
function showAlert(message, type = 'info') {
    // Create alert element
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alertDiv.style.position = 'fixed';
    alertDiv.style.top = '20px';
    alertDiv.style.right = '20px';
    alertDiv.style.zIndex = '9999';
    alertDiv.style.minWidth = '300px';
    
    alertDiv.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-${getAlertIcon(type)} me-2"></i>
            <span>${message}</span>
            <button type="button" class="btn-close ms-auto" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (alertDiv && alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function getAlertIcon(type) {
    switch(type) {
        case 'success': return 'check-circle';
        case 'warning': return 'exclamation-triangle';
        case 'error':
        case 'danger': return 'exclamation-circle';
        default: return 'info-circle';
    }
}

// Update token count in navigation
function updateTokenCount(tokens) {
    const tokenElement = document.getElementById('token-count');
    const tokenElementMobile = document.getElementById('token-count-mobile');
    
    if (tokenElement) {
        tokenElement.textContent = tokens;
        
        // Add animation effect
        tokenElement.style.transform = 'scale(1.2)';
        tokenElement.style.color = '#ff6b6b';
        setTimeout(() => {
            tokenElement.style.transform = 'scale(1)';
            tokenElement.style.color = '';
        }, 300);
    }
    
    if (tokenElementMobile) {
        tokenElementMobile.textContent = tokens;
        
        // Add animation effect for mobile
        tokenElementMobile.style.transform = 'scale(1.2)';
        tokenElementMobile.style.color = '#ff6b6b';
        setTimeout(() => {
            tokenElementMobile.style.transform = 'scale(1)';
            tokenElementMobile.style.color = '';
        }, 300);
    }
}

// Show coming soon modal for unimplemented features
function showComingSoon(feature) {
    showAlert(`${feature} feature coming soon!`, 'info');
}

// Load token count on page load
document.addEventListener('DOMContentLoaded', function() {
    // Fetch current token count
    fetch('/api/tokens')
        .then(response => response.json())
        .then(data => {
            if (data.tokens !== undefined) {
                updateTokenCount(data.tokens);
            }
        })
        .catch(error => {
            console.error('Error fetching token count:', error);
        });
});

// Handle form validation
function validateForm(formId, requiredFields) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    let isValid = true;
    const errors = [];
    
    requiredFields.forEach(field => {
        const input = form.querySelector(`#${field.id}`);
        if (input) {
            const value = input.type === 'checkbox' ? input.checked : input.value.trim();
            
            if (field.required && (!value || value === '')) {
                isValid = false;
                errors.push(field.message || `${field.label || field.id} is required`);
                input.classList.add('is-invalid');
            } else {
                input.classList.remove('is-invalid');
            }
        }
    });
    
    if (!isValid) {
        showAlert(errors[0], 'warning');
    }
    
    return isValid;
}

// File size formatter
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Loading state management
function setLoadingState(element, isLoading, originalText = '') {
    if (isLoading) {
        element.disabled = true;
        element.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
    } else {
        element.disabled = false;
        element.innerHTML = originalText;
    }
}

// Debounce function for API calls
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// API error handler
function handleApiError(error, defaultMessage = 'An error occurred') {
    console.error('API Error:', error);
    
    if (error.response) {
        // Server responded with error status
        error.response.json().then(data => {
            showAlert(data.error || defaultMessage, 'error');
        }).catch(() => {
            showAlert(defaultMessage, 'error');
        });
    } else if (error.message) {
        // Network or other error
        showAlert(error.message, 'error');
    } else {
        showAlert(defaultMessage, 'error');
    }
}

// Initialize tooltips if Bootstrap is available
document.addEventListener('DOMContentLoaded', function() {
    if (typeof bootstrap !== 'undefined') {
        // Initialize tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
});

// Smooth scrolling for anchor links
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
});

// Mobile menu handling
document.addEventListener('DOMContentLoaded', function() {
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarCollapse = document.querySelector('.navbar-collapse');
    
    if (navbarToggler && navbarCollapse) {
        // Close mobile menu when clicking outside
        document.addEventListener('click', function(e) {
            if (!navbarToggler.contains(e.target) && !navbarCollapse.contains(e.target)) {
                if (navbarCollapse.classList.contains('show')) {
                    navbarToggler.click();
                }
            }
        });
    }
});

// Progress bar for file uploads
function updateProgress(progressEvent) {
    if (progressEvent.lengthComputable) {
        const percentComplete = (progressEvent.loaded / progressEvent.total) * 100;
        const progressBar = document.querySelector('.progress-bar');
        if (progressBar) {
            progressBar.style.width = percentComplete + '%';
            progressBar.setAttribute('aria-valuenow', percentComplete);
            progressBar.textContent = Math.round(percentComplete) + '%';
        }
    }
}

// Copy to clipboard functionality
function copyToClipboard(text, successMessage = 'Copied to clipboard!') {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showAlert(successMessage, 'success');
        }).catch(() => {
            fallbackCopyToClipboard(text, successMessage);
        });
    } else {
        fallbackCopyToClipboard(text, successMessage);
    }
}

function fallbackCopyToClipboard(text, successMessage) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.top = '0';
    textArea.style.left = '0';
    textArea.style.width = '2em';
    textArea.style.height = '2em';
    textArea.style.padding = '0';
    textArea.style.border = 'none';
    textArea.style.outline = 'none';
    textArea.style.boxShadow = 'none';
    textArea.style.background = 'transparent';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showAlert(successMessage, 'success');
    } catch (err) {
        showAlert('Unable to copy to clipboard', 'error');
    }
    
    document.body.removeChild(textArea);
}

// Local storage helpers
const Storage = {
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (error) {
            console.error('Error saving to localStorage:', error);
        }
    },
    
    get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (error) {
            console.error('Error reading from localStorage:', error);
            return defaultValue;
        }
    },
    
    remove(key) {
        try {
            localStorage.removeItem(key);
        } catch (error) {
            console.error('Error removing from localStorage:', error);
        }
    }
};

// Export functions for use in other scripts
window.SLNP = {
    showAlert,
    updateTokenCount,
    showComingSoon,
    validateForm,
    formatFileSize,
    setLoadingState,
    debounce,
    handleApiError,
    copyToClipboard,
    Storage
};
