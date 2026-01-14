/**
 * Chatbot F1 - Frontend Client (Version simplifiée sans authentification)
 * Communication avec le backend FastAPI
 * Gestion des messages et affichage en temps réel
 */

// Références au DOM
const chatBox = document.getElementById("chatBox");
const messageInput = document.getElementById("messageInput");
const messageForm = document.getElementById("messageForm");
const mainNavbar = document.getElementById("mainNavbar");
const navOverlay = document.getElementById("navOverlay");

// État
let isWaiting = false;
let isNavbarOpen = false;
let isNavbarCollapsed = false;

// Conversations store (localStorage uniquement)
let conversations = [];
let currentConversationId = null;

function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

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
    showNotification('Historique supprimé avec succès', 'success');
  }
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
    } else {
      conversations = [];
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

// Remplir l'historique dans la navbar
function renderNavbarHistory() {
  const navbarHistoryList = document.getElementById('navbarHistoryList');
  if (!navbarHistoryList) return;
  
  navbarHistoryList.innerHTML = '';
  if (!conversations || conversations.length === 0) {
    navbarHistoryList.innerHTML = `<p class="text-xs text-slate-400 text-center py-4">Aucune conversation</p>`;
    return;
  }
  
  conversations.forEach(conv => {
    const item = document.createElement('button');
    item.className = 'flex items-center gap-2 w-full p-2 rounded hover:bg-red-800 dark:hover:bg-red-900 transition text-left text-white text-sm group';
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
    delBtn.className = 'p-1 rounded hover:bg-red-700 text-white opacity-0 group-hover:opacity-100 transition flex-shrink-0';
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
      body: JSON.stringify({ 
        message: message,
        conversation_id: currentConversationId || "default"
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Erreur du serveur");
    }

    const data = await response.json();

    removeMessage(loaderId);

    // Afficher avec effet typing
    displayMessage(data.bot_response, "bot", {save: true, typing: true, sources: data.sources || []});
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
 * Formate le texte en markdown simple (gras, italique, liens)
 */
function formatMarkdown(text) {
  return text
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="underline font-semibold hover:opacity-80">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/\n/g, "<br>");
}

/**
 * Affiche un message dans la zone de chat avec effet typing pour le bot
 * Support du markdown et emojis (liens cliquables)
 */
function displayMessage(text, role = "user", opts = {save: true, typing: false, sources: []}) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `flex ${role === "user" ? "justify-end" : "justify-start"} flex-col`;

  const bubble = document.createElement("div");
  bubble.className = `message-bubble ${role === "user" ? "user-message" : "bot-message"}`;

  // Si c'est un message bot avec effet typing activé
  if (role === "bot" && opts.typing && text.length > 0) {
    bubble.innerHTML = "";
    messageDiv.appendChild(bubble);

    // Ajouter sources si présentes
    if (opts.sources && opts.sources.length > 0) {
      const sourcesDiv = createSourcesDisplay(opts.sources);
      messageDiv.appendChild(sourcesDiv);
    }

    chatBox.appendChild(messageDiv);

    // Effet typing progressif
    let currentIndex = 0;
    const typingSpeed = 15; // ms par caractère (ajustable)

    const typeNextChar = () => {
      if (currentIndex < text.length) {
        currentIndex++;
        const partialText = text.substring(0, currentIndex);
        bubble.innerHTML = formatMarkdown(partialText);
        chatBox.scrollTop = chatBox.scrollHeight;

        setTimeout(typeNextChar, typingSpeed);
      } else {
        // Animation terminée, enregistrer dans l'historique si nécessaire
        if (opts.save) {
          addMessageToCurrentConversation(role, text);
        }
      }
    };

    typeNextChar();
  } else {
    // Affichage normal sans typing
    bubble.innerHTML = formatMarkdown(text);
    messageDiv.appendChild(bubble);

    // Ajouter sources si présentes
    if (role === "bot" && opts.sources && opts.sources.length > 0) {
      const sourcesDiv = createSourcesDisplay(opts.sources);
      messageDiv.appendChild(sourcesDiv);
    }

    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;

    if (opts.save) {
      addMessageToCurrentConversation(role, text);
    }
  }
}

/**
 * Crée un élément d'affichage des sources
 */
function createSourcesDisplay(sources) {
  const sourcesDiv = document.createElement("div");
  sourcesDiv.className = "mt-2 text-xs text-gray-400 italic";
  sourcesDiv.style.maxWidth = "85%";

  const sourcesList = sources.map((source) => {
    return `<span class="inline-block mr-2 mb-1 px-2 py-1 bg-red-950/20 border border-red-900/30 rounded text-gray-300">📌 ${source}</span>`;
  }).join("");

  sourcesDiv.innerHTML = `<div class="flex flex-wrap gap-1">${sourcesList}</div>`;
  return sourcesDiv;
}

/**
 * Affiche un loader (indicateur de chargement)
 */
function displayLoader() {
  const loadingDiv = document.createElement("div");
  loadingDiv.className = "flex justify-start";

  const bubble = document.createElement("div");
  bubble.innerHTML = `
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
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
 * Initialisation au chargement de la page
 */
document.addEventListener("DOMContentLoaded", () => {
  loadConversationsFromStorage();
  
  // Nettoyer les conversations vides au démarrage
  deleteEmptyConversations();
  
  // Initialiser le dark mode
  initDarkMode();
  
  // Charger le compte à rebours du prochain GP
  fetchNextRaceCountdown();
  
  // Charger le top 3 des pilotes
  fetchTop3Drivers();
  
  if (!conversations || conversations.length === 0) {
    createConversation();
  } else {
    renderNavbarHistory();
    if (conversations.length>0) loadConversationIntoChat(conversations[0].id);
  }
  messageInput.focus();

  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(e);
    }
  });
  
  // Initialiser l'état de collapse de la navbar
  const savedNavbarCollapsed = localStorage.getItem('navbarCollapsed') === 'true';
  if (savedNavbarCollapsed && window.innerWidth >= 1024) {
    mainNavbar.classList.add("collapsed");
    isNavbarCollapsed = true;
  }
});

messageForm.addEventListener("submit", sendMessage);

// Fonctions de gestion de la navbar collapsible
function toggleNavbar() {
  // Sur mobile : open/close
  // Sur desktop : collapse/expand
  if (window.innerWidth < 1024) {
    // Mobile
    isNavbarOpen = !isNavbarOpen;
    if (isNavbarOpen) {
      mainNavbar.classList.remove("-translate-x-full");
      navOverlay.classList.remove("hidden");
    } else {
      mainNavbar.classList.add("-translate-x-full");
      navOverlay.classList.add("hidden");
    }
  } else {
    // Desktop
    toggleNavbarCollapsed();
  }
}

function toggleNavbarCollapsed() {
  isNavbarCollapsed = !isNavbarCollapsed;
  localStorage.setItem('navbarCollapsed', isNavbarCollapsed);
  
  if (isNavbarCollapsed) {
    mainNavbar.classList.add("collapsed");
  } else {
    mainNavbar.classList.remove("collapsed");
  }
}

function closeNavbar() {
  if (isNavbarOpen) {
    isNavbarOpen = false;
    mainNavbar.classList.add("-translate-x-full");
    navOverlay.classList.add("hidden");
  }
}

/**
 * Ouvre le panneau profil utilisateur (paramètres)
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
 * Affiche une notification toast
 */
function showNotification(message, type = 'info') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let icon = 'ℹ️';
  if (type === 'success') icon = '✅';
  if (type === 'error') icon = '❌';

  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  // Auto-remove after 3 seconds
  setTimeout(() => {
    toast.classList.add('fade-out');
    setTimeout(() => {
      toast.remove();
      if (container.childNodes.length === 0) container.remove();
    }, 300);
  }, 3000);
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
 * Affiche une notification toast (legacy function - compatibility)
 */
function showToast(message, isSuccess = true) {
  showNotification(message, isSuccess ? 'success' : 'error');
}

/**
 * Récupère et affiche le compte à rebours du prochain GP
 */
async function fetchNextRaceCountdown() {
  try {
    const response = await fetch('/next_race_countdown');
    const data = await response.json();

    const countdownText = document.getElementById('countdownText');
    const raceNameText = document.getElementById('raceNameText');

    if (data && data.countdown && data.countdown.trim()) {
      countdownText.textContent = data.countdown;
      countdownText.classList.remove('text-gray-400');
      countdownText.classList.add('text-gray-300');

      // Nom de la course + circuit si disponible
      let raceInfo = '';
      if (data.race_name) {
        raceInfo = `📍 ${data.race_name}`;
        if (data.circuit) {
          raceInfo += ` - ${data.circuit}`;
        }
      }

      // Ajouter la source en petit en dessous
      if (data.source) {
        raceInfo += `\n<span class="text-xs text-gray-500">Source: ${data.source}</span>`;
      }

      raceNameText.innerHTML = raceInfo;
    } else {
      // Fallback si aucune donnée
      countdownText.textContent = 'Prochainement...';
      raceNameText.innerHTML = '';
    }
  } catch (error) {
    console.error('Erreur récupération countdown:', error);
    const countdownText = document.getElementById('countdownText');
    const raceNameText = document.getElementById('raceNameText');
    if (countdownText) {
      countdownText.textContent = 'Informations bientôt disponibles';
      raceNameText.innerHTML = '';
    }
  }
}

// Rafraîchir le compte à rebours toutes les 5 minutes
setInterval(fetchNextRaceCountdown, 5 * 60 * 1000);

/**
 * Récupère et affiche le top 5 des pilotes F1
 */
async function fetchTop3Drivers() {
  try {
    const response = await fetch('/top_drivers?top_n=3');
    const data = await response.json();

    const driversList = document.getElementById('top3DriversList');
    if (!driversList) return;

    if (data && data.drivers && data.drivers.length > 0) {
      const medals = ['🥇', '🥈', '🥉'];
      let html = '';
      data.drivers.slice(0, 3).forEach((driver, index) => {
        const medal = medals[index] || `${index + 1}.`;
        html += `<div class="truncate">${medal} ${driver.name}</div>`;
      });
      driversList.innerHTML = html;
    } else {
      driversList.innerHTML = '<p class="text-gray-600 text-xs">—</p>';
    }
  } catch (error) {
    console.error('Erreur récupération top 3:', error);
    const driversList = document.getElementById('top3DriversList');
    if (driversList) {
      driversList.innerHTML = '<p class="text-gray-600 text-xs">—</p>';
    }
  }
}

// Rafraîchir le top 3 tous les lundis (cache hebdomadaire)
function scheduleTop3Refresh() {
  const now = new Date();
  const dayOfWeek = now.getDay(); // 0=dimanche, 1=lundi, ...
  
  // Si c'est lundi, rafraîchir
  if (dayOfWeek === 1) {
    // Vérifier si on a déjà rafraîchi aujourd'hui
    const lastRefresh = localStorage.getItem('top3LastRefresh');
    const today = now.toDateString();
    if (lastRefresh !== today) {
      fetchTop3Drivers();
      localStorage.setItem('top3LastRefresh', today);
    }
  }
  
  // Vérifier toutes les heures si on est lundi
  setTimeout(scheduleTop3Refresh, 60 * 60 * 1000);
}

// Lancer la vérification hebdomadaire
scheduleTop3Refresh();

/**
 * Animation de particules F1 en arrière-plan
 */
function initF1Particles() {
  const canvas = document.createElement('canvas');
  canvas.style.position = 'fixed';
  canvas.style.top = '0';
  canvas.style.left = '0';
  canvas.style.width = '100%';
  canvas.style.height = '100%';
  canvas.style.pointerEvents = 'none';
  canvas.style.zIndex = '0';
  canvas.style.opacity = '0.4';
  document.body.insertBefore(canvas, document.body.firstChild);

  const ctx = canvas.getContext('2d');
  let particles = [];
  let animationId;

  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  class Particle {
    constructor() {
      this.reset();
    }

    reset() {
      this.x = Math.random() * canvas.width;
      this.y = Math.random() * canvas.height;
      this.vx = -2 - Math.random() * 3; // Vitesse horizontale (vers la gauche)
      this.vy = (Math.random() - 0.5) * 0.5; // Légère dérive verticale
      this.size = Math.random() * 2 + 1;
      this.opacity = Math.random() * 0.5 + 0.2;
      this.life = 1;
    }

    update() {
      this.x += this.vx;
      this.y += this.vy;
      this.life -= 0.005;

      // Réinitialiser si hors écran ou vie écoulée
      if (this.x < -50 || this.life <= 0) {
        this.x = canvas.width + 50;
        this.y = Math.random() * canvas.height;
        this.life = 1;
      }
    }

    draw() {
      ctx.fillStyle = `rgba(220, 38, 38, ${this.opacity * this.life})`;
      ctx.fillRect(this.x, this.y, this.size * 15, this.size);
    }
  }

  function init() {
    resizeCanvas();
    particles = [];
    for (let i = 0; i < 30; i++) {
      particles.push(new Particle());
    }
  }

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    particles.forEach(particle => {
      particle.update();
      particle.draw();
    });

    animationId = requestAnimationFrame(animate);
  }

  window.addEventListener('resize', resizeCanvas);

  init();
  animate();

  // Cleanup function
  return () => {
    cancelAnimationFrame(animationId);
    window.removeEventListener('resize', resizeCanvas);
    canvas.remove();
  };
}

// Initialiser les particules F1 au chargement
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    initF1Particles();
  }, 500);
});
