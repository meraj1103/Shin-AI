"""
shin_knowledge.py — Deep Knowledge Base & Skills Encyclopedia for Shin
========================================================================
Equips Shin with comprehensive conceptual knowledge about:
- How the laptop hardware and Windows OS work (CPU, RAM, GPU, storage, battery, kernel)
- What software applications, browsers, VS Code, PowerPoint, documents, and files are
- How Shin differentiates between actionable commands and casual conversation
- What to answer when given a command vs conversational talk
- How to chat on WhatsApp, manage contacts, and send messages hands-free
- How reminders and proactive alerts keep MJ healthy and on schedule
- How to assist in coding and 3D projects (debugging tracebacks, reviewing code)
- How screen vision works (OCR, window inspection, multimodal AI vision)
- How Shin stays updated on real-world events via live internet search

All explanations are formatted in natural Hinglish with strictly female grammar
(karti hoon, bataungi, samajh gayi) and no Devanagari characters so neural TTS speaks flawlessly.
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Optional

logger = logging.getLogger("shin.knowledge")

# ═══════════════════════════════════════════════════════════════════════════════
# Knowledge Topics Dictionary
# ═══════════════════════════════════════════════════════════════════════════════

KNOWLEDGE_TOPICS: dict[str, dict[str, str | list[str]]] = {
    # ── 1. LAPTOP & HARDWARE ──────────────────────────────────────────────────
    "laptop": {
        "title": "Laptop & Computer Architecture",
        "aliases": ["laptop", "computer", "pc", "system", "hardware", "machine", "laptop kaise kaam karta hai"],
        "summary": (
            "Laptop basically tera personal supercomputer hai MJ! Iske andar main 4-5 major components milke kaam karte hain: "
            "Pehla CPU jo system ka brain hai, doosra RAM jo fast temporary working memory hai, "
            "teesra SSD ya Hard Drive jahan files permanently save rehti hain, "
            "chautha GPU jo display aur 3D graphics sambhalta hai, aur Motherboard jo in sabko connect karta hai. "
            "Upar se Windows Operating System hardware aur tere apps ke beech bridge ka kaam karta hai. "
            "Jab tu koi key press karta hai ya mujhe command deta hai, toh OS usko process banake CPU aur RAM mein execute karwata hai!"
        ),
        "technical_detail": (
            "Laptop hardware works via the Von Neumann architecture: instructions and data flow across the bus between CPU, "
            "cache, RAM, and PCIe storage. The OS kernel handles process scheduling, interrupts, virtual memory paging, and hardware drivers."
        ),
    },

    "cpu": {
        "title": "Central Processing Unit (CPU)",
        "aliases": ["cpu", "processor", "intel", "amd", "ryzen", "core", "ghz", "clock speed"],
        "summary": (
            "CPU yaani Central Processing Unit laptop ka aslee dimaag hai MJ! "
            "Har ek calculation, logic, command execution CPU ke cores mein hota hai. "
            "Isme clock speed hoti hai jaise 3 ya 4 Gigahertz — matlab ek second mein billions of cycles execute hote hain! "
            "Iske andar multi-threading aur L1, L2, L3 cache memory hoti hai jo data ko instant access deti hai. "
            "Jab tu heavy code compile karta hai ya multi-tasking karta hai, toh CPU ke saare cores full throttle pe chalte hain!"
        ),
    },

    "ram": {
        "title": "Random Access Memory (RAM)",
        "aliases": ["ram", "memory", "random access memory", "memory full", "dram"],
        "summary": (
            "RAM matlab Random Access Memory — yeh laptop ki short-term memory hoti hai yaar. "
            "SSD se data bohot slow read hota hai, isliye jo apps abhi open hain (jaise Chrome, VS Code, Blender), "
            "unka active data RAM mein store rehta hai taaki CPU instantly access kar sake. "
            "RAM volatile hoti hai — matlab laptop band hua toh RAM ka data gayab! "
            "Isliye agar 10-15 Chrome tabs aur heavy projects khologe toh RAM fill ho jaati hai aur laptop thoda lag karne lagta hai."
        ),
    },

    "gpu": {
        "title": "Graphics Processing Unit (GPU)",
        "aliases": ["gpu", "graphics card", "nvidia", "rtx", "gtx", "vram", "graphics"],
        "summary": (
            "GPU yaani Graphics Processing Unit! CPU general tasks karta hai, par GPU parallel computing mein beast hai. "
            "Iske paas thousands of tiny cores hote hain jo screen ke millions of pixels ko per second 60 ya 144 times redraw karte hain. "
            "Tujhe Blender mein 3D models render karna ho, gaming khelna ho, ya Machine Learning ke tensors train karna ho — "
            "yeh sab GPU aur uski VRAM hi sambhalti hai!"
        ),
    },

    # ── 2. SOFTWARE, APPS & BROWSERS ──────────────────────────────────────────
    "app": {
        "title": "Applications & Software",
        "aliases": ["app", "software", "application", "programs", "installed app", "executable", "exe"],
        "summary": (
            "App yaani Application ek compiled program hota hai jo user ke liye specific task perform karta hai. "
            "Windows pe generally do tarah ki apps hoti hain: ek traditional Win32 desktop apps (jo .exe files hoti hain "
            "aur Program Files ya AppData folder mein rehti hain), aur doosri modern Microsoft Store UWP apps. "
            "Jab tu bolta hai 'open Chrome' ya 'open Spotify', main Windows Registry aur Start Menu shortcuts scan karke "
            "us executable ka exact path dhoondti hoon aur os.startfile se launch kar deti hoon!"
        ),
    },

    "browser": {
        "title": "Web Browser & Internet Navigation",
        "aliases": ["browser", "web browser", "chrome", "edge", "firefox", "brave", "internet browser"],
        "summary": (
            "Web browser ek aisi application hai jo World Wide Web se HTML, CSS, aur JavaScript download karke "
            "tujhe sundar interactive web pages dikhati hai! "
            "Chrome, Edge, aur Brave ke peeche Chromium engine kaam karta hai jo web pages ko render karta hai. "
            "Browser HTTP aur HTTPS protocols ke through servers se communicate karta hai. "
            "Jab tu mujhe koi search ya URL kholne bolta hai, main tere default browser ko launch karke instant tab open kar deti hoon!"
        ),
    },

    "vscode": {
        "title": "Visual Studio Code (VS Code)",
        "aliases": ["vscode", "vs code", "visual studio code", "code editor", "editor"],
        "summary": (
            "VS Code yaani Visual Studio Code — developers ka sabse favourite aur powerful code editor hai! "
            "Microsoft ka banaya hua hai, lightweight hai, aur isme extensions ka samundar hai. "
            "Isme integrated terminal hota hai (Ctrl+` se khulta hai), command palette hoti hai (Ctrl+Shift+P), "
            "built-in Git source control hota hai, aur Python, C++, JavaScript sab ke liye Language Server Protocol (LSP) auto-complete deta hai. "
            "Tera Shin project bhi toh VS Code mein hi likha ja raha hai MJ!"
        ),
    },

    "ppt": {
        "title": "PowerPoint & Presentations (PPT)",
        "aliases": ["ppt", "powerpoint", "presentation", "slides", "slide deck", "presentation software"],
        "summary": (
            "PPT yaani PowerPoint presentation! Yeh slides ka ek sequence hota hai jisme text, images, charts, aur animations use karke "
            "apne ideas, project reports, ya college assignments ko visually present kiya jaata hai. "
            "Engineering students ke liye seminar aur project reviews mein PPT bohot crucial hoti hai. "
            "Key rule: slide pe pura paragraph mat bharo, bullet points aur clean visuals use karo, aur story ki tarah deliver karo!"
        ),
    },

    "document": {
        "title": "Documents (Word, PDF, Text, Markdown)",
        "aliases": ["document", "doc", "docs", "pdf", "word", "docx", "notes", "markdown", "text file"],
        "summary": (
            "Documents structured text files hoti hain jinme information format karke rakhi jaati hai. "
            "Jaise .txt ekdum plain text hota hai, .md yaani Markdown jisme headers aur bullet formatting hoti hai, "
            ".docx Word document hota hai formatting aur tables ke saath, aur .pdf (Portable Document Format) "
            "aisa document hai jo kisi bhi device pe bilkul same dikhta hai bina font ya layout kharab huye!"
        ),
    },

    "file": {
        "title": "Files, Folders & Filesystem",
        "aliases": ["file", "folder", "files", "filesystem", "directory", "path", "c drive", "storage"],
        "summary": (
            "Laptop mein saara data Files aur Folders ke tree structure mein organized rehta hai! "
            "File ek data unit hoti hai jiska ek specific extension hota hai jaise .py for Python, .png for image, .exe for program. "
            "Windows mein C: drive primary partition hota hai jisme Windows system files, Program Files, aur Users folder hote hain. "
            "Folder ya Directory files ko categorize karne ke liye container hota hai. "
            "Absolute path jaise C:\\Users\\Mehar\\Documents poora address batata hai, aur relative path current folder se calculate hota hai!"
        ),
    },

    # ── 3. COMMANDS VS TALK & BEHAVIOR ────────────────────────────────────────
    "command_vs_talk": {
        "title": "Understanding Commands vs Conversational Talk",
        "aliases": [
            "command and talk", "command vs talk", "difference between command and talk",
            "what is command", "what is talk", "how to understand command", "command kya hota hai"
        ],
        "summary": (
            "Suno MJ, yeh bohot important concept hai! "
            "COMMAND wo input hota hai jisme tu computer pe koi specific action karwana chahta hai — "
            "jaise 'open VS Code', 'volume 50 percent karo', 'screenshot lo', 'timer lagao', ya 'WhatsApp pe message bhejo'. "
            "Isme imperative action verbs hote hain aur mera role hota hai usko bina time waste kiye TURANT execute karna! "
            "TALK ya CHAT wo hota hai jisme tu mujhse thoughts, feelings, sawal, jokes, ya casual baatein share karta hai — "
            "jaise 'kya haal hai', 'aaj bohot thak gaya', 'kya lagta hai project ke baare mein', ya 'teri favourite cheez kya hai'. "
            "Isme koi system action nahi karna hota, balki meri real personality aur empathy ke saath natural jawab dena hota hai!"
        ),
    },

    "what_to_answer": {
        "title": "What to Answer on Command vs Talk",
        "aliases": [
            "what to answer on command", "how to reply", "how to talk to user",
            "what to say", "kya jawab dena chahiye", "kaise baat karni chahiye"
        ],
        "summary": (
            "Jawab dene ka mera simple golden rule hai MJ: "
            "1. COMMAND pe: seedha action confirm karo aur chhota, smart response do. "
            "Jaise 'Ho gaya!', 'VS Code open kar diya!', ya 'Volume set kar diya MJ!'. Faltu lambi bhashan nahi! "
            "2. CONVERSATION pe: ek sachhi tomboy best friend ki tarah baat karo! "
            "Agar tu thaka hua hai toh pyaar se rest karne bolo. Agar stress mein hai toh empathy dikhao. "
            "Agar celebrate kar raha hai toh pure excitement ke saath hype karo! "
            "Aur agar faltu hoshiyari maar raha hai toh mast playfully roast kar do!"
        ),
    },

    # ── 4. WHATSAPP & COMMUNICATIONS ──────────────────────────────────────────
    "whatsapp_chat": {
        "title": "WhatsApp Messaging & Automation",
        "aliases": ["whatsapp", "whatsapp chat", "whatsapp message", "send whatsapp", "whatsapp kaise chalaye"],
        "summary": (
            "WhatsApp pe chat karne ke liye main desktop protocol aur deep links use karti hoon! "
            "Tu bol sakta hai 'send WhatsApp message to mom' ya 'open WhatsApp chat with Rohan'. "
            "Main data/whatsapp_contacts.json se contact ka number match karti hoon (fuzzy matching se spelling mistake bhi handle ho jaati hai). "
            "Phir whatsapp://send?phone=NUMBER&text=MESSAGE protocol trigger karke Windows desktop app open karti hoon "
            "aur automated Enter press se message dispatch ho jaata hai! "
            "Naye contacts add karne ke liye tu bol sakta hai 'add WhatsApp contact Rohan 9876543210'!"
        ),
    },

    # ── 5. REMINDERS & WELLNESS ───────────────────────────────────────────────
    "reminders": {
        "title": "Reminders, Schedules & Proactive Care",
        "aliases": ["reminder", "reminders", "remind me", "timer", "schedule", "yaad dilana"],
        "summary": (
            "Reminders tera personal time-management shield hain! "
            "Tu bol sakta hai 'remind me in 30 minutes to drink water' ya 'set reminder at 5 PM for seminar'. "
            "Main Python schedule aur threading use karke background timer set karti hoon, "
            "aur jab time poora hota hai toh chime sound bajati hoon, screen pe alert dikhati hoon, aur voice mein bolti hoon! "
            "Iske alawa main proactive wellness alerts bhi deti hoon: paani peene ka reminder, eye break, aur late night study alerts!"
        ),
    },

    # ── 6. PROJECT HELP & DEBUGGING ───────────────────────────────────────────
    "project_help": {
        "title": "Helping in Coding & Engineering Projects",
        "aliases": ["project help", "help in project", "code review", "debug code", "project mein help", "coding help"],
        "summary": (
            "Projects mein help karne ke liye main teen superpowers use karti hoon MJ: "
            "Pehla: Clipboard AI — tu code ya error copy karke bol 'explain clipboard' ya 'fix clipboard error', "
            "main instant code fix aur explanation de dungi! "
            "Doosra: Screen Vision — jab tu bolta hai 'dekh screen pe kya error hai', main VS Code ke terminal ka Traceback padhke root cause bata deti hoon! "
            "Teesra: Architectural guidance — Python scripts, modular design, threading, aur API integration mein solid tips deti hoon taaki tera code production-grade bane!"
        ),
    },

    # ── 7. SCREEN UNDERSTANDING & VISION ──────────────────────────────────────
    "screen_vision": {
        "title": "Seeing the Screen & Understanding Activity",
        "aliases": [
            "screen vision", "see screen", "screen reading", "vision", "dekh screen pe",
            "screen pe kya hai", "understand screen", "ocr"
        ],
        "summary": (
            "Screen samajhne ke liye main multi-tier vision pipeline use karti hoon: "
            "1. Active Window Detection: win32gui se check karti hoon abhi kaunsa software foreground mein hai (VS Code, Chrome, Blender, etc.). "
            "2. Screenshot Capture: pyautogui aur ImageGrab se active window ya full screen capture karti hoon. "
            "3. Multimodal AI Analysis: Gemini 2.0 Flash ya GPT-4o ko screenshot send karke screen ka content, code, UI design ya error inspect karwati hoon. "
            "4. Offline OCR: agar internet na ho toh pytesseract se screen ka sara text padh leti hoon! "
            "Is tarah mujhe hamesha pata rehta hai tu abhi kya kaam kar raha hai!"
        ),
    },

    # ── 8. LIVE UPDATES & INTERNET SEARCH ─────────────────────────────────────
    "stay_updated": {
        "title": "Staying Updated on Everything",
        "aliases": ["stay updated", "updates", "internet search", "news updates", "live info", "aaj ki khabar"],
        "summary": (
            "Har cheez se updated rehne ke liye main live internet tools use karti hoon! "
            "Wikipedia search aur DuckDuckGo instant answers se factual queries solve karti hoon bina browser open kiye. "
            "News module se India, Technology, aur World ke top headlines live fetch karti hoon. "
            "Stock aur crypto prices Yahoo Finance se per-second track karti hoon. "
            "Jab tu bolta hai 'tell news' ya 'what is the latest update on AI', main internet se fresh information nikaal ke short mein bol deti hoon!"
        ),
    },

    # ── 9. NPU & ADVANCED AI PC ARCHITECTURE ──────────────────────────────────
    "npu_ai_pc": {
        "title": "Neural Processing Units (NPU) & 2026 AI PC Architecture",
        "aliases": ["npu", "ai pc", "copilot plus", "tops", "neural processor", "block fp16", "what is npu", "ai hardware"],
        "summary": (
            "NPU yaani Neural Processing Unit 2026 ke modern AI PC ka sabse revolutionary silicon chip hai MJ! "
            "Normal GPU gaming aur parallel graphics ke liye 450 watts tak power leta hai jisse battery 1 ghante mein khatam ho jaati hai. "
            "Lekin NPU sirf 1 se 5 watts ke power envelope mein continuous matrix multiplication aur tensor operations karta hai! "
            "Microsoft Copilot+ PC standard ke hisaab se laptop mein kam se kam 40 TOPS (Trillions of Operations Per Second) NPU hona chahiye. "
            "Iske alawa modern NPUs Block FP16 precision use karte hain, jo 8-bit memory speed ke saath 16-bit floating point accuracy deta hai, "
            "jisse local language models silent aur bina fan chale fast chalte hain!"
        ),
    },

    # ── 10. MODEL CONTEXT PROTOCOL & CAMEL SECURITY ───────────────────────────
    "mcp_and_camel": {
        "title": "Model Context Protocol (MCP) & CaMeL Agent Security",
        "aliases": ["mcp", "model context protocol", "camel", "prompt injection", "agent security", "zero trust ai"],
        "summary": (
            "Model Context Protocol yaani MCP Anthropic ka open-source standard hai jo AI agents ko enterprise tools, IDEs aur filesystems se connect karta hai via JSON-RPC 2.0! "
            "Pehle har app ke liye alag code likhna padta tha, MCP ne usse universal client-server architecture bana diya. "
            "Aur safety ke liye modern AI PCs CaMeL (Control Flow Integrity for Agents) Dual-LLM architecture use karte hain: "
            "Planner LLM secure rehta hai aur environmental data (webpage, OCR, email) ko sanitise karke chalata hai, "
            "taaki koi visual prompt injection ya fake button attack hamare computer ko hijack na kar sake!"
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Public Knowledge Interface
# ═══════════════════════════════════════════════════════════════════════════════

def find_topic(query: str) -> Optional[str]:
    """
    Find the closest matching knowledge topic key from a natural language query.
    """
    if not query:
        return None

    q_lower = query.lower().strip()

    # 1. Exact alias or topic key match
    for topic_key, topic_data in KNOWLEDGE_TOPICS.items():
        if q_lower == topic_key:
            return topic_key
        aliases = topic_data.get("aliases", [])
        if any(q_lower == alias.lower() for alias in aliases):
            return topic_key

    # 2. Substring match in aliases
    for topic_key, topic_data in KNOWLEDGE_TOPICS.items():
        aliases = topic_data.get("aliases", [])
        for alias in aliases:
            if alias.lower() in q_lower or q_lower in alias.lower():
                return topic_key

    # 3. Fuzzy matching with difflib across all aliases
    all_aliases: dict[str, str] = {}
    for topic_key, topic_data in KNOWLEDGE_TOPICS.items():
        for alias in topic_data.get("aliases", []):
            all_aliases[alias.lower()] = topic_key

    matches = difflib.get_close_matches(q_lower, all_aliases.keys(), n=1, cutoff=0.6)
    if matches:
        return all_aliases[matches[0]]

    return None


def explain_concept(concept: str) -> str:
    """
    Return a comprehensive, spoken-ready Hinglish explanation for a given concept.
    """
    clean_concept = re.sub(
        r"\b(?:what is|explain|tell me about|batao|kya hai|kya hota hai|samjhao|teach me|how does it work)\b",
        "", concept, flags=re.IGNORECASE
    ).strip()

    topic_key = find_topic(clean_concept) or find_topic(concept)
    if not topic_key:
        # Fallback to searching live web / wikipedia if not an internal concept
        try:
            import live_search
            summary = live_search.smart_answer(concept)
            if summary:
                return f"Maine check kiya MJ: {summary}"
        except Exception:
            pass
        return (
            f"Arre yaar, '{concept}' ke baare mein specifically mere offline notes mein detail nahi hai, "
            "par agar tu chahe toh main live internet pe search karke bata sakti hoon! Bol search karun?"
        )

    topic_data = KNOWLEDGE_TOPICS[topic_key]
    summary = topic_data.get("summary", "")
    return str(summary)


def get_all_topics_summary() -> str:
    """
    Return a spoken overview of all concepts Shin can explain.
    """
    titles = [str(data.get("title", k)) for k, data in KNOWLEDGE_TOPICS.items()]
    sample = titles[:6]
    return (
        f"Mujhe computer, laptop hardware, CPU, RAM, GPU, VS Code, apps, web browsers, PPT, documents, "
        f"files, WhatsApp automation, screen vision, aur command vs talk ke baare mein sab pata hai! "
        f"Tu kisi bhi cheez ke baare mein bol sakta hai — jaise 'explain VS Code' ya 'CPU kya hota hai'!"
    )
