# Frigate-Vision
---
<sup>**Firstly, credit where credit is due!** A lot of this automation was inspired and even copied from @SgtBatten's [Frigate notification Blueprint](https://community.home-assistant.io/t/frigate-mobile-app-notifications-2-0/559732). Earlier versions also borrowed from @valentinfrlch's [LLMVision Blueprint](https://llmvision.gitbook.io/getting-started/setup/blueprint). If anyone has an issue with content or code, please reach out.</sup>

[After sharing a screenshot](https://www.reddit.com/r/homeassistant/comments/1lohkx9/my_take_on_a_frigatellm_vision_notification/) of one of my Frigate automations the other day, a few of you asked if I had a blueprint. At the time I didn’t… so I sat down, taught myself how to build one and here it is!

Introducing **Frigate Vision**: a blueprint that gives you Frigate notifications you can read at a glance. It waits for the whole activity to finish, then updates the notification with an animated GIF of the entire event.

> **v2 is a rewrite.** Frigate now has built-in AI (GenAI review summaries, face recognition and LPR), so Frigate Vision no longer uses LLMVision. It now focuses on the notification itself. If you're upgrading, re-create your automation from the blueprint, because the inputs have changed.

---

**📄 Get the Blueprint:**

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fzacharyd3%2FFrigate-Vision%2Fblob%2Fmain%2Ffrigate_vision.yaml)

---
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/zacharyd3)
#### 💡 How it works

1. **🚨 Review starts.** Frigate publishes a new review item (alert or detection) on `frigate/reviews`. You immediately get a notification with the object's thumbnail. You can turn this off if you only want the GIF.
2. **🏷️ While it's happening:** if Frigate recognizes someone (face recognition) or spots more objects, the same notification updates silently, e.g. *"Zach detected"*.
3. **🎞️ Review ends.** The blueprint waits for Frigate to close the review, then swaps the image for an **animated GIF covering the whole review** (sped up, like Frigate's review timeline previews) and adds the duration, e.g. *"Back Door Cam (0:42)"*.
4. **🧠 Frigate GenAI (optional).** If you've enabled [GenAI review summaries](https://docs.frigate.video/configuration/genai/review_summaries) in Frigate 0.17+, the notification updates once more. With *Notification Title* set to *Advanced* (the default), Frigate's title becomes the notification title (with ⚠️/🚨 if Frigate rates it as a potential threat), and with *Notification Text* set to *Advanced* (the default) its one-line short summary becomes the message.
5. **📖 Want the details?** Tap the **Summary** button. The notification is replaced with Frigate's full scene description and observations, shown as plain text so it fits in the notification shade.

Every update replaces the same notification, and only the first one makes a sound.

#### ✨ Features

* **Multiple cameras**: each review gets its own run, so simultaneous activity on different cameras produces separate notifications
* **Filters** for review severity (alert/detection), labels and zones. A review that later upgrades to an alert or enters a zone still triggers, and a review that was in a zone at any point counts.
* **Recognized names for people only**: names from face recognition are shown, while names Frigate gives other objects (like known license plates on cars) are left out
* **Cooldown** between new notifications
* **Multiple notification devices**, grouped and channelled per camera, so the camera name shows in the notification group
* **Notification title and text, set separately**: title *Basic* (camera name), *Advanced* (Frigate's GenAI title) or *None*; text *Basic* (e.g. *"Zach was detected"*), *Advanced* (Frigate's GenAI short summary) or *None*. Mix them, e.g. the camera name as the title with the GenAI summary as the text, or set both to *None* for the biggest image
* **Actions**: *Summary* (full GenAI description), *View Clip* (through Home Assistant) and *Open in Frigate* (links straight to the review)
* **History dashboard** for your phone: every event's GIF and GenAI summary, filterable by camera and type (see [History Dashboard](#-history-dashboard))

---

### ⚙️ Requirements:

* Home Assistant **2025.4** or newer
* [Frigate](https://docs.frigate.video/) with MQTT enabled, and the [Frigate integration](https://docs.frigate.video/integrations/home-assistant/) with the notification proxy enabled (it's on by default)
* Frigate **previews** enabled (the default). The GIF is built from them.
* Home Assistant mobile app. Animated GIFs play in the notification shade on **iOS** and **Android 14+**. Older Android versions show the first frame.
* *(Optional)* Frigate 0.17+ with GenAI review summaries enabled, for AI titles and summaries

---

### 🛠️ Tips

* **Severity**: Frigate decides what counts as an *alert* (`review -> alerts -> labels / required_zones` in your Frigate config). Tuning that in Frigate is usually cleaner than filtering in the blueprint.
* **GIF delay**: Frigate pads the review GIF with about 8s after the activity ends. The default 10s delay makes sure the whole clip is included.
* **Per-camera cooldowns**: the cooldown applies to the whole automation. Create one automation per camera if you want each camera to cool down on its own.
* **Taller image on Android**: Android gives an expanded notification a fixed height, and the image gets whatever the text and buttons leave, so tall (hallway-mode) cameras get cropped. Set both *Notification Title* and *Notification Text* to *None* and remove *Action Buttons* you don't need to give the image as much room as possible. Tapping the notification still opens the review in Frigate, where the GenAI summary is shown.
* **Custom topic prefix**: if you changed Frigate's MQTT `topic_prefix`, update *Frigate Reviews MQTT Topic* in Advanced Options.

---

### 🗺️ Multi-Camera Journeys (experimental)

A second blueprint, **FrigateVision - Multi-Camera Journeys** (`frigate_vision_multicam.yaml`), follows an object as it moves between cameras and sends **one notification for the whole journey**. Its GIF is built from the full recordings and cuts from one camera to the next as the object moves, e.g. *"Zach detected: Street Cam → Front Door Cam (0:24)"*.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fzacharyd3%2FFrigate-Vision%2Fblob%2Fmain%2Ffrigate_vision_multicam.yaml)

**How it links cameras.** Reviews are part of the same journey when they are for the same kind of object (person, car, dog...) and each one starts while the previous one is still going, or within the *Link Gap* (20s by default) after it ends. If both reviews have recognized names (faces, plates), the names must match. A dog in the back yard doesn't join a person walking to the front door. A journey that stays on one camera simply gets a one-camera GIF, so use this blueprint *instead of* the regular one for the cameras you add to it.

**How the GIF is cut.** The GIF always shows the camera that most recently picked the object up. When the next camera sees it, the GIF hard-cuts to that camera. That includes walking back to a camera that is still recording from earlier: the GIF cuts back as soon as that camera picks the object up again. If the newest camera loses it while an earlier one still sees it, the GIF cuts back. Stretches where no camera saw anything are skipped. Each camera's name is shown in the corner.

**Portrait and landscape cameras.** With *Frame Shape* on *Auto*, the GIF follows the cameras in each journey:
* all portrait (e.g. doorbell or hallway cameras): portrait GIF
* all landscape: landscape GIF, at the camera's own aspect ratio
* mixed: square GIF

A camera that doesn't match the frame sits on a blurred copy of itself (like phones show vertical video), or on black bars if you prefer.

**What you get, in order:** a thumbnail as soon as the journey starts, updated silently as the object reaches more cameras. When the journey ends, the notification updates with Frigate's own GIF of the first camera. Once the journey GIF is built, it replaces that GIF in place. If the journey GIF can't be built, the Frigate GIF stays and a warning explains why in the Home Assistant log.

**Frigate GenAI (optional).** Set *Notification Title* and/or *Notification Text* to *Advanced* to use Frigate's [GenAI review summaries](https://docs.frigate.video/configuration/genai/review_summaries) (Frigate 0.17+). You can mix them, e.g. the GenAI title with the cameras as the text. Each camera's review in a journey can get its own summary. The notification uses the one Frigate rates as the biggest potential threat (with ⚠️/🚨 on the title), or the first camera's if they're rated the same. Until a summary arrives, the title says what was detected and the text lists the cameras. A summary that arrives after the GIF still updates the notification, silently, for up to the *GenAI Summary Timeout* (90s by default).

#### Setup (one time)

Frigate only makes GIFs of one review on one camera, so the journey GIF is built by a small Python script run by Home Assistant. It uses the `python3` and `ffmpeg` that already come with Home Assistant, so nothing else needs installing.

1. Copy [`frigate_vision_multicam.py`](frigate_vision_multicam.py) to `/config/frigate_vision/frigate_vision_multicam.py` (e.g. with the File editor or Samba add-on).
2. Add this to `configuration.yaml`:
   ```yaml
   shell_command:
     frigate_vision_multicam: "python3 /config/frigate_vision/frigate_vision_multicam.py {{ args }}"
   ```
3. Make sure the folder `/config/www` exists, then **restart** Home Assistant. Home Assistant only serves `/local/` if that folder existed at startup.
4. Import the blueprint and create an automation. Set *GIF → Frigate URL (from Home Assistant)* to the address Home Assistant uses to reach Frigate's API. For the Frigate add-on this is `http://ccab4aaf-frigate:5000` (the default). Use the unauthenticated port 5000.

#### Good to know

* **Recordings must be enabled** in Frigate for these cameras. The GIF is built from them, not from previews.
* **Timing:** a journey ends once everything has ended and the *Link Gap* has passed. Frigate's GIF follows about 10s later, and the journey GIF after the *Recording Delay* plus the time to build it. On a Raspberry Pi with 4K cameras, building can take a minute or more. Lower *Size*/*Frames per Second*, or raise *GIF Timeout*, if it times out.
* **GIF size:** iOS only shows images up to 10 MB in notifications. The defaults (640px, 8 fps, 2x speed, 20s max) stay well under that. *Blurred* backgrounds make bigger files than *Black*.
* **Where the GIFs live:** in `/config/www/frigate_vision/`. They are deleted after 48 hours, or after the notification timeout if that's longer. Like everything under `/local/`, they can be opened without logging in by anyone who can reach your Home Assistant and knows the file name. The names include a random part, so they can't be guessed.
* **Troubleshooting:** each GIF has a log in `/config/frigate_vision/jobs/`, named in the Home Assistant log warning. If the warning says it can't reach Frigate, check the **Frigate URL (from Home Assistant)** input: it must be a full address such as `http://192.168.1.50:5000`.
* **Not in this version (yet):** zone filters, the *Summary* button with GenAI's full description, and pulling in a camera's review from *before* the journey started (e.g. a car on the street "detection" before the person at the door "alert"). Add *Detection* to *Review Severity* if you want those to start a journey.

---

### 📱 History Dashboard

A dashboard of recent camera events, made for the Home Assistant app on a phone. Each event shows its GIF, what was detected (and who), the cameras, time, length and zones, and Frigate's GenAI title, short summary and full details with any concerns flagged. The GenAI summary is recorded **even if your notifications don't use it**. Filter by camera or by *Alerts*, *People*, *Vehicles*, *Animals* or *Potential threats*. A line at the top sums up today: how many events and alerts, who was seen, and which cameras were busy.

Both blueprints record to it. It keeps the last 40 events and survives restarts.

#### Setup (one time)

1. Copy [`dashboard/frigate_vision_history.yaml`](dashboard/frigate_vision_history.yaml) to `/config/packages/frigate_vision_history.yaml`. It creates the history sensor, the two filters and a *Clear History* script.
2. If you don't use packages yet, add this to `configuration.yaml`:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
3. *(Optional)* The history is too big for the recorder, which logs a warning about it. To silence the warning, add this to `configuration.yaml` (merge it into your `recorder:` section if you already have one):
   ```yaml
   recorder:
     exclude:
       entities:
         - sensor.frigate_vision_history
   ```
4. Restart Home Assistant.
5. **Settings → Dashboards → Add Dashboard → New dashboard from scratch**, open it, then **✏️ → ⋮ → Raw configuration editor**, and paste in [`dashboard/frigate_vision_dashboard.yaml`](dashboard/frigate_vision_dashboard.yaml).

*Record History* (under Advanced Options, on by default) must be on in your Frigate Vision automations. Events show up once their GIF is ready and update when the GenAI summary comes in.

#### Good to know

* **Only built-in cards are used.** With [card-mod](https://github.com/thomasloven/lovelace-card-mod) installed (HACS), GIFs get rounded corners and portrait GIFs never get taller than the screen.
* **GIFs load as you scroll**, so opening the dashboard on mobile data only loads what's on screen. Frigate builds each GIF when it's requested, so a long feed can take a moment.
* **How far back GIFs go** depends on Frigate. They are built from Frigate's previews, which are kept as long as your recordings. A journey's own GIF is deleted after 48 hours. After that the dashboard shows Frigate's GIF of the first camera instead.
* **Settings** (how many events to show, 12 or 24-hour times, which objects count as vehicles or animals) are at the top of the feed card's template. To keep more than 40 events, change `keep` in the package.
* **GenAI summaries** need Frigate 0.17+ with GenAI review summaries enabled. If your notifications don't use them (*Use Frigate GenAI Summary* off, or a journey without an *Advanced* title or text), the automation still waits up to the *GenAI Summary Timeout* for the summary, just for the dashboard. The notification doesn't change.

---

### 🧠 TL;DR:

**Frigate Vision** sends one notification per Frigate review. It updates in place with names as they're recognized, then an animated GIF of the whole event, then Frigate's AI summary, so you can see what happened without opening anything.

---

I’d love your feedback, ideas, bug reports (via github please), and feature requests. If you use it and like it, drop a comment; let’s make Frigate Vision even smarter!
