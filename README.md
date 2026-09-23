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

1. **🚨 Review starts.** Frigate publishes a new review item (alert or detection) on `frigate/reviews`. You immediately get a notification with a full-frame snapshot of the camera. You can turn this off if you only want the GIF.
2. **🏷️ While it's happening:** if Frigate recognizes someone (face recognition, LPR, etc.) or spots more objects, the same notification updates silently, e.g. *"Zach detected"*.
3. **🎞️ Review ends.** The blueprint waits for Frigate to close the review, then swaps the image for an **animated GIF covering the whole review** (sped up, like Frigate's review timeline previews) and adds the duration, e.g. *"Back Door Cam (0:42)"*.
4. **🧠 Frigate GenAI (optional).** If you've enabled [GenAI review summaries](https://docs.frigate.video/configuration/genai/review_summaries) in Frigate 0.17+, the notification updates once more. Frigate's title becomes the notification title (with ⚠️/🚨 if Frigate rates it as a potential threat) and its one-line short summary becomes the message.
5. **📖 Want the details?** Tap the **Summary** button. The notification is replaced with Frigate's full scene description and observations, shown as plain text so it fits in the notification shade.

Every update replaces the same notification, and only the first one makes a sound.

#### ✨ Features

* **Multiple cameras**: each review gets its own run, so simultaneous activity on different cameras produces separate notifications
* **Filters** for review severity (alert/detection), labels and zones. A review that later upgrades to an alert or enters a zone still triggers.
* **Cooldown** between new notifications
* **Multiple notification devices**, grouped and channelled per camera, so the camera name shows in the notification group
* **Actions**: *Summary* (full GenAI description), *View Clip* (through Home Assistant) and *Open in Frigate* (links straight to the review)

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
* **Custom topic prefix**: if you changed Frigate's MQTT `topic_prefix`, update *Frigate Reviews MQTT Topic* in Advanced Options.

---

### 🧠 TL;DR:

**Frigate Vision** sends one notification per Frigate review. It updates in place with names as they're recognized, then an animated GIF of the whole event, then Frigate's AI summary, so you can see what happened without opening anything.

---

I’d love your feedback, ideas, bug reports (via github please), and feature requests. If you use it and like it, drop a comment; let’s make Frigate Vision even smarter!
