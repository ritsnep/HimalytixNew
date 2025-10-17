document.addEventListener('DOMContentLoaded', function() {
    const toggleSidebar = document.getElementById('toggleSidebar');
    const sidebar = document.querySelector('.sidebar');
    const contentArea = document.querySelector('.content-area');
    
    // Check for saved sidebar state
    const sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (sidebarCollapsed) {
        sidebar.classList.add('collapsed');
        contentArea.classList.add('expanded');
    }
    
    toggleSidebar.addEventListener('click', function() {
        sidebar.classList.toggle('collapsed');
        contentArea.classList.toggle('expanded');
        localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    });
    
    // Close sidebar on mobile when clicking outside
    document.addEventListener('click', function(e) {
        if (window.innerWidth < 768) {
            if (!sidebar.contains(e.target) && !toggleSidebar.contains(e.target)) {
                sidebar.classList.add('collapsed');
                contentArea.classList.add('expanded');
                localStorage.setItem('sidebarCollapsed', true);
            }
        }
    });
});
