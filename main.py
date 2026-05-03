import time
import machine
import lcd_bus
import lvgl as lv
import ili9341
import xpt2046
import task_handler
from micropython import const
import random
import json


SEED = {
    'noun':      [['morning', 0], ['silence', 0], ['distance', 0], ['window', 0]],
    'quality':   [['quiet', 0], ['unfinished', 0], ['familiar', 0], ['tender', 0]],
    'action':    [['carrying', 0], ['returning', 0], ['waiting', 0], ['circling', 0]],
    'verb_past': [['remembered', 0], ['noticed', 0], ['felt', 0]],
}

GRAMMAR_PATH = '/grammar.json'

def load_grammar():
    try:
        with open(GRAMMAR_PATH) as f:
            return json.load(f)
    except:
        return {k: list(v) for k, v in SEED.items()}

def save_grammar(rules):
    try:
        with open(GRAMMAR_PATH, 'w') as f:
            json.dump(rules, f)
    except Exception as e:
        print('save error:', e)

def grammar_pick(rules, slot):
    entries = rules.get(slot, [])
    if not entries:
        return slot
    weights = [max(1, e[1]) for e in entries]
    total = sum(weights)
    r = random.randint(0, total - 1)
    cumulative = 0
    for entry, w in zip(entries, weights):
        cumulative += w
        if r < cumulative:
            return entry[0]
    return entries[-1][0]

def grammar_expand(rules, template):
    result = []
    i = 0
    while i < len(template):
        if template[i] == '#':
            try:
                closing = template.index('#', i + 1)
                slot = template[i+1:closing]
                result.append(grammar_pick(rules, slot))
                i = closing + 1
            except ValueError:
                result.append(template[i])
                i += 1
        else:
            result.append(template[i])
            i += 1
    return ''.join(result)

def grammar_push(rules, slot, word, session_n):
    if slot not in rules:
        rules[slot] = []
    existing = [e[0] for e in rules[slot]]
    if word not in existing:
        rules[slot].append([word, session_n])


DETERMINERS  = {'the','a','an','this','that','my','your','its'}
PREPOSITIONS = {'in','on','at','by','for','with','about','under','through'}
CONJUNCTIONS = {'and','but','or','so','because','when','if'}
AUXILIARIES  = {'is','was','were','are','had','have','did','do','could','would'}
PRONOUNS     = {'i','me','you','he','she','it','we','they','them','us'}
STOPWORDS    = {'thing','things','something','way','time','day','bit','lot',
                'really','very','just','quite','also','even','still','maybe'}

def tag(word):
    w = word.lower().rstrip('.,!?')
    if not w or len(w) < 3: return None
    if w in DETERMINERS:  return None
    if w in PREPOSITIONS: return None
    if w in CONJUNCTIONS: return None
    if w in AUXILIARIES:  return None
    if w in PRONOUNS:     return None
    if w in STOPWORDS:    return None
    if w.endswith('ing'): return 'action'
    if w.endswith('ed'):  return 'verb_past'
    if w.endswith('ly'):  return None
    if w.endswith('ful'): return 'quality'
    if w.endswith('less'):return 'quality'
    return 'noun'


PROMPTS = [
    "What are you #action# today?",
    "Something felt #quality#. What was it?",
    "What did you #verb_past# that you haven't said aloud?",
    "Where does the #noun# live in your body?",
    "The #quality# thing and the #noun#,what do they share?",
    "You have been #action# the #noun#. Is that true?",
    "The #noun# you #verb_past#, is it still #quality#?",
]

STRANGERS = [
    "What accumulates without your permission?",
    "The gap before the next thing, what lives there?",
    "Name the liminal thing.",
    "What is neither here nor gone?",
]

session_count = 0

def get_prompt(rules):
    if random.randint(0, 5) == 0:
        return STRANGERS[random.randint(0, len(STRANGERS) - 1)]
    t = PROMPTS[random.randint(0, len(PROMPTS) - 1)]
    return grammar_expand(rules, t)


BG    = 0x1a1a2e
TEXT  = 0xe0e0e0
DIM   = 0x888888
BTN   = 0x4a4a8a
BTN2  = 0x2a2a4a
SEL   = 0x6a6aaa

WORD_POOL_SIZE = 8

class App:
    def __init__(self, rules):
        self.rules = rules
        self.session_n = 0
        self.current_prompt = ""
        self.selected_words = set()
        self._home_screen = None
        self._session_screen = None
        self._harvest_screen = None
        self._prompt_lbl = None
        self._cloud_btns = {}  


    def build_home(self):
        scr = lv.obj()
        scr.set_style_bg_color(lv.color_hex(BG), 0)
        scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

        title = lv.label(scr)
        title.set_text("Echo")
        title.set_style_text_color(lv.color_hex(TEXT), 0)
        title.set_style_text_font(lv.font_montserrat_24, 0)
        title.align(lv.ALIGN.CENTER, 0, -40)

        sub = lv.label(scr)
        sub.set_text("a solo journaling game")
        sub.set_style_text_color(lv.color_hex(DIM), 0)
        sub.align(lv.ALIGN.CENTER, 0, -10)

        btn = lv.button(scr)
        btn.set_size(180, 46)
        btn.align(lv.ALIGN.CENTER, 0, 40)
        btn.set_style_bg_color(lv.color_hex(BTN), 0)
        btn.set_style_radius(8, 0)
        btn.add_event_cb(lambda e: self.go_session(), lv.EVENT.CLICKED, None)
        lbl = lv.label(btn)
        lbl.set_text("Begin Session")
        lbl.center()

        self._home_screen = scr

    def go_home(self):
        if self._home_screen is None:
            self.build_home()
        lv.screen_load(self._home_screen)

    def build_session(self):
        scr = lv.obj()
        scr.set_style_bg_color(lv.color_hex(BG), 0)
        scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

        top = lv.label(scr)
        top.set_text("reflect")
        top.set_style_text_color(lv.color_hex(DIM), 0)
        top.align(lv.ALIGN.TOP_MID, 0, 10)

        self._prompt_lbl = lv.label(scr)
        self._prompt_lbl.set_width(290)
        self._prompt_lbl.set_long_mode(lv.label.LONG_MODE.WRAP)
        self._prompt_lbl.set_style_text_color(lv.color_hex(TEXT), 0)
        self._prompt_lbl.set_style_text_font(lv.font_montserrat_16, 0)
        self._prompt_lbl.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        self._prompt_lbl.align(lv.ALIGN.CENTER, 0, -10)

        btn = lv.button(scr)
        btn.set_size(130, 34)
        btn.align(lv.ALIGN.BOTTOM_RIGHT, -10, -10)
        btn.set_style_bg_color(lv.color_hex(BTN2), 0)
        btn.set_style_radius(6, 0)
        btn.add_event_cb(lambda e: self.go_harvest(), lv.EVENT.CLICKED, None)
        lbl = lv.label(btn)
        lbl.set_text("Done reflecting")
        lbl.center()

        self._session_screen = scr

    def go_session(self):
        if self._session_screen is None:
            self.build_session()
        self.current_prompt = get_prompt(self.rules)
        self._prompt_lbl.set_text(self.current_prompt)
        lv.screen_load(self._session_screen)

    def build_harvest(self):
        scr = lv.obj()
        scr.set_style_bg_color(lv.color_hex(BG), 0)
        scr.remove_flag(lv.obj.FLAG.SCROLLABLE)

        top = lv.label(scr)
        top.set_text("what landed? tap words to save")
        top.set_style_text_color(lv.color_hex(DIM), 0)
        top.align(lv.ALIGN.TOP_MID, 0, 8)

        self._cloud_cont = lv.obj(scr)
        self._cloud_cont.set_size(300, 130)
        self._cloud_cont.align(lv.ALIGN.CENTER, 0, 0)
        self._cloud_cont.set_style_bg_opa(0, 0)
        self._cloud_cont.set_style_border_width(0, 0)
        self._cloud_cont.set_layout(lv.LAYOUT.FLEX)
        self._cloud_cont.set_style_flex_flow(lv.FLEX_FLOW.ROW_WRAP, 0)
        self._cloud_cont.set_style_pad_gap(6, 0)

        btn = lv.button(scr)
        btn.set_size(100, 34)
        btn.align(lv.ALIGN.BOTTOM_RIGHT, -10, -10)
        btn.set_style_bg_color(lv.color_hex(BTN), 0)
        btn.set_style_radius(6, 0)
        btn.add_event_cb(lambda e: self.save_and_home(), lv.EVENT.CLICKED, None)
        lbl = lv.label(btn)
        lbl.set_text("Save")
        lbl.center()

        self._ta = lv.textarea(scr)
        self._ta.set_size(150, 34)
        self._ta.set_one_line(True)
        self._ta.set_placeholder_text("add a word...")
        self._ta.align(lv.ALIGN.BOTTOM_LEFT, 10, -10)

        self._kb = lv.keyboard(scr)
        self._kb.set_size(300, 110)
        self._kb.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self._kb.set_textarea(self._ta)
        self._kb.add_flag(lv.obj.FLAG.HIDDEN)

        self._ta.add_event_cb(self._on_ta_focus, lv.EVENT.FOCUSED, None)
        self._kb.add_event_cb(self._on_kb_ready, lv.EVENT.READY, None)


        self._harvest_screen = scr

    def _on_ta_focus(self, evt):
        self._kb.remove_flag(lv.obj.FLAG.HIDDEN)

    def _on_kb_ready(self, evt):
        word = self._ta.get_text().strip().lower()
        if word and len(word) >= 3:
            self.selected_words.add(word)
            self._add_chip(word)
            self._ta.set_text("")
            self._kb.add_flag(lv.obj.FLAG.HIDDEN)

    def _populate_cloud(self):
        self._cloud_cont.clean()
        self._cloud_btns.clear()
        self.selected_words.clear()

        from_prompt = []
        for raw in self.current_prompt.split():
            w = raw.lower().rstrip('.,!?')
            slot = tag(w)
            if slot:
                from_prompt.append(w)

        from_grammar = []
        for slot in self.rules:
            if self.rules[slot]:
                pick = grammar_pick(self.rules, slot)
                if pick not in from_prompt:
                    from_grammar.append(pick)

        candidates = list(set(from_prompt + from_grammar))
        for i in range(len(candidates) - 1, 0, -1):
            j = random.randint(0, i)
            candidates[i], candidates[j] = candidates[j], candidates[i]

        candidates = candidates[:WORD_POOL_SIZE]

        for word in candidates:
            self._add_chip(word)

    def _add_chip(self, word):
        btn = lv.button(self._cloud_cont)
        btn.set_style_bg_color(lv.color_hex(BTN2), 0)
        btn.set_style_radius(12, 0)
        btn.set_height(30)
        btn.set_width(len(word) * 10 + 20)
        btn.set_style_pad_hor(10, 0)
        lbl = lv.label(btn)
        lbl.set_text(word)
        lbl.set_style_text_color(lv.color_hex(TEXT), 0)
        btn.add_event_cb(
            lambda e, w=word, b=btn: self._toggle(w, b),
            lv.EVENT.CLICKED, None
        )
        self._cloud_btns[word] = btn

    def _toggle(self, word, btn):
        if word in self.selected_words:
            self.selected_words.discard(word)
            btn.set_style_bg_color(lv.color_hex(BTN2), 0)
        else:
            self.selected_words.add(word)
            btn.set_style_bg_color(lv.color_hex(SEL), 0)

    def go_harvest(self):
        if self._harvest_screen is None:
            self.build_harvest()
        self._populate_cloud()
        lv.screen_load(self._harvest_screen)

    def save_and_home(self):
        self.session_n += 1
        for word in self.selected_words:
            slot = tag(word)
            if slot:
                grammar_push(self.rules, slot, word, self.session_n)
        save_grammar(self.rules)
        self.go_home()



def main():
    spi_bus = machine.SPI.Bus(host=1, mosi=13, sck=14)
    display_bus = lcd_bus.SPIBus(spi_bus=spi_bus, freq=24_000_000, dc=2, cs=15)

    display = ili9341.ILI9341(
        data_bus=display_bus,
        display_width=320,
        display_height=240,
        backlight_pin=21,
        backlight_on_state=ili9341.STATE_PWM,
        color_space=lv.COLOR_FORMAT.RGB565,
        color_byte_order=ili9341.BYTE_ORDER_RGB,
        rgb565_byte_swap=1
    )
    display.set_power(True)
    display.init(1)
    display._ORIENTATION_TABLE = (0xE0, 0x0, 0x0, 0x0)
    display.set_rotation(lv.DISPLAY_ROTATION._0)
    display.set_backlight(100)

    indev_bus = machine.SPI.Bus(host=2, mosi=32, miso=39, sck=25)
    indev_device = machine.SPI.Device(spi_bus=indev_bus, freq=2000000, cs=33)
    indev = xpt2046.XPT2046(device=indev_device)
    if not indev.is_calibrated:
        indev.calibrate()
        indev._cal.save()

    task_handler.TaskHandler()

    rules = load_grammar()
    app = App(rules)
    app.go_home()


main()
while True:
    time.sleep(1)
