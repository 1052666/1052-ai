document.addEventListener('DOMContentLoaded', () => {
    // Shared Sidebar Logic
    const sidebar = document.getElementById('sidebar');
    const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');

    if (sidebar && toggleSidebarBtn) {
        toggleSidebarBtn.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
        });

        // Apply state immediately (also handled by inline script in HTML to prevent flicker)
        if (localStorage.getItem('sidebarCollapsed') === 'true') {
            sidebar.classList.add('collapsed');
        }
    }
});

// Shared Custom UI Helpers
const customModal = document.getElementById('custom-modal');
const customModalMessage = document.getElementById('custom-modal-message');
const customModalActions = document.getElementById('custom-modal-actions');

// Close modal on backdrop click (optional, but good for "stuck" modals)
if (customModal) {
    customModal.addEventListener('click', (e) => {
        if (e.target === customModal) {
            // Try to find a cancel button or ok button and click it.
            const cancelBtn = customModalActions.querySelector('.secondary-btn'); // Cancel
            const okBtn = customModalActions.querySelector('.primary-btn'); // OK
            
            if (cancelBtn) cancelBtn.click();
            else if (okBtn) okBtn.click();
        }
    });
}

function showCustomAlert(message) {
    return new Promise((resolve) => {
        if (!customModal) {
            alert(message);
            resolve();
            return;
        }
        customModalMessage.textContent = message;
        customModalActions.innerHTML = '';
        
        const okBtn = document.createElement('button');
        okBtn.className = 'primary-btn';
        okBtn.textContent = '确定';
        okBtn.onclick = () => {
            customModal.classList.remove('active');
            resolve();
        };
        
        customModalActions.appendChild(okBtn);
        customModal.classList.add('active');
        okBtn.focus(); // Focus for accessibility
    });
}

function showCustomConfirm(message) {
    return new Promise((resolve) => {
        if (!customModal) {
            resolve(confirm(message));
            return;
        }
        customModalMessage.textContent = message;
        customModalActions.innerHTML = '';
        
        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'secondary-btn';
        cancelBtn.textContent = '取消';
        cancelBtn.onclick = () => {
            customModal.classList.remove('active');
            resolve(false);
        };
        
        const confirmBtn = document.createElement('button');
        confirmBtn.className = 'primary-btn';
        confirmBtn.textContent = '确定';
        confirmBtn.onclick = () => {
            customModal.classList.remove('active');
            resolve(true);
        };
        
        customModalActions.appendChild(cancelBtn);
        customModalActions.appendChild(confirmBtn);
        customModal.classList.add('active');
        confirmBtn.focus();
    });
}

