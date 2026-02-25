document.addEventListener('DOMContentLoaded', () => {
    let currentConversationId = null;

    // Elements
    const conversationsList = document.getElementById('conversations-list');
    const chatMessages = document.getElementById('chat-messages');
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    const newChatBtn = document.getElementById('new-chat-btn');
    // toggleSidebarBtn and sidebar are handled in common.js now
    const currentChatTitle = document.getElementById('current-chat-title');

    // Custom UI Helpers
    // Now implemented in common.js

    // API Helpers
    async function apiCall(url, method = 'GET', body = null) {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        if (body) {
            options.body = JSON.stringify(body);
        }
        const response = await fetch(url, options);
        return response.json();
    }

    // Load Conversations
    async function loadConversations() {
        const conversations = await apiCall('/api/conversations');
        conversationsList.innerHTML = '';
        conversations.forEach(conv => {
            const div = document.createElement('div');
            div.className = `conversation-item ${conv.id === currentConversationId ? 'active' : ''}`;
            div.innerHTML = `
                <span class="title">${conv.title}</span>
                <button class="delete-chat-btn" data-id="${conv.id}">
                    <i class="fas fa-trash"></i>
                </button>
            `;
            div.onclick = (e) => {
                if (!e.target.closest('.delete-chat-btn')) {
                    selectConversation(conv.id, conv.title);
                }
            };
            
            // Delete button handler
            const deleteBtn = div.querySelector('.delete-chat-btn');
            deleteBtn.onclick = async (e) => {
                e.stopPropagation();
                // Use showCustomConfirm if available, otherwise native confirm
                let confirmed = false;
                if (typeof showCustomConfirm === 'function') {
                    confirmed = await showCustomConfirm('确定要删除这个对话吗？');
                } else {
                    confirmed = confirm('确定要删除这个对话吗？');
                }
                
                if (confirmed) {
                    await apiCall(`/api/conversations/${conv.id}`, 'DELETE');
                    if (currentConversationId === conv.id) {
                        currentConversationId = null;
                        chatMessages.innerHTML = `
                            <div class="welcome-message">
                                <i class="fas fa-robot fa-3x"></i>
                                <p>对话已删除</p>
                            </div>
                        `;
                        currentChatTitle.textContent = '选择或创建一个对话';
                    }
                    loadConversations();
                }
            };

            conversationsList.appendChild(div);
        });
    }

    // Select Conversation
    async function selectConversation(id, title) {
        currentConversationId = id;
        currentChatTitle.textContent = title;
        loadConversations(); // Re-render to update active class
        
        const messages = await apiCall(`/api/conversations/${id}/messages`);
        renderMessages(messages);
    }

    // Render Messages
    function renderMessages(messages) {
        chatMessages.innerHTML = '';
        if (messages.length === 0) {
            chatMessages.innerHTML = '<div class="welcome-message"><p>开始新的对话...</p></div>';
            return;
        }
        messages.forEach(msg => {
            appendMessage(msg.role, msg.content);
        });
        scrollToBottom();
    }

    // Append Message
    function appendMessage(role, content) {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        // Create content div to hold markdown or raw text
        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';
        contentDiv.innerHTML = marked.parse(content);
        div.appendChild(contentDiv);
        
        chatMessages.appendChild(div);
        scrollToBottom();
        return contentDiv; // Return content div for updating
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Send Message
    async function sendMessage() {
        const text = messageInput.value.trim();
        if (!text) return;

        if (!currentConversationId) {
            // Create new conversation if none selected
            const newConv = await apiCall('/api/conversations', 'POST', { title: text.substring(0, 20) + '...' });
            currentConversationId = newConv.id;
            currentChatTitle.textContent = newConv.title;
            await loadConversations();
            chatMessages.innerHTML = ''; // Clear welcome message
        }

        // Add user message to UI
        appendMessage('user', text);
        messageInput.value = '';
        sendBtn.disabled = true;

        try {
            // Create placeholder for assistant message
            // We will now create a container that can hold multiple elements (text, tool calls, etc.)
            const assistantMessageDiv = document.createElement('div');
            assistantMessageDiv.className = 'message assistant';
            const assistantContentDiv = document.createElement('div');
            assistantContentDiv.className = 'content';
            assistantMessageDiv.appendChild(assistantContentDiv);
            chatMessages.appendChild(assistantMessageDiv);
            scrollToBottom();

            let fullResponse = "";
            let currentToolCallDiv = null;

            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    conversation_id: currentConversationId,
                    message: text
                })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.trim()) continue;
                    
                    try {
                        const event = JSON.parse(line);
                        
                        if (event.type === 'content') {
                            fullResponse += event.data;
                            assistantContentDiv.innerHTML = marked.parse(fullResponse);
                        } else if (event.type === 'tool_start') {
                            // Create tool call UI
                            currentToolCallDiv = document.createElement('div');
                            currentToolCallDiv.className = 'tool-call-container';
                            currentToolCallDiv.innerHTML = `
                                <div class="tool-call-header">
                                    <span><i class="fas fa-tools"></i> 调用工具: ${event.tool}</span>
                                    <span class="tool-status-icon"></span>
                                </div>
                                <div class="tool-call-args" style="display:none;">${JSON.stringify(event.args, null, 2)}</div>
                            `;
                            // Allow toggling args
                            currentToolCallDiv.querySelector('.tool-call-header').onclick = () => {
                                const args = currentToolCallDiv.querySelector('.tool-call-args');
                                args.style.display = args.style.display === 'none' ? 'block' : 'none';
                            };
                            
                            // Insert BEFORE the text content if text is empty, or AFTER if text exists?
                            // Usually tools run before final answer, but sometimes interspersed.
                            // We'll append to the message div, but before the main content div if it's empty?
                            // For simplicity, let's append to the message div, before content div if content is empty.
                            if (!fullResponse) {
                                assistantMessageDiv.insertBefore(currentToolCallDiv, assistantContentDiv);
                            } else {
                                // If we already have text, tool usage might be weird in UI flow. 
                                // Let's just append before content div for now, assuming tools run first.
                                // Or append to message div.
                                assistantMessageDiv.appendChild(currentToolCallDiv);
                                // Move content div to bottom
                                assistantMessageDiv.appendChild(assistantContentDiv);
                            }
                        } else if (event.type === 'tool_end') {
                            if (currentToolCallDiv) {
                                const statusIcon = currentToolCallDiv.querySelector('.tool-status-icon');
                                statusIcon.classList.add('done');
                                statusIcon.innerHTML = '<i class="fas fa-check"></i>';
                                
                                // Optional: show result?
                                // const resultDiv = document.createElement('div');
                                // resultDiv.className = 'tool-result';
                                // resultDiv.textContent = 'Result: ' + (event.result.length > 100 ? event.result.substring(0, 100) + '...' : event.result);
                                // currentToolCallDiv.appendChild(resultDiv);
                                currentToolCallDiv = null;
                            }
                        } else if (event.type === 'error') {
                            fullResponse += `\n\n**Error:** ${event.content}`;
                            assistantContentDiv.innerHTML = marked.parse(fullResponse);
                        }
                    } catch (e) {
                        console.error('Error parsing stream line:', e, line);
                    }
                }
                scrollToBottom();
            }

        } catch (error) {
            appendMessage('assistant', 'Error: Failed to send message.');
            console.error(error);
        } finally {
            sendBtn.disabled = false;
            messageInput.focus();
        }
    }

    // Event Listeners
    newChatBtn.addEventListener('click', async () => {
        const newConv = await apiCall('/api/conversations', 'POST', { title: 'New Chat' });
        selectConversation(newConv.id, newConv.title);
    });

    sendBtn.addEventListener('click', sendMessage);

    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    messageInput.addEventListener('input', () => {
        sendBtn.disabled = messageInput.value.trim() === '';
    });



    // Initial Load
    loadConversations();

    // Poll for new messages (e.g. scheduled reminders)
    setInterval(async () => {
        if (!currentConversationId) return;
        
        // Don't poll if we are waiting for a response (sendBtn is disabled)
        if (sendBtn.disabled) return;

        try {
            const messages = await apiCall(`/api/conversations/${currentConversationId}/messages`);
            
            // Count existing messages (excluding tool call containers if they are not .message)
            // appendMessage creates <div class="message ...">
            const currentElements = chatMessages.querySelectorAll('.message');
            const currentCount = currentElements.length;
            
            if (messages.length > currentCount) {
                // If we had a welcome message, clear it first
                if (chatMessages.querySelector('.welcome-message')) {
                    chatMessages.innerHTML = '';
                }

                // Append new messages
                const newMessages = messages.slice(currentCount);
                newMessages.forEach(msg => {
                     appendMessage(msg.role, msg.content);
                });
                
                if (newMessages.length > 0) {
                    // Play a notification sound if supported? 
                    // Or just scroll
                    scrollToBottom();
                    
                    // Optional: Browser Notification
                    if (Notification.permission === "granted") {
                        new Notification("1052 AI", { body: newMessages[newMessages.length-1].content });
                    } else if (Notification.permission !== "denied") {
                        Notification.requestPermission().then(permission => {
                            if (permission === "granted") {
                                new Notification("1052 AI", { body: newMessages[newMessages.length-1].content });
                            }
                        });
                    }
                }
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 5000);
});
