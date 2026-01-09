/**
 * Chatbot Ollama Local - Frontend Client
 * Communication avec le backend FastAPI
 * Gestion des messages et affichage en temps réel
 */

// Références au DOM
const chatBox = document.getElementById("chatBox");
const messageInput = document.getElementById("messageInput");
const chatForm = document.getElementById("chatForm");
const sendBtn = document.getElementById("sendBtn");

// État
let isWaiting = false;

// References to history UI (initialized on DOMContentLoaded)
let historyPanel = null;
let historyOverlay = null;
let historyContent = null;

// Conversations store (frontend only, ChatGPT-like)
let conversations = [];
let currentConversationId = null;

function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function saveConversations() {
  try {
    localStorage.setItem('conversations', JSON.stringify(conversations));
  } catch (e) {
    console.error('Impossible de sauvegarder les conversations', e);
  }
}

function loadConversationsFromStorage() {
  try {
    const raw = localStorage.getItem('conversations');
    if (raw) {
      conversations = JSON.parse(raw);
    }
  } catch (e) {
    console.error('Erreur lecture conversations', e);
    conversations = [];
  }
}

function createConversation(fromHistory) {
  console.log('[createConversation] START', {count: conversations.length});
  
  const conv = {
    id: uid(),
    title: fromHistory && fromHistory.title ? fromHistory.title : 'Nouvelle conversation',
    messages: fromHistory && fromHistory.messages ? fromHistory.messages : []
  };
  
  conversations.unshift(conv);
  currentConversationId = conv.id;
  
  console.log('[createConversation] Created:', {id: conv.id, title: conv.title});
  
  saveConversations();
  renderConversationList();
  loadConversationIntoChat(conv.id);
  
  console.log('[createConversation] DONE');
}

function isConversationEmpty(conv) {
  return !conv || !conv.messages || conv.messages.length === 0;
}

function deleteConversation(id, silent = false) {
  const idx = conversations.findIndex(c=>c.id===id);
  if (idx===-1) return;
  
  // Demander confirmation uniquement si ce n'est pas une suppression silencieuse
  if (!silent && !confirm('Supprimer cette conversation ?')) return;
  
  conversations.splice(idx,1);
  if (currentConversationId===id) {
    if (conversations.length>0) currentConversationId = conversations[0].id;
    else currentConversationId = null;
  }
  saveConversations();
  renderConversationList();
  if (currentConversationId) loadConversationIntoChat(currentConversationId);
  else chatBox.innerHTML = `<div class="message-info"><p class="muted">Aucune conversation. Créez-en une.</p></div>`;
}

function deleteEmptyConversations() {
  const emptyIds = conversations.filter(conv => isConversationEmpty(conv)).map(conv => conv.id);
  emptyIds.forEach(id => deleteConversation(id, true));
}

function renameConversation(id) {
  const conv = conversations.find(c=>c.id===id);
  if (!conv) return;
  const newTitle = prompt('Nouveau titre', conv.title);
  if (!newTitle) return;
  conv.title = newTitle;
  saveConversations();
  renderConversationList();
}

function addMessageToCurrentConversation(role, content) {
  if (!currentConversationId) {
    createConversation();
  }
  const conv = conversations.find(c=>c.id===currentConversationId);
  if (!conv) return;
  
  // Si c'est le premier message utilisateur et que la conversation a un titre par défaut, la renommer
  if (role === 'user' && (!conv.messages || conv.messages.length === 0)) {
    const isDefaultTitle = conv.title === 'Nouvelle conversation';
    if (isDefaultTitle) {
      conv.title = content.slice(0, 50);
      setConversationTitle(conv.title);
    }
  }
  
  conv.messages.push({role, content, ts: Date.now()});
  saveConversations();
  renderConversationList();
}

function loadConversationIntoChat(id) {
  // Avant de changer, supprimer les conversations vides (sauf celle qu'on va charger)
  const previousConvId = currentConversationId;
  if (previousConvId && previousConvId !== id) {
    const previousConv = conversations.find(c => c.id === previousConvId);
    if (previousConv && isConversationEmpty(previousConv)) {
      deleteConversation(previousConvId, true);
    }
  }
  
  const conv = conversations.find(c=>c.id===id);
  if (!conv) return;
  currentConversationId = id;
  chatBox.innerHTML = '';
  setConversationTitle(conv.title);
  if (!conv.messages || conv.messages.length===0) {
    chatBox.innerHTML = `<div class="message-info"><p class="muted">Conversation vide. Envoyez un message pour commencer.</p></div>`;
    return;
  }
  conv.messages.forEach(m => {
    displayMessage(m.content, m.role, {save:false});
  });
}

function setConversationTitle(title) {
  try {
    const el = document.getElementById('convTitleText');
    if (el) el.textContent = title || 'Aucune conversation active';
  } catch (e) {
    console.error('Impossible de mettre à jour le titre de conversation', e);
  }
}

function renderConversationList() {
  if (!historyContent) return;
  historyContent.innerHTML = '';
  if (!conversations || conversations.length===0) {
    historyContent.innerHTML = `<p class="muted">Aucune conversation.</p>`;
    return;
  }
  conversations.forEach(conv => {
    const item = document.createElement('div');
    item.className = 'conversation-list-item';
    item.title = conv.title;

    const left = document.createElement('div');
    left.style.display = 'flex';
    left.style.flexDirection = 'column';
    left.style.gap = '2px';

    const title = document.createElement('div');
    title.className = 'title';
    title.textContent = conv.title;

    left.appendChild(title);

    const actions = document.createElement('div');
    actions.className = 'conversation-actions';

    const delBtn = document.createElement('button');
    delBtn.innerText = '🗑️';
    delBtn.title = 'Supprimer';
    delBtn.onclick = (e) => { e.stopPropagation(); deleteConversation(conv.id); };

    actions.appendChild(delBtn);

    item.appendChild(left);
    item.appendChild(actions);

    item.onclick = () => {
      loadConversationIntoChat(conv.id);
      closeHistoryPanel();
    };

    historyContent.appendChild(item);
  });
}

/**
 * Envoie un message au backend FastAPI
 */
async function sendMessage(event) {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message || isWaiting) return;

  displayMessage(message, "user");

  messageInput.value = "";
  sendBtn.disabled = true;
  isWaiting = true;

  const loaderId = displayLoader();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message: message }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Erreur du serveur");
    }

    const data = await response.json();

    removeMessage(loaderId);

    displayMessage(data.bot_response, "bot");
  } catch (error) {
    removeMessage(loaderId);

    displayMessage(
      `❌ Erreur: ${error.message}`,
      "bot"
    );
    console.error("Erreur:", error);
  } finally {
    sendBtn.disabled = false;
    isWaiting = false;
    messageInput.focus();
  }
}

/**
 * Affiche un message dans la zone de chat
 * Support du markdown et emojis (liens cliquables)
 */
function displayMessage(text, role = "user", opts = {save: true}) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  
  let htmlContent = text
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color: #3b82f6; text-decoration: underline; font-weight: 600;">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br>");
  
  bubble.innerHTML = htmlContent;

  messageDiv.appendChild(bubble);
  chatBox.appendChild(messageDiv);

  chatBox.scrollTop = chatBox.scrollHeight;

  if (opts.save !== false) addMessageToCurrentConversation(role, text);

  return messageDiv;
}

/**
 * Affiche un loader (indicateur de chargement)
 */
function displayLoader() {
  const loadingDiv = document.createElement("div");
  loadingDiv.className = "message bot";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble loading";
  bubble.innerHTML = "<span>🏎️</span><span>🏁</span><span>⚡</span>";

  loadingDiv.appendChild(bubble);
  chatBox.appendChild(loadingDiv);

  chatBox.scrollTop = chatBox.scrollHeight;

  return loadingDiv;
}

/**
 * Supprime un message du chat
 */
function removeMessage(messageElement) {
  if (messageElement && messageElement.parentNode) {
    messageElement.remove();
  }
}

/**
 * Efface la conversation courante et réinitialise l'UI
 * FIX: Utilise une vraie variable pour le confirm() au lieu de !confirm()
 */
function clearChat() {
  console.log('[clearChat] Demande de confirmation...');
  
  const userConfirmed = confirm("Êtes-vous sûr de vouloir effacer cette conversation ?");
  console.log('[clearChat] Utilisateur a confirmé ?', userConfirmed);
  
  if (!userConfirmed) {
    console.log('[clearChat] ❌ ANNULÉ PAR UTILISATEUR - RIEN NE SERA SUPPRIMÉ');
    return; // RETOUR IMMÉDIAT si l'utilisateur clique Cancel
  }

  console.log('[clearChat] ✅ Utilisateur a confirmé, suppression en cours...');
  doDeleteConversation(); // Appel asynchrone mais non bloquant
}

function doDeleteConversation() {
  // Utiliser un IIFE async pour ne pas bloquer clearChat()
  (async () => {
    try {
      const response = await fetch("/clear_history", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("Erreur lors de l'effacement");
      }

      console.log('[doDeleteConversation] Backend a confirmé la suppression');

      // Supprimer la conversation courante du localStorage
      if (currentConversationId) {
        const idx = conversations.findIndex(c => c.id === currentConversationId);
        if (idx !== -1) {
          conversations.splice(idx, 1);
          console.log('[doDeleteConversation] Conversation supprimée de localStorage');
          
          if (conversations.length > 0) {
            currentConversationId = conversations[0].id;
            loadConversationIntoChat(currentConversationId);
          } else {
            currentConversationId = null;
            chatBox.innerHTML = `<div class="message-info"><p class="muted">Aucune conversation. Créez-en une.</p></div>`;
            setConversationTitle('Aucune conversation active');
          }
          
          saveConversations();
          renderConversationList();
        }
      }

      messageInput.focus();
      console.log('[doDeleteConversation] ✅ DONE');
    } catch (error) {
      alert(`Erreur: ${error.message}`);
      console.error("[doDeleteConversation] Erreur:", error);
    }
  })();
}

/**
 * Initialisation au chargement de la page
 */
document.addEventListener("DOMContentLoaded", () => {
  try {
    historyPanel = document.getElementById("historyPanel");
    historyContent = document.getElementById("historyContent");

    console.log('Frontend: history UI initialized', {historyPanel: !!historyPanel, historyContent: !!historyContent});
  } catch (e) {
    console.error('Erreur initialisation UI:', e);
  }

  loadConversationsFromStorage();
  
  // Nettoyer les conversations vides au démarrage
  deleteEmptyConversations();
  
  if (!conversations || conversations.length === 0) {
    (async () => {
      try {
        const res = await fetch('/history');
        if (res.ok) {
          const data = await res.json();
          const msgs = data.history || [];
          const messages = msgs.map(m => ({role: m.role, content: m.content, ts: Date.now()}));
          if (messages.length>0) createConversation({title: 'Session serveur', messages});
          else createConversation();
        } else {
          createConversation();
        }
      } catch (e) {
        console.error('Impossible de récupérer /history pour initialiser', e);
        createConversation();
      }
    })();
  } else {
    renderConversationList();
    if (conversations.length>0) loadConversationIntoChat(conversations[0].id);
  }
  messageInput.focus();

  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(e);
    }
  });
  
  const closeBtn = document.getElementById("closeHistoryBtn");
  const newConvBtn = document.getElementById("newConversationBtn");
  
  console.log('[DOMContentLoaded] Binding buttons:', {
    closeBtn: !!closeBtn,
    newConvBtn: !!newConvBtn
  });
  
  if (closeBtn) {
    closeBtn.addEventListener("click", (e) => {
      e.preventDefault();
      console.log('[closeBtn] clicked');
      closeHistoryPanel();
    });
  }
  
  if (newConvBtn) {
    newConvBtn.addEventListener('click', (e) => {
      e.preventDefault();
      console.log('[newConvBtn in panel] clicked');
      createConversation();
      closeHistoryPanel();
    });
  }

  // Initialiser le dark mode et les infos utilisateur
  initDarkMode();
  initUserInfo();
});

chatForm.addEventListener("submit", sendMessage);

/** * Bascule l'ouverture/fermeture du panneau d'historique
 */
function toggleHistoryPanel() {
  if (!historyPanel) return;
  const isOpen = historyPanel.getAttribute("aria-hidden") === "false";
  if (isOpen) {
    closeHistoryPanel();
  } else {
    openHistoryPanel();
  }
}

/** * Ouvre le panneau d'historique (affiche la liste des conversations)
 */
async function openHistoryPanel() {
  if (!historyPanel) return;
  historyPanel.setAttribute("aria-hidden", "false");
  renderConversationList();
}

/**
 * Ferme le panneau d'historique
 */
function closeHistoryPanel() {
  if (!historyPanel) return;
  historyPanel.setAttribute("aria-hidden", "true");
}

/**
 * Remplit le panneau avec les items d'historique (legacy function, not used currently)
 */
function renderHistoryItems(items) {
  if (!historyContent) return;
  if (!items || items.length === 0) {
    historyContent.innerHTML = `<p class="muted">Aucun historique trouvé.</p>`;
    return;
  }

  historyContent.innerHTML = '';
  items.forEach((it, idx) => {
    const el = document.createElement('div');
    el.className = 'history-item';

    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = `${idx + 1} • ${it.role === 'user' ? 'Utilisateur' : 'Assistant'}`;

    const content = document.createElement('div');
    content.className = 'content';
    let html = it.content
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color: #3b82f6; text-decoration: underline; font-weight: 600;">$1</a>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');

    content.innerHTML = html;

    el.appendChild(meta);
    el.appendChild(content);

    historyContent.appendChild(el);
  });
}

/**
 * Ouvre le panneau profil utilisateur
 */
function openUserProfile() {
  const userProfilePanel = document.getElementById("userProfilePanel");
  const userProfileOverlay = document.getElementById("userProfileOverlay");
  if (!userProfilePanel) return;
  userProfileOverlay.hidden = false;
  userProfilePanel.setAttribute("aria-hidden", "false");
}

/**
 * Ferme le panneau profil utilisateur
 */
function closeUserProfile() {
  const userProfilePanel = document.getElementById("userProfilePanel");
  const userProfileOverlay = document.getElementById("userProfileOverlay");
  if (!userProfilePanel) return;
  userProfilePanel.setAttribute("aria-hidden", "true");
  userProfileOverlay.hidden = true;
}

/**
 * Gère la connexion utilisateur
 */
function handleLogin() {
  const username = prompt("Entrez votre nom d'utilisateur :");
  if (username && username.trim()) {
    localStorage.setItem("username", username.trim());
    updateUserInfo(username.trim());
  }
}

/**
 * Met à jour l'affichage des infos utilisateur
 */
function updateUserInfo(username) {
  const userInfo = document.getElementById("userInfo");
  if (!userInfo) return;
  userInfo.innerHTML = `
    <p>Connecté en tant que <strong>${username}</strong></p>
    <button class="profile-btn" onclick="handleLogout()">Se déconnecter</button>
  `;
}

/**
 * Gère la déconnexion utilisateur
 */
function handleLogout() {
  localStorage.removeItem("username");
  const userInfo = document.getElementById("userInfo");
  if (!userInfo) return;
  userInfo.innerHTML = `
    <p class="muted">Non connecté</p>
    <button class="profile-btn" onclick="handleLogin()">Se connecter</button>
  `;
}

/**
 * Active/désactive le dark mode
 */
function toggleDarkMode() {
  const isDarkMode = document.body.classList.toggle("dark-mode");
  localStorage.setItem("darkMode", isDarkMode);
  updateDarkModeVariables(isDarkMode);
}

/**
 * Met à jour les variables CSS pour le dark mode
 */
function updateDarkModeVariables(isDarkMode) {
  const root = document.documentElement;
  if (isDarkMode) {
    // Dark Mode Palette
    root.style.setProperty("--primary", "#8b0000");
    root.style.setProperty("--primary-dark", "#6b0000");
    root.style.setProperty("--bg", "#0f0f0f");
    root.style.setProperty("--bg-alt", "#1a1a1a");
    root.style.setProperty("--fg", "#f5f5f5");
    root.style.setProperty("--fg-light", "#b0b0b0");
    root.style.setProperty("--border", "#333333");
  } else {
    // Light Mode Palette
    root.style.setProperty("--primary", "#7b1b1e");
    root.style.setProperty("--primary-dark", "#671a1b");
    root.style.setProperty("--bg", "#ffffff");
    root.style.setProperty("--bg-alt", "#f0f0f0");
    root.style.setProperty("--fg", "#1a1a1a");
    root.style.setProperty("--fg-light", "#6b6b6b");
    root.style.setProperty("--border", "#e1e1e1");
  }
}

/**
 * Initialise le dark mode au chargement
 */
function initDarkMode() {
  const darkModeToggle = document.getElementById("darkModeToggle");
  const isDarkMode = localStorage.getItem("darkMode") === "true";
  if (darkModeToggle) {
    darkModeToggle.checked = isDarkMode;
  }
  if (isDarkMode) {
    document.body.classList.add("dark-mode");
    updateDarkModeVariables(true);
  }
}

/**
 * Initialise les infos utilisateur au chargement
 */
function initUserInfo() {
  const username = localStorage.getItem("username");
  if (username) {
    updateUserInfo(username);
  }
}
