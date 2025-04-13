document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const puzzleFileInput = document.getElementById('puzzle-file');
    const setupPuzzleBtn = document.getElementById('setup-puzzle-btn');
    const remainingWordsTextarea = document.getElementById('remaining-words');
    const getRecommendationBtn = document.getElementById('get-recommendation-btn');
    const recommendedGroupTextarea = document.getElementById('recommended-group');
    const connectionReasonTextarea = document.getElementById('connection-reason');
    const statusTextarea = document.getElementById('status');
    const recommenderTextarea = document.getElementById('recommender');
    const terminateBtn = document.getElementById('terminate-btn');
    const colorButtons = document.querySelectorAll('.color-btn');
    const responseButtons = document.querySelectorAll('.response-btn');
    const manualOverrideBtn = document.getElementById('manual-override-btn');
    const confirmOverrideBtn = document.getElementById('confirm-override-btn');
    const correctGroupsTextarea = document.getElementById('correct-groups');
    const invalidGroupsTextarea = document.getElementById('invalid-groups');

    // Current state
    let currentRecommendation = {
        group: [],
        reason: ""
    };

    // WEB01, WEB01a: Setup Puzzle
    setupPuzzleBtn.addEventListener('click', function() {
        const filePath = puzzleFileInput.value.trim();
        if (!filePath) {
            alert('Please enter a puzzle file path');
            return;
        }

        const formData = new FormData();
        formData.append('puzzle_file', filePath);

        fetch('/setup', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            remainingWordsTextarea.value = data.remaining_words.join(', ');
            statusTextarea.value = data.status;
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error setting up puzzle: ' + error.message);
        });
    });

    // WEB03: Get Next Recommendation
    getRecommendationBtn.addEventListener('click', function() {
        fetch('/recommend')
        .then(response => response.json())
        .then(data => {
            currentRecommendation.group = data.recommended_group;
            currentRecommendation.reason = data.connection_reason;
            
            recommendedGroupTextarea.value = data.recommended_group.join(', ');
            connectionReasonTextarea.value = data.connection_reason;
            recommenderTextarea.value = data.recommender;
        })
        .catch(error => {
            console.error('Error:', error);
        });
    });

    // WEB04: Process Feedback (Color Buttons)
    colorButtons.forEach(button => {
        button.addEventListener('click', function() {
            const color = this.getAttribute('data-color');
            
            fetch('/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    color: color,
                    group: currentRecommendation.group,
                    reason: currentRecommendation.reason
                })
            })
            .then(response => response.json())
            .then(updateUIWithFeedbackResponse)
            .catch(error => {
                console.error('Error:', error);
            });
        });
    });

    // WEB04: Process Feedback (Response Buttons)
    responseButtons.forEach(button => {
        button.addEventListener('click', function() {
            const response = this.getAttribute('data-response');
            
            fetch('/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    response: response,
                    group: currentRecommendation.group,
                    reason: currentRecommendation.reason
                })
            })
            .then(response => response.json())
            .then(updateUIWithFeedbackResponse)
            .catch(error => {
                console.error('Error:', error);
            });
        });
    });

    // WEB05: Manual Override
    manualOverrideBtn.addEventListener('click', function() {
        // Make textareas editable
        recommendedGroupTextarea.readOnly = false;
        connectionReasonTextarea.readOnly = false;
        
        // Show confirm button
        confirmOverrideBtn.style.display = 'inline-block';
    });

    confirmOverrideBtn.addEventListener('click', function() {
        // Parse the edited group
        const editedGroup = recommendedGroupTextarea.value.split(',').map(word => word.trim());
        const editedReason = connectionReasonTextarea.value;
        
        fetch('/override', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                group: editedGroup,
                reason: editedReason
            })
        })
        .then(response => response.json())
        .then(data => {
            // Update current recommendation
            currentRecommendation.group = editedGroup;
            currentRecommendation.reason = editedReason;
            
            // Reset textareas to readonly
            recommendedGroupTextarea.readOnly = true;
            connectionReasonTextarea.readOnly = true;
            
            // Hide confirm button
            confirmOverrideBtn.style.display = 'none';
            
            statusTextarea.value = data.status;
        })
        .catch(error => {
            console.error('Error:', error);
        });
    });

    // WEB08: Terminate
    terminateBtn.addEventListener('click', function() {
        if (confirm('Are you sure you want to terminate the puzzle-solving process?')) {
            fetch('/terminate', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                statusTextarea.value = data.status;
                alert(data.message);
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
    });

    // Helper Functions
    function updateUIWithFeedbackResponse(data) {
        remainingWordsTextarea.value = data.remaining_words.join(', ');
        statusTextarea.value = data.status;
        
        // Update correct groups display (WEB07)
        let correctGroupsText = '';
        for (const color in data.correct_groups) {
            if (data.correct_groups[color].length > 0) {
                correctGroupsText += `${color.toUpperCase()}:\n`;
                data.correct_groups[color].forEach(group => {
                    correctGroupsText += `- ${group.words.join(', ')} (${group.reason})\n`;
                });
                correctGroupsText += '\n';
            }
        }
        correctGroupsTextarea.value = correctGroupsText;
        
        // Update invalid groups display (WEB07)
        let invalidGroupsText = '';
        data.invalid_groups.forEach(group => {
            invalidGroupsText += `- ${group.words.join(', ')} (${group.reason})\n`;
            invalidGroupsText += `  Error type: ${group.error_type}\n\n`;
        });
        invalidGroupsTextarea.value = invalidGroupsText;
    }
});