"""
tests/test_nlp.py — Unit tests for the intent parser (rule-based tier)

Run with:  pytest tests/ -v
"""

import sys
import os
# Ensure the project root and core/ are both on the path so this file works when
# run directly (e.g. `python tests/test_nlp.py`) as well as via pytest + conftest.
_project_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(_project_root, "core"))
sys.path.insert(0, _project_root)


import pytest
from nlp import parse_intent
import nlp
_original_ai_parse = nlp._ai_parse
nlp._ai_parse = lambda text: None


# ── Helper ─────────────────────────────────────────────────────────────────────

def intent_of(text: str) -> str:
    return parse_intent(text)["intent"]

def args_of(text: str) -> dict:
    return parse_intent(text)["args"]


# ── App control ────────────────────────────────────────────────────────────────

class TestAppControl:
    def test_open_chrome(self):
        assert intent_of("open chrome") == "open_app"
        assert args_of("open chrome")["app"] == "chrome"

    def test_launch_spotify(self):
        assert intent_of("launch Spotify") == "open_app"

    def test_start_notepad(self):
        assert intent_of("start notepad") == "open_app"

    def test_open_canva(self):
        assert intent_of("open canva") == "open_app"
        assert args_of("open canva")["app"] == "canva"

    def test_open_paint(self):
        assert intent_of("open paint") == "open_app"
        assert args_of("open paint")["app"] == "paint"

    def test_predict_next_move(self):
        assert intent_of("what should I do next") == "predict_next_move"
        assert intent_of("aage kya karoon") == "predict_next_move"
        assert intent_of("predict my next move") == "predict_next_move"

    def test_file_search(self):
        assert intent_of("find my file resume") == "file_search"
        assert args_of("find my file resume")["query"] == "resume"
        assert intent_of("where is my document notes") == "file_search"
        assert intent_of("project report dhoondh ke do") == "file_search"

    def test_close_app(self):
        assert intent_of("close firefox") == "close_app"
        assert args_of("close firefox")["app"] == "firefox"

    def test_close_the_app(self):
        assert intent_of("close the youtube") == "close_app"
        assert args_of("close the youtube")["app"] == "youtube"

    def test_kill_app(self):
        assert intent_of("kill discord") == "close_app"

    def test_close_active_window(self):
        assert intent_of("close this window") == "close_active_window"
        assert intent_of("close the current app") == "close_active_window"


# ── Volume ─────────────────────────────────────────────────────────────────────

class TestVolume:
    def test_mute(self):
        assert intent_of("mute") == "mute_volume"

    def test_silence(self):
        assert intent_of("silence the volume") == "mute_volume"

    def test_unmute(self):
        assert intent_of("unmute") == "unmute_volume"

    def test_volume_up(self):
        assert intent_of("volume up") == "volume_up"

    def test_increase_volume(self):
        assert intent_of("increase the volume") == "volume_up"

    def test_volume_down(self):
        assert intent_of("turn the volume down") == "volume_down"

    def test_set_volume(self):
        assert intent_of("set volume to 60") == "set_volume"
        assert args_of("set volume to 60")["level"] == 60

    def test_set_volume_percent(self):
        assert args_of("volume 75 percent")["level"] == 75

    def test_set_volume_percentage_advanced(self):
        assert intent_of("set to 20%") == "set_volume"
        assert args_of("set to 20%")["level"] == 20
        assert intent_of("set to 50 percent volume") == "set_volume"
        assert args_of("set to 50 percent volume")["level"] == 50


# ── Voice Pitch ────────────────────────────────────────────────────────────────

class TestVoicePitch:
    def test_set_voice_pitch_high(self):
        assert intent_of("set voice pitch to high") == "set_voice_pitch"
        assert args_of("set voice pitch to high")["pitch"] == "high"

    def test_set_voice_pitch_deep(self):
        assert intent_of("change pitch to deep") == "set_voice_pitch"
        assert args_of("change pitch to deep")["pitch"] == "deep"

    def test_reset_voice_pitch(self):
        assert intent_of("reset voice pitch") == "set_voice_pitch"
        assert args_of("reset voice pitch")["pitch"] == "default"

    def test_voice_pitch_hz(self):
        assert intent_of("set pitch to +15Hz") == "set_voice_pitch"
        assert args_of("set pitch to +15Hz")["pitch"] == "+15hz"


# ── Brightness ─────────────────────────────────────────────────────────────────

class TestBrightness:
    def test_brightness_up(self):
        assert intent_of("brightness up") == "brightness_up"

    def test_brightness_down(self):
        assert intent_of("lower the brightness") == "brightness_down"

    def test_set_brightness(self):
        assert intent_of("set brightness to 50") == "set_brightness"
        assert args_of("set brightness to 50")["level"] == 50

    def test_set_brightness_percentage_advanced(self):
        assert intent_of("set to 80% brightness") == "set_brightness"
        assert args_of("set to 80% brightness")["level"] == 80
        assert intent_of("75 percent brightness") == "set_brightness"
        assert args_of("75 percent brightness")["level"] == 75


# ── Web ────────────────────────────────────────────────────────────────────────

class TestWebSearch:
    def test_google(self):
        assert intent_of("google python tutorials") == "web_search"
        assert "python tutorials" in args_of("google python tutorials")["query"]

    def test_search(self):
        assert intent_of("search for best coffee shops") == "web_search"

    def test_look_up(self):
        assert intent_of("look up weather in London") == "web_search"

    def test_open_url(self):
        assert intent_of("go to github.com") == "open_url"

    def test_open_website(self):
        assert intent_of("open website youtube.com") == "open_url"


# ── Files & Folders ────────────────────────────────────────────────────────────

class TestFiles:
    def test_open_folder(self):
        assert intent_of("open folder downloads") == "open_folder"

    def test_save_note(self):
        assert intent_of("take a note that I need to call mom") == "save_note"
        assert "call mom" in args_of("take a note that I need to call mom")["text"]

    def test_note_shorthand(self):
        assert intent_of("note: buy groceries") == "save_note"


# ── System ─────────────────────────────────────────────────────────────────────

class TestSystem:
    def test_shutdown(self):
        assert intent_of("shutdown the computer") == "shutdown"
        assert intent_of("shutdown the pc") == "shutdown"
        assert intent_of("shutdown the assistant") == "quit_assistant"
        assert intent_of("shutdown shin") == "quit_assistant"

    def test_shutdown_timer(self):
        assert intent_of("shutdown the pc in 10 minutes") == "shutdown_timer"
        assert args_of("shutdown the pc in 10 minutes")["quantity"] == 10
        assert args_of("shutdown the pc in 10 minutes")["unit"] == "minute"
        assert intent_of("power off in 2 hours") == "shutdown_timer"
        assert args_of("power off in 2 hours")["unit"] == "hour"
        assert intent_of("shutdown after 1 hour") == "shutdown_timer"
        assert args_of("shutdown after 1 hour")["quantity"] == 1
        assert args_of("shutdown after 1 hour")["unit"] == "hour"
        assert intent_of("shutdown for 30 minutes") == "shutdown_timer"
        assert args_of("shutdown for 30 minutes")["quantity"] == 30
        assert args_of("shutdown for 30 minutes")["unit"] == "minute"
        
    def test_wifi(self):
        assert intent_of("turn on the wifi") == "wifi_control"
        assert args_of("turn on the wifi")["action"] == "on"
        assert intent_of("turn off wifi") == "wifi_control"
        assert args_of("turn off wifi")["action"] == "off"

    def test_bluetooth(self):
        assert intent_of("turn on the bluetooth") == "bluetooth_control"
        assert args_of("turn on the bluetooth")["action"] == "on"
        assert intent_of("disable bluetooth") == "bluetooth_control"
        assert args_of("disable bluetooth")["action"] == "off"
        assert intent_of("toggle bluetooth") == "bluetooth_control"
        assert args_of("toggle bluetooth")["action"] == "toggle"

    def test_airplane_mode(self):
        assert intent_of("turn on airplane mode") == "airplane_mode_control"
        assert args_of("turn on airplane mode")["action"] == "on"
        assert intent_of("disable aeroplane mode") == "airplane_mode_control"
        assert args_of("disable aeroplane mode")["action"] == "off"
        assert intent_of("toggle airplane mode") == "airplane_mode_control"
        assert args_of("toggle airplane mode")["action"] == "toggle"

    def test_night_light(self):
        assert intent_of("turn on night light") == "night_light_control"
        assert args_of("turn on night light")["action"] == "on"
        assert intent_of("disable the night light") == "night_light_control"
        assert args_of("disable the night light")["action"] == "off"
        assert intent_of("toggle night light") == "night_light_control"
        assert args_of("toggle night light")["action"] == "toggle"

    def test_mobile_hotspot(self):
        assert intent_of("turn on the mobile hotspot") == "mobile_hotspot_control"
        assert args_of("turn on the mobile hotspot")["action"] == "on"
        assert intent_of("disable mobile hotspot") == "mobile_hotspot_control"
        assert args_of("disable mobile hotspot")["action"] == "off"
        assert intent_of("toggle mobile hotspot") == "mobile_hotspot_control"
        assert args_of("toggle mobile hotspot")["action"] == "toggle"

    def test_nearby_share(self):
        assert intent_of("turn on near by share") == "nearby_share_control"
        assert args_of("turn on near by share")["action"] == "on"
        assert intent_of("disable nearby sharing") == "nearby_share_control"
        assert args_of("disable nearby sharing")["action"] == "off"
        assert intent_of("toggle near by share") == "nearby_share_control"
        assert args_of("toggle near by share")["action"] == "toggle"

    def test_restart(self):
        assert intent_of("restart") == "restart"

    def test_lock(self):
        assert intent_of("lock the screen") == "lock_screen"

    def test_sleep(self):
        assert intent_of("sleep") == "sleep"

    def test_sleep_shutdown(self):
        assert intent_of("i am going to sleep") == "sleep_shutdown"
        assert intent_of("i'm going to sleep") == "sleep_shutdown"
        assert intent_of("going to sleep") == "sleep_shutdown"
        assert intent_of("going to bed") == "sleep_shutdown"
        assert intent_of("i am going to bed") == "sleep_shutdown"


# ── Meta ───────────────────────────────────────────────────────────────────────

class TestMeta:
    def test_tell_time(self):
        assert intent_of("what time is it") == "tell_time"

    def test_tell_date(self):
        assert intent_of("what's today's date") == "tell_date"

    def test_quit(self):
        assert intent_of("stop shin") == "quit_assistant"

    def test_screenshot(self):
        assert intent_of("take a screenshot") == "screenshot"

    def test_type_text(self):
        assert intent_of("type hello world") == "type_text"
        assert args_of("type hello world")["text"] == "hello world"
        assert intent_of("write hello world") == "type_text"
        assert args_of("write hello world")["text"] == "hello world"

    def test_personality(self):
        assert intent_of("be brief") == "set_personality"
        assert args_of("be brief")["mode"] == "brief"
        assert intent_of("act sarcastic") == "set_personality"
        assert intent_of("sound formal") == "set_personality"

# ── Unknown ────────────────────────────────────────────────────────────────────

class TestUnknown:
    def test_gibberish(self):
        assert intent_of("blargaflonk xyz") == "unknown"


# ── Screen Vision ──────────────────────────────────────────────────────────────

class TestVision:
    def test_what_is_this(self):
        assert intent_of("what is this") == "screen_query"

    def test_summarize_this(self):
        assert intent_of("summarize this") == "screen_query"

    def test_explain_error(self):
        assert intent_of("explain this error") == "screen_query"

    def test_what_am_i_looking_at(self):
        assert intent_of("what am I looking at") == "screen_query"

    def test_describe_screen(self):
        assert intent_of("describe my screen") == "screen_query"

    def test_read_screen_mode(self):
        assert intent_of("read my screen") == "screen_query"
        assert args_of("read my screen")["mode"] == "read"
        assert intent_of("screen padh ke bata") == "screen_query"
        assert args_of("screen padh ke bata")["mode"] == "read"

    def test_find_screen_text(self):
        assert intent_of("find Submit on my screen") == "screen_query"
        assert args_of("find Submit on my screen")["mode"] == "find"
        assert args_of("find Submit on my screen")["target"] == "Submit"

    def test_hinglish_screen_query(self):
        assert intent_of("screen mein kya hai") == "screen_query"
        assert args_of("screen mein kya hai")["mode"] == "describe"



# ── Window Management ──────────────────────────────────────────────────────────

class TestWindowManagement:
    def test_minimize_all(self):
        assert intent_of("minimize all windows") == "window_minimize_all"

    def test_show_desktop(self):
        assert intent_of("show desktop") == "window_minimize_all"

    def test_snap_left(self):
        assert intent_of("snap this window to the left") == "window_snap_left"

    def test_snap_right(self):
        assert intent_of("snap to the right") == "window_snap_right"
        
    def test_snap_quadrants(self):
        assert intent_of("snap window to top left") == "window_snap_quadrant"
        assert args_of("snap window to top left")["v"] == "top"
        assert args_of("snap window to top left")["h"] == "left"
        assert intent_of("snap to the bottom right") == "window_snap_quadrant"
        assert args_of("snap to the bottom right")["v"] == "bottom"
        assert args_of("snap to the bottom right")["h"] == "right"

    def test_maximize(self):
        assert intent_of("maximize this window") == "window_maximize"

    def test_maximize_fullscreen(self):
        assert intent_of("make it full screen") == "window_maximize"

    def test_minimize(self):
        assert intent_of("minimize this window") == "window_minimize"


# ── Media Controls ─────────────────────────────────────────────────────────────

class TestMedia:
    def test_play_pause_combo(self):
        assert intent_of("play pause") == "media_play_pause"

    def test_pause_music(self):
        assert intent_of("pause the music") == "media_play_pause"

    def test_resume(self):
        assert intent_of("resume the song") == "media_play_pause"

    def test_next_song(self):
        assert intent_of("next song") == "media_next"

    def test_skip(self):
        assert intent_of("skip") == "media_next"

    def test_previous_song(self):
        assert intent_of("previous song") == "media_prev"

    def test_go_back(self):
        assert intent_of("go back") == "media_prev"


# ── Clipboard Actions ──────────────────────────────────────────────────────────

class TestClipboard:
    def test_translate(self):
        assert intent_of("translate my clipboard to Spanish") == "clipboard_translate"
        assert args_of("translate my clipboard to Spanish")["language"] == "Spanish"

    def test_rewrite_professional(self):
        assert intent_of("rewrite my clipboard to sound more professional") == "clipboard_rewrite"

    def test_summarize(self):
        assert intent_of("summarize my clipboard") == "clipboard_summarize"

    def test_fix_grammar(self):
        assert intent_of("fix grammar in my clipboard") == "clipboard_fix"

    def test_correct_spelling(self):
        assert intent_of("correct the spelling in my clipboard") == "clipboard_fix"


# ── Macros / Routines ──────────────────────────────────────────────────────────

class TestMacros:
    def test_morning_routine(self):
        assert intent_of("start my morning routine") == "run_macro"
        assert args_of("start my morning routine")["name"] == "morning"

    def test_good_morning(self):
        assert intent_of("good morning shin") == "run_macro"
        assert args_of("good morning shin")["name"] == "morning"

    def test_focus_mode(self):
        assert intent_of("start focus mode") == "run_macro"
        assert args_of("start focus mode")["name"] == "focus"

    def test_work_mode(self):
        assert intent_of("activate work mode") == "run_macro"

    def test_evening_routine(self):
        assert intent_of("start my evening routine") == "run_macro"
        assert args_of("start my evening routine")["name"] == "evening"

    def test_good_night(self):
        assert intent_of("good night shin") == "run_macro"
        assert args_of("good night shin")["name"] == "evening"

    def test_developer_mode(self):
        assert intent_of("activate programming mode") == "run_macro"
        assert args_of("activate programming mode")["name"] == "dev"

    def test_entertainment_mode(self):
        assert intent_of("start movie mode") == "run_macro"
        assert args_of("start movie mode")["name"] == "entertainment"

    def test_leaving_mode(self):
        assert intent_of("leaving") == "run_macro"
        assert args_of("leaving")["name"] == "leaving"


# ── WhatsApp Commands ──────────────────────────────────────────────────────────

class TestWhatsApp:
    def test_send_whatsapp_message_basic(self):
        assert intent_of("send a message to Dad saying I am home") == "send_whatsapp_message"
        assert args_of("send a message to Dad saying I am home")["contact"] == "dad"
        assert args_of("send a message to Dad saying I am home")["message"] == "I am home"

    def test_send_whatsapp_message_direct_phone(self):
        assert intent_of("send whatsapp to +919876543210 saying meeting at 5") == "send_whatsapp_message"
        assert args_of("send whatsapp to +919876543210 saying meeting at 5")["contact"] == "+919876543210"

    def test_send_whatsapp_message_hinglish(self):
        assert intent_of("Dad ko whatsapp karo I am home") == "send_whatsapp_message"
        assert args_of("Dad ko whatsapp karo I am home")["contact"] == "dad"
        assert intent_of("whatsapp pe Dad ko message karo meet me") == "send_whatsapp_message"
        assert args_of("whatsapp pe Dad ko message karo meet me")["contact"] == "dad"

    def test_send_whatsapp_tell_explicit(self):
        # "tell X on whatsapp" is the safe explicit form that avoids matching "tell me a joke"
        assert intent_of("tell Dad on whatsapp I am late") == "send_whatsapp_message"
        assert args_of("tell Dad on whatsapp I am late")["contact"] == "dad"
        assert args_of("tell Dad on whatsapp I am late")["message"] == "I am late"

    def test_add_whatsapp_contact(self):
        assert intent_of("add whatsapp contact Soham 9172381205") == "add_whatsapp_contact"
        assert args_of("add whatsapp contact Soham 9172381205")["name"] == "soham"
        assert args_of("add whatsapp contact Soham 9172381205")["phone"] == "9172381205"

    def test_list_whatsapp_contacts(self):
        assert intent_of("show my whatsapp contacts") == "list_whatsapp_contacts"
        assert intent_of("who are my whatsapp contacts") == "list_whatsapp_contacts"

    def test_whatsapp_calls(self):
        assert intent_of("whatsapp call Dad") == "whatsapp_call"
        assert args_of("whatsapp call Dad")["contact"] == "dad"
        assert args_of("whatsapp call Dad")["video"] is False
        assert intent_of("whatsapp video call Mom") == "whatsapp_call"
        assert args_of("whatsapp video call Mom")["video"] is True

    def test_whatsapp_location(self):
        assert intent_of("send location to Dad on whatsapp") == "send_whatsapp_location"
        assert args_of("send location to Dad on whatsapp")["contact"] == "dad"

    def test_whatsapp_file(self):
        assert intent_of("send photo to Soham on whatsapp") == "send_whatsapp_file"
        assert args_of("send photo to Soham on whatsapp")["contact"] == "soham"


# ── URL Normalization ──────────────────────────────────────────────────────────

class TestUrlNormalization:
    def test_bare_name_gets_dotcom(self):
        result = args_of("go to github")
        assert result["url"] == "https://github.com"

    def test_domain_gets_https(self):
        result = args_of("go to github.com")
        assert result["url"] == "https://github.com"

    def test_already_has_https(self):
        result = args_of("visit https://example.com")
        assert result["url"] == "https://example.com"


# ── Confidence Metadata ────────────────────────────────────────────────────────

class TestMetadata:
    def test_rule_confidence(self):
        result = parse_intent("open chrome")
        assert result.get("_confidence") == 0.9

    def test_no_confirm_flag_shutdown(self):
        """shutdown/restart use ConfirmationRequired in commands.py, not _confirm."""
        result = parse_intent("shutdown the computer")
        assert not result.get("_confirm")

    def test_no_confirm_flag_sleep(self):
        """sleep uses ConfirmationRequired in commands.py, not _confirm."""
        result = parse_intent("sleep")
        assert not result.get("_confirm")


    def test_no_confirm_flag_restart(self):
        """shutdown/restart use ConfirmationRequired in commands.py, not _confirm."""
        result = parse_intent("restart")
        assert not result.get("_confirm")

    def test_no_confirm_flag_lock(self):
        result = parse_intent("lock the screen")
        assert not result.get("_confirm")

    def test_web_search_engine_google(self):
        result = parse_intent("google python tutorials")
        assert result["args"]["engine"] == "google"

    def test_web_search_engine_default(self):
        result = parse_intent("search for coffee shops")
        assert result["args"]["engine"] == "default"


# ── News ───────────────────────────────────────────────────────────────────────

class TestNews:
    def test_tell_news_general(self):
        assert intent_of("latest news") == "tell_news"
        assert intent_of("what's in the news") == "tell_news"
        assert intent_of("breaking news") == "tell_news"
        assert intent_of("Today's news") == "tell_news"
        assert intent_of("today news") == "tell_news"
        assert intent_of("news today") == "tell_news"

    def test_tell_news_country(self):
        assert intent_of("news of India") == "tell_news"
        assert args_of("news of India")["country"] == "India"

        assert intent_of("news of America") == "tell_news"
        assert args_of("news of America")["country"] == "America"

        assert intent_of("news of Russia") == "tell_news"
        assert args_of("news of Russia")["country"] == "Russia"

        assert intent_of("India ki news") == "tell_news"
        assert args_of("India ki news")["country"] == "India"

        assert intent_of("Russian headlines") == "tell_news"
        assert args_of("Russian headlines")["country"] == "Russian"

    def test_tell_news_topic(self):
        assert intent_of("news about tech") == "tell_news"
        assert args_of("news about tech")["topic"] == "tech"
        assert intent_of("headlines on sports") == "tell_news"
        assert args_of("headlines on sports")["topic"] == "sports"



# ── Calendar ───────────────────────────────────────────────────────────────────

class TestCalendar:
    def test_calendar_list_general(self):
        assert intent_of("what's my next meeting") == "calendar_list"
        assert intent_of("what's on my calendar") == "calendar_list"

    def test_calendar_list_relative(self):
        assert intent_of("what does my day look like tomorrow") == "calendar_list"
        assert args_of("what does my day look like tomorrow")["day"] == "tomorrow"
        assert intent_of("what is my schedule today") == "calendar_list"
        assert args_of("what is my schedule today")["day"] == "today"
        assert intent_of("what is on my calendar tomorrow") == "calendar_list"
        assert args_of("what is on my calendar tomorrow")["day"] == "tomorrow"
        assert intent_of("show meetings today") == "calendar_list"
        assert args_of("show meetings today")["day"] == "today"

    def test_calendar_add(self):
        assert intent_of("add dentist appointment to my calendar at tomorrow at 2 PM") == "calendar_add"
        args = args_of("add dentist appointment to my calendar at tomorrow at 2 PM")
        assert args["event"] == "dentist appointment"
        assert args["time"] == "tomorrow at 2 PM"

    def test_calendar_add_optional_preposition(self):
        assert intent_of("add dentist appointment to my calendar tomorrow at 2 PM") == "calendar_add"
        args = args_of("add dentist appointment to my calendar tomorrow at 2 PM")
        assert args["event"] == "dentist appointment"
        assert args["time"] == "tomorrow at 2 PM"


# ── Spotify ────────────────────────────────────────────────────────────────────

class TestPlayFallback:
    def test_default_play_to_youtube(self):
        assert intent_of("play Synthwave music on Spotify") == "youtube_play"
        assert args_of("play Synthwave music on Spotify")["query"] == "Synthwave music on Spotify"

    def test_default_play_implicit(self):
        assert intent_of("play Synthwave") == "youtube_play"
        assert args_of("play Synthwave")["query"] == "Synthwave"


# ── Smart Home ─────────────────────────────────────────────────────────────────

class TestSmartHome:
    def test_smart_home_control_state(self):
        assert intent_of("turn off the lights") == "smart_home_control"
        assert args_of("turn off the lights")["state"] == "off"
        assert intent_of("turn on the smart light") == "smart_home_control"
        assert args_of("turn on the smart light")["state"] == "on"

    def test_smart_home_control_color(self):
        assert intent_of("set the lights to blue") == "smart_home_control"
        args = args_of("set the lights to blue")
        assert args["state"] == "on"
        assert args["color"] == "blue"

    def test_smart_home_control_brightness(self):
        assert intent_of("set smart light brightness to 75") == "smart_home_control"
        args = args_of("set smart light brightness to 75")
        assert args["state"] == "on"
        assert args["brightness"] == 75

    def test_activate_scene(self):
        assert intent_of("activate movie mode") == "activate_scene"
        assert args_of("activate movie mode")["name"] == "movie"


# ── Process Monitor ────────────────────────────────────────────────────────────

class TestProcessMonitor:
    def test_monitor_process_pid(self):
        assert intent_of("monitor process 5678") == "monitor_process"
        assert args_of("monitor process 5678")["pid"] == 5678

    def test_monitor_process_name(self):
        assert intent_of("watch the latest python process") == "monitor_process"
        assert args_of("watch the latest python process")["name"] == "python"

    def test_monitor_process_alert(self):
        assert intent_of("alert me when python finishes") == "monitor_process"
        assert args_of("alert me when python finishes")["name"] == "python"


# ── Window Listing ─────────────────────────────────────────────────────────────

class TestListOpenWindows:
    def test_list_open_windows(self):
        assert intent_of("which tabs are open") == "list_open_windows"
        assert intent_of("what windows are running") == "list_open_windows"
        assert intent_of("list open tabs") == "list_open_windows"


# ── Standby Mode ──────────────────────────────────────────────────────────────

class TestMuteStandbyMode:
    def test_standby_mode(self):
        assert intent_of("stop listening") == "pause_listening"
        assert intent_of("pause listening") == "pause_listening"
        assert intent_of("stop listing") == "pause_listening"
        assert intent_of("stop listining") == "pause_listening"
        assert intent_of("stop listning") == "pause_listening"
        assert intent_of("stop listen") == "pause_listening"
        assert intent_of("go to sleep") == "pause_listening"
        assert intent_of("go to standby") == "pause_listening"
        assert intent_of("don't listen") == "pause_listening"
        assert intent_of("mute mic") == "pause_listening"
        assert intent_of("mute microphone") == "pause_listening"

        assert intent_of("start listening") == "resume_listening"
        assert intent_of("resume listening") == "resume_listening"
        assert intent_of("start listing") == "resume_listening"
        assert intent_of("start listining") == "resume_listening"
        assert intent_of("start listning") == "resume_listening"
        assert intent_of("start listen") == "resume_listening"
        assert intent_of("wake up") == "resume_listening"
        assert intent_of("get back to work") == "resume_listening"
        assert intent_of("get back online") == "resume_listening"
        assert intent_of("unmute mic") == "resume_listening"
        assert intent_of("unmute microphone") == "resume_listening"
        assert intent_of("listen to me") == "resume_listening"
        assert intent_of("start responding") == "resume_listening"


# ── Hand Gestures ─────────────────────────────────────────────────────────────

class TestGestures:
    def test_start_gesture_control(self):
        assert intent_of("start gesture control") == "start_gesture_control"
        assert intent_of("enable hand gestures") == "start_gesture_control"
        assert intent_of("turn on gesture mode") == "start_gesture_control"

    def test_stop_gesture_control(self):
        assert intent_of("stop gesture control") == "stop_gesture_control"
        assert intent_of("disable hand gestures") == "stop_gesture_control"
        assert intent_of("turn off gesture mode") == "stop_gesture_control"

    def test_toggle_gesture_control(self):
        assert intent_of("toggle gesture control") == "toggle_gesture_control"
        assert intent_of("switch hand gestures") == "toggle_gesture_control"


# ── Memory ────────────────────────────────────────────────────────────────────

class TestMemory:
    def test_save_memory(self):
        assert intent_of("remember that my keys are on the table") == "save_memory"
        assert args_of("remember that my keys are on the table")["content"] == "my keys are on the table"
        assert intent_of("remember to lock the door") == "save_memory"

    def test_recall_memory(self):
        assert intent_of("what do you remember about my keys") == "recall_memory"
        assert args_of("what do you remember about my keys")["query"] == "my keys"
        assert intent_of("recall keys") == "recall_memory"
        assert args_of("recall keys")["query"] == "keys"
        assert intent_of("where is my wallet") == "recall_memory"
        assert args_of("where is my wallet")["query"] == "wallet"
        assert intent_of("what do you remember") == "recall_memory"

    def test_forget_memory(self):
        assert intent_of("forget that my keys are on the table") == "forget_memory"
        assert args_of("forget that my keys are on the table")["query"] == "my keys are on the table"
        assert intent_of("clear all memories") == "forget_memory"
        assert args_of("clear all memories")["query"] == "all"


# ── YouTube ───────────────────────────────────────────────────────────────────

class TestYoutube:
    def test_youtube_play_query(self):
        assert intent_of("play despacito on youtube") == "youtube_play"
        assert args_of("play despacito on youtube")["query"] == "despacito"
        
        # Test youtube search commands
        assert intent_of("search night luffy song on youtube") == "youtube_play"
        assert args_of("search night luffy song on youtube")["query"] == "night luffy song"
        assert intent_of("youtube search lofi beats") == "youtube_play"
        assert args_of("youtube search lofi beats")["query"] == "lofi beats"

    def test_youtube_play_generic(self):
        assert intent_of("play some music on youtube") == "youtube_play"
        assert args_of("play some music on youtube")["query"] == "random hindi songs mix"


# ── Hindi ──────────────────────────────────────────────────────────────────────

class TestHindi:
    def test_hindi_time(self):
        assert intent_of("क्या टाइम हो रहा है") == "tell_time"
        assert intent_of("समय क्या हुआ है") == "tell_time"
        assert intent_of("कितने बजे हैं") == "tell_time"
        assert intent_of("टाइम बताओ") == "tell_time"

    def test_hindi_date(self):
        assert intent_of("आज क्या तारीख है") == "tell_date"
        assert intent_of("आज की तारीख") == "tell_date"

    def test_hindi_open_app(self):
        assert intent_of("chrome खोलो") == "open_app"
        assert args_of("chrome खोलो")["app"] == "chrome"
        assert intent_of("चालू करो spotify") == "open_app"
        assert args_of("चालू करो spotify")["app"] == "spotify"

    def test_hindi_close_app(self):
        assert intent_of("firefox बंद करो") == "close_app"
        assert args_of("firefox बंद करो")["app"] == "firefox"

    def test_hindi_volume(self):
        assert intent_of("म्यूट करो") == "mute_volume"
        assert intent_of("आवाज़ चालू करो") == "unmute_volume"
        assert intent_of("वॉल्यूम बढ़ाओ") == "volume_up"
        assert intent_of("आवाज़ कम करो") == "volume_down"
        assert intent_of("वॉल्यूम 50 करो") == "set_volume"
        assert args_of("वॉल्यूम 50 करो")["level"] == 50

    def test_hindi_screenshot(self):
        assert intent_of("स्क्रीनशॉट लो") == "screenshot"

    def test_hindi_quit(self):
        assert intent_of("बाय") == "quit_assistant"
        assert intent_of("अलविदा") == "quit_assistant"
        assert intent_of("बंद हो जाओ") == "quit_assistant"

    def test_hindi_standby(self):
        assert intent_of("सुनना बंद करो") == "pause_listening"
        assert intent_of("सुनना रोको") == "pause_listening"
        assert intent_of("चुप हो जाओ") == "pause_listening"
        assert intent_of("सो जाओ") == "pause_listening"
        assert intent_of("स्टैंडबाय पे जाओ") == "pause_listening"

        assert intent_of("सुनना शुरू करो") == "resume_listening"
        assert intent_of("सुनना चालू करो") == "resume_listening"
        assert intent_of("जाग जाओ") == "resume_listening"
        assert intent_of("उठ जाओ") == "resume_listening"
        assert intent_of("वापस आओ") == "resume_listening"

    def test_language_switch(self):
        assert intent_of("hindi mein baat karo") in ("chat", "set_language")
        assert intent_of("hindi me baat") in ("chat", "set_language")
        assert intent_of("talk in english") in ("chat", "set_language")
        assert intent_of("change language into english") in ("chat", "set_language")
        assert intent_of("change language into") in ("chat", "set_language")
        assert intent_of("हिंदी में बात करो") in ("chat", "set_language")
        assert intent_of("टॉक इन इंग्लिश") in ("chat", "set_language")
        assert intent_of("भाषा बदलो") in ("chat", "set_language")
        assert intent_of("talk ine english") in ("chat", "set_language")
        assert intent_of("change d language") in ("chat", "set_language")
        assert intent_of("bhasha badlo") in ("chat", "set_language")

    def test_casual_talks(self):
        assert intent_of("hello shin") == "chat"
        assert intent_of("who are you") == "chat"
        assert "Shin" in args_of("who are you")["response"]
        assert intent_of("tumhe kisne banaya") == "chat"
        assert "M J" in args_of("tumhe kisne banaya")["response"]
        assert intent_of("who is your creator") == "chat"
        assert "M J" in args_of("who is your creator")["response"]
        assert intent_of("who is your creater") == "chat"
        assert "M J" in args_of("who is your creater")["response"]
        assert intent_of("who created you") == "chat"
        assert "M J" in args_of("who created you")["response"]
        assert intent_of("i am tired") == "chat"
        assert "rest" in args_of("i am tired")["response"].lower()

    def test_expanded_small_talk(self):
        assert intent_of("kaise ho") == "chat"
        assert intent_of("kese ho") == "chat"
        assert intent_of("kya hal hai") == "chat"
        assert intent_of("tell me a joke") == "tell_joke"
        assert intent_of("chutkula sunao") == "tell_joke"

    def test_hinglish_and_fallbacks(self):
        # Hinglish App control
        assert intent_of("youtube kholo") == "open_app"
        assert args_of("youtube kholo")["app"] == "youtube"
        assert intent_of("kholo chrome") == "open_app"
        assert args_of("kholo chrome")["app"] == "chrome"
        assert intent_of("whatsapp band karo") == "close_app"
        assert args_of("whatsapp band karo")["app"] == "whatsapp"

        # App name / scene / screen fallbacks
        assert intent_of("whatsapp seen") == "open_app"
        assert args_of("whatsapp seen")["app"] == "whatsapp"
        assert intent_of("spotify screen") == "open_app"
        assert args_of("spotify screen")["app"] == "spotify"
        assert intent_of("calculator") == "open_app"
        assert args_of("calculator")["app"] == "calculator"
        
        # Incomplete / stopword app name prevention
        assert intent_of("close the") == "unknown"
        assert intent_of("close all") == "window_minimize_all"

        # Time / Date improvements
        assert intent_of("what is time") == "tell_time"
        assert intent_of("time kya ho raha hai") == "tell_time"
        assert intent_of("aaj kya date hai") == "tell_date"

        # Search Fallback
        assert intent_of("facts on cat") == "live_query"
        assert args_of("facts on cat")["query"] == "cat"
        assert intent_of("tell me about cats") == "live_query"


class TestVoiceAuth:
    def test_delete_voice_profile_commands(self):
        assert intent_of("Delete my voice profile") == "delete_voice_profile"
        assert intent_of("Forget my voice") == "delete_voice_profile"
        assert intent_of("Remove my voice data") == "delete_voice_profile"
        assert intent_of("Forget my voice fingerprint") == "delete_voice_profile"
        assert intent_of("delete my voice") == "delete_voice_profile"


class TestClickText:
    def test_click_commands(self):
        assert intent_of("click on youtube") == "click_text"
        assert args_of("click on youtube")["text"] == "youtube"
        assert args_of("click on youtube")["action"] == "click"

        assert intent_of("tap mix") == "click_text"
        assert args_of("tap mix")["text"] == "mix"
        assert args_of("tap mix")["action"] == "tap"

        assert intent_of("click the button for next") == "click_text"
        assert args_of("click the button for next")["text"] == "next"
        assert args_of("click the button for next")["action"] == "click"


class TestStudyMode:
    def test_activate_study_mode(self):
        assert intent_of("activate study mode") == "activate_study_mode"
        assert intent_of("start study mode") == "activate_study_mode"
        assert intent_of("padhai mode chalu karo") == "activate_study_mode"
        assert intent_of("study mode start karo") == "activate_study_mode"

    def test_deactivate_study_mode(self):
        assert intent_of("deactivate study mode") == "deactivate_study_mode"
        assert intent_of("stop study mode") == "deactivate_study_mode"
        assert intent_of("padhai mode band karo") == "deactivate_study_mode"
        assert intent_of("study mode stop karo") == "deactivate_study_mode"

    def test_check_study_status(self):
        assert intent_of("am i studying") == "check_study_status"
        assert intent_of("am i focused") == "check_study_status"
        assert intent_of("study status") == "check_study_status"
        assert intent_of("how much have i studied") == "check_study_status"
        assert intent_of("padhai kaise chal rahi hai") == "check_study_status"
        assert intent_of("kya main padh raha hun") == "check_study_status"


class TestCustomMacros:
    def test_learn_macro_parsing(self):
        assert intent_of("when I say relax, set volume to 10 then play spotify") == "learn_macro"
        assert args_of("when I say relax, set volume to 10 then play spotify")["trigger"] == "relax"
        assert args_of("when I say relax, set volume to 10 then play spotify")["commands"] == "set volume to 10 then play spotify"

        assert intent_of("create shortcut study to open vs code and mute") == "learn_macro"
        assert args_of("create shortcut study to open vs code and mute")["trigger"] == "study"
        assert args_of("create shortcut study to open vs code and mute")["commands"] == "open vs code and mute"

        assert intent_of("teach you a new routine") == "learn_macro"
        assert args_of("teach you a new routine") == {}

        assert intent_of("record shortcut chill") == "learn_macro"
        assert args_of("record shortcut chill")["trigger"] == "chill"
        assert args_of("record shortcut chill")["commands"] == "record"

    def test_learn_macro_synonym(self):
        assert intent_of("when I say browser it means open chrome") == "learn_macro"
        assert args_of("when I say browser it means open chrome")["trigger"] == "browser"
        assert args_of("when I say browser it means open chrome")["commands"] == "open chrome"
        assert intent_of("if i tell you to relax, then play spotify") == "learn_macro"
        assert args_of("if i tell you to relax, then play spotify")["trigger"] == "relax"
        assert args_of("if i tell you to relax, then play spotify")["commands"] == "play spotify"

    def test_list_macros_parsing(self):
        assert intent_of("list my custom macros") == "list_macros"
        assert intent_of("show my shortcuts") == "list_macros"
        assert intent_of("what are my routines") == "list_macros"

    def test_delete_macro_parsing(self):
        assert intent_of("delete shortcut relax") == "delete_macro"
        assert args_of("delete shortcut relax")["name"] == "relax"
        assert intent_of("remove macro study") == "delete_macro"
        assert args_of("remove macro study")["name"] == "study"

    def test_edit_macro_parsing(self):
        assert intent_of("add open discord to my shortcut called gaming") == "edit_macro"
        assert args_of("add open discord to my shortcut called gaming")["trigger"] == "gaming"
        assert args_of("add open discord to my shortcut called gaming")["command"] == "open discord"

    def test_custom_macro_matching(self):
        import unittest.mock as mock
        with mock.patch("macros._load_custom_macros", return_value={
            "relax": {"trigger": "relax", "commands": ["set volume to 10", "play spotify"]}
        }):
            assert intent_of("relax") == "run_macro"
            assert args_of("relax")["name"] == "relax"
            assert intent_of("run relax") == "run_macro"
            assert args_of("run relax")["name"] == "relax"
            assert intent_of("start my relax routine") == "run_macro"
            assert args_of("start my relax routine")["name"] == "relax"

    def test_learn_that_memory(self):
        assert intent_of("learn that my favorite food is pizza") == "save_memory"
        assert args_of("learn that my favorite food is pizza")["content"] == "my favorite food is pizza"
        assert intent_of("memorize that i have a meeting on friday") == "save_memory"

    def test_interactive_macro_recording(self):
        import assistant
        import macros
        import unittest.mock as mock

        # Reset state
        assistant._recording_macro = {"trigger": "chill", "commands": []}

        # Mock speak so we don't output audio during tests
        with mock.patch("assistant.speak") as mock_speak:
            with mock.patch("macros._save_custom_macros") as mock_save:
                # Mock load custom macros
                with mock.patch("macros._load_custom_macros", return_value={}) as mock_load:
                    # Run a step
                    res = assistant.handle_command("set volume to 10")
                    assert res is True
                    assert assistant._recording_macro["commands"] == ["set volume to 10"]

                    # Run another step
                    res = assistant.handle_command("play spotify")
                    assert res is True
                    assert assistant._recording_macro["commands"] == ["set volume to 10", "play spotify"]

                    # Stop and save
                    res = assistant.handle_command("stop recording")
                    assert res is True
                    assert assistant._recording_macro is None

                    # Verify macros._save_custom_macros was called with the saved macro
                    mock_save.assert_called_once()
                    saved_data = mock_save.call_args[0][0]
                    assert "chill" in saved_data
                    assert saved_data["chill"]["commands"] == ["set volume to 10", "play spotify"]


# ── Ollama Multi-Model Fallback Tests ──────────────────────────────────────────

import unittest.mock as mock

class TestOllamaFallback:
    def test_nlp_fallback_loop(self):
        # Setup environment
        with mock.patch.dict(os.environ, {
            "OPENAI_API_KEY": "",
            "GEMINI_API_KEY": "",
            "LM_STUDIO_URL": "",
            "OLLAMA_MODEL": "minimax-m2.5:cloud, llama3"
        }):
            nlp._OLLAMA_OFFLINE_UNTIL = 0.0
            # Mock requests.post
            with mock.patch("requests.post") as mock_post:
                # First model returns 404
                resp1 = mock.Mock()
                resp1.status_code = 404
                
                # Second model returns success JSON
                resp2 = mock.Mock()
                resp2.status_code = 200
                resp2.json.return_value = {"response": '{"intent": "tell_time", "args": {}}'}
                
                mock_post.side_effect = [resp1, resp2]
                
                # Temporarily restore nlp._ai_parse
                try:
                    nlp._ai_parse = _original_ai_parse
                    result = nlp._ai_parse("what time is it")
                    assert result["intent"] == "tell_time"
                    
                    # Verify mock calls
                    assert mock_post.call_count == 2
                    call1_args = mock_post.call_args_list[0]
                    assert call1_args[1]["json"]["model"] == "minimax-m2.5:cloud"
                    call2_args = mock_post.call_args_list[1]
                    assert call2_args[1]["json"]["model"] == "llama3"
                finally:
                    # Restore dummy mock to avoid side-effects in other tests
                    nlp._ai_parse = lambda text: None

    def test_clipboard_fallback_loop(self):
        import clipboard_ai
        with mock.patch.dict(os.environ, {
            "GEMINI_API_KEY": "",
            "OPENAI_API_KEY": "",
            "GROQ_API_KEY": "",
            "OLLAMA_MODEL": "minimax-m2.5:cloud, llama3"
        }):
            with mock.patch("requests.post") as mock_post:
                resp1 = mock.Mock()
                resp1.status_code = 404
                
                resp2 = mock.Mock()
                resp2.status_code = 200
                resp2.json.return_value = {"response": "Transformed Text"}
                
                mock_post.side_effect = [resp1, resp2]
                
                with mock.patch("clipboard_ai.get_clipboard", return_value="Original Text"):
                    with mock.patch("clipboard_ai.set_clipboard") as mock_set:
                        result = clipboard_ai.transform_clipboard("Instruction")
                        assert result == "Transformed Text"
                        mock_set.assert_called_once_with("Transformed Text")
                        assert mock_post.call_count == 2

    def test_memory_fallback_loop(self):
        import memory
        memory._ollama_offline_until = 0.0
        with mock.patch.dict(os.environ, {
            "GEMINI_API_KEY": "",
            "OPENAI_API_KEY": "",
            "GROQ_API_KEY": "",
            "OLLAMA_MODEL": "minimax-m2.5:cloud, llama3"
        }):
            with mock.patch("requests.post") as mock_post:
                resp1 = mock.Mock()
                resp1.status_code = 404
                
                resp2 = mock.Mock()
                resp2.status_code = 200
                resp2.json.return_value = {"response": "FACT: The user has a test"}
                
                mock_post.side_effect = [resp1, resp2]
                
                with mock.patch("memory.add_memory") as mock_add_memory:
                    memory.extract_and_store_implicit_knowledge("I have a test tomorrow")
                    mock_add_memory.assert_called_once_with("The user has a test")
                    assert mock_post.call_count == 2


class TestSecurityGuardrails:
    def test_unsafe_open_app(self):
        from commands import dispatch
        res = dispatch({"intent": "open_app", "args": {"app": "regedit.exe"}})
        assert "Access denied" in res

    def test_unsafe_open_file(self):
        from commands import dispatch
        res = dispatch({"intent": "open_file", "args": {"path": "C:\\malicious.bat"}})
        assert "Access denied" in res

    def test_unsafe_pattern(self):
        from commands import dispatch
        res = dispatch({"intent": "type_text", "args": {"text": "rm -rf /"}})
        assert "Access denied" in res


class TestEntertainment:
    def test_tell_joke(self):
        assert intent_of("tell me a joke") == "tell_joke"
        assert intent_of("chutkula sunao") == "tell_joke"

    def test_tell_fact(self):
        assert intent_of("tell me a fact") == "tell_fact"
        assert intent_of("did you know") == "tell_fact"
        assert intent_of("kuch fact batao") == "tell_fact"

    def test_tell_riddle(self):
        assert intent_of("ask me a riddle") == "tell_riddle"
        assert intent_of("pehli sunao") == "tell_riddle"
        assert intent_of("paheli sunao") == "tell_riddle"


class TestMarathi:
    def test_time(self):
        assert intent_of("किती वाजले") == "tell_time"
        assert intent_of("काय वेळ झाली आहे") == "tell_time"

    def test_date(self):
        assert intent_of("आज कोणती तारीख आहे") == "tell_date"
        assert intent_of("तारीख सांग") == "tell_date"

    def test_open_app(self):
        assert intent_of("chrome उघड") == "open_app"
        assert args_of("chrome उघड")["app"] == "chrome"
        assert intent_of("spotify चालू कर") == "open_app"
        assert args_of("spotify चालू कर")["app"] == "spotify"

    def test_close_app(self):
        assert intent_of("chrome बंद कर") == "close_app"
        assert args_of("chrome बंद कर")["app"] == "chrome"

    def test_volume(self):
        assert intent_of("आवाज बंद कर") == "mute_volume"
        assert intent_of("आवाज चालू कर") == "unmute_volume"
        assert intent_of("आवाज वाढव") == "volume_up"
        assert intent_of("आवाज कमी कर") == "volume_down"

    def test_screenshot(self):
        assert intent_of("स्क्रीनशॉट काढ") == "screenshot"

    def test_quit(self):
        assert intent_of("बंद हो") == "quit_assistant"

    def test_chat(self):
        assert intent_of("नमस्कार") == "chat"
        assert "मदत" in args_of("नमस्कार")["response"]
        assert intent_of("कशी आहेस") == "chat"
        assert "शिन" in args_of("कशी आहेस")["response"]


class TestSpeechNormalization:
    def test_clean_text_speed(self):
        from assistant import _clean_text_for_speech
        assert "kilometers per hour" in _clean_text_for_speech("The speed limit is 60 km/h")
        assert "kilometers per hour" in _clean_text_for_speech("He runs 10 km/hr")
        assert "kilometers per hour" in _clean_text_for_speech("60KMH is fast")
        assert "kilometers per hour" in _clean_text_for_speech("60km/h is fast")

    def test_clean_text_degrees(self):
        from assistant import _clean_text_for_speech
        assert "degrees Celsius" in _clean_text_for_speech("It is 22°C outside")
        assert "degrees" in _clean_text_for_speech("Rotated by 90°")


class TestNeuralNLP:
    def test_neural_classification(self):
        import sys
        import os
        sys.path.append(os.path.abspath("core"))
        import neural_nlp
        
        # Test open app classification
        res = neural_nlp.predict_intent("open chrome browser")
        assert res is not None
        assert res["intent"] == "open_app"
        assert "chrome" in res["args"]["app"]
        
        # Test volume up classification
        res = neural_nlp.predict_intent("sound increase please")
        assert res is not None
        assert res["intent"] == "volume_up"
        
        # Test low confidence fallback (should return None for unrecognized commands)
        res = neural_nlp.predict_intent("what is the chemical structure of benzene")
        assert res is None


class TestNewTrainingAndMissedRules:
    def test_train_shin(self):
        assert intent_of("train yourself") == "train_shin"
        assert intent_of("train shin") == "train_shin"
        assert intent_of("train her") == "train_shin"
        assert intent_of("teach her") == "train_shin"
        assert intent_of("teach her new things") == "train_shin"
        assert intent_of("seekho") == "train_shin"

    def test_news_intents(self):
        assert intent_of("tell me the news") == "tell_news"
        assert intent_of("latest tech news") == "tell_news"
        assert args_of("latest tech news")["topic"] == "technology"
        assert intent_of("news about AI") == "tell_news"
        assert args_of("news about AI")["topic"] == "AI"

    def test_learn_from_internet(self):
        assert intent_of("learn about quantum computing from internet") == "learn_from_internet"
        assert args_of("learn about quantum computing from internet")["topic"] == "quantum computing"
        assert intent_of("take info about black holes from internet") == "learn_from_internet"
        assert args_of("take info about black holes from internet")["topic"] == "black holes"
        assert intent_of("fetch and learn about artificial intelligence") == "learn_from_internet"
        assert args_of("fetch and learn about artificial intelligence")["topic"] == "artificial intelligence"


    def test_remind_me(self):
        assert intent_of("Remind me to exercise at 11 pm") == "set_reminder"
        assert args_of("Remind me to exercise at 11 pm")["task"] == "exercise"
        assert args_of("Remind me to exercise at 11 pm")["time"] == "11 pm"

    def test_hindi_schedule(self):
        assert intent_of("aaj ka karyakram") == "calendar_list"
        assert args_of("aaj ka karyakram")["range"] == "today"

    def test_bare_scroll(self):
        assert intent_of("scroll") == "scroll"
        assert args_of("scroll")["direction"] == "down"

    def test_save_and_recall_memory_hinglish(self):
        assert intent_of("yaad rakh ki my keys are in car") == "save_memory"
        assert intent_of("batao kya yaad hai") == "recall_memory"

    def test_explain_internet(self):
        assert intent_of("how do you use the internet") == "explain_internet"
        assert intent_of("tell me about the internet") == "explain_internet"
        assert intent_of("teach her about internet") == "explain_internet"

    def test_wiki_search(self):
        assert intent_of("search wikipedia for quantum computing") == "wiki_search"
        assert args_of("search wikipedia for quantum computing")["query"] == "quantum computing"
        assert intent_of("wikipedia artificial intelligence") == "wiki_search"
        assert args_of("wikipedia artificial intelligence")["query"] == "artificial intelligence"
        assert intent_of("wiki search black holes") == "wiki_search"


class TestKnowledgeAndDeveloperCapabilities:
    def test_explain_concept(self):
        assert intent_of("what is vs code") == "explain_concept"
        assert args_of("what is vs code")["concept"] == "vs code"
        assert intent_of("explain laptop") == "explain_concept"
        assert args_of("explain laptop")["concept"] == "laptop"
        assert intent_of("what is cpu") == "explain_concept"
        assert args_of("what is cpu")["concept"] == "cpu"
        assert intent_of("command vs talk") == "explain_concept"

    def test_locate_app(self):
        assert intent_of("where is chrome installed") == "locate_app"
        assert args_of("where is chrome installed")["app"] == "chrome"
        assert intent_of("where is blender located") == "locate_app"
        assert args_of("where is blender located")["app"] == "blender"

    def test_project_help_and_screen(self):
        assert intent_of("help me with my project") == "help_with_project"
        assert intent_of("project mein help karo") == "help_with_project"
        assert intent_of("what is happening on screen") == "explain_screen_activity"
        assert intent_of("screen pe kya chal raha hai") == "explain_screen_activity"
        assert intent_of("check screen error") == "screen_diagnose_bug"
        assert intent_of("diagnose screen bug") == "screen_diagnose_bug"

    def test_code_generation_and_execution(self):
        assert intent_of("write python code for calculator") == "generate_code"
        assert args_of("write python code for calculator")["language"] == "python"
        assert intent_of("explain this code") == "explain_code"
        assert intent_of("code samjhao") == "explain_code"
        assert intent_of("run python code: print('hi')") == "run_python_code"
        assert args_of("run python code: print('hi')")["code"] == "print('hi')"

    def test_git_and_file_creation(self):
        assert intent_of("check git status") == "project_git_status"
        assert intent_of("git status") == "project_git_status"
        assert intent_of("git diff") == "git_diff_summary"
        assert intent_of("create file test.py") == "create_project_file"
        assert args_of("create file test.py")["filename"] == "test.py"
        assert intent_of("naya file banao utils.py") == "create_project_file"
        assert args_of("naya file banao utils.py")["filename"] == "utils.py"

    def test_draft_whatsapp(self):
        assert intent_of("draft whatsapp message to dad saying I reached college") == "draft_whatsapp_message"
        assert args_of("draft whatsapp message to dad saying I reached college")["contact"] == "dad"
        assert intent_of("draft a message saying I will be late") == "draft_whatsapp_message"

    def test_ai_hardware_and_code_reviewer(self):
        assert intent_of("check ai hardware") == "check_ai_hardware"
        assert intent_of("is my laptop copilot ready") == "check_ai_hardware"
        assert intent_of("review this code") == "review_code"
        assert intent_of("code review karo") == "review_code"
        assert intent_of("review file order_service.py") == "review_code"
        assert args_of("review file order_service.py")["filepath"] == "order_service.py"

    def test_ui_tree_controls(self):
        assert intent_of("get ui controls") == "get_ui_tree"
        assert intent_of("list buttons on screen") == "get_ui_tree"
        assert intent_of("click button save button") == "click_ui_element"

    def test_hinglish_music_intents(self):
        # Generic Hinglish & English music requests
        assert intent_of("koi gana lagao") == "youtube_play"
        assert args_of("koi gana lagao")["query"] == "random hindi songs mix"

        assert intent_of("koi gana baja do") == "youtube_play"
        assert args_of("koi gana baja do")["query"] == "random hindi songs mix"

        assert intent_of("gana lagao") == "youtube_play"
        assert intent_of("gana bajao") == "youtube_play"
        assert intent_of("sing koi gana laga do") == "youtube_play"
        assert intent_of("can you play music") == "youtube_play"
        assert intent_of("play music") == "youtube_play"
        assert intent_of("play some music") == "youtube_play"
        assert intent_of("play a song") == "youtube_play"
        assert intent_of("koi gana sunao") == "youtube_play"

        # Genre-specific
        assert intent_of("koi sad gana lagao") == "youtube_play"
        assert args_of("koi sad gana lagao")["query"] == "sad hindi songs mix"

        assert intent_of("koi party gana bajao") == "youtube_play"
        assert args_of("koi party gana bajao")["query"] == "party hindi songs mix"

        # Artist-specific
        assert intent_of("arijit singh ka gana lagao") == "youtube_play"
        assert "arijit singh" in args_of("arijit singh ka gana lagao")["query"].lower()

        # Specific play commands
        assert intent_of("play spotify") == "open_app"
        assert args_of("play spotify")["app"] == "spotify"

    def test_hinglish_app_and_internet_understanding(self):
        # Hinglish app opening
        assert intent_of("github open kar") == "open_app"
        assert args_of("github open kar")["app"].lower() == "github"

        assert intent_of("vs code open karo") == "open_app"
        assert args_of("vs code open karo")["app"].lower() == "vs code"

        # Acoustic leading wake words stripped
        assert intent_of("singh github open karo") == "open_app"
        assert args_of("singh github open karo")["app"].lower() == "github"

        assert intent_of("achcha seen aaj din kya hai") == "tell_date"
        assert intent_of("aaj din kya hai") == "tell_date"
        assert intent_of("aaj kaun sa din hai") == "tell_date"
        assert intent_of("what day is today") == "tell_date"

        # Internet understanding
        assert intent_of("how do you use the internet") == "explain_internet"
        assert intent_of("explain internet access") == "explain_internet"
        assert intent_of("internet kaise use karti ho") == "explain_internet"

    def test_female_grammar_enforcement(self):
        from nlp import enforce_female_grammar
        assert enforce_female_grammar("Kaise help kar sakta hoon aapko?") == "Kaise help kar sakti hoon aapko?"
        assert enforce_female_grammar("Main abhi dekh raha hoon.") == "Main abhi dekh rahi hoon."
        assert enforce_female_grammar("Main bataunga.") == "Main bataungi."
        assert enforce_female_grammar("Main samajh gaya.") == "Main samajh gayi."
        assert enforce_female_grammar("Main karta hoon kaam.") == "Main karti hoon kaam."
        assert enforce_female_grammar("Main thak gaya hoon.") == "Main thak gayi hoon."

    def test_phonetic_wake_word_handling(self):
        # ASR phonetic variants like 'singh', 'sin', 'seen', 'sing'
        assert intent_of("singh open chrome") == "open_app"
        assert args_of("singh open chrome")["app"] == "chrome"

        assert intent_of("sin close youtube") == "close_app"
        assert args_of("sin close youtube")["app"] == "youtube"

        assert intent_of("seen volume badhao") == "volume_up"

        assert intent_of("sing koi gana lagao") == "youtube_play"

        # Preserving real singer names and English verbs
        assert intent_of("arijit singh ka gana lagao") == "youtube_play"
        assert "arijit singh" in args_of("arijit singh ka gana lagao")["query"]

    def test_normalize_recognized_name(self):
        import assistant
        assert assistant._normalize_recognized_name("singh guitar open karo") == "shin guitar open karo"
        assert assistant._normalize_recognized_name("sin volume badhao") == "shin volume badhao"
        assert assistant._normalize_recognized_name("seen volume badhao") == "shin volume badhao"
        assert assistant._normalize_recognized_name("in close the youtube") == "shin close the youtube"
        assert assistant._normalize_recognized_name("achcha seen aaj din kya hai") == "achcha shin aaj din kya hai"
        assert assistant._normalize_recognized_name("sing koi gana lagao") == "shin koi gana lagao"
        # preserve singer and english
        assert assistant._normalize_recognized_name("arijit singh ka gana lagao") == "arijit singh ka gana lagao"
        assert assistant._normalize_recognized_name("sing a song") == "sing a song"






