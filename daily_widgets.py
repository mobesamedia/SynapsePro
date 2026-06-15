# -*- coding: utf-8 -*-

import os
import re
import math
import base64
import traceback
from datetime import date, timedelta
import time
from typing import Dict, List, Optional
import json

from aqt import mw

# --- Night Mode Detection ---
is_night_mode = False
try:
    if mw and mw.pm.night_mode():
        is_night_mode = True
except Exception:
    pass

try:
    from .theme import palette as _palette, FONT_FAMILY as _FONT_FAMILY
except ImportError:
    def _palette(night): return {"blue": "#0071D3", "blue_bright": "#40A5FF" if night else "#007AFF"}  # type: ignore
    _FONT_FAMILY = "sans-serif"

# --- Import LearningPlanManager ---
try:
    from .learning_plan import LearningPlanManager
except ImportError:
    LearningPlanManager = object

# --- Translation Function ---
# NOTE on fact translations:
# The MEDICAL_FACTS / LAW_FACTS / GENERAL_FACTS / COUNTRY_FACTS dicts keep
# their English text as-is. The _() wrapper is applied at the READ site
# inside ``generate_fact_widget`` so that live language switches actually
# take effect on the next render. Wrapping the dict literals directly with
# _() would freeze the translations at module-import time and break the
# live-update contract for the fact widget.
try:
    from .locales import _
except ImportError:
    def _(text): return text  # safety fallback

# --- Debug offset (days) ---
_debug_day_offset = 0

# --- Konstanten & Konfiguration ---
PLAN_WIDGET_FLEX_GROW = "1"
PLAN_WIDGET_FLEX_SHRINK = "1"
PLAN_WIDGET_FLEX_BASIS = "280px"
PLAN_WIDGET_MAX_WIDTH = "350px"

FACT_WIDGET_FLEX_GROW = "2"
FACT_WIDGET_FLEX_SHRINK = "1"
FACT_WIDGET_FLEX_BASIS = "450px"
FACT_WIDGET_MAX_WIDTH = "600px"

PLAN_TEXT_COLOR = "white"
PLAN_COLOR_ADJUST_STEP = 15
PLAN_ROW_DONE_COLOR = "#6ABE57"
PLAN_ROW_PAUSED_COLOR = "#F5A623"

FACT_IMAGE_SUBFOLDER = "images"
IMAGE_MIME_TYPE = "image/png"
DAILY_WIDGETS_GAP = "15px"
DAILY_WIDGETS_MARGIN_BOTTOM = "15px"
DAILY_WIDGETS_MAX_WIDTH = "880px"

# --- Medizinische Fakten Liste ---
MEDICAL_FACTS = [
    {"text": "Did you know? Your brain consumes a significant amount of energy, about 20% of your body's total supply, despite only accounting for roughly 2% of your total body weight.", "image": "brain_energy.png"},
    {"text": "It's astounding: If you lined up all ~25 trillion erythrocytes (red blood cells) in your body end-to-end, they would form a chain long enough to circle the entire Earth four times at the equator!", "image": "erythrocyte_chain.png"},
    {"text": "Technically, you perceive sound with your brain, not directly with your ears. Your ears simply act as sophisticated collectors, converting sound waves into signals the brain interprets.", "image": "brain_hearing.png"},
    {"text": "Unique within the body, the cornea lacks its own blood supply. Instead, this transparent eye layer gets the oxygen it needs directly from the surrounding air.", "image": "cornea_oxygen.png"},
    {"text": "Your skeleton isn't static! Bones are constantly undergoing a process of breakdown and rebuilding, leading to a complete skeletal renewal approximately every 10 years.", "image": "bone_renewal.png"},
    {"text": "The power of the mind: The placebo effect can be so potent that treatments sometimes still work even when patients are fully aware they're receiving a placebo.", "image": "placebo_effect.png"},
    {"text": "Contrary to popular belief, human blood is never actually blue. It only appears bluish through the skin because of how different wavelengths of light penetrate and reflect off tissues.", "image": "blood_color.png"},
    {"text": "Those wrinkly fingers after a bath aren't just from water absorption! It's an active nervous system response, possibly evolved to improve grip on wet surfaces.", "image": "wrinkled_fingers.png"},
    {"text": "Your gut contains its own complex 'brain,' the enteric nervous system. This extensive network boasts over 100 million neurons, managing digestion largely independently.", "image": "gut_brain.png"},
    {"text": "The sheer complexity of the human brain is staggering: It contains more connections (synapses) between neurons than there are estimated stars in the entire Milky Way galaxy.", "image": "brain_synapses.png"},
    {"text": "During moments of intense fear, your body initiates the 'fight or flight' response, strategically redirecting blood flow away from non-essential areas and towards your major muscles.", "image": "fight_or_flight.png"},
    {"text": "A good laugh is like natural medicine! Laughter can actually increase your pain tolerance by triggering the release of endorphins, the body's natural feel-good chemicals, in the brain.", "image": "laughter_pain.png"},
    {"text": "Despite its widespread use in medicine for decades, the precise mechanisms of how general anesthesia works to induce unconsciousness remain surprisingly not fully understood by science.", "image": "anesthesia_mystery.png"},
    {"text": "Those tiny bumps on your skin? Goosebumps are a fascinating evolutionary leftover, a reflex inherited from our hairier ancestors used to raise fur for insulation or intimidation.", "image": "goosebumps_reflex.png"},
    {"text": "You're vastly outnumbered inside! Your gut microbiome hosts more individual bacterial cells than there are human cells comprising your entire body, playing vital roles in overall health.", "image": "gut_bacteria.png"},
    {"text": "A rare condition known as Superior Canal Dehiscence Syndrome allows some individuals to actually hear internal body sounds, such as their own eyeballs moving within their sockets.", "image": "eyeball_hearing.png"},
    {"text": "Why do we yawn? One leading theory suggests yawning might function as a natural thermostat, helping to cool down an overheating brain by increasing blood flow and air intake.", "image": "yawning_brain_cool.png"},
    {"text": "There's a physiological basis for connection: Studies show that when people hold hands or gaze into each other's eyes for a period, their heartbeats can actually synchronize.", "image": "heartbeat_sync.png"},
    {"text": "Over an average lifetime, you'll shed approximately 40 pounds (around 18kg) of dead skin cells. Much of the common household dust is actually composed of this sloughed-off skin.", "image": "skin_shedding.png"},
    {"text": "The brain's internal body map is powerful: Phantom limb sensations or even pain can occur in individuals born without that specific limb, demonstrating the map's innate nature.", "image": "phantom_limb.png"},
    {"text": "The liver possesses an incredible regenerative capacity. It's capable of regrowing back to its full, original size even if only 25% of the healthy tissue remains after damage or surgery.", "image": "liver_regrowth.png"},
    {"text": "Believe it or not, humans actually emit a faint glow through natural bioluminescence! However, this light is approximately 1,000 times weaker than what the unaided human eye is capable of detecting.", "image": "human_glow.png"},
    {"text": "You experience a slight height change daily! You're typically taller just after waking up because the cartilage discs in your spine gradually compress under gravity throughout the day.", "image": "spine_compression.png"},
    {"text": "Fibrodysplasia Ossificans Progressiva, sometimes called 'Stone Man Syndrome,' is an extremely rare genetic condition where injured muscle and connective tissue gradually ossify, turning into solid bone over time.", "image": "stone_man_syndrome.png"}
]

# --- Jura Fakten Liste ---
LAW_FACTS = [
    {"text": "The word 'lawyer' comes from the Middle English 'lawe,' meaning 'that which is laid down,' highlighting how laws were seen as fixed foundations of society.", "image": "lawyer_etymology.png"},
    {"text": "The first-year law curriculum is notoriously intense; it’s designed less to teach content and more to train the mind to 'think like a lawyer.'", "image": "think_like_a_lawyer.png"},
    {"text": "Some students experience 'law school syndrome' — jokingly believing they have every legal condition they study, similar to medical student syndrome.", "image": "law_school_syndrome.png"},
    {"text": "Legal language, often mocked for being confusing, is intentionally precise, as small word choices can completely change a statute's interpretation.", "image": "legal_language_precision.png"},
    {"text": "The scales of justice, a symbol recognized globally, date back to ancient Egypt, representing the weighing of truth and fairness before the gods.", "image": "scales_of_justice.png"},
    {"text": "The adversarial system, where two sides argue before a neutral judge, is based on the belief that truth emerges from conflict, not harmony.", "image": "adversarial_system.png"},
    {"text": "In legal philosophy, a core debate exists between natural law (law based on morality) and legal positivism (law based on human-made rules).", "image": "natural_law_positivism.png"},
    {"text": "The phrase 'ignorance of the law is no excuse' exists in most legal systems, even though no one can possibly know all the laws that apply to them.", "image": "ignorance_no_excuse.png"},
    {"text": "Many of the world’s influential legal systems, from civil law to common law, ultimately trace their roots back to Roman law.", "image": "roman_law_roots.png"},
    {"text": "The Latin phrases still used in modern law—like habeas corpus or mens rea—survive from medieval times, when Latin was the universal language of educated discourse.", "image": "latin_in_law.png"},
    {"text": "The first recorded 'law school' dates back to ancient Rome around 450 BCE, when the Twelve Tables were taught as the foundation of Roman law.", "image": "roman_law_school.png"},
    {"text": "Most legal disputes never reach a courtroom; the vast majority are settled privately through negotiation or mediation.", "image": "private_settlement.png"},
    {"text": "There’s a famous saying in legal circles: 'Hard cases make bad law,' meaning emotionally charged cases often lead to poor general rules.", "image": "hard_cases_bad_law.png"},
    {"text": "In France, it is illegal to name a pig 'Napoleon' out of respect for the famous emperor.", "image": "napoleon_pig_law.png"},
    {"text": "In Samoa, it’s illegal to forget your wife’s birthday—a law meant to protect marital harmony.", "image": "samoa_birthday_law.png"},
    {"text": "The United States has more lawyers than any other country—roughly 1.3 million—which means about one lawyer for every 240 people.", "image": "usa_lawyer_count.png"},
    {"text": "In ancient Greece, lawyers didn’t exist; citizens had to represent themselves in court, though they could hire speechwriters to craft their arguments.", "image": "ancient_greece_law.png"},
    {"text": "International law technically lacks a global 'police force'; compliance depends largely on mutual agreement and political pressure.", "image": "international_law.png"},
    {"text": "Lawyers are sometimes called 'professional pessimists,' as their job is to imagine every possible way something could go wrong to protect their clients.", "image": "professional_pessimist.png"},
    {"text": "The correct answer to almost any complex legal question is: 'It depends.'", "image": "it_depends.png"},
    {"text": "Many famous revolutions, from the American to the French, began not with weapons but with legal arguments about rights and legitimacy.", "image": "legal_revolutions.png"},
    {"text": "The phrase 'law and order' is misleading—in reality, law often creates conflict before it restores order, since every rule can be challenged or reinterpreted.", "image": "law_conflict_order.png"},
    {"text": "Law students often spend more time reading cases than attending lectures—a single case can run dozens of pages, filled with historical reasoning.", "image": "case_law_reading.png"},
    {"text": "In South Korea, law students may study for up to 20 hours a day before bar exams, preparing for years before even sitting the test.", "image": "south_korea_bar_exam.png"},
    {"text": "The shortest U.S. Supreme Court decision ever written contained only one word: 'Affirmed.' It meant the lower court’s decision stood.", "image": "shortest_scotus_decision.png"},
    {"text": "In China, law students must study Marxist legal theory as part of their curriculum, as it is a foundation for the country's legal philosophy.", "image": "china_marxist_law.png"}
]

# --- Allgemeine Fakten Liste ---
GENERAL_FACTS = [
    {"text": "If you could remove all the empty space inside atoms, the entire human race would fit into a sugar cube.", "image": "sugar_cube_humanity.png"},
    {"text": "Sloths can hold their breath longer than dolphins — up to 40 minutes — by slowing their heart rate.", "image": "sloth_breath.png"},
    {"text": "The average cloud weighs around one million pounds, but floats because the air below it is even heavier.", "image": "cloud_weight.png"},
    {"text": "There are more trees on Earth than stars in the Milky Way — roughly three trillion versus 100–400 billion.", "image": "trees_vs_stars.png"},
    {"text": "A single strand of spider silk, if scaled up to the thickness of a pencil, could stop a passenger plane in flight.", "image": "spider_silk_plane.png"},
    {"text": "In Antarctica, there’s a waterfall that runs red as blood — it’s actually caused by oxidized iron in saltwater.", "image": "blood_falls_antarctica.png"},
    {"text": "Time passes slightly faster at your head than at your feet — thanks to Einstein’s theory of relativity and gravity’s effect on time.", "image": "time_relativity.png"},
    {"text": "Bananas are berries, but strawberries aren’t — botanically speaking.", "image": "banana_berry.png"},
    {"text": "Wombat poop is cube-shaped, so it doesn’t roll away and can be used to mark territory.", "image": "wombat_cube_poop.png"},
    {"text": "Octopuses have three hearts and blue blood; two hearts pump to the gills, one to the rest of the body.", "image": "octopus_hearts.png"},
    {"text": "Cleopatra lived closer in time to the invention of the iPhone than to the construction of the Great Pyramid.", "image": "cleopatra_iphone.png"},
    {"text": "There are more possible ways to shuffle a deck of cards than there are atoms on Earth.", "image": "card_shuffle.png"},
    {"text": "Sharks existed before trees did — by about 50 million years.", "image": "shark_before_trees.png"},
    {"text": "In theory, if you could fold a piece of paper 42 times, it would reach the Moon.", "image": "paper_fold_moon.png"},
    {"text": "The Eiffel Tower grows taller in summer; heat expands the metal by about 15 centimeters.", "image": "eiffel_tower_summer.png"},
    {"text": "Honey never spoils — archaeologists have found 3,000-year-old honey that’s still edible.", "image": "honey_never_spoils.png"},
    {"text": "A day on Venus is longer than a year on Venus — it rotates so slowly that it spins once per orbit.", "image": "venus_day_year.png"},
    {"text": "The fingerprints of koalas are so similar to humans’ that they’ve confused crime scene investigators.", "image": "koala_fingerprint.png"},
    {"text": "You can’t hum while holding your nose closed — try it, it’s impossible.", "image": "hum_nose.png"},
    {"text": "Some turtles can breathe through their rear ends during hibernation — it’s called cloacal respiration.", "image": "turtle_breathe_rear.png"},
    {"text": "There’s enough DNA in your body to stretch from the Sun to Pluto and back — 17 times.", "image": "dna_stretch.png"},
    {"text": "A teaspoon of neutron star material would weigh about six billion tons.", "image": "neutron_star_weight.png"},
    {"text": "The shortest war in history was between Britain and Zanzibar in 1896 — it lasted 38 minutes.", "image": "shortest_war.png"},
    {"text": "Cows have best friends and get stressed when they’re separated.", "image": "cow_friends.png"},
    {"text": "Space smells like seared steak — astronauts report the odor comes from dying stars and cosmic dust.", "image": "space_smell.png"}
]

# --- Countries / Sprachen Fakten Liste ---
COUNTRY_FACTS = [
    {"text": "Did you know? Papua New Guinea is the most linguistically diverse country on Earth. With over 800 indigenous languages, it houses roughly 12% of the world's languages despite its small population.", "image": "png_languages.png"},
    {"text": "A musical masterpiece: South Africa's national anthem is globally unique. Its lyrics seamlessly switch between five of the country's twelve official languages: Xhosa, Zulu, Sesotho, Afrikaans, and English.", "image": "south_africa_anthem.png"},
    {"text": "A touch of antiquity: Because Latin is the official language of the Catholic Church, Vatican City is the only country in the world offering ATMs with a Latin language interface.", "image": "vatican_atm_latin.png"},
    {"text": "A matter of perception: Historically, Japan used only one word ('ao') for both blue and green. Due to this linguistic quirk, Japanese traffic lights often illuminate in a distinct blue instead of green.", "image": "japan_blue_traffic_lights.png"},
    {"text": "A record holder for inclusion: Bolivia holds the world record for the most official languages. Alongside Spanish, the country's constitution recognizes a staggering 36 indigenous languages as completely equal.", "image": "bolivia_official_languages.png"},
    {"text": "A linguistic quirk: The Irish language (Gaeilge) has no direct words for 'yes' or 'no'. Instead, you answer by repeating the question's verb in either a positive or negative form.", "image": "irish_yes_no.png"},
    {"text": "An artificial alphabet: The Korean script, Hangul, didn't evolve naturally; it was invented in 1443. The letter shapes ingeniously mimic the anatomical positions of your tongue and lips when speaking.", "image": "hangul_invention.png"},
    {"text": "Whistling instead of speaking: On the Canary Island of La Gomera, locals communicate across vast valleys using 'Silbo Gomero'—a fully whistled version of Spanish that translates vowels and consonants into tones.", "image": "silbo_gomero_whistling.png"},
    {"text": "Absolute orientation: The Australian Aboriginal language Guugu Yimithirr lacks words for 'left' or 'right'. Speakers use only cardinal directions, giving them an incredibly precise internal compass from birth.", "image": "aboriginal_compass.png"},
    {"text": "Strict naming rules: In Iceland, you can't just pick any name for a child. A government Naming Committee strictly reviews new names to ensure they follow traditional Icelandic grammatical rules.", "image": "iceland_naming_committee.png"},
    {"text": "It's astounding: Mandarin Chinese doesn't use a standard alphabet, but rather thousands of individual characters. To fluently read a daily newspaper, you must memorize approximately 3,000 of these logograms.", "image": "chinese_characters.png"},
    {"text": "Historical irony: Despite being linguistic rivals today, French was actually the official language of the English royal court and nobility for nearly 300 years following the Norman Conquest in 1066.", "image": "french_english_court.png"},
    {"text": "Living in the present: The Finnish language completely lacks a grammatical future tense. Finns simply use the present tense for future events, relying entirely on conversational context to establish the timeframe.", "image": "finnish_no_future.png"},
    {"text": "Mind your punctuation: When writing a question in Greek, don't use a standard question mark. The official Greek question mark actually looks exactly like an English semicolon (;).", "image": "greek_question_mark.png"},
    {"text": "An absolute mystery: Euskara, spoken by the Basque people in Spain and France, is a language isolate. It has absolutely no known genealogical relationship to any other living language on Earth.", "image": "basque_language_isolate.png"},
    {"text": "A singing culture: In the Indian village of Kongthong, residents don't use regular names. Instead, every person is assigned a unique melody composed by their mother, which is whistled to call them.", "image": "india_whistling_village.png"},
    {"text": "A completely different worldview: The Pirahã people of the Brazilian Amazon speak a language entirely lacking words for exact numbers or specific colors, relying only on concepts like 'few' or 'many'.", "image": "piraha_numbers.png"},
    {"text": "A historical misunderstanding: The name 'Canada' stems from an explorer's mistake. He wrongly believed the Iroquoian word 'kanata'—which simply means 'village' or 'settlement'—was the specific name for the entire country.", "image": "canada_name_origin.png"},
    {"text": "A surprising greeting: The famous word 'Ciao', used today in Italian for both 'hello' and 'goodbye', originated in the Venetian dialect where it literally translated to 'I am your slave'.", "image": "ciao_etymology.png"},
    {"text": "Culture encoded in law: The Kingdom of Bhutan measures national success by 'Gross National Happiness' rather than GDP. This Buddhist-inspired concept is officially enshrined directly in the country's constitution.", "image": "bhutan_national_happiness.png"},
    {"text": "A cartographical tongue-twister: The Welsh village of 'Llanfairpwllgwyngyllgogerychwyrndrobwllllantysiliogogogoch' holds the record for Europe's longest place name. It meticulously describes the precise geographic location of the local parish church.", "image": "wales_long_name.png"},
    {"text": "A mark of inclusion: In 2006, New Zealand became the very first country in the world to make its national sign language (NZSL) an official state language, alongside English and Māori.", "image": "nz_sign_language.png"},
    {"text": "Unique in typography: The letter 'ß' (Eszett) exists exclusively in written German. Interestingly, it isn't even used in German-speaking Switzerland, where writers consistently use a double 'ss' instead.", "image": "german_eszett.png"},
    {"text": "No federal official language: Despite having the world's largest Spanish-speaking population, Spanish isn't Mexico's federal official language. Instead, 68 indigenous languages are recognized as co-equal national languages alongside it.", "image": "mexico_no_official_language.png"},
    {"text": "Linguistic distance: Despite being in Central Europe, Hungarian belongs to the Uralic language family. Distantly related to Finnish, it is completely incomprehensible to all of Hungary's direct geographical neighbors.", "image": "hungarian_uralic_language.png"}
]


# --- Hilfsfunktionen ---
def get_base_widget_style() -> str:
    return "background-color: var(--stat-bg); border-radius:12px; text-align: left;"

def get_widget_title_style(margin_bottom="8px") -> str:
    return f"font-size:1.1em; font-weight:bold; color: var(--text-color); margin:0 0 {margin_bottom} 0; text-align: left;"

def adjust_hex_color(hex_color: str, amount: int) -> str:
    hex_color = hex_color.lstrip('#')
    if not re.match(r'^[0-9a-fA-F]{6}$', hex_color): return f"#{hex_color}"
    try:
        rgb = list(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        new_rgb = [max(0, min(255, val + amount)) for val in rgb]
        return "#{:02x}{:02x}{:02x}".format(*new_rgb)
    except Exception as e:
        print(f"ERROR: Adjusting color '{hex_color}': {e}"); traceback.print_exc()
        return f"#{hex_color}"

def format_seconds(seconds: float) -> str:
    """Format seconds into human readable string for display."""
    seconds = int(seconds)
    if seconds < 60:
        return _("{} sec").format(seconds)
    minutes = seconds // 60
    if minutes < 60:
        return _("{} min").format(minutes)
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes == 0:
        return _("{} h").format(hours)
    else:
        return _("{} h {} min").format(hours, remaining_minutes)

# --- Widget generators ---

def generate_learning_plan_widget(plan_data: List[Dict]) -> str:
    base_style = get_base_widget_style()
    main_title_style = get_widget_title_style(margin_bottom="0")
    widget_title = _("Study Plan")
    try:
        today_str = date.today().strftime("%a %d.%m.%y")
        today_str = today_str[0].upper() + today_str[1:]
    except Exception:
        today_str = date.today().strftime("%Y-%m-%d")

    # Pre-compute translated labels so the long JS template stays readable
    # and every render picks up the current USER_LANG.
    label_done = _("Done")
    label_paused = _("Paused")
    label_pause = _("Pause")
    label_resume = _("Resume")
    label_reset = _("Reset")
    label_cancel = _("Cancel")
    label_timer_running = _("Timer is running")
    label_timer_paused = _("Timer is paused")
    label_subject_finished = _("Subject finished")
    label_modal_title = _("Study Plan Timer")
    # %s gets replaced in JS with the actual subject name at runtime.
    label_finished_tpl = _("Finished learning %s!")

    date_style = f"font-size: 0.95em; font-weight: bold; color: var(--plan-date-color); white-space: nowrap;"
    header_style = "display: flex; justify-content: space-between; align-items: center; padding: 15px 15px 10px 15px;"

    header_html = f'''<div style="{header_style}"><h5 style="{main_title_style}">{widget_title}</h5><span style="{date_style}">{today_str}</span></div>'''

    rows_html = ""

# Custom modal HTML for control buttons (pause, reset, etc.)
    modal_html = f'''
    <style>
        /* Wir nutzen divs statt buttons, um Ankis globale Hover-Regeln komplett zu umgehen */
        .ptm-btn {{
            border-radius: 5px;
            padding: 8px 12px;
            font-weight: bold;
            cursor: pointer;
            flex: 1;
            text-align: center;
            user-select: none; /* Verhindert das Markieren des Textes */
            box-sizing: border-box;
        }}

        /* Absolut statischer Cancel Button in Weiß */
        #ptm-btn-cancel {{
            background-color: white !important;
            color: black !important;
            border: 1px solid #ccc !important;
        }}
    </style>

    <!-- Komplett transparenter Hintergrund -->
    <div id="plan-timer-modal" style="display:none; position:fixed; z-index:10000; left:0; top:0; width:100%; height:100%; background:transparent; align-items:center; justify-content:center;">
        <div style="background-color:var(--stat-bg); border-radius:10px; padding:20px; width:300px; text-align:center; box-shadow: 0 4px 15px rgba(0,0,0,0.4); border: 1px solid var(--stat-border);">
            <h3 style="color:var(--text-color); margin-top:0; margin-bottom:10px; font-size:1.3em;">{label_modal_title}</h3>
            <p id="ptm-msg" style="color:var(--text-color); font-size:1.0em; margin-top:0; margin-bottom:20px;"></p>
            <div style="display:flex; justify-content:center; gap:10px;">
                <!-- divs statt buttons, damit Anki sie beim Hovern in Ruhe lässt -->
                <div id="ptm-btn1" class="ptm-btn"></div>
                <div id="ptm-btn2" class="ptm-btn"></div>
                <div id="ptm-btn-cancel" class="ptm-btn">{label_cancel}</div>
            </div>
        </div>
    </div>
    '''

    if not plan_data:
        no_plan_msg = _("No learning plan configured yet.")
        rows_html = f"<div style='padding: 0 15px 15px 15px;'><p style='font-size:0.9em; color: var(--text-color-light); margin: 0;'>{no_plan_msg}</p></div>"
    else:
        rows_container_style = "padding: 0 10px 10px 10px;"
        rows_content = ""

        js_timer_logic = f'''
        <script>
            (function() {{
                const DONE_COLOR = '{PLAN_ROW_DONE_COLOR}';
                const RUNNING_COLOR = '{_palette(is_night_mode)["blue_bright"]}';
                const PAUSED_COLOR = '{PLAN_ROW_PAUSED_COLOR}';
                const STORAGE_KEY = 'gamification_plus_plan_state';

                // Localized labels injected from Python at render time.
                const LBL_DONE = "{label_done}";
                const LBL_PAUSED = "{label_paused}";
                const LBL_TIMER_RUNNING = "{label_timer_running}";
                const LBL_TIMER_PAUSED = "{label_timer_paused}";
                const LBL_SUBJECT_FINISHED = "{label_subject_finished}";
                const LBL_PAUSE = "{label_pause}";
                const LBL_RESUME = "{label_resume}";
                const LBL_RESET = "{label_reset}";
                const FINISHED_TPL = "{label_finished_tpl}";

                function getState() {{
                    try {{
                        return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}');
                    }} catch (e) {{ return {{}}; }}
                }}

                function saveState(state) {{
                    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
                }}

                function formatTime(totalSeconds) {{
                    if (totalSeconds <= 0) return LBL_DONE;
                    const h = Math.floor(totalSeconds / 3600);
                    const m = Math.floor((totalSeconds % 3600) / 60);
                    const s = totalSeconds % 60;

                    if (h > 0) return h + "h " + (m < 10 ? "0" + m : m) + "m " + (s < 10 ? "0" + s : s) + "s";
                    return m + "m " + (s < 10 ? "0" + s : s) + "s";
                }}

                function showCustomModal(msg, btn1Text, btn1Color, btn1Cb, btn2Text, btn2Color, btn2Cb) {{
                    const modal = document.getElementById('plan-timer-modal');
                    document.getElementById('ptm-msg').textContent = msg;

                    const btn1 = document.getElementById('ptm-btn1');
                    const btn2 = document.getElementById('ptm-btn2');
                    const cancel = document.getElementById('ptm-btn-cancel');

                    // Klonen, um alte Event-Listener sauber zu entfernen
                    const newBtn1 = btn1.cloneNode(true);
                    btn1.parentNode.replaceChild(newBtn1, btn1);
                    const newBtn2 = btn2.cloneNode(true);
                    btn2.parentNode.replaceChild(newBtn2, btn2);
                    const newCancel = cancel.cloneNode(true);
                    cancel.parentNode.replaceChild(newCancel, cancel);

                    if (btn1Text) {{
                        newBtn1.style.display = 'block';
                        newBtn1.textContent = btn1Text;
                        newBtn1.style.backgroundColor = btn1Color;
                        newBtn1.style.color = 'white';
                        newBtn1.style.border = 'none';
                        newBtn1.onclick = () => {{ modal.style.display = 'none'; btn1Cb(); }};
                    }} else {{ newBtn1.style.display = 'none'; }}

                    if (btn2Text) {{
                        newBtn2.style.display = 'block';
                        newBtn2.textContent = btn2Text;
                        newBtn2.style.backgroundColor = btn2Color;
                        newBtn2.style.color = 'white';
                        newBtn2.style.border = 'none';
                        newBtn2.onclick = () => {{ modal.style.display = 'none'; btn2Cb(); }};
                    }} else {{ newBtn2.style.display = 'none'; }}

                    newCancel.onclick = () => {{ modal.style.display = 'none'; }};
                    modal.style.display = 'flex';
                }}

                window.handlePlanClick = function(element) {{
                    const subject = element.dataset.subject;
                    const duration = parseInt(element.dataset.seconds);
                    const state = getState();
                    const now = Date.now();
                    const todayKey = new Date().toDateString();
                    const key = subject + "_" + todayKey;

                    if (!state[key]) state[key] = {{ status: 'idle', elapsedTime: 0 }};

                    const actionPause = () => {{
                        state[key].status = 'paused';
                        const elapsedSinceStart = (Date.now() - state[key].startTime) / 1000;
                        state[key].elapsedTime = (state[key].elapsedTime || 0) + elapsedSinceStart;
                        saveState(state);
                        renderRow(element, state[key], duration, element.dataset.originalBg);
                    }};

                    const actionReset = () => {{
                        state[key].status = 'idle';
                        state[key].elapsedTime = 0;
                        delete state[key].startTime;
                        saveState(state);
                        renderRow(element, state[key], duration, element.dataset.originalBg);
                    }};

                    const actionResume = () => {{
                        state[key].status = 'running';
                        state[key].startTime = Date.now();
                        saveState(state);
                        updateTimers();
                    }};

                    if (state[key].status === 'running') {{
                        // Pause ist Orange (PAUSED_COLOR), Reset ist Blau (#0071D3)
                        showCustomModal(LBL_TIMER_RUNNING, LBL_PAUSE, PAUSED_COLOR, actionPause, LBL_RESET, '{_palette(is_night_mode)["blue"]}', actionReset);
                    }} else if (state[key].status === 'paused') {{
                        // Resume ist Grün (RUNNING_COLOR), Reset ist Blau (#0071D3)
                        showCustomModal(LBL_TIMER_PAUSED, LBL_RESUME, RUNNING_COLOR, actionResume, LBL_RESET, '{_palette(is_night_mode)["blue"]}', actionReset);
                    }} else if (state[key].status === 'done') {{
                        showCustomModal(LBL_SUBJECT_FINISHED, LBL_RESET, '{_palette(is_night_mode)["blue"]}', actionReset, null, null, null);
                    }} else {{
                        state[key].status = 'running';
                        state[key].startTime = now;
                        state[key].duration = duration;
                        if (!state[key].elapsedTime) state[key].elapsedTime = 0;
                        saveState(state);
                        updateTimers();
                    }}
                }};

                function renderRow(el, itemState, originalDuration, originalBg) {{
                    const timeSpan = el.querySelector('.time-display');

                    if (!itemState || itemState.status === 'idle') {{
                        el.style.backgroundColor = originalBg;
                        timeSpan.textContent = el.dataset.initialText;
                        return;
                    }}

                    if (itemState.status === 'done') {{
                        el.style.backgroundColor = DONE_COLOR;
                        timeSpan.textContent = LBL_DONE;
                        return;
                    }}

                    if (itemState.status === 'paused') {{
                        el.style.backgroundColor = PAUSED_COLOR;
                        const totalElapsed = (itemState.elapsedTime || 0);
                        const remaining = originalDuration - totalElapsed;
                        timeSpan.textContent = formatTime(Math.max(0, Math.floor(remaining))) + " (" + LBL_PAUSED + ")";
                        return;
                    }}

                    if (itemState.status === 'running') {{
                        el.style.backgroundColor = RUNNING_COLOR;
                        const elapsedSinceStart = (Date.now() - itemState.startTime) / 1000;
                        const totalElapsed = (itemState.elapsedTime || 0) + elapsedSinceStart;
                        const remaining = originalDuration - totalElapsed;

                        if (remaining <= 0) {{
                            itemState.status = 'done';
                            const subject = el.dataset.subject;
                            const todayKey = new Date().toDateString();
                            const key = subject + "_" + todayKey;

                            let globalState = getState();
                            globalState[key] = itemState;
                            saveState(globalState);

                            el.style.backgroundColor = DONE_COLOR;
                            timeSpan.textContent = LBL_DONE;

                            if (window.pycmd) {{
                                window.pycmd("tooltip:" + FINISHED_TPL.replace("%s", subject));
                            }}
                        }} else {{
                            timeSpan.textContent = formatTime(Math.floor(remaining));
                        }}
                    }}
                }}

                function updateTimers() {{
                    const rows = document.querySelectorAll('.plan-row-item');
                    const state = getState();
                    const todayKey = new Date().toDateString();

                    rows.forEach(row => {{
                        const subject = row.dataset.subject;
                        const key = subject + "_" + todayKey;
                        const duration = parseInt(row.dataset.seconds);

                        renderRow(row, state[key], duration, row.dataset.originalBg);
                    }});
                }}

                setInterval(updateTimers, 1000);
                setTimeout(updateTimers, 100);
            }})();
        </script>
        '''

        rows_content += js_timer_logic

        for i, item in enumerate(plan_data):
            subject = item.get('subject', _('Unknown Subject'))
            target_seconds = item.get('target_seconds', 0)

            adjusted_bg_color = adjust_hex_color(_palette(is_night_mode)["blue"], i * PLAN_COLOR_ADJUST_STEP)

            time_display_text = format_seconds(target_seconds)

            row_padding = "8px 12px"; row_margin_bottom = "6px"
            row_id = f"lp-item-{i}"

            current_row_style = f"background-color:{adjusted_bg_color}; color:{PLAN_TEXT_COLOR}; border-radius:8px; padding: {row_padding}; margin-bottom:{row_margin_bottom}; display:flex; justify-content:space-between; align-items:center; font-size: 0.95em; font-weight: 500; cursor: pointer; transition: background-color 0.2s ease;"

            if i == len(plan_data) - 1:
                current_row_style = current_row_style.replace(f"margin-bottom:{row_margin_bottom};", "")

            onclick_handler = "handlePlanClick(this)"
            data_attributes = f'data-subject="{subject}" data-seconds="{target_seconds}" data-original-bg="{adjusted_bg_color}" data-initial-text="{time_display_text}"'

            rows_content += f'''
            <div id="{row_id}" class="plan-row-item" style="{current_row_style}" {data_attributes} onclick="{onclick_handler}">
                <span style="flex-grow: 1; margin-right: 10px; pointer-events: none;">{subject}</span>
                <span class="time-display" style="font-weight:bold; white-space: nowrap; pointer-events: none;">{time_display_text}</span>
            </div>
            '''

        rows_html = f'<div style="{rows_container_style}">{rows_content}{modal_html}</div>'

    widget_style = f"{base_style} flex: {PLAN_WIDGET_FLEX_GROW} {PLAN_WIDGET_FLEX_SHRINK} {PLAN_WIDGET_FLEX_BASIS}; max-width: {PLAN_WIDGET_MAX_WIDTH}; min-width: 200px; min-height: 100px; display: flex; flex-direction: column; justify-content: flex-start;"
    widget_html = f'''<div class="daily-widget plan-widget" style="{widget_style}">{header_html}{rows_html}</div>'''
    return widget_html

def generate_fact_widget(fact_theme: str = "Medical") -> str:
    """Generiert das HTML für das Fakten-Widget basierend auf dem gewählten Thema."""
    global _debug_day_offset

    if fact_theme == "Law":
        active_facts = LAW_FACTS
        fact_title = _("Daily Legal Fact")
    elif fact_theme == "General":
        active_facts = GENERAL_FACTS
        fact_title = _("Daily General Fact")
    elif fact_theme == "Countries":
        active_facts = COUNTRY_FACTS
        fact_title = _("Daily Country Fact")
    else:
        active_facts = MEDICAL_FACTS
        fact_title = _("Daily Medical Fact")

    base_style = get_base_widget_style()
    title_style = get_widget_title_style(margin_bottom="8px")
    text_style = "font-size:0.9em; color: var(--text-color); margin:0; line-height:1.4; text-align: left;"
    img_style = "max-width: 130px; max-height: 90px; border-radius: 8px; object-fit: cover; flex-shrink: 0; display: block;"

    fact_text = _("No daily facts available.")
    image_filename = None

    if active_facts:
        try:
            num_facts = len(active_facts)
            day_of_year = date.today().timetuple().tm_yday
            effective_day = day_of_year + _debug_day_offset
            fact_index = (effective_day - 1) % num_facts
            selected_fact = active_facts[fact_index]
            # Translate the fact text on read. Wrapping the dict literals
            # with _() would freeze translations at module-import time; this
            # read-site call ensures live language switches work correctly.
            raw_text = selected_fact.get("text", "")
            fact_text = _(raw_text) if raw_text else _("Fact text missing.")
            image_filename = selected_fact.get("image")
        except Exception as e:
            print(f"ERROR selecting daily fact: {e}"); traceback.print_exc()
            fact_text = _("Error loading daily fact."); image_filename = None
    else:
        print(f"WARNING: {fact_theme.upper()}_FACTS list is empty.")

    # Localized SVG placeholder labels (created at render time so they pick
    # up the current language).
    def _svg_placeholder(bg: str, fg: str, label: str) -> str:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="130" height="90" viewBox="0 0 130 90">'
            f'<rect width="130" height="90" fill="{bg}"/>'
            f'<text x="50%" y="50%" fill="{fg}" dy=".3em" font-size="14" text-anchor="middle">{label}</text>'
            f'</svg>'
        )
        return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("utf-8")

    image_src_base64 = ""
    if image_filename:
        try:
            addon_package_name = None; addon_dir = None
            if mw and hasattr(mw, 'addonManager'):
                addon_manager = mw.addonManager
                addon_package_name = addon_manager.addonFromModule(__name__)
                if addon_package_name: addon_dir = os.path.join(addon_manager.addonsFolder(), addon_package_name)
            if not addon_dir:
                try: addon_dir = os.path.dirname(__file__)
                except Exception as e_path: print(f"ERROR (Fact Img): Fallback path failed: {e_path}"); addon_dir = None
            if addon_dir:
                image_filesystem_path = os.path.join(addon_dir, FACT_IMAGE_SUBFOLDER, image_filename)
                if os.path.exists(image_filesystem_path):
                    with open(image_filesystem_path, "rb") as image_file:
                        image_src_base64 = f"data:{IMAGE_MIME_TYPE};base64,{base64.b64encode(image_file.read()).decode('utf-8')}"
                else:
                    image_src_base64 = _svg_placeholder("#ddd", "#888", _("Missing"))
            else:
                image_src_base64 = _svg_placeholder("#ccc", "#555", _("Error"))
        except Exception as e:
            print(f"CRITICAL ERROR (Base64): Image loading failed: {e}"); traceback.print_exc()
            image_src_base64 = _svg_placeholder("#ccc", "#555", _("Load Error"))
    else:
        image_src_base64 = _svg_placeholder("#eee", "#aaa", _("No Image"))

    alt_text = _("Fact Image")

    widget_inner_style = "padding: 15px; display:flex; gap: 15px; align-items: flex-start; width: 100%; box-sizing: border-box;"
    widget_outer_style = f"{base_style} flex: {FACT_WIDGET_FLEX_GROW} {FACT_WIDGET_FLEX_SHRINK} {FACT_WIDGET_FLEX_BASIS}; max-width: {FACT_WIDGET_MAX_WIDTH}; min-width: 300px; min-height: 100px;"
    widget_html = f'''
    <div class="daily-widget fact-widget" style="{widget_outer_style}">
      <div style="{widget_inner_style}">
        <div style="flex: 1; text-align: left;">
            <h5 style="{title_style}">{fact_title}</h5>
            <p style="{text_style}">{fact_text}</p>
        </div>
        <img src="{image_src_base64}" style="{img_style}" alt="{alt_text}">
      </div>
    </div>
    '''
    return widget_html

# --- Entry point ---
def generate_daily_widgets_html(learning_plan_data: List[Dict], fact_theme: str) -> str:
    _cl = _palette(False)
    _cd = _palette(True)
    css_styles = f"""
    <style>
        :root {{
            --stat-bg: {_cl["surface"]};
            --stat-border: {_cl["grey_light"]};
            --text-color: {_cl["text"]};
            --text-color-light: {_cl["text_muted"]};
            --plan-date-color: {_cl["blue"]};
        }}
        .daily-widget {{
            border: 1px solid var(--stat-border);
        }}
        body.night_mode {{
            --stat-bg: {_cd["surface"]};
            --stat-border: {_cd["grey_mid"]};
            --text-color: {_cd["text"]};
            --text-color-light: {_cd["text_muted"]};
            --plan-date-color: {_cd["blue_bright"]};
        }}
        body.night_mode .daily-widget {{
            border: 1px solid {_cd["grey_mid"]} !important;
        }}
    </style>
    """

    plan_widget_html = ""; fact_widget_html = ""
    try: plan_widget_html = generate_learning_plan_widget(learning_plan_data)
    except Exception as e: print(f"ERROR generating plan widget: {e}"); traceback.print_exc(); plan_widget_html = "<!-- Error -->"
    try: fact_widget_html = generate_fact_widget(fact_theme)
    except Exception as e: print(f"ERROR generating fact widget: {e}"); traceback.print_exc(); fact_widget_html = "<!-- Error -->"

    container_style = f"""
        display: flex; align-items: flex-start; flex-wrap: wrap;
        gap: {DAILY_WIDGETS_GAP}; max-width: {DAILY_WIDGETS_MAX_WIDTH};
        margin: 0 auto {DAILY_WIDGETS_MARGIN_BOTTOM} auto;
        padding: 0 10px; box-sizing: border-box;
    """
    container_html = f'''<div id="daily-widgets-container" style="{container_style}">{plan_widget_html}{fact_widget_html}</div>'''

    return css_styles + container_html
