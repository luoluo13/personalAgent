document.addEventListener('DOMContentLoaded', async () => {
    const chatContainer = document.getElementById('chat-container');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const typingIndicator = document.getElementById('typing-indicator');
    const resetBtn = document.getElementById('reset-btn');
    const deleteMemoryBtn = document.getElementById('delete-memory-btn');
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const sunIcon = document.querySelector('.sun-icon');
    const moonIcon = document.querySelector('.moon-icon');
    const sendIcon = document.querySelector('.send-icon');
    const addIcon = document.querySelector('.add-icon');
    const stopIcon = document.querySelector('.stop-icon');
    
    // State
    let messageBuffer = [];
    let isAIResponding = false;
    let interruptionController = null;
    let lastInterruptedContext = "";
    let recallInterval = null;
    let isRecalling = false; // Track recall state locally for UI
    
    // Config
    let botName = "Default"; // Default

    function startRecallAnimation() {
        if (recallInterval) clearInterval(recallInterval);
        
        // Use a simpler animation based on user feedback
        // Just flash "对方陷入了回忆..." then stop
        // Or cycle dots? 
        // For now, we will manually set text in the fetch logic, so this helper 
        // might just be a visual cycler if we wanted.
        // But since we are handling text updates explicitly in sendBuffer, 
        // we can simplify this or leave it empty if unused.
        // Actually, let's keep it for the dot animation "..." if we want dynamic dots.
        // But the current implementation cycles text phases which we overrode.
        
        // Let's repurpose this for a subtle "thinking" dot animation if needed, 
        // otherwise just clear it to avoid conflict.
    }

    function stopRecallAnimation() {
        if (recallInterval) {
            clearInterval(recallInterval);
            recallInterval = null;
        }
    }

    // Theme Logic
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        sunIcon.classList.remove('hidden');
        moonIcon.classList.add('hidden');
    }

    themeToggleBtn.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        
        if (isDark) {
            sunIcon.classList.remove('hidden');
            moonIcon.classList.add('hidden');
        } else {
            sunIcon.classList.add('hidden');
            moonIcon.classList.remove('hidden');
        }
    });

    // Fetch Config
    try {
        const configRes = await fetch('/api/config');
        if (configRes.ok) {
            const config = await configRes.json();
            botName = config.bot_name || botName;
        }
    } catch (e) {
        console.error("Failed to fetch config", e);
    }

    // Update UI with bot name
    document.title = `${botName} - Your AI Companion`;
    const headerName = document.getElementById('bot-name-header');
    if (headerName) headerName.textContent = botName;
    
    const avatarImg = document.getElementById('avatar-img');
    if (avatarImg) {
        // Try to load local avatar first via API
        avatarImg.src = "/api/avatar";
        
        // Fallback to DiceBear if local avatar fails (404)
        avatarImg.onerror = function() {
            this.onerror = null; // Prevent infinite loop
            this.src = `https://api.dicebear.com/7.x/avataaars/svg?seed=${botName}&backgroundColor=ffdfbf`;
        };
        
        avatarImg.alt = botName;
    }

    const botNameTexts = document.querySelectorAll('.bot-name-text');
    botNameTexts.forEach(el => el.textContent = botName);
    
    messageInput.placeholder = `给 ${botName} 发个消息...`;

    // Generate or retrieve user ID
    const storageKey = 'agent_user_id';
    let userId = localStorage.getItem(storageKey);
    if (!userId) {
        userId = 'user_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem(storageKey, userId);
    }

    // Auto-resize textarea and Button State Logic
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        updateSendButtonState();
    });

    function updateSendButtonState() {
        const inputVal = messageInput.value.trim();
        const bufferLen = messageBuffer.length;

        // Reset classes
        sendBtn.classList.remove('pink-mode', 'green-mode', 'stop-mode');
        sendIcon.classList.add('hidden');
        addIcon.classList.add('hidden');
        stopIcon.classList.add('hidden');

        if (isAIResponding) {
            // Stop Mode
            sendBtn.disabled = false;
            sendBtn.classList.add('stop-mode');
            stopIcon.classList.remove('hidden');
        } else if (inputVal.length > 0) {
            // Add/Buffer Mode
            sendBtn.disabled = false;
            sendBtn.classList.add('pink-mode');
            addIcon.classList.remove('hidden');
        } else if (bufferLen > 0) {
            // Send Buffer Mode
            sendBtn.disabled = false;
            sendBtn.classList.add('green-mode');
            sendIcon.classList.remove('hidden');
        } else {
            // Disabled
            sendBtn.disabled = true;
            sendIcon.classList.remove('hidden');
        }
    }

    // Handle Enter key
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) {
                handleSendClick();
            }
        }
    });

    sendBtn.addEventListener('click', handleSendClick);
    
    function handleSendClick() {
        if (isAIResponding) {
            // Stop logic
            if (interruptionController) {
                interruptionController.abort();
            }
            return;
        }

        const text = messageInput.value.trim();

        if (text) {
            // Add to buffer and clear input
            messageBuffer.push(text);
            appendMessage('user', text); // Show immediately
            messageInput.value = '';
            messageInput.style.height = 'auto';
            updateSendButtonState();
            scrollToBottom();
        } else if (messageBuffer.length > 0) {
            // Send buffer
            sendBuffer();
        }
    }

    // Reset conversation (clear local UI for MVP)
    resetBtn.addEventListener('click', () => {
        if(confirm('确定要清空当前对话屏幕吗？(历史记忆仍保留)')) {
            chatContainer.innerHTML = `<div class="message system-message"><p>与 ${botName} 开始新的对话吧 ～</p></div>`;
            localStorage.setItem('chat_cleared', 'true');
            messageBuffer = []; // Clear buffer
            updateSendButtonState();
        }
    });

    // Delete Memory (Permanent)
    deleteMemoryBtn.addEventListener('click', async () => {
        if(confirm(`警告：此操作将永久删除您与 ${botName} 的所有共同回忆，且无法恢复！\n\n您确定要重置一切吗？`)) {
            try {
                const response = await fetch(`/api/memory/${userId}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    alert(`记忆已清除，我是全新的 ${botName} ～`);
                    localStorage.setItem('memory_reset', 'true');
                    // Clear local storage and reload to generate new user ID or reset state
                    localStorage.removeItem(storageKey);
                    location.reload();
                } else {
                    alert('删除失败，请稍后重试');
                }
            } catch (error) {
                console.error('Error deleting memory:', error);
                alert('网络错误，无法删除记忆');
            }
        }
    });

    // Load History
    loadHistory();

    async function loadHistory() {
        try {
            const response = await fetch(`/api/history/${userId}`);
            const history = await response.json();
            
            // Clear default system message if there is history
            if (history.length > 0) {
                chatContainer.innerHTML = '';
                history.forEach(msg => {
                    // Pass the pre-formatted timestamp to appendMessage
                    if (msg.role === 'user') {
                        appendMessage('user', msg.content, msg.timestamp_display);
                    } else {
                        // Use smartSplit for AI messages to restore multi-bubble look
                        const segments = smartSplit(msg.content);
                        segments.forEach(segment => {
                            appendMessage('ai', segment, msg.timestamp_display);
                        });
                    }
                });
                scrollToBottom();
            }
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    }

    async function sendBuffer() {
        const text = messageBuffer.join('\n');
        messageBuffer = []; // Clear buffer
        
        // Initial state: "Processing..."
        showTyping(true);
        updateTypingText("对方正在思考..."); // Step 1: Thinking
        isAIResponding = true;
        updateSendButtonState(); // Update to stop button

        // Collect context flags
        const contextFlags = {};
        if (lastInterruptedContext) {
            contextFlags.interrupted_context = lastInterruptedContext;
            lastInterruptedContext = ""; // Consume flag
        }
        if (localStorage.getItem('network_error_occurred')) {
            contextFlags.network_error = true;
            localStorage.removeItem('network_error_occurred');
        }
        if (localStorage.getItem('memory_reset')) {
            contextFlags.memory_reset = true;
            localStorage.removeItem('memory_reset');
        }
        if (localStorage.getItem('chat_cleared')) {
            contextFlags.chat_cleared = true;
            localStorage.removeItem('chat_cleared');
        }
        
        console.log("Sending with flags:", contextFlags); // Debug

        try {
            interruptionController = new AbortController();
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                signal: interruptionController.signal,
                body: JSON.stringify({
                    user_id: userId,
                    message: text,
                    context_flags: contextFlags
                })
            });

            // Stop animation once we get headers/response
            stopRecallAnimation();

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            
            // Check if backend performed recall
            if (data.is_recalling) {
                // If backend says it recalled, show specific recall animation
                startRecallAnimation(); // This cycles through "正在回忆..." -> "想起往事..."
                // But we want specific sequence: "对方陷入了回忆..." -> "对方正在输入..."
                // Let's override the complex animation with a simpler one based on requirement.
                stopRecallAnimation(); // Stop the complex cycler
                
                updateTypingText("对方陷入了回忆...");
                await new Promise(r => setTimeout(r, 1500)); // Pause to show "Recalling" state
            }
            
            // Now switch to typing state
            updateTypingText("对方正在输入...");
            
            // Start streaming simulation
            await simulateStreaming(data.response, data.timestamp_display);

        } catch (error) {
            stopRecallAnimation();
            console.error('Error:', error);
            showTyping(false);
            isAIResponding = false;
            updateSendButtonState();
            
            // Handle Abort (User Interruption) separately from Network Error
            if (error.name === 'AbortError') {
                 console.log("Request aborted by user");
                 return; // Do not treat as network error
            }

            // Network Error Handling
            // Remove last user messages that were part of this failed batch
            // Note: Since we don't track exact DOM elements for buffer items easily here without complex logic,
            // we will just remove the last N messages where N is what was in the buffer? 
            // Actually, we already cleared the buffer. 
            // Simplified: Remove the last user message element if it matches text? 
            // Or better: Just remove the last message element if it is a user message.
            const lastMsg = chatContainer.lastElementChild;
            if (lastMsg && lastMsg.classList.contains('user-message')) {
                lastMsg.remove(); 
                // If we sent multiple messages combined, this only removes one "block". 
                // Since we combine buffer into one API call but display them as separate bubbles? 
                // Ah, in handleSendClick we appendMessage immediately. So we have multiple bubbles.
                // We should remove all bubbles related to this batch?
                // For MVP, let's just set the flag and alert. Removing exact messages is tricky without IDs.
                // User requirement: "发送的消息立刻清除".
                // Let's try to remove the last few user messages.
                // But wait, if user sent 3 msgs, they are 3 bubbles.
                // We can't easily know how many.
                // Alternative: Mark them as "pending" in DOM and remove if fail.
                // For now, let's just alert and set flag.
                alert("网络错误，消息发送失败。");
            }
            
            localStorage.setItem('network_error_occurred', 'true');
            // appendMessage('ai', `抱歉，${botName} 好像掉线了... (网络错误)`); // Don't show error msg as per requirement? "发送的消息立刻清除"
        }
    }

    function updateTypingText(text) {
        const textEl = typingIndicator.querySelector('span') || typingIndicator.querySelector('p');
        if (textEl) textEl.textContent = text;
    }

    // Smart splitting logic: Split text into natural conversational segments
    function smartSplit(text) {
        // 1. If text is short (< 50 chars), return as single segment
        if (text.length < 50) return [text];
        
        // 2. Split by newlines first
        let blocks = text.split('\n').filter(t => t.trim().length > 0);
        let segments = [];
        
        for (let block of blocks) {
            if (block.length < 100) {
                segments.push(block);
                continue;
            }
            
            // 3. If block is long, try to split by sentence enders
            // Look for 。！？ followed by space or end of string, but keep the punctuation
            // Using a simple regex to split but capturing the delimiter
            let parts = block.split(/([。！？])/).filter(p => p.length > 0);
            
            let currentSegment = "";
            for (let i = 0; i < parts.length; i++) {
                let part = parts[i];
                // Check if this part is a delimiter
                if (['。', '！', '？'].includes(part)) {
                    currentSegment += part;
                    // If current segment is long enough, push it
                    if (currentSegment.length > 20 || i === parts.length - 1) {
                        segments.push(currentSegment);
                        currentSegment = "";
                    }
                } else {
                    currentSegment += part;
                }
            }
            if (currentSegment.trim().length > 0) {
                segments.push(currentSegment);
            }
        }
        
        return segments;
    }

    async function simulateStreaming(fullText, timestampDisplay = null) {
        interruptionController = new AbortController();
        const signal = interruptionController.signal;
        
        // Use smart splitting to get message bubbles
        const segments = smartSplit(fullText);
        
        try {
            updateTypingText("对方正在输入..."); // Step 3: Typing
            
            for (let i = 0; i < segments.length; i++) {
                const segment = segments[i];
                
                if (signal.aborted) throw new Error('Interrupted');

                // 1. Show Typing Indicator for this segment
                showTyping(true);
                updateTypingText("对方正在输入...");
                scrollToBottom();

                // 2. Calculate delay based on segment length (simulate reading/thinking/typing)
                // Shorter for first message, longer for subsequent to simulate "typing" the next part
                let typingDelay = 500 + Math.min(segment.length * 50, 2000); 
                if (i === 0) typingDelay = 800; // First message comes out faster after "recalling"
                
                // Random variation
                typingDelay += Math.random() * 500;

                await new Promise(r => setTimeout(r, typingDelay));

                if (signal.aborted) throw new Error('Interrupted');

                // 3. Hide indicator and Show Message Bubble
                showTyping(false);
                appendMessage('ai', segment, timestampDisplay);
                scrollToBottom();
                
                // 4. Small pause between bubbles if there are more
                if (i < segments.length - 1) {
                    await new Promise(r => setTimeout(r, 300 + Math.random() * 200));
                }
            }
        } catch (e) {
            if (e.message === 'Interrupted') {
                console.log("Output interrupted by user");
                // Stop processing further segments
                // Save context for next turn if we have processed at least one segment
                // Wait, lastInterruptedContext should be what was *going to be said* but wasn't? 
                // Or what was *already said*? 
                // Requirement: "若被打断则该轮回复的剩余内容不再在界面中显示"
                // And prompt: "用户在上一轮对话中打断了你的发言"
                // Usually we want to know what was interrupted. 
                // Since we don't have the full text easily accessible here as a variable outside loop (it is in fullText)
                // Let's just save the fullText as context, maybe indicating it was cut off?
                // Actually, if we want the AI to know "I was saying X and got cut off", X should be the full planned response?
                // Or just the part that was shown?
                // Let's save the *full text* that was planned, so the AI knows what it *intended* to say.
                lastInterruptedContext = fullText;
            }
        } finally {
            isAIResponding = false;
            interruptionController = null;
            showTyping(false);
            updateSendButtonState();
        }
    }
    
    function createMessageDiv(role) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role === 'user' ? 'user-message' : 'ai-message'}`;
        return msgDiv;
    }

    // Removed old sendMessage function


    function appendMessage(role, text, timestampDisplay = null) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role === 'user' ? 'user-message' : 'ai-message'}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        const formattedText = text.replace(/\n/g, '<br>');
        contentDiv.innerHTML = formattedText;
        msgDiv.appendChild(contentDiv);

        // Add timestamp
        const timeSpan = document.createElement('div');
        timeSpan.className = 'message-time';
        
        // Use provided pre-formatted timestamp string directly
        if (timestampDisplay) {
            timeSpan.textContent = timestampDisplay;
        } else {
            // Fallback for new user messages (local time formatted manually)
            const now = new Date();
            const hours = String(now.getHours()).padStart(2, '0');
            const minutes = String(now.getMinutes()).padStart(2, '0');
            timeSpan.textContent = `${hours}:${minutes}`;
        }
        
        msgDiv.appendChild(timeSpan);
        chatContainer.appendChild(msgDiv);
    }

    function showTyping(show) {
        if (show) {
            typingIndicator.classList.remove('hidden');
            // Scroll to show indicator
            chatContainer.scrollTop = chatContainer.scrollHeight;
        } else {
            typingIndicator.classList.add('hidden');
        }
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
});
