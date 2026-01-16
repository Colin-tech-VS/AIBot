/**
 * Chatbot Ollama Local - Frontend Client
 * Communication avec le backend FastAPI
 * Gestion des messages et affichage en temps réel
 */

/**
 * Supprime toutes les conversations de l'historique
 */
function clearAllHistory() {
  if (confirm('Êtes-vous sûr de vouloir supprimer tout l\'historique ? Cette action est irréversible.')) {
    conversations = [];
    currentConversationId = null;
    saveConversations();
    renderNavbarHistory();
    chatBox.innerHTML = '';
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.classList.remove('active-chat');
    chatBox.classList.add('hidden');
    alert('Historique supprimé avec succès');
  }
}

/**
 * Toggle la visibilité de la liste d'historique
 */
function toggleHistoryList() {
  const historyList = document.getElementById('navbarHistoryList');
  if (historyList) {
    historyList.classList.toggle('hidden');
  }
}

// Références au DOM
const chatBox = document.getElementById("chatBox");
const messageInput = document.getElementById("messageInput");
const chatForm = document.getElementById("chatForm");
const sendBtn = document.getElementById("sendBtn");
const mainNavbar = document.getElementById("mainNavbar");
const navOverlay = document.getElementById("navOverlay");

// État
let isWaiting = false;
let isNavbarCollapsed = false;

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
  
  // Si pas d'historique fourni et qu'une conversation vide existe déjà, la charger
  if (!fromHistory && conversations.length > 0) {
    const existingEmpty = conversations.find(c => isConversationEmpty(c));
    if (existingEmpty) {
      console.log('[createConversation] Conversation vide existante trouvée, chargement:', {id: existingEmpty.id});
      loadConversationIntoChat(existingEmpty.id);
      return;
    }
  }
  
  const conv = {
    id: uid(),
    title: fromHistory && fromHistory.title ? fromHistory.title : 'Nouvelle conversation',
    messages: fromHistory && fromHistory.messages ? fromHistory.messages : []
  };
  
  conversations.unshift(conv);
  currentConversationId = conv.id;
  
  console.log('[createConversation] Created:', {id: conv.id, title: conv.title});
  
  saveConversations();
  renderNavbarHistory();
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
  renderNavbarHistory();
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
  renderNavbarHistory();
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
      renderNavbarHistory();
    }
  }
  
  conv.messages.push({role, content, ts: Date.now()});
  saveConversations();
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
  
  // Gérer le layout basé sur si la conversation a des messages
  const chatContainer = document.getElementById("chatContainer");
  if (!conv.messages || conv.messages.length === 0) {
    chatBox.classList.add("hidden");
    chatContainer.classList.remove("active-chat");
    chatBox.innerHTML = '';
    return;
  }
  
  // Si la conversation a des messages, activer le layout actif
  chatBox.classList.remove("hidden");
  chatContainer.classList.add("active-chat");
  
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



// Remplir l'historique dans la navbar
function renderNavbarHistory() {
  const navbarHistoryList = document.getElementById('navbarHistoryList');
  if (!navbarHistoryList) return;
  
  navbarHistoryList.innerHTML = '';
  if (!conversations || conversations.length === 0) {
    navbarHistoryList.innerHTML = `<p class="text-xs text-[#0d0737]/50 dark:text-white/50 text-center py-4">Aucune conversation</p>`;
    return;
  }
  
  conversations.forEach(conv => {
    const item = document.createElement('button');
    item.className = 'flex items-center gap-2 w-full p-2 rounded hover:bg-[#FCE8E7] dark:hover:bg-[#1B2F46] transition text-left text-[#0B1C2D] dark:text-[#E6ECF2] text-xs group';
    item.title = conv.title;
    
    const icon = document.createElement('svg');
    icon.className = 'w-4 h-4 flex-shrink-0';
    icon.setAttribute('fill', 'none');
    icon.setAttribute('stroke', 'currentColor');
    icon.setAttribute('viewBox', '0 0 24 24');
    icon.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path>';
    
    const textSpan = document.createElement('span');
    textSpan.className = 'flex-1 truncate whitespace-nowrap overflow-hidden';
    textSpan.textContent = conv.title;
    
    item.appendChild(icon);
    item.appendChild(textSpan);
    
    // Bouton supprimer au hover
    const delBtn = document.createElement('button');
    delBtn.className = 'p-1 rounded hover:bg-[#FCE8E7] dark:hover:bg-[#FF3B30]/20 text-[#E10600] dark:text-[#FF3B30] opacity-0 group-hover:opacity-100 transition flex-shrink-0';
    delBtn.title = 'Supprimer';
    delBtn.innerHTML = '<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>';
    delBtn.onclick = (e) => { e.stopPropagation(); deleteConversation(conv.id); };
    item.appendChild(delBtn);
    
    item.onclick = () => {
      loadConversationIntoChat(conv.id);
    };
    
    navbarHistoryList.appendChild(item);
  });
}

/**
 * Envoie un message au backend FastAPI
 */
async function sendMessage(event) {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message || isWaiting) return;

  // Activer le layout actif au premier message
  const chatContainer = document.getElementById("chatContainer");
  if (!chatContainer.classList.contains("active-chat")) {
    chatContainer.classList.add("active-chat");
    const chatBox = document.getElementById("chatBox");
    chatBox.classList.remove("hidden");
  }

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
  messageDiv.className = `flex ${role === "user" ? "justify-end" : "justify-start"} mb-2`;

  const bubble = document.createElement("div");
  const baseClass = `max-w-xs lg:max-w-md xl:max-w-lg px-4 py-2 rounded-lg text-sm`;
  
  if (role === "user") {
    bubble.className = `${baseClass} text-white rounded-br-none user-message-bubble`;
    const isDarkMode = document.documentElement.classList.contains("dark");
    bubble.style.backgroundColor = isDarkMode ? "#E10600" : "#E10600";
  } else {
    const roleClass = "bg-[#EEF1F5] dark:bg-[#1B2F46] text-[#0B1C2D] dark:text-[#E6ECF2] rounded-bl-none";
    bubble.className = `${baseClass} ${roleClass}`;
  }
  
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
  bubble.className = "px-4 py-2 rounded-lg bg-[#EEF1F5] dark:bg-[#13263B] rounded-bl-none";
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
  loadConversationsFromStorage();
  
  // Nettoyer les conversations vides au démarrage
  deleteEmptyConversations();
  
  // Always create a new conversation on page load
  createConversation();
  renderNavbarHistory();
  
  messageInput.focus();

  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(e);
    }
  });


  // Initialiser le dark mode et les infos utilisateur
  initDarkMode();
  initUserInfo();
  
  // Initialiser l'état de collapse de la navbar
  const savedNavbarCollapsed = localStorage.getItem('navbarCollapsed') === 'true';
  if (savedNavbarCollapsed && window.innerWidth >= 1024) {
    mainNavbar.classList.add("collapsed");
    isNavbarCollapsed = true;
  }
});

chatForm.addEventListener("submit", sendMessage);

// Fonctions de gestion de la navbar
function toggleNavbar() {
  mainNavbar.classList.toggle("navbar-collapsed");
}

function closeNavbar() {
  mainNavbar.classList.add("navbar-collapsed");
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
    <button class="w-full px-4 py-2 rounded-lg bg-[#E10600] hover:bg-[#FF3B30] text-white transition text-sm font-medium" onclick="handleLogout()">Se déconnecter</button>
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
    <p class="text-sm text-[#8A97A8] dark:text-[#6F8197]">Non connecté</p>
    <button class="w-full px-4 py-2 rounded-lg bg-[#E10600] hover:bg-[#FF3B30] text-white transition text-sm font-medium mt-2" onclick="handleLogin()">Se connecter</button>
  `;
}

/**
 * Active/désactive le dark mode avec Tailwind
 */
function toggleDarkMode() {
  const isDarkMode = document.documentElement.classList.toggle("dark");
  localStorage.setItem("darkMode", isDarkMode);
  
  // Mettre à jour la couleur de tous les messages utilisateurs existants
  const userBubbles = document.querySelectorAll('.user-message-bubble');
  userBubbles.forEach(bubble => {
    bubble.style.backgroundColor = "#E10600";
  });
}

/**
 * Initialise le dark mode au chargement
 */
function initDarkMode() {
  const savedDarkMode = localStorage.getItem("darkMode");
  const isDarkMode = savedDarkMode !== null ? savedDarkMode === "true" : true; // Dark mode activé par défaut
  const darkModeToggle = document.getElementById("darkModeToggle");
  
  // Toujours sauvegarder l'état pour synchroniser le localStorage
  localStorage.setItem("darkMode", isDarkMode);
  
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

/**
 * Initialise la navbar
 */
function initNavbar() {
  // Navbar visible par défaut (non collapsed)
  mainNavbar.classList.remove("navbar-collapsed");
}

// ===== WIDGETS F1 =====

/**
 * Récupère et affiche le prochain GP depuis le backend (qui scrape Aurupteur)
 */
async function fetchNextRaceCountdown() {
  console.log('[Widget GP] Récupération depuis backend...');
  try {
    // Appeler notre backend qui scrape Aurupteur en temps réel
    const response = await fetch('/next_race_countdown');
    if (!response.ok) throw new Error('API Error');
    const data = await response.json();
    
    console.log('[Widget GP] Données reçues:', data);
    
    if (data && data.countdown && data.race_name) {
      document.getElementById('widget-countdown').textContent = data.countdown;
      document.getElementById('widget-gp-name').textContent = data.race_name;
      console.log('[Widget GP] ✅ Mis à jour depuis backend');
    } else {
      throw new Error('Données incomplètes');
    }
    
  } catch (error) {
    console.error('[Widget GP] ❌ Erreur backend:', error);
    // Fallback local uniquement si le backend échoue
    fetchNextRaceCountdownFallback();
  }
}

/**
 * Fallback avec calendrier 2026 hardcodé
 */
function fetchNextRaceCountdownFallback() {
  console.log('[Widget GP] Utilisation du fallback calendrier 2026...');
  const races_2026 = [
    { name: "GP d'Australie", date: "2026-03-06", time: "05:00:00" },
    { name: "GP de Bahreïn", date: "2026-03-22", time: "15:00:00" },
    { name: "GP d'Arabie Saoudite", date: "2026-04-05", time: "18:30:00" },
    { name: "GP de Chine", date: "2026-04-19", time: "13:00:00" },
    { name: "GP du Japon", date: "2026-04-26", time: "14:00:00" },
    { name: "GP de Monaco", date: "2026-05-24", time: "14:00:00" },
    { name: "GP du Canada", date: "2026-06-14", time: "19:00:00" },
    { name: "GP de Silverstone", date: "2026-07-05", time: "14:00:00" },
    { name: "GP de Hongrie", date: "2026-07-19", time: "15:00:00" },
    { name: "GP de Spa-Francorchamps", date: "2026-08-02", time: "15:00:00" },
    { name: "GP des Pays-Bas", date: "2026-08-30", time: "15:00:00" },
    { name: "GP d'Italie", date: "2026-09-06", time: "15:00:00" },
    { name: "GP de Singapour", date: "2026-09-27", time: "19:00:00" },
    { name: "GP de Suzuka", date: "2026-10-04", time: "14:00:00" },
    { name: "GP de Mexico", date: "2026-10-25", time: "20:00:00" },
    { name: "GP de São Paulo", date: "2026-11-08", time: "17:00:00" },
    { name: "GP d'Abu Dhabi", date: "2026-11-29", time: "13:00:00" },
  ];
  
  const now = new Date();
  let nextRace = null;
  
  for (const race of races_2026) {
    const raceDate = new Date(race.date + 'T' + race.time + 'Z');
    if (raceDate > now) {
      nextRace = race;
      break;
    }
  }
  
  if (!nextRace) {
    document.getElementById('widget-countdown').textContent = '—';
    document.getElementById('widget-gp-name').textContent = '—';
    console.warn('[Widget GP] Aucun GP trouvé');
    return;
  }
  
  const raceDate = new Date(nextRace.date + 'T' + nextRace.time + 'Z');
  const diffMs = raceDate - now;
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diffMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  
  let countdownText = `Dans ${days}j ${hours}h`;
  
  document.getElementById('widget-countdown').textContent = countdownText;
  document.getElementById('widget-gp-name').textContent = nextRace.name;
  console.log('[Widget GP] ✅ Fallback utilisé:', nextRace.name, '-', countdownText);
}

/**
 * Récupère et affiche le top 3 des pilotes depuis le backend
 */
async function fetchTop3Drivers() {
  console.log('[Widget Drivers] Récupération depuis backend...');
  try {
    // Appeler notre backend
    const response = await fetch('/top_drivers');
    if (!response.ok) throw new Error('API Error');
    const data = await response.json();
    
    console.log('[Widget Drivers] Données reçues:', data);
    
    if (data && data.drivers && data.drivers.length > 0) {
      const medals = ['🥇', '🥈', '🥉'];
      const topDriversList = document.getElementById('widget-top-drivers');
      
      if (topDriversList) {
        topDriversList.innerHTML = data.drivers.slice(0, 3)
          .map((driver, i) => {
            return `<div>${medals[i]} ${driver.name} · ${driver.points}pts</div>`;
          })
          .join('');
        console.log('[Widget Drivers] ✅ Mis à jour depuis backend');
      }
    } else {
      throw new Error('Données incomplètes');
    }
    
  } catch (error) {
    console.error('[Widget Drivers] ❌ Erreur backend:', error);
    const topDriversList = document.getElementById('widget-top-drivers');
    if (topDriversList) {
      topDriversList.innerHTML = '<div>Service indisponible</div>';
    }
  }
}

// Initialisation
document.addEventListener("DOMContentLoaded", () => {
  initNavbar();
  initDarkMode();
  initUserInfo();
  renderNavbarHistory();

  // Charger les widgets F1
  fetchNextRaceCountdown();
  fetchTop3Drivers();
});