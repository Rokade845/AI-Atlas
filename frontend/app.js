const API_BASE = window.location.origin;

// State management
let state = {
    currentScreen: 'directory',
    sectors: [],
    companies: [],
    selectedSegment: '',
    searchQuery: '',
    filterType: '',
    filterMaturity: '',
    watchlist: [],
    newsFeed: [],
    activeProfileId: null,
    activeProfileTab: 'overview',
    discoveredCandidates: [],
    feedFilter: 'watched' // 'watched' or 'all'
};

// Start application
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    setupRoutes();
    setupEventListeners();
    await checkApiStatus();
    await loadInitialData();
}

// Router
function setupRoutes() {
    const handleRoute = () => {
        const hash = window.location.hash || '#/directory';
        const parts = hash.split('/');
        const route = parts[1] || 'directory';
        
        switchScreen(route);
        
        // If route is company detail in URL (e.g. #/company/12)
        if (route === 'company' && parts[2]) {
            openCompanyProfile(parseInt(parts[2]));
            // Switch menu active to directory
            setActiveMenuItem('directory');
        } else {
            setActiveMenuItem(route);
        }
    };
    
    window.addEventListener('hashchange', handleRoute);
    handleRoute(); // Run once on startup
}

function switchScreen(screenId) {
    state.currentScreen = screenId;
    
    // Hide all screens
    document.querySelectorAll('.app-screen').forEach(s => s.classList.remove('active'));
    
    // Show correct screen
    const targetScreen = document.getElementById(`screen-${screenId}`);
    if (targetScreen) {
        targetScreen.classList.add('active');
    }
    
    // Update Page Header Title
    const pageTitle = document.getElementById('page-title');
    if (pageTitle) {
        if (screenId === 'directory') pageTitle.textContent = 'Company Directory';
        else if (screenId === 'ask') pageTitle.textContent = 'Ask AI Grounded Assistant';
        else if (screenId === 'watchlist') pageTitle.textContent = 'My Watchlist & Feed';
        else if (screenId === 'admin') pageTitle.textContent = 'Admin Console';
    }
    
    // Screen specific logic
    if (screenId === 'watchlist') {
        loadWatchlistScreen();
    } else if (screenId === 'admin') {
        loadAdminScreen();
    } else if (screenId === 'directory') {
        loadCompanies();
    }
}

function setActiveMenuItem(route) {
    document.querySelectorAll('.menu-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeItem = document.getElementById(`menu-${route}`);
    if (activeItem) {
        activeItem.classList.add('active');
    }
}

// Event Listeners Setup
function setupEventListeners() {
    // Search inputs
    const dirSearch = document.getElementById('dir-search');
    if (dirSearch) {
        dirSearch.addEventListener('input', debounce((e) => {
            state.searchQuery = e.target.value;
            loadCompanies();
        }, 300));
    }
    
    // Select Filters
    const filterType = document.getElementById('filter-type');
    if (filterType) {
        filterType.addEventListener('change', (e) => {
            state.filterType = e.target.value;
            loadCompanies();
        });
    }
    
    const filterMaturity = document.getElementById('filter-maturity');
    if (filterMaturity) {
        filterMaturity.addEventListener('change', (e) => {
            state.filterMaturity = e.target.value;
            loadCompanies();
        });
    }
    
    // Profile Slideout close
    const profileCloseBtn = document.getElementById('profile-close-btn');
    if (profileCloseBtn) {
        profileCloseBtn.addEventListener('click', closeCompanyProfile);
    }
    const profileOverlay = document.getElementById('profile-overlay');
    if (profileOverlay) {
        profileOverlay.addEventListener('click', closeCompanyProfile);
    }
    
    // On-Demand News Refresh Button
    const btnRefreshNews = document.getElementById('btn-refresh-news');
    if (btnRefreshNews) {
        btnRefreshNews.addEventListener('click', refreshActiveCompanyNews);
    }
    
    // Profile Watchlist Follow Toggle
    const profileFollowBtn = document.getElementById('profile-follow-btn');
    if (profileFollowBtn) {
        profileFollowBtn.addEventListener('click', toggleFollowStatus);
    }
    
    // Chat Submit Form
    const chatForm = document.getElementById('chat-form');
    if (chatForm) {
        chatForm.addEventListener('submit', handleChatSubmit);
    }
    
    // Chat Suggestion Buttons
    document.querySelectorAll('.suggest-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const query = e.target.textContent;
            const chatInput = document.getElementById('chat-input');
            if (chatInput) {
                chatInput.value = query;
                chatForm.dispatchEvent(new Event('submit'));
            }
        });
    });
    
    // Admin Discovery Search Form
    const discoveryForm = document.getElementById('discovery-search-form');
    if (discoveryForm) {
        discoveryForm.addEventListener('submit', handleCompanyDiscoverySubmit);
    }
    
    // Admin Company Data Form (Manual CRUD)
    const companyDataForm = document.getElementById('company-data-form');
    if (companyDataForm) {
        companyDataForm.addEventListener('submit', handleManualCompanySubmit);
    }
    
    const btnCancelEdit = document.getElementById('btn-cancel-edit');
    if (btnCancelEdit) {
        btnCancelEdit.addEventListener('click', resetManualForm);
    }
    
    const manageSearch = document.getElementById('manage-search');
    if (manageSearch) {
        manageSearch.addEventListener('input', debounce((e) => {
            renderAdminCompaniesList(e.target.value);
        }, 200));
    }
    
    // Feed Toggle buttons
    const toggleWatched = document.getElementById('feed-toggle-watched');
    const toggleAll = document.getElementById('feed-toggle-all');
    if (toggleWatched && toggleAll) {
        toggleWatched.addEventListener('click', () => {
            toggleWatched.classList.add('active');
            toggleAll.classList.remove('active');
            state.feedFilter = 'watched';
            loadWatchlistScreen();
        });
        toggleAll.addEventListener('click', () => {
            toggleAll.classList.add('active');
            toggleWatched.classList.remove('active');
            state.feedFilter = 'all';
            loadWatchlistScreen();
        });
    }
}

// Initial Data Loading
async function checkApiStatus() {
    const indicator = document.getElementById('api-status-indicator');
    const dot = indicator.querySelector('.status-dot');
    const text = indicator.querySelector('.status-text');
    
    try {
        const response = await fetch(`${API_BASE}/api/sectors`);
        if (response.ok) {
            dot.className = 'status-dot active';
            text.textContent = 'Knowledge Base Connected';
        } else {
            dot.className = 'status-dot warning';
            text.textContent = 'API Error';
        }
    } catch (err) {
        dot.className = 'status-dot danger';
        text.textContent = 'Server Offline';
        showToast('Error connecting to backend server. Make sure it is running.', 'danger');
    }
}

async function loadInitialData() {
    try {
        // Load sectors
        const res = await fetch(`${API_BASE}/api/sectors`);
        if (res.ok) {
            state.sectors = await res.json();
            renderSegmentTabs();
        }
        
        // Load initial companies list
        await loadCompanies();
        
    } catch (err) {
        console.error('Error loading initial data:', err);
    }
}

// Render Segment Pills
function renderSegmentTabs() {
    const container = document.getElementById('segment-tabs-list');
    if (!container) return;
    
    // Clear dynamic tabs (keep the first 'All Segments' tab)
    const allTab = container.querySelector('[data-id=""]');
    container.innerHTML = '';
    container.appendChild(allTab);
    
    state.sectors.forEach(s => {
        const btn = document.createElement('button');
        btn.className = 'segment-tab';
        btn.setAttribute('data-id', s.id);
        btn.textContent = s.name.split(' ')[0] + ' ' + (s.name.split(' ')[1] || ''); // truncate for pill size
        btn.title = s.name;
        
        btn.addEventListener('click', () => {
            document.querySelectorAll('.segment-tab').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
            state.selectedSegment = s.id;
            loadCompanies();
        });
        
        container.appendChild(btn);
    });
    
    // Re-attach listener to 'All Segments' tab
    allTab.addEventListener('click', () => {
        document.querySelectorAll('.segment-tab').forEach(t => t.classList.remove('active'));
        allTab.classList.add('active');
        state.selectedSegment = '';
        loadCompanies();
    });
}

// Fetch & Load Companies
async function loadCompanies() {
    const grid = document.getElementById('companies-grid-list');
    if (!grid) return;
    
    grid.innerHTML = '<div class="loading-placeholder">Searching intelligence directory...</div>';
    
    try {
        let url = `${API_BASE}/api/companies?`;
        const params = [];
        
        if (state.searchQuery) params.push(`search=${encodeURIComponent(state.searchQuery)}`);
        if (state.selectedSegment) params.push(`segment=${state.selectedSegment}`);
        if (state.filterType) params.push(`company_type=${state.filterType}`);
        if (state.filterMaturity) params.push(`maturity=${state.filterMaturity}`);
        
        url += params.join('&');
        
        const res = await fetch(url);
        if (res.ok) {
            state.companies = await res.json();
            renderCompaniesGrid();
        } else {
            grid.innerHTML = '<div class="empty-state">Failed to fetch companies. Check console.</div>';
        }
    } catch (err) {
        grid.innerHTML = '<div class="empty-state">Error connecting to server.</div>';
    }
}

function renderCompaniesGrid() {
    const grid = document.getElementById('companies-grid-list');
    if (!grid) return;
    
    if (state.companies.length === 0) {
        grid.innerHTML = '<div class="empty-state">No companies found matching the filters.</div>';
        return;
    }
    
    grid.innerHTML = '';
    state.companies.forEach(c => {
        const card = document.createElement('div');
        card.className = 'company-card';
        card.addEventListener('click', () => {
            window.location.hash = `#/company/${c.id}`;
        });
        
        // Initials for logo
        const initials = c.name ? c.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : 'CO';
        
        // Maturity Rating stars
        let maturityVal = parseInt(c.maturity) || 1;
        let stars = '★'.repeat(maturityVal) + '☆'.repeat(Math.max(0, 5 - maturityVal));
        
        const typeClass = c.company_type ? c.company_type.toLowerCase() : 'incumbent';
        
        card.innerHTML = `
            <div class="card-header">
                <div class="logo-placeholder">${initials}</div>
                <div class="card-title-area">
                    <h3>${c.name}</h3>
                    <span class="country-badge">${c.germany_presence || c.country}</span>
                </div>
            </div>
            <div class="card-body">
                <p class="card-category">${c.ai_category || 'AI Solutions'}</p>
                <p class="card-desc">${c.use_cases || 'Deploying AI use cases in F&B manufacturing.'}</p>
            </div>
            <div class="card-footer">
                <span class="maturity-stars" title="Maturity Rating: ${c.maturity}">${stars}</span>
                <span class="card-type-badge ${typeClass}">${c.company_type || 'Incumbent'}</span>
            </div>
        `;
        
        grid.appendChild(card);
    });
}

// Slideout Company Profile Logic
async function openCompanyProfile(companyId) {
    state.activeProfileId = companyId;
    const panel = document.getElementById('profile-panel');
    if (!panel) return;
    
    panel.classList.add('active');
    
    // Clear UI inputs first
    document.getElementById('profile-name').textContent = 'Loading Profile...';
    document.getElementById('profile-category-subtitle').textContent = '';
    document.getElementById('profile-website-url').textContent = '';
    document.getElementById('profile-usecases').innerHTML = 'Loading use cases...';
    
    // Default Tab
    switchProfileTab('overview');
    
    try {
        const res = await fetch(`${API_BASE}/api/companies/${companyId}`);
        if (res.ok) {
            const data = await res.json();
            renderProfileDetails(data);
        } else {
            showToast('Failed to load company details.', 'danger');
            closeCompanyProfile();
        }
    } catch (err) {
        console.error(err);
        showToast('Error loading company details.', 'danger');
    }
}

function closeCompanyProfile() {
    state.activeProfileId = null;
    const panel = document.getElementById('profile-panel');
    if (panel) {
        panel.classList.remove('active');
    }
    // Return back to directory screen hash safely
    if (window.location.hash.startsWith('#/company/')) {
        window.location.hash = '#/directory';
    }
}

function renderProfileDetails(c) {
    document.getElementById('profile-name').textContent = c.name;
    document.getElementById('profile-category-subtitle').textContent = c.ai_category || 'AI Services';
    
    const webUrl = document.getElementById('profile-website-url');
    webUrl.textContent = c.website || 'website.com';
    const webLink = document.getElementById('profile-website-link');
    webLink.href = c.website ? (c.website.startsWith('http') ? c.website : `https://${c.website}`) : '#';
    
    // Watchlist Follow status
    const followBtn = document.getElementById('profile-follow-btn');
    if (c.is_watched) {
        followBtn.className = 'btn-follow watched';
        followBtn.querySelector('.follow-icon').textContent = '★';
        followBtn.querySelector('.follow-text').textContent = 'Following';
    } else {
        followBtn.className = 'btn-follow';
        followBtn.querySelector('.follow-icon').textContent = '☆';
        followBtn.querySelector('.follow-text').textContent = 'Follow';
    }
    
    // Overview Fields
    document.getElementById('profile-type').textContent = c.company_type || 'Incumbent';
    document.getElementById('profile-maturity').textContent = c.maturity || 'Not Rated';
    document.getElementById('profile-funding').textContent = c.funding || 'Unknown';
    document.getElementById('profile-revenue').textContent = c.revenue || 'Unknown';
    document.getElementById('profile-presence').textContent = c.germany_presence || 'Not Specified';
    document.getElementById('profile-customers').textContent = c.customers || 'None Specified';
    document.getElementById('profile-evidence').textContent = c.deployment_evidence || 'No direct evidence cited in directory.';
    
    // Use Cases List formatting
    const usecasesBox = document.getElementById('profile-usecases');
    usecasesBox.innerHTML = '';
    if (c.use_cases) {
        const list = document.createElement('ul');
        c.use_cases.split(',').forEach(uc => {
            const li = document.createElement('li');
            li.textContent = uc.strip ? uc.strip() : uc.trim();
            list.appendChild(li);
        });
        usecasesBox.appendChild(list);
    } else {
        usecasesBox.textContent = 'None documented.';
    }
    
    // Newsletter Tab News Items
    renderProfileNewsList(c.news);
    
    // Problems Solved Tab
    renderProfileProblemsList(c.solved_problems);
}

function renderProfileNewsList(news) {
    const list = document.getElementById('profile-news-list');
    if (!list) return;
    
    if (!news || news.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <p>No recent news articles found for this company.</p>
                <p style="font-size:0.75rem; margin-top:0.25rem;">Click "Refresh Live News" above to execute automated web ingestion.</p>
            </div>
        `;
        return;
    }
    
    list.innerHTML = '';
    news.forEach(item => {
        const card = document.createElement('div');
        card.className = 'news-card';
        card.innerHTML = `
            <div class="news-card-header">
                <h4><a href="${item.url}" target="_blank">${item.headline}</a></h4>
                <span class="news-meta">${item.source} • ${item.publication_date}</span>
            </div>
            <p class="news-summary">${item.summary}</p>
        `;
        list.appendChild(card);
    });
}

function renderProfileProblemsList(problems) {
    const list = document.getElementById('profile-problems-list');
    if (!list) return;
    
    if (!problems || problems.length === 0) {
        list.innerHTML = '<div class="empty-state">No matching segment problem statements documented.</div>';
        return;
    }
    
    list.innerHTML = '';
    problems.forEach(p => {
        const card = document.createElement('div');
        card.className = `problem-card ${p.is_core_solution ? 'core-solution' : ''}`;
        
        let sevBadge = `severity-${p.severity}`;
        let coreBadge = p.is_core_solution ? '<span class="badge core">Core Solution Vendor</span>' : '';
        
        let roiBlock = '';
        if (p.roi_benchmark) {
            roiBlock = `
                <div class="problem-impact-row">
                    <div class="impact-item">
                        <span>ROI Benchmark</span>
                        <p>${p.roi_benchmark}</p>
                    </div>
                    <div class="impact-item">
                        <span>Payback Period</span>
                        <p>${p.payback_months ? p.payback_months + ' months' : 'N/A'}</p>
                    </div>
                </div>
            `;
        }
        
        card.innerHTML = `
            <div class="problem-card-header">
                <span class="problem-cat">${p.category || 'General'}</span>
                <div class="problem-badges">
                    ${coreBadge}
                    <span class="badge ${sevBadge}">Severity ${p.severity}/5</span>
                </div>
            </div>
            <h4>${p.statement}</h4>
            <p class="problem-sol"><strong>AI Solution Match:</strong> ${p.use_case_solution || 'Not available'}</p>
            ${roiBlock}
        `;
        list.appendChild(card);
    });
}

function switchProfileTab(tabId) {
    state.activeProfileTab = tabId;
    
    // Toggle active tabs
    document.querySelectorAll('.slideout-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.getElementById(`tab-${tabId}`).classList.add('active');
    
    // Toggle panels
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`panel-${tabId}`).classList.add('active');
}

// On-Demand News Refresh Handler
async function refreshActiveCompanyNews() {
    if (!state.activeProfileId) return;
    
    const btn = document.getElementById('btn-refresh-news');
    btn.classList.add('loading');
    btn.disabled = true;
    
    try {
        const res = await fetch(`${API_BASE}/api/companies/${state.activeProfileId}/news/refresh`, {
            method: 'POST'
        });
        
        if (res.ok) {
            const data = await res.json();
            const addedCount = data.added_count;
            if (addedCount > 0) {
                showToast(`Aggregated ${addedCount} new relevant articles!`, 'success');
                // Reload profile data
                const profileRes = await fetch(`${API_BASE}/api/companies/${state.activeProfileId}`);
                if (profileRes.ok) {
                    const profileData = await profileRes.json();
                    renderProfileNewsList(profileData.news);
                }
            } else {
                showToast('No new articles found. Already up to date.', 'warning');
            }
        } else {
            showToast('Error refreshing news feed.', 'danger');
        }
    } catch (err) {
        showToast('Connection error. Failed to refresh.', 'danger');
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

// Watchlist Follow/Unfollow Toggle
async function toggleFollowStatus() {
    if (!state.activeProfileId) return;
    
    try {
        const res = await fetch(`${API_BASE}/api/watchlist/toggle`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ company_id: state.activeProfileId })
        });
        
        if (res.ok) {
            const data = await res.json();
            const added = data.added;
            
            const btn = document.getElementById('profile-follow-btn');
            if (added) {
                btn.className = 'btn-follow watched';
                btn.querySelector('.follow-icon').textContent = '★';
                btn.querySelector('.follow-text').textContent = 'Following';
                showToast('Added company to watchlist.', 'success');
            } else {
                btn.className = 'btn-follow';
                btn.querySelector('.follow-icon').textContent = '☆';
                btn.querySelector('.follow-text').textContent = 'Follow';
                showToast('Removed company from watchlist.', 'warning');
            }
        }
    } catch (err) {
        showToast('Error modifying watchlist.', 'danger');
    }
}

// Ask AI chatbot handler
async function handleChatSubmit(e) {
    e.preventDefault();
    const chatInput = document.getElementById('chat-input');
    const query = chatInput.value.trim();
    if (!query) return;
    
    chatInput.value = '';
    
    // Render user message
    renderChatMessage(query, 'user');
    
    // Render typing placeholder
    const typingBubble = renderChatMessage('Analyzing knowledge base and synthesizing grounded facts...', 'bot typing');
    
    try {
        const res = await fetch(`${API_BASE}/api/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });
        
        typingBubble.remove();
        
        if (res.ok) {
            const data = await res.json();
            renderChatMessage(data.answer, 'bot', data.sources, data.steps);
            
            // Check if discovery tool was run during the chat and update UI lists/logs
            const ranDiscovery = data.steps && data.steps.some(s => s.action === 'trigger_company_discovery');
            if (ranDiscovery) {
                await loadCompanies();
                renderAutoIngestedLogs();
                renderAdminCompaniesList();
            }
        } else {
            renderChatMessage('Sorry, I encountered an error answering your question.', 'bot error');
        }
    } catch (err) {
        typingBubble.remove();
        renderChatMessage('Offline. Failed to reach the grounded AI endpoint.', 'bot error');
    }
}

function renderChatMessage(text, sender, sources = [], steps = []) {
    const box = document.getElementById('chat-messages-box');
    if (!box) return null;
    
    const wrapper = document.createElement('div');
    wrapper.className = `chat-message ${sender}`;
    
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble';
    
    if (sender.includes('bot') && !sender.includes('typing')) {
        bubble.innerHTML = parseMarkdown(text);
        
        // If reasoning steps exist, add collapsible agent thought block
        if (steps && steps.length > 0) {
            const stepsContainer = document.createElement('div');
            stepsContainer.className = 'agent-steps-container';
            
            const title = document.createElement('div');
            title.className = 'agent-steps-title';
            title.innerHTML = '⚡ Agent Reasoning Trace (Click to toggle)';
            title.style.cursor = 'pointer';
            
            const list = document.createElement('div');
            list.className = 'agent-steps-list';
            list.style.display = 'none'; // collapsed by default
            
            steps.forEach(step => {
                const item = document.createElement('div');
                item.className = 'agent-step-item';
                item.textContent = `→ ${step.detail}`;
                list.appendChild(item);
            });
            
            title.addEventListener('click', () => {
                list.style.display = list.style.display === 'none' ? 'block' : 'none';
            });
            
            stepsContainer.appendChild(title);
            stepsContainer.appendChild(list);
            bubble.insertBefore(stepsContainer, bubble.firstChild);
        }
        
        // Add dynamic listener for company route links within chat
        bubble.querySelectorAll('a').forEach(link => {
            const href = link.getAttribute('href');
            if (href && href.startsWith('/#/company/')) {
                const id = parseInt(href.split('/').pop());
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    window.location.hash = href;
                });
            }
        });
        
        // If sources exist, add small citation footer
        if (sources && sources.length > 0) {
            const sourcesFooter = document.createElement('div');
            sourcesFooter.className = 'msg-sources';
            sourcesFooter.innerHTML = '<strong style="display:block; font-size:0.75rem; color:var(--text-muted); margin-top:0.75rem; text-transform:uppercase;">Grounded Sources:</strong>';
            
            const ul = document.createElement('ul');
            ul.style.listStyle = 'none';
            ul.style.fontSize = '0.75rem';
            ul.style.padding = '0';
            
            sources.forEach(src => {
                const li = document.createElement('li');
                li.style.display = 'inline-block';
                li.style.marginRight = '0.75rem';
                
                const isProfile = src.type === 'database_profile';
                const linkHref = isProfile ? src.link : src.link;
                
                const a = document.createElement('a');
                a.href = linkHref;
                a.target = isProfile ? '_self' : '_blank';
                a.textContent = src.title;
                a.className = 'citation-link';
                
                if (isProfile) {
                    a.addEventListener('click', (e) => {
                        e.preventDefault();
                        window.location.hash = linkHref;
                    });
                }
                
                li.appendChild(a);
                ul.appendChild(li);
            });
            sourcesFooter.appendChild(ul);
            bubble.appendChild(sourcesFooter);
        }
        
    } else {
        bubble.textContent = text;
    }
    
    wrapper.appendChild(bubble);
    box.appendChild(wrapper);
    
    // Scroll to bottom
    box.scrollTop = box.scrollHeight;
    
    return wrapper;
}

// Watchlist Screen Loader
async function loadWatchlistScreen() {
    const listContainer = document.getElementById('watchlist-companies-list');
    const feedContainer = document.getElementById('watchlist-news-feed');
    
    if (!listContainer || !feedContainer) return;
    
    listContainer.innerHTML = '<p class="empty-state">Loading watchlist...</p>';
    feedContainer.innerHTML = '<p class="empty-state">Aggregating feed...</p>';
    
    try {
        // Fetch watchlist companies
        const listRes = await fetch(`${API_BASE}/api/watchlist`);
        // Fetch all news for feed
        const feedRes = await fetch(`${API_BASE}/api/news`);
        
        if (listRes.ok && feedRes.ok) {
            const watched = await listRes.json();
            const allNews = await feedRes.json();
            
            // Render Watchlist List
            if (watched.length === 0) {
                listContainer.innerHTML = '<p class="empty-state">No watched companies. Tap the Star on any profile to follow.</p>';
            } else {
                listContainer.innerHTML = '';
                watched.forEach(c => {
                    const item = document.createElement('div');
                    item.className = 'watchlist-company-item';
                    item.textContent = c.name;
                    item.addEventListener('click', () => {
                        window.location.hash = `#/company/${c.id}`;
                    });
                    listContainer.appendChild(item);
                });
            }
            
            const watchedIds = new Set(watched.map(w => w.id));
            
            // Filter news depending on toggle state
            const filteredNews = (state.feedFilter === 'all')
                ? allNews
                : allNews.filter(n => watchedIds.has(n.company_id));
            
            if (filteredNews.length === 0) {
                feedContainer.innerHTML = state.feedFilter === 'all'
                    ? '<p class="empty-state">No news found in the database yet.</p>'
                    : '<p class="empty-state">No news found for watched companies. Refresh news on company profiles to fetch articles.</p>';
                return;
            }
            
            feedContainer.innerHTML = '';
            filteredNews.forEach(n => {
                const card = document.createElement('div');
                card.className = 'feed-card';
                card.innerHTML = `
                    <div class="feed-card-header">
                        <span class="feed-company-badge" style="cursor:pointer;" onclick="window.location.hash='#/company/${n.company_id}'">${n.company_name}</span>
                        <span class="news-meta">${n.source} • ${n.publication_date}</span>
                    </div>
                    <h3><a href="${n.url}" target="_blank">${n.headline}</a></h3>
                    <p class="news-summary">${n.summary}</p>
                `;
                feedContainer.appendChild(card);
            });
        }
    } catch (err) {
        console.error(err);
    }
}

// Admin Tab Management
let activeAdminTab = 'discover';
function switchAdminTab(tabId) {
    activeAdminTab = tabId;
    
    document.querySelectorAll('.admin-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.getElementById(`btn-admin-${tabId}`).classList.add('active');
    
    document.querySelectorAll('.admin-tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`admin-${tabId}-content`).classList.add('active');
    
    if (tabId === 'logs') {
        renderAutoIngestedLogs();
    }
}

// AI Discovery Submit Handler
async function handleCompanyDiscoverySubmit(e) {
    e.preventDefault();
    const sector = document.getElementById('disc-sector').value.trim();
    const country = document.getElementById('disc-country').value.trim();
    
    const btn = document.getElementById('btn-run-discovery');
    const text = btn.querySelector('.btn-text');
    const spinner = btn.querySelector('.btn-spinner');
    const statusBox = document.getElementById('discovery-status-box');
    const resultsBox = document.getElementById('discovery-results-box');
    
    text.textContent = 'Searching Defect Databases & Defect Solutions...';
    spinner.classList.remove('hidden');
    btn.disabled = true;
    
    statusBox.classList.remove('hidden');
    resultsBox.classList.add('hidden');
    
    try {
        const res = await fetch(`${API_BASE}/api/admin/discover`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sector, country })
        });
        
        if (res.ok) {
            const data = await res.json();
            state.discoveredCandidates = data.candidates;
            renderDiscoveredCandidates();
            resultsBox.classList.remove('hidden');
        } else {
            showToast('AI Discovery failed. Check server log.', 'danger');
        }
    } catch (err) {
        showToast('Offline or connection failure during discovery.', 'danger');
    } finally {
        text.textContent = 'Research & Discover Candidates';
        spinner.classList.add('hidden');
        btn.disabled = false;
        statusBox.classList.add('hidden');
    }
}

function renderDiscoveredCandidates() {
    const list = document.getElementById('discovered-candidates-list');
    if (!list) return;
    
    if (state.discoveredCandidates.length === 0) {
        list.innerHTML = '<div class="empty-state">No real verifiable companies discovered matching the sector.</div>';
        return;
    }
    
    list.innerHTML = '';
    state.discoveredCandidates.forEach((cand, idx) => {
        const card = document.createElement('div');
        card.className = 'candidate-card';
        card.id = `candidate-card-${idx}`;
        
        const confidenceClass = cand.confidence ? cand.confidence.toLowerCase() : 'medium';
        
        // Build Evidence lines
        let evidenceHtml = '';
        if (cand.evidence && cand.evidence.length > 0) {
            evidenceHtml = `
                <div class="evidence-container">
                    <div class="evidence-title">Web Evidence & Search Grounding</div>
                    <div class="evidence-list">
                        ${cand.evidence.map(ev => `
                            <div class="evidence-item">
                                <blockquote>"${ev.snippet}"</blockquote>
                                <a href="${ev.source_url}" target="_blank">${ev.source_url}</a>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        // Candidate Edit & Ingest Form template
        card.innerHTML = `
            <div class="candidate-header">
                <div class="candidate-title">
                    <h3>${cand.name}</h3>
                    <p style="font-size:0.8rem; color:var(--text-secondary);">${cand.website}</p>
                </div>
                <div class="candidate-meta-badges">
                    <span class="badge-confidence ${confidenceClass}">Confidence: ${cand.confidence}</span>
                </div>
            </div>
            
            <form id="ingest-form-${idx}" class="candidate-ingest-form" onsubmit="handleIngestApprove(event, ${idx})">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Company Name</label>
                        <input type="text" name="name" value="${cand.name}" required>
                    </div>
                    <div class="form-group">
                        <label>Country</label>
                        <input type="text" name="country" value="${cand.country}" required>
                    </div>
                    <div class="form-group">
                        <label>AI Category</label>
                        <input type="text" name="ai_category" value="${cand.ai_category || ''}">
                    </div>
                    <div class="form-group">
                        <label>F&B Segment IDs</label>
                        <input type="text" name="seg_tags" value="${cand.seg_tags || ''}">
                    </div>
                    <div class="form-group">
                        <label>German Presence</label>
                        <input type="text" name="germany_presence" value="${cand.germany_presence || ''}">
                    </div>
                    <div class="form-group">
                        <label>Company Type</label>
                        <select name="company_type">
                            <option value="Incumbent" ${cand.company_type === 'Incumbent' ? 'selected' : ''}>Incumbent</option>
                            <option value="NewCo" ${cand.company_type === 'NewCo' ? 'selected' : ''}>NewCo</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Funding Stage</label>
                        <input type="text" name="funding" value="${cand.funding || ''}">
                    </div>
                    <div class="form-group">
                        <label>Est. Revenue</label>
                        <input type="text" name="revenue" value="${cand.revenue || ''}">
                    </div>
                    <div class="form-group">
                        <label>Maturity (e.g. 3 — Scaling)</label>
                        <input type="text" name="maturity" value="${cand.maturity || ''}">
                    </div>
                    <div class="form-group">
                        <label>Website</label>
                        <input type="text" name="website" value="${cand.website || ''}">
                    </div>
                    <div class="form-group full-width">
                        <label>Use Cases</label>
                        <textarea name="use_cases" rows="2">${cand.use_cases || ''}</textarea>
                    </div>
                    <div class="form-group full-width">
                        <label>Top German Customers</label>
                        <input type="text" name="customers" value="${cand.customers || ''}">
                    </div>
                    <div class="form-group full-width">
                        <label>Deployment Evidence</label>
                        <textarea name="deployment_evidence" rows="2">${cand.deployment_evidence || ''}</textarea>
                    </div>
                </div>
                
                ${evidenceHtml}
                
                <div class="form-actions" style="margin-top:1.5rem;">
                    <button type="button" class="btn-secondary" onclick="rejectCandidate(${idx})">Reject</button>
                    <button type="submit" class="btn-primary">Approve & Ingest Company</button>
                </div>
            </form>
        `;
        
        list.appendChild(card);
    });
}

async function handleIngestApprove(e, idx) {
    e.preventDefault();
    const form = e.target;
    
    // Pull values from form fields
    const payload = {
        name: form.elements['name'].value.trim(),
        country: form.elements['country'].value.trim(),
        ai_category: form.elements['ai_category'].value.trim(),
        seg_tags: form.elements['seg_tags'].value.trim(),
        germany_presence: form.elements['germany_presence'].value.trim(),
        company_type: form.elements['company_type'].value,
        funding: form.elements['funding'].value.trim(),
        revenue: form.elements['revenue'].value.trim(),
        maturity: form.elements['maturity'].value.trim(),
        website: form.elements['website'].value.trim(),
        use_cases: form.elements['use_cases'].value.trim(),
        customers: form.elements['customers'].value.trim(),
        deployment_evidence: form.elements['deployment_evidence'].value.trim()
    };
    
    try {
        const res = await fetch(`${API_BASE}/api/admin/approve-company`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            showToast(`Approved and Ingested: ${payload.name}!`, 'success');
            // Remove candidate card from UI
            document.getElementById(`candidate-card-${idx}`).remove();
            // Re-fetch directory list
            await loadInitialData();
        } else {
            showToast('Ingest request rejected by database.', 'danger');
        }
    } catch (err) {
        showToast('Connection failed during approval check.', 'danger');
    }
}

function rejectCandidate(idx) {
    document.getElementById(`candidate-card-${idx}`).remove();
    showToast('Candidate rejected and discarded.', 'warning');
}

// Manual CRUD Data Management
async function loadAdminScreen() {
    // Fill the directory lists in manual console
    renderAdminCompaniesList();
    renderAutoIngestedLogs();
}

function renderAdminCompaniesList(search = '') {
    const container = document.getElementById('admin-companies-list');
    if (!container) return;
    
    // Sort all directory companies by name
    let list = [...state.companies];
    if (search) {
        list = list.filter(c => c.name.toLowerCase().includes(search.toLowerCase()));
    }
    
    list.sort((a,b) => a.name.localeCompare(b.name));
    
    container.innerHTML = '';
    list.forEach(c => {
        const row = document.createElement('div');
        row.className = 'manage-company-row';
        row.innerHTML = `
            <div class="manage-company-info">
                <h4>${c.name}</h4>
                <p>${c.ai_category || 'No Category'}</p>
            </div>
            <button class="btn-edit-quick" onclick="setupManualFormEdit(${c.id})">Edit</button>
        `;
        container.appendChild(row);
    });
}

function setupManualFormEdit(id) {
    const comp = state.companies.find(c => c.id === id);
    if (!comp) return;
    
    document.getElementById('data-form-title').textContent = `Edit: ${comp.name}`;
    document.getElementById('edit-company-id').value = comp.id;
    document.getElementById('comp-name').value = comp.name;
    document.getElementById('comp-country').value = comp.country;
    document.getElementById('comp-category').value = comp.ai_category || '';
    document.getElementById('comp-tags').value = comp.seg_tags || '';
    document.getElementById('comp-presence').value = comp.germany_presence || '';
    document.getElementById('comp-type').value = comp.company_type || 'Incumbent';
    document.getElementById('comp-funding').value = comp.funding || '';
    document.getElementById('comp-revenue').value = comp.revenue || '';
    document.getElementById('comp-maturity').value = comp.maturity || '';
    document.getElementById('comp-website').value = comp.website || '';
    document.getElementById('comp-usecases').value = comp.use_cases || '';
    document.getElementById('comp-customers').value = comp.customers || '';
    document.getElementById('comp-evidence').value = comp.deployment_evidence || '';
    
    document.getElementById('btn-cancel-edit').style.display = 'block';
    
    // Scroll form into view if responsive
    document.querySelector('.data-form-box').scrollIntoView({ behavior: 'smooth' });
}

function resetManualForm() {
    document.getElementById('data-form-title').textContent = 'Add New Company';
    document.getElementById('company-data-form').reset();
    document.getElementById('edit-company-id').value = '';
    document.getElementById('btn-cancel-edit').style.display = 'none';
}

async function handleManualCompanySubmit(e) {
    e.preventDefault();
    const id = document.getElementById('edit-company-id').value;
    
    const payload = {
        name: document.getElementById('comp-name').value.trim(),
        country: document.getElementById('comp-country').value.trim(),
        ai_category: document.getElementById('comp-category').value.trim(),
        seg_tags: document.getElementById('comp-tags').value.trim(),
        germany_presence: document.getElementById('comp-presence').value.trim(),
        company_type: document.getElementById('comp-type').value,
        funding: document.getElementById('comp-funding').value.trim(),
        revenue: document.getElementById('comp-revenue').value.trim(),
        maturity: document.getElementById('comp-maturity').value.trim(),
        website: document.getElementById('comp-website').value.trim(),
        use_cases: document.getElementById('comp-usecases').value.trim(),
        customers: document.getElementById('comp-customers').value.trim(),
        deployment_evidence: document.getElementById('comp-evidence').value.trim()
    };
    
    const isEdit = id !== '';
    const url = isEdit ? `${API_BASE}/api/companies/${id}` : `${API_BASE}/api/companies`;
    const method = isEdit ? 'PUT' : 'POST';
    
    try {
        const res = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (res.ok) {
            showToast(isEdit ? 'Company updated successfully!' : 'Company added successfully!', 'success');
            resetManualForm();
            // Refresh directory list & lists
            await loadInitialData();
            renderAdminCompaniesList();
        } else {
            const data = await res.json();
            showToast(`Error: ${data.detail || 'Request rejected.'}`, 'danger');
        }
    } catch (err) {
        showToast('Offline or connection failure during save.', 'danger');
    }
}

// Utility: Toast Alerts
function showToast(message, type = 'info') {
    const box = document.getElementById('toast-box');
    if (!box) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    box.appendChild(toast);
    
    // Auto-remove after 4 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Utility: Debounce
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

// Simple Markdown parser to compile citations and text in Ask AI chat
function parseMarkdown(text) {
    if (!text) return '';
    let html = text;
    
    // Tables
    // Matches markdown table structures
    const tableRegex = /\|(.+)\|[\r\n]+\|[-:| ]+\|[\r\n]+((?:\|.+\|[\r\n]*)+)/g;
    html = html.replace(tableRegex, (match, headerRow, rowsText) => {
        const headers = headerRow.split('|').map(h => h.trim()).filter(h => h);
        const rows = rowsText.trim().split('\n').map(row => {
            return row.split('|').map(td => td.trim()).filter((td, idx) => td || idx > 0);
        });
        
        let tableHtml = '<table><thead><tr>';
        headers.forEach(h => { tableHtml += `<th>${h}</th>`; });
        tableHtml += '</tr></thead><tbody>';
        
        rows.forEach(row => {
            tableHtml += '<tr>';
            row.forEach(td => { tableHtml += `<td>${td}</td>`; });
            tableHtml += '</tr>';
        });
        tableHtml += '</tbody></table>';
        return tableHtml;
    });

    // Bold text (**text**)
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Lists
    // Matches multiple bullet lines
    html = html.replace(/^\s*-\s+(.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/g, '<ul>$1</ul>');
    // clean up nested list double wraps
    html = html.replace(/<\/ul>\s*<ul>/g, '');
    
    // Markdown links: [title](url)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    
    return html;
}

function renderAutoIngestedLogs() {
    const tbody = document.getElementById('auto-logs-tbody');
    if (!tbody) return;
    
    // Filter companies with ingestion_source === 'Auto-Discovered'
    const autoCompanies = state.companies.filter(c => c.ingestion_source === 'Auto-Discovered');
    
    if (autoCompanies.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state" style="text-align: center; padding: 2rem;">No auto-ingested companies found yet.</td></tr>';
        return;
    }
    
    // Sort by ID descending (latest first)
    autoCompanies.sort((a, b) => b.id - a.id);
    
    tbody.innerHTML = '';
    autoCompanies.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong><a href="/#/company/${c.id}">${c.name}</a></strong></td>
            <td><span class="confidence-badge">${c.confidence_score}%</span></td>
            <td>${c.seg_tags || 'None'}</td>
            <td>${c.ai_category || 'N/A'}</td>
            <td><a href="https://${c.website}" target="_blank">${c.website || 'N/A'}</a></td>
            <td>${c.germany_presence || 'N/A'}</td>
        `;
        tbody.appendChild(tr);
    });
}
