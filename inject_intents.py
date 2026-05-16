import re

with open('D:/Freya/brain/intent.py', 'r', encoding='utf-8') as f:
    text = f.read()

automation_intents = '''
    # --- DESKTOP AUTOMATION ---
    ("type_text", [
        r"\\\\b(type|write|enter the text|input)\\\\s+(.+)"
    ], {}, False),
    ("press_enter", [
        r"\\\\b(press enter|hit enter|submit)\\\\b"
    ], {}, False),
    ("switch_window", [
        r"\\\\b(switch window|switch tab|next window|change window)\\\\b"
    ], {}, False),
    ("close_window", [
        r"\\\\b(close window|close tab|close this)\\\\b"
    ], {}, False),
'''
if "type_text" not in text:
    text = text.replace('INTENT_PATTERNS = [', 'INTENT_PATTERNS = [' + automation_intents)
    with open('D:/Freya/brain/intent.py', 'w', encoding='utf-8') as f:
        f.write(text)

with open('D:/Freya/freya.py', 'r', encoding='utf-8') as f:
    text = f.read()

freya_automation = '''
    if name == "type_text":
        from automation.desktop import type_text as dt_type
        return dt_type(ent.get("text", intent.raw.replace("type ", "").replace("write ", "")))

    if name == "press_enter":
        from automation.desktop import press_key
        return press_key("enter")

    if name == "switch_window":
        from automation.desktop import switch_window
        return switch_window()

    if name == "close_window":
        from automation.desktop import close_active_window
        return close_active_window()
'''
if "type_text" not in text:
    text = text.replace('    if name == "take_screenshot":', freya_automation + '\\n    if name == "take_screenshot":')
    with open('D:/Freya/freya.py', 'w', encoding='utf-8') as f:
        f.write(text)

with open('D:/Freya/brain/intent.py', 'r', encoding='utf-8') as f:
    text = f.read()
if "entities['text']" not in text:
    text = text.replace('    if intent == "youtube_search":', '''    if intent == "type_text":
        m = re.search(r"\\\\b(?:type|write|input)\\\\s+(.+)", text)
        if m:
            entities["text"] = m.group(1).strip()
            
    if intent == "youtube_search":''')
    with open('D:/Freya/brain/intent.py', 'w', encoding='utf-8') as f:
        f.write(text)
