# ⚡ XEROS App Server + Android App

Architecture complète pour connecter ton smartphone Android à Hermes Agent via commandes vocales.

## Structure

```
/opt/data/xeros-app-server/     ← Serveur API Python (FastAPI)
/opt/data/xeros-android-app/    ← App Android native Kotlin
```

## Démarrage rapide

### 1. Serveur API

```bash
cd /opt/data/xeros-app-server
./start.sh
```

Le serveur écoute sur le port **8645**.

### 2. App Android

Ouvrir `/opt/data/xeros-android-app/` dans Android Studio, builder et installer sur le téléphone.

**Configuration dans l'app** (appui long sur le statut "● Connecté") :
- **Serveur API** : `http://<IP_DU_SERVEUR>:8645`
- **Clé secrète** : `xeros-godmode-2024`

## Endpoints API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health` | Santé du serveur |
| POST | `/chat` | Chat textuel → réponse texte |
| POST | `/voice` | Audio WAV → transcription → réponse + TTS audio |
| POST | `/quick` | Chat texte rapide (sans TTS) |

## Fonctionnalités App Android

- 🎤 **Reconnaissance vocale** — enregistre en WAV 16kHz, envoie au serveur
- 🔊 **Réponses audio** — TTS via Hermes, lecture automatique
- 💬 **Chat textuel** — clavier classique
- 🎨 **Design sombre** — thème XEROS orange/vert
- 🔐 **Auth HMAC-SHA256** — signature de chaque requête
- ⚙️ **Configurable** — URL serveur et clé modifiables dans l'app

## Service systemd (optionnel)

```bash
cp xeros-server.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now xeros-server
```

## Sécurité

- HMAC-SHA256 sur chaque requête
- Cleartext autorisé uniquement sur réseaux locaux (192.168.x.x, 10.x.x.x)
- Clé API configurable
