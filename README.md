# SynapsePro for Anki

SynapsePro is a desktop-only Anki add-on that combines study planning,
gamification, statistics, a notebook/PDF workspace, mind maps, focus tools,
music, a web sidebar, and an optional multi-provider AI assistant.

Website: <https://www.synapse-pro.de>  
Support: <help.synapse.pro@gmail.com>

## Requirements

- Anki Desktop 25.09.4 or newer
- Windows, macOS, or Linux with Anki's bundled Qt 6 WebEngine
- An internet connection only for features that deliberately access an online
  service, such as the web sidebar, SoundCloud, or a cloud AI provider

AnkiMobile and AnkiDroid do not load desktop add-ons.

## Installation

### AnkiWeb

1. In Anki Desktop, open **Tools → Add-ons → Get Add-ons**.
2. Enter the SynapsePro add-on code shown on its AnkiWeb page.
3. Restart Anki.

### Local folder installation

1. Quit Anki completely.
2. Copy the `SynapseProClaude` folder into Anki's `addons21` directory.
3. Start Anki again.

SynapsePro is developed and tested directly as an add-on folder. Changes to a
separate source copy only become active after that folder has been copied into
`addons21` and Anki has been restarted.

## Main features

- Configurable launcher sidebar and keyboard shortcuts
- XP, ranks, streaks, measurable daily challenges, and review statistics
- Daily study plan, countdown timers, deadlines, and Pomodoro sessions
- Notebook, task list, offline PDF.js viewer, and mind maps
- Local music plus optional SoundCloud playback
- Optional website sidebar and selected-text web search
- Optional AI assistant for OpenAI, Gemini, Anthropic, OpenRouter, Ollama, and
  llama.cpp-compatible servers
- Light/dark mode, multiple color themes, and multilingual interface strings

## Privacy and network access

After the onboarding privacy notice is accepted, SynapsePro sends the selected
setup categories and version numbers once to its Supabase database. Opening
Settings loads the SynapsePro news banner from `www.synapse-pro.de`. API keys are stored in the current Anki profile's
local `SynapsePro_Data/ai_secrets.json` file, not in collection configuration
that can sync to AnkiWeb.

Online features send data only when used: AI prompts go directly to the chosen
provider; optional card context includes the visible card text; the website
sidebar loads the pages you open; SoundCloud mode contacts SoundCloud. See
[PRIVACY.md](PRIVACY.md) for the complete data and network behavior.

AI output and the bundled daily facts can be wrong. They are study aids, not
medical, legal, or other professional advice.

## Reporting problems

Please include your Anki version, operating system, SynapsePro version, steps
to reproduce, and the relevant lines from **Help → About → Copy Debug Info**.
Do not include API keys, private card content, or personal URLs.

- Email: <help.synapse.pro@gmail.com>
- GitHub issues: <https://github.com/mobesamedia/SynapsePro/issues>

## Development and release verification

Run the static release gate:

```bash
python3 scripts/release_check.py
```

The check validates metadata, JSON, Python and inline JavaScript syntax,
required assets, forbidden runtime/private files, remote script allowlisting,
and archive root layout. It does not replace testing inside real Anki builds;
follow [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) before publishing.

## License

Source code is licensed under the MIT License. SynapsePro branding, images,
animations, and audio are excluded and remain All Rights Reserved by
MobesaMedia; see [LICENSE](LICENSE). Bundled library licenses are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
