# Frigate-Vision
---
<sup>**Credit where it's due!** This blueprint was inspired by and builds on the work of @SgtBatten's [Frigate Notification Blueprint](https://community.home-assistant.io/t/frigate-mobile-app-notifications-2-0/559732) and @valentinfrlch's [LLMVision Blueprint](https://llmvision.gitbook.io/getting-started/setup/blueprint). If anyone has an issue with content or code, please reach out.</sup>

**Frigate Vision** brings intelligent, AI-powered notifications to your Home Assistant setup — combining real-time Frigate detections with snapshot analysis via Home Assistant's native `ai_task` integration.

---

**📄 Import the Blueprint:**

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fzacharyd3%2FFrigate-Vision%2Fblob%2Fmain%2Ffrigate_vision.yaml)

---

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/zacharyd3)

---

## 💡 What Frigate Vision Does

- **🚨 Listens for Frigate detection events** from any camera via MQTT
- **🧠 Analyses snapshots with AI** using Home Assistant's `ai_task` domain — works with Ollama, OpenAI, Google, and any other provider you have configured
- **📸 Optional multi-frame collage** — extracts 4 labelled frames from the event clip and feeds them to the AI for richer temporal context
- **🕒 Per-camera cooldowns** to prevent notification spam
- **📱 Instant + enriched notifications** — a fast initial push fires immediately, then a second enriched notification follows once AI analysis is complete
- **🔔 Multi-device support** — send to one or more phones/tablets simultaneously
- **🧩 Input Boolean helper** for queuing AI jobs across multiple cameras without conflicts
- **📊 MQTT detection history** — publishes a rolling JSON history to a retained topic for use in a Lovelace dashboard card
- **🐛 Debug mode** for inspecting all variables and logic without sending notifications

---

## ⚙️ Requirements

- [Frigate](https://docs.frigate.video/integrations/home-assistant/) installed with MQTT events enabled
- An `ai_task` entity configured in Home Assistant (e.g. via the [Ollama](https://www.home-assistant.io/integrations/ollama/), [OpenAI](https://www.home-assistant.io/integrations/openai_conversation/), or [Google Generative AI](https://www.home-assistant.io/integrations/google_generative_ai_conversation/) integrations)
- Home Assistant Companion app installed on your phone(s)
- An `input_boolean` helper for multi-camera AI job queuing
- The shell commands below added to your `configuration.yaml`

---

## 🛠️ Required Setup: Shell Commands

FrigateVision uses two shell commands to prepare images for AI analysis. Add the following to your `configuration.yaml` and restart Home Assistant:

```yaml
shell_command:
  download_frigate_snapshot: >
    curl -s -o "/config/www/frigate/frigate_event_{{ camera }}_{{ id }}.jpg"
    "{{ snapshot_url }}"
  frigate_build_collage: >-
    /config/scripts/frigate_collage.sh
    "{{ clip_url }}"
    "{{ event_id }}"
    "{{ camera }}"
```

Then copy the scripts to `/config/scripts/` and make them executable:

```bash
chmod +x /config/scripts/frigate_collage.sh
chmod +x /config/scripts/extract_frigate_frames.sh
```

> **Note:** `frigate_build_collage` requires **ffmpeg** inside your HA environment. It is included by default on Home Assistant OS and most container installs. If it's missing, install the [ffmpeg add-on](https://github.com/home-assistant/addons/tree/master/ffmpeg).

### What the scripts do

| Script | Purpose |
|---|---|
| `frigate_collage.sh` | Downloads the event clip, extracts 4 frames at 10/35/60/90% through the clip, stamps each with camera name and timestamp, and assembles a 2×2 collage for AI analysis |
| `extract_frigate_frames.sh` | Lightweight alternative — extracts 3 frames directly from the remote clip URL without downloading it first. No collage is built; useful for custom workflows |

The snapshot download command (`download_frigate_snapshot`) is always required. The collage script is only called when **Use Multi-Frame Collage** is enabled in the blueprint.

---

## 🧠 AI Analysis

FrigateVision uses Home Assistant's native `ai_task.generate_data` action, which means it works with **any AI provider** you have set up as a conversation agent — Ollama (local), OpenAI, Google Gemini, Anthropic, and more.

Select your `ai_task` entity in the **AI Analysis** section of the blueprint, and optionally customise the prompt.

### Multi-Frame Collage (optional)

Enable **Use Multi-Frame Collage** in the AI Analysis section to send the AI a 2×2 grid of frames from the event clip instead of a single snapshot. This gives the model visibility into how the event unfolded over time, which can improve summary quality for longer events.

Requires `frigate_collage.sh` to be installed and `frigate_build_collage` to be defined in `shell_command` (see setup above).

---

## 📊 MQTT Detection History

After each event, FrigateVision publishes a structured JSON array to a retained MQTT topic. This powers a Lovelace card that shows a scrollable detection feed with thumbnails, AI summaries, and clip links.

Add the following to your `configuration.yaml` to create the sensor that reads the history back into Home Assistant:

```yaml
mqtt:
  sensor:
    - name: "Frigate Vision History"
      unique_id: frigate_vision_history
      state_topic: frigate/vision/history
      value_template: "{{ value_json | length }} detections"
      json_attributes_topic: frigate/vision/history
      json_attributes_template: >
        {"history": {{ value_json | to_json }}}
```

Then select `sensor.frigate_vision_history` as the **MQTT History Sensor Entity** in the blueprint.

---

## 📋 Blueprint Options

| Section | Option | Description |
|---|---|---|
| — | Camera | Frigate camera entity to monitor |
| — | Labels | Object types to notify on (person, dog, car, etc.) |
| — | Helper | `input_boolean` for AI job queuing |
| — | Cooldown | Minimum time between notifications |
| — | Mobile Device(s) | One or more devices to notify |
| Notification | iOS Notification | Enable iOS-specific notification features |
| Notification | Append / Expand | Camera name formatting options |
| Notification | Notification Image | Thumbnail (1:1 crop) or Snapshot (full frame) |
| Notification | Timeout | Android notification auto-dismiss time |
| Notification | Dashboard URI | URI opened by the "View Summary" action |
| AI Analysis | AI Task Entity | Your `ai_task` entity |
| AI Analysis | Prompt | Custom prompt sent with each snapshot |
| AI Analysis | Use Multi-Frame Collage | Feed a 4-frame collage to the AI instead of a single snapshot |
| MQTT History | Topic | Retained MQTT topic for detection history |
| MQTT History | History Limit | Max records to keep (1–50) |
| MQTT History | History Sensor | The `sensor` entity reading the history topic |
| Advanced | Include Sublabels | Include Frigate sublabels in AI context |
| Advanced | HA URL / Port | Your Home Assistant base URL |
| Advanced | Frigate URL / Port | Your Frigate base URL |
| Advanced | Debug Logging | Log all variables to the logbook |

---

## 🗂️ Repository Structure

```
frigate_vision.yaml          # The blueprint — import this into Home Assistant
scripts/
  frigate_collage.sh         # Builds a 2×2 multi-frame collage from a Frigate clip
  extract_frigate_frames.sh  # Extracts 3 individual frames (lightweight alternative)
```

---

I'd love your feedback, ideas, and bug reports (via GitHub Issues please). If you're using it and enjoying it, drop a comment or a ⭐ — let's make Frigate Vision even smarter!
