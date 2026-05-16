with open('D:/Freya/voice/speaker.py', 'r', encoding='utf-8') as f:
    text = f.read()

import re
text = re.sub(r'print\(f"\\n.*?Freya: \{clean\}\\n"\)', 'print(f"\\nFreya: {clean}\\n")', text)

with open('D:/Freya/voice/speaker.py', 'w', encoding='utf-8') as f:
    f.write(text)
