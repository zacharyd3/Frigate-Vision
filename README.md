# Frigate-Vision
---
<sup>**Firstly, credit where credit is due!** A lot of this automation was inspired and even copied from @SgtBatten's [Frigate notification Blueprint](https://community.home-assistant.io/t/frigate-mobile-app-notifications-2-0/559732). Earlier versions also borrowed from @valentinfrlch's [LLMVision Blueprint](https://llmvision.gitbook.io/getting-started/setup/blueprint). If anyone has an issue with content or code, please reach out.</sup>

[After sharing a screenshot](https://www.reddit.com/r/homeassistant/comments/1lohkx9/my_take_on_a_frigatellm_vision_notification/) of one of my Frigate automations the other day, a few of you asked if I had a blueprint. At the time I didn’t… so I sat down, taught myself how to build one and here it is!

Introducing **Frigate Vision**: a blueprint that gives you Frigate notifications you can read at a glance. It follows a person (or car, or dog...) as they move between your cameras and sends **one notification for the whole journey**, with an animated GIF that cuts from one camera to the next as they move, e.g. *"Zach detected: Street Cam → Front Door Cam (0:24)"*. It works just as well for one camera: add only that camera.

> **One blueprint now.** The original single-camera blueprint (*FrigateVision - GIF Notifications*, `frigate_vision.yaml`) has been retired in favour of *FrigateVision - Multi-Camera Journeys*, which handles a single camera too. Automations made from the old blueprint keep working, but it won't get updates and can't be re-imported. To switch, do the one-time [Setup](#-setup-one-time) and create a new automation from the blueprint below. Unlike the old blueprint, it sends one notification once the activity is over, instead of a thumbnail straight away that updates as it goes.

---

**📄 Get the Blueprint:**

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fzacharyd3%2FFrigate-Vision%2Fblob%2Fmain%2Ffrigate_vision_multicam.yaml)

It needs a small one-time [Setup](#-setup-one-time) (a script that builds the GIFs).

---
[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://buymeacoffee.com/zacharyd3)
#### 💡 How it works

1. **🚨 Review starts.** Frigate publishes a new review item (an alert, by default) on one of your cameras, and a journey starts, following that kind of object (person, car, dog...).
2. **🚶 It moves.** When another camera sees the same kind of object while the last one still does, or within the *Link Gap* (20s by default) after it's gone, that camera joins the journey.
3. **🎞️ It's gone.** Once nothing new has turned up for the *Link Gap*, the journey is over. A small script cuts the cameras' recordings together into one animated GIF that follows the object from camera to camera.
4. **🧠 Frigate GenAI (optional).** If you've enabled [GenAI review summaries](https://docs.frigate.video/configuration/genai/review_summaries) in Frigate 0.17+, it waits for them, then uses Frigate's title (with ⚠️/🚨 if Frigate rates it as a potential threat) and short summary. Or have your own AI combine every camera's summary into one.
5. **🔔 One notification.** 30-90s after the object is gone you get one notification for the whole journey: the GIF, the cameras it went through and how long it took, and the summary. It doesn't change after it arrives.

#### ✨ Features

* **Follows objects across cameras**: one notification and one GIF per journey, however many cameras it crosses. A journey that stays on one camera gets a one-camera GIF.
* **Follow-only cameras**: a camera like a busy street camera never starts a journey on its own, but a journey still follows someone onto it
* **GIF built from the recordings**, cutting to whichever camera picked the object up last, in portrait, landscape or square to match your cameras
* **Filters** for review severity (alert/detection) and the objects to follow, and an option to let detections join a journey an alert started
* **Recognized names for people only**: names from face recognition are shown, while names Frigate gives other objects (like known license plates on cars) are left out
* **No "unidentified person"**: when Frigate's GenAI calls someone an *unidentified person* but Frigate recognized them (later on, or on another camera), their name is used instead; if nobody was recognized, it just says *person*
* **Summarize with AI**: an [AI Task](https://www.home-assistant.io/integrations/ai_task/) (e.g. a local Ollama model) can merge every camera's GenAI summary into one account of the whole journey
* **Cooldown** between new notifications, and a **Snooze** button
* **Multiple notification devices**, grouped and channelled by the camera the journey started on, so the camera name shows in the notification group
* **Notification title and text, set separately**: what was detected (e.g. *"Zach detected"*), the cameras (e.g. *"Street Cam → Front Door Cam (0:24)"*), *Advanced* (the GenAI title or short summary) or *None*. Set both to *None* for the biggest image
* **Buttons**: *View GIF*, *View Clip*, *View Snapshot*, *View Live*, *Open in Frigate*, *Open Dashboard*, *Snooze*, or your own
* **History dashboard** for your phone: every journey's GIF and GenAI summary, filterable by camera and type (see [History Dashboard](#-history-dashboard))

---

### ⚙️ Requirements:

* Home Assistant **2025.4** or newer
* [Frigate](https://docs.frigate.video/) with MQTT enabled, and the [Frigate integration](https://docs.frigate.video/integrations/home-assistant/) with the notification proxy enabled (it's on by default)
* **Recordings** enabled in Frigate for your cameras. The GIF is built from them.
* Home Assistant able to reach Frigate's API on its unauthenticated port (5000)
* Home Assistant mobile app. Animated GIFs play in the notification shade on **iOS** and **Android 14+**. Older Android versions show the first frame.
* *(Optional)* Frigate 0.17+ with GenAI review summaries enabled, for AI titles and summaries

---

### 🔧 Setup (one time)

Frigate only makes GIFs of one review on one camera, so the journey GIF is built by a small Python script run by Home Assistant. It uses the `python3` and `ffmpeg` that already come with Home Assistant, so nothing else needs installing.

1. Copy [`frigate_vision_multicam.py`](frigate_vision_multicam.py) to `/config/frigate_vision/frigate_vision_multicam.py` (e.g. with the File editor or Samba add-on).
2. Add this to `configuration.yaml`:
   ```yaml
   shell_command:
     frigate_vision_multicam: "python3 /config/frigate_vision/frigate_vision_multicam.py {{ args }}"
   ```
3. Make sure the folder `/config/www` exists, then **restart** Home Assistant. Home Assistant only serves `/local/` if that folder existed at startup.
4. Import the blueprint and create an automation. Set *GIF → Frigate URL (from Home Assistant)* to the address Home Assistant uses to reach Frigate's API. For the Frigate add-on this is `http://ccab4aaf-frigate:5000` (the default). Use the unauthenticated port 5000.

---

### 🗺️ Following objects across cameras

**How it links cameras.** Reviews are part of the same journey when they are for the same kind of object (person, car, dog...) and each one starts while the previous one is still going, or within the *Link Gap* (20s by default) after it ends. If both reviews have recognized names (faces, plates), the names must match. A dog in the back yard doesn't join a person walking to the front door. Pick the objects to follow in the *Labels* checklist (at least one). If a review has more than one of them, the journey follows the one highest in the list, so a person getting out of a car is followed as a person. A journey only follows the cameras in its own automation, so put all the cameras an object can move between in one automation.

**Follow-only cameras.** Some cameras see too much to start a journey, like a street camera with people walking past all day, but you still want to follow someone onto them. Add those to *Follow-Only Cameras* (under *Filters*) instead of *Frigate Cameras*. They never start a journey or notify on their own, but if someone walks from the front door to the street, the journey follows them onto the street camera, e.g. *"Zach detected: Front Door Cam → Street Cam (0:31)"*. A follow-only camera only joins while the object is on one of your other cameras, or within the *Link Gap* after it leaves one, so a busy street can't keep a journey going on its own. Coming back from the street to a regular camera links as usual.

**How the GIF is cut.** The GIF always shows the camera that most recently picked the object up. When the next camera sees it, the GIF hard-cuts to that camera. That includes walking back to a camera that is still recording from earlier: the GIF cuts back as soon as that camera picks the object up again. If the newest camera loses it while an earlier one still sees it, the GIF cuts straight back (the *Lead-out* only plays when no other camera still sees the object). Stretches where no camera saw anything are skipped. Each camera's name is shown in the corner.

**Portrait and landscape cameras.** With *Frame Shape* on *Auto*, the GIF follows the cameras in each journey:
* all portrait (e.g. doorbell or hallway cameras): portrait GIF
* all landscape: landscape GIF, at the camera's own aspect ratio
* mixed: square GIF

A camera that doesn't match the frame sits on a blurred copy of itself (like phones show vertical video), or on black bars if you prefer.

**Buttons.** Pick any of these in *Action Buttons*, in the order you want them (Android shows the first 3, iOS shows them all when you long-press the notification). Most of them can also be the *Tap Action*.
* **View GIF**: the journey GIF, full size
* **View Clip** / **View Snapshot**: the first camera's clip or snapshot
* **View Live**: the last camera the object reached, live in Frigate (with the *External Frigate URL* set) or, without it, in Home Assistant (Android only)
* **Open in Frigate**: the review in the Frigate UI
* **Open Dashboard**: any dashboard, e.g. the [History Dashboard](#-history-dashboard). Set *Dashboard Path* to the end of its address, like `/dashboard-cameras/camera-history`.
* **Snooze**: no notifications from this automation for the *Snooze Length* (30 minutes by default), on any device. Journeys are still recorded to the history dashboard meanwhile. It needs a *Snooze Timer*: create a Timer helper (**Settings → Devices & services → Helpers → Create helper → Timer**, with *Restore* on) and pick it. Automations that share a timer are snoozed together.
* **Custom**: your own label and link, e.g. another dashboard, a website, or `entityId:lock.front_door` (Android) to open an entity

**Frigate GenAI (optional).** Set *Notification Title* and/or *Notification Text* to *Advanced* to use Frigate's [GenAI review summaries](https://docs.frigate.video/configuration/genai/review_summaries) (Frigate 0.17+). You can mix them, e.g. the GenAI title with the cameras as the text. Each camera's review in a journey can get its own summary. The notification uses the one Frigate rates as the biggest potential threat (with ⚠️/🚨 on the title), or the first camera's if they're rated the same. The notification waits for the summaries for up to the *GenAI Summary Timeout* (90s by default), but only for the reviews Frigate actually summarises: the script reads that from Frigate's config (`review -> genai`, which by default covers alerts but not detections). Without GenAI in Frigate there's no wait at all. If *Frigate URL (from Home Assistant)* is blank, it waits for the alerts' summaries. If none arrives in time, the title says what was detected and the text lists the cameras.

**Summarize with AI (optional).** Set *Summarize with AI* to an [AI Task](https://www.home-assistant.io/integrations/ai_task/) entity (e.g. a local Ollama model) to have it write the *Advanced* title and text instead of Frigate's GenAI. It merges every camera's summary into one title, summary and description of the whole journey, in the order things happened (or rewrites the one summary of a single-camera journey), with the people Frigate recognized called by name. Only the summaries' text is sent, not images, so even a small local model handles it in a few seconds. Use *Extra AI Instructions* for context like who lives there. If the AI Task fails, the notification falls back to the summary picked as above. The threat level (⚠️/🚨) always comes from Frigate's own ratings. On the history dashboard, an AI-written journey shows the AI's title, summary and description as its main text, with each camera's original GenAI summary underneath in a collapsed *Frigate GenAI summaries* section, so you can always see what the AI worked from. A journey more than one camera summarized gets that section too, even without *Summarize with AI*.

---

### 🛠️ Tips

* **Severity**: Frigate decides what counts as an *alert* (`review -> alerts -> labels / required_zones` in your Frigate config). Tuning that in Frigate is usually cleaner than filtering in the blueprint.
* **Timing:** a journey ends once everything has ended and the *Link Gap* has passed. The journey GIF is built after the *Recording Delay*, then the notification waits for any GenAI summaries Frigate is writing (up to the *GenAI Summary Timeout*). The recordings are downloaded in parallel, one clip per camera. All of these are in the blueprint's *Timing* section. On a Raspberry Pi with 4K cameras, building the GIF can take a minute or more. Lower *Size*/*Frames per Second*, or raise *GIF Timeout*, if it times out.
* **GIF size:** iOS only shows images up to 10 MB in notifications. The defaults (640px, 8 fps, 2x speed, 20s max) stay well under that. *Blurred* backgrounds make bigger files than *Black*.
* **Cooldowns**: the cooldown applies to the whole automation. You can create one automation per camera so each cools down on its own, but then a journey can't follow an object from one camera to the next.
* **Taller image on Android**: Android gives an expanded notification a fixed height, and the image gets whatever the text and buttons leave, so tall (hallway-mode) cameras get cropped. Set both *Notification Title* and *Notification Text* to *None* and remove *Action Buttons* you don't need to give the image as much room as possible. Tapping the notification still opens the *Tap Action* (the GIF by default).
* **Custom topic prefix**: if you changed Frigate's MQTT `topic_prefix`, update *Frigate Reviews MQTT Topic* in Advanced Options.
* **Where the GIFs live:** in `/config/www/frigate_vision/`. They are deleted after 48 hours, or after the notification timeout if that's longer. Like everything under `/local/`, they can be opened without logging in by anyone who can reach your Home Assistant and knows the file name. The names include a random part, so they can't be guessed.
* **Troubleshooting:** if the journey GIF can't be built, the notification uses Frigate's own GIF of the first camera, and a warning in the Home Assistant log explains why. Each GIF has a log in `/config/frigate_vision/jobs/`, named in that warning. If the warning says it can't reach Frigate, check the **Frigate URL (from Home Assistant)** input: it must be a full address such as `http://192.168.1.50:5000`.
* **Not in this version (yet):** zone filters, the *Summary* button with GenAI's full description, and pulling in a camera's review from *before* the journey started (e.g. a car on the street "detection" before the person at the door "alert"). Add *Detection* to *Review Severity* if you want those to start a journey.

---

### 📱 History Dashboard

A dashboard of recent camera events, made for the Home Assistant app on a phone. Each event shows its GIF, what was detected (and who), the cameras, time, length and zones, and Frigate's GenAI title, short summary and full details with any concerns flagged, plus links to its clips (one per camera for a multi-camera journey). The GenAI summary is recorded **even if your notifications don't use it**. Filter by camera or by *Alerts*, *People*, *Vehicles*, *Animals* or *Potential threats*. A line at the top sums up today: how many events and alerts, who was seen, and which cameras were busy.

It keeps the last 40 events and survives restarts.

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

*Record History* (under Advanced Options, on by default) must be on in your Frigate Vision automations. Each journey shows up once it's done, at the same time as its notification (and even while notifications are snoozed).

#### Good to know

* **Only built-in cards are used.** With [card-mod](https://github.com/thomasloven/lovelace-card-mod) installed (HACS), GIFs get rounded corners and portrait GIFs never get taller than the screen.
* **GIFs load as you scroll**, so opening the dashboard on mobile data only loads what's on screen.
* **How far back GIFs go:** a journey's own GIF is deleted after 48 hours. After that the dashboard shows Frigate's GIF of the first camera instead, which Frigate builds from its previews (kept as long as your recordings) when it's requested, so older events can take a moment to load.
* **Settings** (how many events to show, 12 or 24-hour times, which objects count as vehicles or animals) are at the top of the feed card's template. To keep more than 40 events, change `keep` in the package.
* **GenAI summaries** need Frigate 0.17+ with GenAI review summaries enabled. If your notifications don't use them (no *Advanced* title or text), the notification still waits for them, up to the *GenAI Summary Timeout*, so the dashboard gets them. It only waits for the reviews Frigate summarises, so not at all without GenAI in Frigate.

---

### 🧠 TL;DR:

**Frigate Vision** follows an object across your cameras and sends one notification once it's gone: an animated GIF that cuts from camera to camera, the path it took, and Frigate's (or your own AI's) summary, so you can see what happened without opening anything.

---

I’d love your feedback, ideas, bug reports (via github please), and feature requests. If you use it and like it, drop a comment; let’s make Frigate Vision even smarter!
