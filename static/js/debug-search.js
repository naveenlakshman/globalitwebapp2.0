// Debug script to test search functionality
(function() {
    console.log('Debug script loaded');
    
    // Wait for DOM to be ready
    document.addEventListener('DOMContentLoaded', function() {
        console.log('DOM ready - debugging search functionality');
        
        // Check if elements exist
        const studentSearch = document.getElementById('studentSearch');
        const courseSearch = document.getElementById('courseSearch');
        const studentResults = document.getElementById('studentResults');
        const courseResults = document.getElementById('courseResults');
        
        console.log('Element check:');
        console.log('studentSearch:', studentSearch);
        console.log('courseSearch:', courseSearch);
        console.log('studentResults:', studentResults);
        console.log('courseResults:', courseResults);
        
        // Check course items
        const courseItems = document.querySelectorAll('.course-search-item');
        console.log('Course items found:', courseItems.length);
        courseItems.forEach((item, index) => {
            console.log(`Course ${index}:`, {
                id: item.getAttribute('data-course-id'),
                name: item.getAttribute('data-course-name'),
                fee: item.getAttribute('data-course-fee')
            });
        });
        
        // Check student options
        const studentOptions = document.querySelectorAll('#student_id option[value]');
        console.log('Student options found:', studentOptions.length);
        studentOptions.forEach((option, index) => {
            console.log(`Student ${index}:`, {
                id: option.value,
                name: option.getAttribute('data-name')
            });
        });
        
        // Test student search functionality
        if (studentSearch) {
            studentSearch.addEventListener('input', function() {
                console.log('Student search input:', this.value);
            });
        }
        
        // Test course search functionality
        if (courseSearch) {
            courseSearch.addEventListener('input', function() {
                console.log('Course search input:', this.value);
            });
            
            courseSearch.addEventListener('focus', function() {
                console.log('Course search focused');
                if (courseResults) {
                    courseResults.style.display = 'block';
                    console.log('Course results shown');
                }
            });
        }
        
        // Add click handlers to course items for testing
        courseItems.forEach(item => {
            item.addEventListener('click', function() {
                console.log('Course item clicked:', this.getAttribute('data-course-name'));
                alert('Course clicked: ' + this.getAttribute('data-course-name'));
            });
            
            // Add visual indicator that items are clickable
            item.style.border = '1px solid #ccc';
            item.style.marginBottom = '2px';
            item.style.backgroundColor = '#f8f9fa';
        });
    });
})();
