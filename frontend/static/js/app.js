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

/**
 * Envoie un message au backend FastAPI
 */
async function sendMessage(event) {
  event.preventDefault();

  const message = messageInput.value.trim();
  if (!message || isWaiting) return;

  // Afficher le message utilisateur
  displayMessage(message, "user");

  // Vider l'input et désactiver le bouton
  messageInput.value = "";
  sendBtn.disabled = true;
  isWaiting = true;

  // Afficher le loader
  const loaderId = displayLoader();

  try {
    // Appel au backend POST /chat
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

    // Supprimer le loader
    removeMessage(loaderId);

    // Afficher la réponse du bot
    displayMessage(data.bot_response, "bot");
  } catch (error) {
    // Supprimer le loader
    removeMessage(loaderId);

    // Afficher le message d'erreur
    displayMessage(
      `❌ Erreur: ${error.message}`,
      "bot"
    );
    console.error("Erreur:", error);
  } finally {
    // Réactiver l'input et le bouton
    sendBtn.disabled = false;
    isWaiting = false;
    messageInput.focus();
  }
}

/**
 * Affiche un message dans la zone de chat
 * Support du markdown et emojis (liens cliquables)
 */
function displayMessage(text, role = "user") {
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  
  // Convertir le markdown simple en HTML (gras, italique, liens, listes)
  let htmlContent = text
    // [texte](url) → <a href="url" target="_blank">texte</a>
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color: #3b82f6; text-decoration: underline; font-weight: 600;">$1</a>')
    // **gras** → <strong>gras</strong>
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    // *italique* → <em>italique</em>
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    // Nouvelles lignes → <br>
    .replace(/\n/g, "<br>");
  
  bubble.innerHTML = htmlContent;

  messageDiv.appendChild(bubble);
  chatBox.appendChild(messageDiv);

  // Scroll vers le bas
  chatBox.scrollTop = chatBox.scrollHeight;

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
 * Efface l'historique et réinitialise l'UI
 */
async function clearChat() {
  if (!confirm("Êtes-vous sûr de vouloir effacer l'historique ?")) {
    return;
  }

  try {
    // Appel au backend POST /clear_history
    const response = await fetch("/clear_history", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("Erreur lors de l'effacement");
    }

    // Vider la zone de chat
    chatBox.innerHTML = `
      <div class="message-info">
        <p><strong>✅ Historique effacé</strong></p>
        <p>🏁 Posez une nouvelle question pour commencer...</p>
      </div>
    `;

    messageInput.focus();
  } catch (error) {
    alert(`Erreur: ${error.message}`);
    console.error("Erreur:", error);
  }
}

/**
 * Chargement initial - Récupérer l'historique existant
 */
async function loadChatHistory() {
  try {
    const response = await fetch("/history");
    if (!response.ok) throw new Error("Erreur du serveur");

    const data = await response.json();

    if (data.history && data.history.length > 0) {
      // Vider la zone d'info
      chatBox.innerHTML = "";

      // Afficher l'historique
      data.history.forEach((msg) => {
        displayMessage(msg.content, msg.role);
      });
    }
  } catch (error) {
    console.error("Erreur lors du chargement de l'historique:", error);
  }
}

/**
 * Initialisation au chargement de la page
 */
document.addEventListener("DOMContentLoaded", () => {
  loadChatHistory();
  messageInput.focus();

  // Raccourci clavier : Shift+Enter pour envoyer (optionnel)
  messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(e);
    }
  });
});

// Bind du formulaire
chatForm.addEventListener("submit", sendMessage);

