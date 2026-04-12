document.addEventListener('DOMContentLoaded', () => {
    const connectBtn = document.getElementById('connect-btn');
    const generateBtn = document.getElementById('generate-btn');
    const publishBtn = document.getElementById('publish-btn');
    const topicText = document.getElementById('topic-text');
    const descText = document.getElementById('desc-text');
    const promptStatus = document.getElementById('prompt-status');
    const toast = document.getElementById('toast');

    let currentConcept = null;

    const authUrl = "https://www.pinterest.com/oauth/?client_id=1561156&redirect_uri=http://localhost:8080&response_type=code&scope=boards:read,boards:write,pins:read,pins:write,user_accounts:read";

    connectBtn.addEventListener('click', () => {
        connectBtn.textContent = "Connecting...";
        setTimeout(() => {
            window.open(authUrl, '_blank');
            connectBtn.textContent = "Pinterest Connected ✅";
            connectBtn.classList.remove('btn-primary');
            connectBtn.classList.add('btn-secondary');
        }, 800);
    });

    generateBtn.addEventListener('click', () => {
        generateBtn.classList.add('disabled');
        publishBtn.classList.add('disabled');
        topicText.textContent = "...";
        descText.textContent = "...";
        promptStatus.textContent = "Selecting WordPress Article...";

        fetch('/api/generate')
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    currentConcept = data;
                    
                    setTimeout(() => {
                        topicText.textContent = data.topic;
                        descText.textContent = data.desc;
                        topicText.style.color = "#00FF85";
                        promptStatus.textContent = "AI Goal: Sync Pin to Site Article ✅";
                    }, 500);

                    setTimeout(() => {
                        promptStatus.textContent = "SiliconFlow rendering background art...";
                        promptStatus.style.color = "#00c2ff";
                        
                        publishBtn.classList.remove('disabled');
                        generateBtn.classList.remove('disabled');
                        generateBtn.textContent = "✨ Sync Another Article";
                    }, 2000);

                } else {
                    toast.textContent = "AI Error: " + data.message;
                    toast.classList.add('show');
                    generateBtn.classList.remove('disabled');
                    setTimeout(() => toast.classList.remove('show'), 4000);
                }
            })
            .catch(err => {
                toast.textContent = "Connection Error: " + err;
                toast.classList.add('show');
                generateBtn.classList.remove('disabled');
            });
    });

    publishBtn.addEventListener('click', () => {
        publishBtn.textContent = "Linking Pin to Site...";
        publishBtn.classList.add('disabled');
        
        fetch('/api/publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentConcept)
        })
            .then(r => r.json())
            .then(data => {
                if (data.status === 'success') {
                    toast.textContent = "Live Link Created! Pin ID: " + data.pin_id;
                    toast.classList.add('show');
                    publishBtn.textContent = "Published Successfully! ✅";
                    
                    // Small delay then show the link in log
                    setTimeout(() => {
                        promptStatus.textContent = "Article Pinned: " + currentConcept.url;
                        promptStatus.style.color = "#FFF";
                    }, 1000);
                } else {
                    toast.textContent = "Publish Error: " + data.message;
                    toast.classList.add('show');
                    publishBtn.textContent = "Publish Failed ❌";
                }
                
                setTimeout(() => {
                    toast.classList.remove('show');
                    publishBtn.textContent = "🚀 Publish to Pinterest Board";
                    publishBtn.classList.remove('disabled');
                }, 5000);
            })
            .catch(err => {
                toast.textContent = "Server Error: " + err;
                toast.classList.add('show');
                publishBtn.classList.remove('disabled');
            });
    });
});
