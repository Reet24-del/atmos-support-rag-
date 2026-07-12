document.addEventListener("DOMContentLoaded", () => {
    const chatForm = document.getElementById("chat-form");
    const userInput = document.getElementById("user-input");
    const messageFeed = document.getElementById("message-feed");
    const clearChatBtn = document.getElementById("clear-chat-btn");
    const quickReplyPills = document.querySelectorAll(".quick-reply-pill");
    const faqCards = document.querySelectorAll(".faq-card");

    // Sidebar Mobile Drawer Elements
    const toggleBtn = document.getElementById("sidebar-toggle-btn");
    const closeBtn = document.getElementById("sidebar-close-btn");
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebar-overlay");

    // Open Mobile Sidebar Drawer
    if (toggleBtn) {
        toggleBtn.addEventListener("click", () => {
            sidebar.classList.add("open");
            overlay.classList.add("active");
        });
    }

    // Close Mobile Sidebar Drawer
    if (closeBtn) {
        closeBtn.addEventListener("click", () => {
            sidebar.classList.remove("open");
            overlay.classList.remove("active");
        });
    }

    if (overlay) {
        overlay.addEventListener("click", () => {
            sidebar.classList.remove("open");
            overlay.classList.remove("active");
        });
    }

    // Clear chat history
    clearChatBtn.addEventListener("click", async () => {
        if (confirm("Are you sure you want to clear the chat history?")) {
            try {
                const response = await fetch("/clear", { method: "POST" });
                if (response.ok) {
                    messageFeed.innerHTML = "";
                    appendMessage("assistant", "Hello! Welcome to Atmos Support. I am your virtual customer service assistant. How can I help you today?\n\nYou can click on any of the common topics above, or type your question below. I can answer questions about shipping rates, service tiers, business hours, and return processes.");
                }
            } catch (err) {
                console.error("Error clearing chat:", err);
            }
        }
    });

    // Toggle FAQ Cards
    faqCards.forEach(card => {
        card.addEventListener("click", () => {
            card.classList.toggle("active");
        });
    });

    // Quick Action Pill Clicking
    quickReplyPills.forEach(pill => {
        pill.addEventListener("click", () => {
            const text = pill.getAttribute("data-query");
            if (text) {
                sendUserQuery(text);
            }
        });
    });

    // Form Submission
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = userInput.value.trim();
        if (text) {
            sendUserQuery(text);
            userInput.value = "";
        }
    });

    // Core Messaging pipeline
    async function sendUserQuery(query) {
        // 1. Append user bubble
        appendMessage("user", query);
        
        // 2. Append assistant typing indicator
        const typingIndicator = appendTypingIndicator();
        scrollToBottom();

        try {
            const response = await fetch("/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: query })
            });

            // Remove typing indicator
            typingIndicator.remove();

            if (response.ok) {
                const data = await response.json();
                appendMessage("assistant", data.answer, data.citations);
            } else {
                appendMessage("assistant", "Sorry, I encountered an issue processing that request. Please try again.");
            }
        } catch (err) {
            typingIndicator.remove();
            console.error("Network error:", err);
            appendMessage("assistant", "Error: Connection lost. Verify that the local FastAPI server is running.");
        }
        
        scrollToBottom();
    }

    // Append standard message bubble
    function appendMessage(role, text, citations = []) {
        const row = document.createElement("div");
        row.className = `message-row ${role}`;

        const bubble = document.createElement("div");
        bubble.className = "message-bubble";

        // Parse markdown to HTML using Marked.js
        const formattedText = marked.parse(text);
        bubble.innerHTML = formattedText;

        // Handle citations
        if (citations && citations.length > 0) {
            const citationDiv = document.createElement("div");
            citationDiv.className = "citation-container";
            
            const header = document.createElement("div");
            header.className = "citation-header";
            header.innerHTML = "<span>📄 Citations & Sources</span>";
            
            const details = document.createElement("div");
            details.className = "citation-details";
            
            citations.forEach(cit => {
                const badge = document.createElement("div");
                badge.className = "citation-badge";
                badge.innerText = cit.section;
                details.appendChild(badge);
                
                const contentText = document.createElement("p");
                contentText.style.fontSize = "0.75rem";
                contentText.style.marginTop = "0.3rem";
                contentText.style.marginBottom = "0.6rem";
                contentText.style.borderBottom = "1px solid #fce7f3";
                contentText.style.paddingBottom = "0.3rem";
                contentText.innerText = cit.content;
                details.appendChild(contentText);
            });

            header.addEventListener("click", () => {
                citationDiv.classList.toggle("active");
                scrollToBottom();
            });

            citationDiv.appendChild(header);
            citationDiv.appendChild(details);
            bubble.appendChild(citationDiv);
        }

        row.appendChild(bubble);
        messageFeed.appendChild(row);
        scrollToBottom();
    }

    // Append loading dots
    function appendTypingIndicator() {
        const row = document.createElement("div");
        row.className = "message-row assistant";

        const bubble = document.createElement("div");
        bubble.className = "message-bubble";
        bubble.innerHTML = `
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        row.appendChild(bubble);
        messageFeed.appendChild(row);
        return row;
    }

    // Smooth Scroll container
    function scrollToBottom() {
        messageFeed.scrollTo({
            top: messageFeed.scrollHeight,
            behavior: "smooth"
        });
    }

    // Initial load message if feed is empty
    if (messageFeed.children.length === 0) {
        appendMessage("assistant", "Hello! Welcome to Atmos Support. I am your virtual customer service assistant. How can I help you today?\n\nYou can click on any of the common topics above, or type your question below. I can answer questions about shipping rates, service tiers, business hours, and return processes.");
    }
});
