import json
import re

# 1. Update config
with open('D:/Freya/config.json', 'r', encoding='utf-8') as f:
    cfg = json.load(f)

cfg['voice']['kokoro_voice'] = 'if_sara'
cfg['voice']['kokoro_lang'] = 'a'

with open('D:/Freya/config.json', 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=4)


# 2. Add open_app intent
with open('D:/Freya/brain/intent.py', 'r', encoding='utf-8') as f:
    text = f.read()

if "open_app" not in text:
    new_intents = '''
    ("open_app", [
        r"\\\\bopen\\\\s+(?!chrome)([a-zA-Z0-9]+)\\\\b",
        r"\\\\blaunch\\\\s+([a-zA-Z0-9]+)\\\\b",
        r"\\\\bstart\\\\s+([a-zA-Z0-9]+)\\\\b"
    ], {}, False),
'''
    text = text.replace('INTENT_PATTERNS = [', 'INTENT_PATTERNS = [' + new_intents)
    
if "entities['app_name']" not in text:
    new_entity_logic = '''
    if intent == "open_app":
        m = re.search(r"\\\\b(?:open|launch|start)\\\\s+(.+)", text)
        if m:
            entities["app_name"] = m.group(1).strip()
            
    if intent == "youtube_search":'''
    text = text.replace('    if intent == "youtube_search":', new_entity_logic)

with open('D:/Freya/brain/intent.py', 'w', encoding='utf-8') as f:
    f.write(text)


# 3. Add streaming to freya.py and open_app routing
with open('D:/Freya/freya.py', 'r', encoding='utf-8') as f:
    text = f.read()

streaming_func = '''
def _llm_respond_stream(text: str):
    from brain.llm import chat_stream
    if not is_ollama_running():
        yield "Ollama isn't running."
        return
    memory_sum = get_memory_summary()
    system_prompt = build_system_prompt(ctx, memory_sum)
    history = ctx.conversation_history[-8:]
    yield from chat_stream(text, system_prompt, history)
'''

if "_llm_respond_stream" not in text:
    text = text.replace('def _llm_respond(text: str) -> str:', streaming_func + '\\ndef _llm_respond(text: str) -> str:')

route_app = '''
    if name == "open_app":
        app_name = ent.get("app_name", "")
        from automation.desktop import open_app_via_run
        return open_app_via_run(app_name)
'''
if "if name == \"open_app\":" not in text:
    text = text.replace('    if name == "open_chrome":', route_app + '\\n    if name == "open_chrome":')

# Modify the voice_loop to stream chat
loop_replace = '''
            if intent.name in ("chat", "greeting", "status_check", "read_screen"):
                full_response = ""
                sentence = ""
                for chunk in _llm_respond_stream(intent.raw):
                    full_response += chunk
                    sentence += chunk
                    # Check for sentence boundaries
                    if any(p in sentence for p in [". ", "! ", "? ", "\\n"]):
                        parts = re.split(r'(?<=[.!?\\n])\\s', sentence, 1)
                        if len(parts) > 1:
                            speak(parts[0], priority=False)
                            sentence = parts[1]
                        else:
                            speak(sentence, priority=False)
                            sentence = ""
                if sentence.strip():
                    speak(sentence, priority=False)
                response = full_response
            else:
                response = route_intent(intent)
                if intent.name not in ["exit", "google_search"]:
                    rephrase_prompt = f"System task executed. Result: '{response}'. Tell Atharv you did this. Keep it short (1 sentence), casual, and use your bestie persona."
                    natural_response = _llm_respond(rephrase_prompt)
                    if natural_response and len(natural_response) < 150:
                        response = natural_response
                        speak(response)
                    else:
                        speak(response)
                else:
                    speak(response)
'''

# We need to carefully replace the logic block inside voice_loop
# Let's write a targeted regex replacement for voice_loop routing block
import re
pattern = r'try:\s*response = route_intent\(intent\).*?speak\(response\)'
text = re.sub(pattern, loop_replace.strip(), text, flags=re.DOTALL)

with open('D:/Freya/freya.py', 'w', encoding='utf-8') as f:
    f.write(text)

