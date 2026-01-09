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
    historyContent.innerHTML = `<p class="text-sm text-slate-500 dark:text-slate-400">Aucune conversation.</p>`;
    return;
  }
  conversations.forEach(conv => {
    const item = document.createElement('div');
    item.className = 'p-3 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer transition flex justify-between items-center group';
    item.title = conv.title;

    const titleDiv = document.createElement('div');
    titleDiv.className = 'flex-1 min-w-0';
    const titleEl = document.createElement('p');
    titleEl.className = 'text-sm font-medium text-slate-900 dark:text-white truncate';
    titleEl.textContent = conv.title;
    titleDiv.appendChild(titleEl);

    const actions = document.createElement('div');
    actions.className = 'flex gap-1 opacity-0 group-hover:opacity-100 transition';

    const delBtn = document.createElement('button');
    delBtn.className = 'p-1 rounded hover:bg-red-100 dark:hover:bg-red-900 text-red-900 dark:text-red-400 transition';
    delBtn.title = 'Supprimer';
    delBtn.innerHTML = '<svg class="w-4 h-4" data-lucide="trash-2"></svg>';
    delBtn.onclick = (e) => { e.stopPropagation(); deleteConversation(conv.id); };

    actions.appendChild(delBtn);

    item.appendChild(titleDiv);
    item.appendChild(actions);

    item.onclick = () => {
      loadConversationIntoChat(conv.id);
      closeHistoryPanel();
    };

    historyContent.appendChild(item);
  });
  
  // Réinitialiser les icônes Lucide après l'ajout des éléments
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }
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
  messageDiv.className = `flex ${role === "user" ? "justify-end" : "justify-start"}`;

  const bubble = document.createElement("div");
  const baseClass = `max-w-xs lg:max-w-md xl:max-w-lg px-4 py-2 rounded-lg text-sm`;
  const roleClass = role === "user" 
    ? "bg-red-900 text-white rounded-br-none" 
    : "bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-white rounded-bl-none";
  
  bubble.className = `${baseClass} ${roleClass}`;
  
  let htmlContent = text
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="underline font-semibold hover:opacity-80">$1</a>')
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
  loadingDiv.className = "flex justify-start";

  const bubble = document.createElement("div");
  bubble.className = "px-4 py-2 rounded-lg bg-slate-100 dark:bg-slate-800 rounded-bl-none";
  bubble.innerHTML = `
    <div class="flex gap-1">
      <span class="inline-block animate-bounce">🏎️</span>
      <span class="inline-block animate-bounce" style="animation-delay: 0.1s">🏁</span>
      <span class="inline-block animate-bounce" style="animation-delay: 0.2s">⚡</span>
    </div>
  `;

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

function toggleHistoryPanel() {
  if (!historyPanel) return;
  const isHidden = historyPanel.classList.contains("hidden");
  if (isHidden) {
    openHistoryPanel();
  } else {
    closeHistoryPanel();
  }
}

/**
 * Ouvre le panneau d'historique (affiche la liste des conversations)
 */
async function openHistoryPanel() {
  if (!historyPanel) return;
  historyPanel.classList.remove("hidden");
  historyPanel.setAttribute("aria-hidden", "false");
  renderConversationList();
}

/**
 * Ferme le panneau d'historique
 */
function closeHistoryPanel() {
  if (!historyPanel) return;
  historyPanel.classList.add("hidden");
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
  userProfileOverlay.classList.remove("hidden");
  userProfilePanel.classList.remove("translate-x-full");
  userProfilePanel.setAttribute("aria-hidden", "false");
}

/**
 * Ferme le panneau profil utilisateur
 */
function closeUserProfile() {
  const userProfilePanel = document.getElementById("userProfilePanel");
  const userProfileOverlay = document.getElementById("userProfileOverlay");
  if (!userProfilePanel) return;
  userProfilePanel.classList.add("translate-x-full");
  userProfileOverlay.classList.add("hidden");
  userProfilePanel.setAttribute("aria-hidden", "true");
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
    <p class="text-sm">Connecté en tant que <strong>${username}</strong></p>
    <button class="w-full px-4 py-2 rounded-lg bg-red-900 hover:bg-red-800 text-white transition text-sm font-medium" onclick="handleLogout()">Se déconnecter</button>
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
    <p class="text-sm text-slate-500 dark:text-slate-400">Non connecté</p>
    <button class="w-full px-4 py-2 rounded-lg bg-red-900 hover:bg-red-800 text-white transition text-sm font-medium mt-2" onclick="handleLogin()">Se connecter</button>
  `;
}

/**
 * Active/désactive le dark mode avec Tailwind
 */
function toggleDarkMode() {
  const isDarkMode = document.documentElement.classList.toggle("dark");
  localStorage.setItem("darkMode", isDarkMode);
}

/**
 * Initialise le dark mode au chargement
 */
function initDarkMode() {
  const isDarkMode = localStorage.getItem("darkMode") === "true";
  const darkModeToggle = document.getElementById("darkModeToggle");
  if (isDarkMode) {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
  if (darkModeToggle) {
    darkModeToggle.checked = isDarkMode;
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
