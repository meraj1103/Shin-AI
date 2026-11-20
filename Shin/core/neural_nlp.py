import os
import re
import random
import logging
import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

# Core intents and training samples (English, Hinglish, Marathi)
TRAINING_DATA = {
    "open_app": [
        "open chrome", "launch notepad", "start calculator", "open spotify",
        "open browser", "run code", "launch blender", "open whatsapp",
        "start steam", "start discord", "open application", "start notepad",
        "launch chrome", "open terminal", "open vs code", "chrome chalu kar"
    ],
    "close_app": [
        "close notepad", "exit calculator", "shutdown chrome", "close spotify",
        "close app", "close browser", "kill window", "exit application",
        "notepad band kar", "close chrome browser"
    ],
    "tell_time": [
        "what time is it", "tell me the time", "current time", "what is the time",
        "time kya hua hai", "samay kya hai", "aaj ki time batao", "ki vaajle",
        "time please", "tell time", "current time status", "vela kay aahe"
    ],
    "tell_date": [
        "what is the date today", "tell me the date", "current date", "date kya hai today",
        "aaj ki date kya hai", "aaj konti tarikh aahe", "date please", "tarikh sanga",
        "today date"
    ],
    "screenshot": [
        "take a screenshot", "capture the screen", "screenshot please", "screen click",
        "screenshot lo", "screen cha photo kaadh", "screen capture", "screenshot",
        "screen save kar"
    ],
    "mute_volume": [
        "mute the system", "mute volume", "mute audio", "silence", "chup ho jao",
        "mute kar do", "system mute", "audio off"
    ],
    "unmute_volume": [
        "unmute the volume", "unmute audio", "unmute the system", "unmute",
        "audio on", "sound chalu kar"
    ],
    "volume_up": [
        "volume up", "increase volume", "make it louder", "sound badhao",
        "volume increase", "sound increase", "awaj vadhav"
    ],
    "volume_down": [
        "volume down", "decrease volume", "make it quieter", "sound kam karo",
        "volume decrease", "sound decrease", "awaj kami kar"
    ],
    "set_volume": [
        "set volume to 50 percent", "change volume to 80", "volume eighty percent",
        "volume fifty", "volume adjust to 60", "volume hundred", "volume zero"
    ],
    "clean_pc": [
        "clean my pc", "free up memory", "clean cache", "clean junk files",
        "optimize system", "pc clean karo", "ram clean kar"
    ],
    "weather_query": [
        "how is the weather today", "weather report", "is it raining",
        "temperature in kolhapur", "mausam kaisa hai", "hawaman kase aahe",
        "weather update", "climate status"
    ],
    "chat": [
        "hello", "hi shin", "how are you", "kasa aahe", "kya chal raha hai",
        "good morning", "good evening", "namaskar", "namaste", "tum kashi aahes",
        "hey there", "hola", "wassup", "what is up", "khaana kha liya", "kashi aahes",
        "i had a long day", "i am so tired", "talk to me", "bore ho raha hai yaar",
        "yaar", "kuch baat karo", "gappa maar", "bol na"
    ],
    "tell_joke": [
        "tell me a joke", "crack a joke", "joke sunao", "ek joke saang",
        "make me laugh", "say something funny", "joke please"
    ],
    "tell_fact": [
        "tell me a fun fact", "fact of the day", "share a fact", "koi fact batao",
        "interesting fact", "fact please"
    ],
    "tell_riddle": [
        "ask me a riddle", "tell me a riddle", "riddle please", "koi paheli pucho",
        "paheli sunao", "riddle game"
    ],
    "activate_study_mode": [
        "activate study mode", "start study mode", "study session start",
        "padhai shuru karte hain", "study mode on", "study mode activate"
    ],
    "deactivate_study_mode": [
        "deactivate study mode", "stop study mode", "exit study mode",
        "study mode off", "stop study session"
    ],
    "check_study_status": [
        "check study status", "am i in study mode", "study time elapsed",
        "study progress"
    ],
    "smart_home_control": [
        "turn on the light", "turn off the fan", "switch off the bulb",
        "smart home control", "fan chalu kar", "light band kar"
    ],
    "youtube_play": [
        "play a video on youtube", "open youtube video", "youtube play song",
        "youtube video of", "play perfect on youtube",
        "search for night luffy on youtube", "search songs on youtube",
        "find dynamic video on youtube", "youtube search tutorials",
        "search lo-fi beats on youtube", "play night luffy song on youtube",
        "paly luffy song on youtube", "paly luffy song", "play luffy song",
        "play luffy song on youtube", "paly music", "play music",
        "koi gana lagao", "koi gana baja do", "koi gana bajao", "gana lagao",
        "gana bajao", "gana chalao", "sing koi gana laga do", "can you play music",
        "play some music", "play a song", "koi gaana lagao", "koi gana sunao",
        "kuch gana bajao", "kuch gaana sunao", "gana sunao"
    ],
    "tell_news": [
        "tell me the news", "latest tech news", "technology news",
        "technology updates", "what is happening in technology",
        "world news", "top headlines", "news today", "khabar batao"
    ],
    "train_shin": [
        "train yourself", "train shin", "train her", "teach her",
        "teach her new things", "teach shin", "seekho", "apne aap ko train karo",
        "learn about me", "know me better", "teach her how to behave",
        "how to behave", "behave better", "personality training",
        "train her teach her", "teach her nwe thing", "teach her new thing",
        "train her and teach her", "teach her everything",
        "mujhe jaano", "mujhe samjho", "about me seekho",
        "what do you know about me", "what have you learned about me",
        "what do you remember about me", "sikhao",
        "teach her to handle my moods", "make her smarter",
    ],
    "learn_from_internet": [
        "learn about quantum computing from internet",
        "learn from internet about black holes",
        "fetch and learn about artificial intelligence",
        "take info from internet about python 3.12",
        "internet se physics seekho",
        "search and learn about space exploration",
        "learn new things from internet about technology"
    ],
    "explain_concept": [
        "what is vs code", "explain laptop", "what is cpu", "what is ram", "what is gpu",
        "what is an app", "what is a web browser", "what is powerpoint", "what is ppt",
        "what is document", "what is a file", "explain files and folders",
        "difference between command and talk", "what is command and talk",
        "what to answer on command", "how to talk to me",
        "laptop kaise kaam karta hai", "ram kya hota hai", "cpu kya hai",
        "vs code ke baare mein batao", "explain screen vision"
    ],
    "locate_app": [
        "where is chrome installed", "where is blender located", "locate app vs code",
        "find where spotify is installed", "chrome kahan installed hai",
        "show notepad in file explorer", "find app path", "locate application"
    ],
    "help_with_project": [
        "help me with my project", "help with project", "project mein help karo",
        "debug my code", "check my code for errors", "review this code",
        "code review karo", "project help", "fix my program"
    ],
    "explain_screen_activity": [
        "what is happening on screen", "screen pe kya chal raha hai", "look at my screen",
        "what is on my screen", "screen pe kya hai", "summarize screen", "dekh screen pe"
    ],
    "screen_diagnose_bug": [
        "check screen error", "diagnose screen bug", "screen pe koi error hai kya",
        "dekh screen pe kya error hai", "find bug on screen", "screen error check karo"
    ],
    "generate_code": [
        "write python code for calculator", "generate a python script",
        "create a python function", "write javascript code",
        "code banao python mein", "code likho for snake game",
        "generate code for api request", "write script for file backup"
    ],
    "explain_code": [
        "explain this code", "code samjhao", "explain clipboard code",
        "yeh code kya karta hai", "explain python code", "what does this code do"
    ],
    "run_python_code": [
        "run python code", "execute python code", "python run karo",
        "run this python script", "execute this code", "python code chalao",
        "run code print hello", "execute snippet"
    ],
    "project_git_status": [
        "check git status", "git status", "project git status",
        "kya changes hue hain project mein", "git status batao",
        "check git repo status", "repository status check karo"
    ],
    "git_diff_summary": [
        "git diff", "explain git diff", "show git diff",
        "kya diff hai", "code changes summary", "summarize git changes"
    ],
    "create_project_file": [
        "create file test.py", "naya file banao utils.py", "create project file",
        "save clipboard to file script.py", "file bana do server.js", "make a new file"
    ],
    "draft_whatsapp_message": [
        "draft whatsapp message to dad", "draft message for meeting",
        "whatsapp message draft karo", "draft a message saying I will be late",
        "draft reply for friend on whatsapp"
    ],
    "review_code": [
        "review this code", "code review karo", "review file order service",
        "scan code for security", "check code for anti patterns", "code review"
    ],
    "check_ai_hardware": [
        "check ai hardware", "is my laptop copilot ready", "check npu",
        "ai hardware check", "check my gpu vram", "hardware ai capability"
    ],
    "get_ui_tree": [
        "get ui controls", "list buttons on screen", "screen pe kaunse buttons hain",
        "inspect ui tree", "get interactive elements"
    ],
    "click_ui_element": [
        "click button save", "click on submit", "click run button",
        "tap cancel button", "click control file"
    ],
    "quit_assistant": [
        "quit assistant", "exit assistant", "bye shin", "close shin",
        "band ho jao shin", "shut down shin"
    ]
}

# Preprocessing helpers
def tokenize(sentence):
    return re.findall(r'\b\w+\b', sentence.lower())

# Build vocabulary
all_words = []
tags = sorted(list(TRAINING_DATA.keys()))
xy = []

for tag, patterns in TRAINING_DATA.items():
    for pattern in patterns:
        w = tokenize(pattern)
        all_words.extend(w)
        xy.append((w, tag))

# Remove duplicates and sort
all_words = sorted(list(set(all_words)))

def bag_of_words(tokenized_sentence, words_vocab):
    bag = np.zeros(len(words_vocab), dtype=np.float32)
    for idx, w in enumerate(words_vocab):
        if w in tokenized_sentence:
            bag[idx] = 1.0
    return bag

# PyTorch Intent Classification Model (Feed-Forward Neural Network / MLP)
class IntentMLP(nn.Module):
    def __init__(self, input_size, hidden_size, num_classes):
        super(IntentMLP, self).__init__()
        self.l1 = nn.Linear(input_size, hidden_size)
        self.relu = nn.ReLU()
        self.l2 = nn.Linear(hidden_size, num_classes)
        
    def forward(self, x):
        out = self.l1(x)
        out = self.relu(out)
        out = self.l2(out)
        return out

# Path to save/load weights
MODEL_DIR = os.path.join("data")
MODEL_PATH = os.path.join(MODEL_DIR, "neural_intent_model.pth")

# Model hyper-parameters
INPUT_SIZE = len(all_words)
HIDDEN_SIZE = 16
NUM_CLASSES = len(tags)

_model = None

def _train_and_save_model():
    global _model
    logger.info("Training neural intent classifier on CPU...")
    
    # Prepare training tensors
    X_train = []
    y_train = []
    
    for (pattern_words, tag) in xy:
        bag = bag_of_words(pattern_words, all_words)
        X_train.append(bag)
        label = tags.index(tag)
        y_train.append(label)
        
    X_train = torch.tensor(np.array(X_train), dtype=torch.float32)
    y_train = torch.tensor(np.array(y_train), dtype=torch.long)
    
    model = IntentMLP(INPUT_SIZE, HIDDEN_SIZE, NUM_CLASSES)
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    
    # Train for 150 epochs (extremely fast, ~0.03 seconds)
    for epoch in range(150):
        # Forward pass
        outputs = model(X_train)
        loss = criterion(outputs, y_train)
        
        # Backward and optimize
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
    # Save the trained model and vocabulary metadata
    os.makedirs(MODEL_DIR, exist_ok=True)
    state = {
        "model_state": model.state_dict(),
        "input_size": INPUT_SIZE,
        "hidden_size": HIDDEN_SIZE,
        "num_classes": NUM_CLASSES,
        "all_words": all_words,
        "tags": tags
    }
    torch.save(state, MODEL_PATH)
    _model = model
    logger.info("Neural model training complete and saved successfully.")

def init_model():
    global _model, all_words, tags
    if _model is not None:
        return
        
    current_tags = sorted(list(TRAINING_DATA.keys()))
    if os.path.exists(MODEL_PATH):
        try:
            state = torch.load(MODEL_PATH, map_location="cpu")
            if state.get("tags") != current_tags:
                logger.info("Training tags updated (%d vs %d). Retraining neural model...", len(state.get("tags", [])), len(current_tags))
                _train_and_save_model()
                return
            all_words = state["all_words"]
            tags = state["tags"]
            _model = IntentMLP(state["input_size"], state["hidden_size"], state["num_classes"])
            _model.load_state_dict(state["model_state"])
            _model.eval()
            logger.info("Loaded neural intent classifier weights successfully.")
        except Exception as exc:
            logger.warning("Failed to load neural model weights: %s. Retraining...", exc)
            _train_and_save_model()
    else:
        _train_and_save_model()

# Extract arguments from text for common intents
def extract_neural_args(intent_name: str, text: str) -> dict:
    args = {}
    cleaned = text.lower()
    
    # Strip trigger words
    if intent_name == "open_app":
        cleaned = re.sub(r'\b(open|launch|start|run|shin)\b', '', cleaned).strip()
        args["app"] = cleaned if cleaned else "app"
    elif intent_name == "close_app":
        cleaned = re.sub(r'\b(close|exit|stop|kill|terminate|shin)\b', '', cleaned).strip()
        args["app"] = cleaned if cleaned else "app"
    elif intent_name == "set_volume":
        match = re.search(r'\d+', text)
        args["level"] = int(match.group(0)) if match else 50
    elif intent_name in ("volume_up", "volume_down"):
        match = re.search(r'\d+', text)
        args["delta"] = int(match.group(0)) if match else 10
    elif intent_name == "youtube_play":
        cleaned = re.sub(r'\b(play|search|open|on youtube|youtube|video|of|koi|bhi|gaana|gana|geet|lagao|laga do|bajao|baja do|chalao|chala do|sunao|suna do|sing|can you|music|song)\b', '', cleaned, flags=re.IGNORECASE).strip()
        args["query"] = cleaned if cleaned else "random hindi songs mix"
    elif intent_name == "spotify_play":
        cleaned = re.sub(r'\b(play|search|open|on spotify|spotify|song|music)\b', '', cleaned).strip()
        args["query"] = cleaned if cleaned else "music"
    elif intent_name == "web_search":
        cleaned = re.sub(r'\b(search for|search|google|find)\b', '', cleaned).strip()
        args["query"] = cleaned if cleaned else "search query"
    elif intent_name == "open_url":
        cleaned = re.sub(r'\b(open website|open link|go to|open)\b', '', cleaned).strip()
        args["url"] = cleaned if cleaned else "google.com"
    elif intent_name == "explain_concept":
        cleaned = re.sub(r'\b(what is|explain|tell me about|batao|kya hai|kya hota hai|samjhao|the)\b', '', cleaned).strip()
        args["concept"] = cleaned if cleaned else "laptop"
    elif intent_name == "locate_app":
        cleaned = re.sub(r'\b(where is|locate|find where|installed|located|kahan hai|kahan installed hai|app)\b', '', cleaned).strip()
        args["app"] = cleaned if cleaned else "app"
    elif intent_name == "generate_code":
        cleaned = re.sub(r'\b(write|generate|create|code|script|program|function|for|to)\b', '', cleaned).strip()
        args["prompt"] = cleaned if cleaned else "python script"
        args["language"] = "python"
    elif intent_name == "explain_code":
        args = {}
    elif intent_name == "run_python_code":
        cleaned = re.sub(r'\b(run|execute|python|code|script|chalao|karo|snippet)\b', '', cleaned).strip()
        args["code"] = cleaned if cleaned else ""
    elif intent_name == "create_project_file":
        cleaned = re.sub(r'\b(create|make|new|project|file|banao|bana do|save|clipboard|to)\b', '', cleaned).strip()
        args["filename"] = cleaned if cleaned else "new_file.py"
    elif intent_name == "draft_whatsapp_message":
        args["topic"] = cleaned
    elif intent_name in ("project_git_status", "git_diff_summary", "check_ai_hardware", "get_ui_tree"):
        args = {}
    elif intent_name == "review_code":
        cleaned = re.sub(r'\b(review|code|file|scan|for|check|karo)\b', '', cleaned).strip()
        args["filepath"] = cleaned if cleaned else ""
    elif intent_name == "click_ui_element":
        cleaned = re.sub(r'\b(click|button|control|tap|on|the)\b', '', cleaned).strip()
        args["name"] = cleaned if cleaned else "button"
        
    return args

def predict_intent(text: str) -> dict | None:
    """
    Run PyTorch inference to classify text.
    Returns parsed intent dictionary if confidence > 0.80, else None.
    """
    init_model()
    if _model is None:
        return None
        
    tokenized = tokenize(text)
    bag = bag_of_words(tokenized, all_words)
    if not any(bag):
        return None
    bag = torch.tensor(bag, dtype=torch.float32).unsqueeze(0)
    
    with torch.no_grad():
        outputs = _model(bag)
        probs = torch.softmax(outputs, dim=1)
        max_prob, idx = torch.max(probs, dim=1)
        confidence = max_prob.item()
        
    intent_name = tags[idx.item()]
    
    # Require higher confidence for casual chat to avoid hijacking factual LLM questions
    required_conf = 0.95 if intent_name == "chat" else 0.80
    
    if confidence >= required_conf:
        args = extract_neural_args(intent_name, text)
        
        # Guard against incomplete sentences (e.g. "close the" or "open a")
        STOPWORDS = {"the", "a", "an", "this", "that", "it", "please", "karo", "kar", "kholo", "band", "shin", "app", "application"}
        if intent_name in ("open_app", "close_app"):
            app_val = args.get("app", "").strip().lower()
            if not app_val or app_val in STOPWORDS or len(app_val) <= 1:
                return None
        elif intent_name in ("youtube_play", "spotify_play", "web_search"):
            query_val = args.get("query", "").strip().lower()
            if not query_val or query_val in STOPWORDS or len(query_val) <= 1:
                return None
        elif intent_name == "open_url":
            url_val = args.get("url", "").strip().lower()
            if not url_val or url_val in STOPWORDS or len(url_val) <= 1:
                return None
                
        logger.info("Neural network predicted intent: %s (confidence: %.2f)", intent_name, confidence)
        return {
            "intent": intent_name,
            "args": args,
            "_confidence": round(confidence, 2)
        }
        
    return None
