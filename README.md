> [!NOTE]
> This App is almost completely Vibed Coded. I wanted to have a simple interface for Hand Recognition and [Double Take](https://github.com/skrashevich/double-take) wasn't really working for me. After understanding the problem at hand, I noticed that the project structure was going to be very simple, so I gave Claude a shot.
> I made this app for my personal use, but I am sharing it because it works perfectly for my use case, and maybe its useful for others.
> If you have an issue with the app being Vibe Coded, please refrain to make any comments. Thanks.

# Home Assistant Hand Recognition Add-on

Detects and classifies hand gestures from [Frigate](https://github.com/blakeblackshear/frigate) camera snapshots using [MediaPipe](https://github.com/google-ai-edge/mediapipe).
When a gesture is recognized, it publishes the result to an MQTT topic so Home Assistant automations can react to it.

![UI](./imgs/ui.png)

## Installation

1. In Home Assistant, go to **Settings > Add-ons > Add-on Store**.
2. Click the menu (top right) and select **Repositories**.
3. Add: `https://github.com/benja-opazo/home-assistant-hand-recognition`
4. Install the **Hand Recognition** add-on and start it.
5. Open the web UI from the add-on page to configure connections and detection settings.

> [!TIP]
> The installation takes a while, because the Home Assistant has to build the Docker image. Be patient

## Configuration

The web UI has five tabs:

| Tab | Purpose |
|-----|---------|
| Snapshots | Grid of captured snapshots with gesture and camera filters. Supports single download/delete per card, and multi-select for bulk delete or ZIP download. |
| Connections | MQTT broker credentials, Frigate URL, snapshot mode (event vs. latest frame), and output topic template. |
| Detection | MQTT topic to subscribe to, plus configurable message filters (property, comparator, value) for routing events. |
| MediaPipe | Toggle individual gestures on/off, select the recognition backend (Landmarks or GestureRecognizer), and adjust model settings (confidence threshold, max hands, model complexity, scoring parameters). |
| Logs | Live log stream with level and source filters, pause, clear, and download. |

The default configuration should work out of the box, except for the MQTT credentials that have to be configured.

## MQTT Output

When a gesture is detected, the add-on publishes to the configured topic (default: `hand-recognition/{camera}`):

```json
{
  "camera": "front_door",
  "detections": [
    {
      "gesture": "open_palm",
      "score": 0.97,
      "hand": "Right"
    }
  ]
}
```

If no hands are detected in the snapshot, **nothing is published**.

## Recognition Backends

The **MediaPipe** tab lets you choose between two recognition backends. Both output the same MQTT payload format.

### Landmarks (default)

Uses MediaPipe's hand landmark detection combined with a custom gesture classifier built into this add-on. Gestures are scored by how well each finger matches its expected open/closed state, and the best-matching gesture wins.

**Pros:**
- Supports a larger and fully customizable gesture set (10 gestures out of the box)
- Two tunable parameters — **sigmoid sharpness** and **score threshold** — let you dial in sensitivity without a restart
- No extra model file required

**Cons:**
- Confidence scores are relative (how well the hand matches a pattern), not absolute probabilities
- Can struggle with non-upright hand orientations, though palm rotation is compensated automatically

**Supported gestures:** `fist`, `thumbs_up`, `pointing`, `peace`, `open_palm`, `four_fingers`, `three_fingers`, `rock_on`, `call_me`, `pinky`

---

### MediaPipe GestureRecognizer

Uses MediaPipe's own built-in gesture classifier, which runs a neural network trained by Google on top of the landmarks.

**Pros:**
- Returns true probability scores — more meaningful confidence values
- More robust to hand orientation and lighting variation

**Cons:**
- Requires downloading a separate model file (~20 MB) via the UI
- Fixed gesture set — only the gestures Google trained for are available
- Does not support the custom gestures from the Landmarks backend

**Supported gestures:** `fist`, `open_palm`, `pointing`, `thumbs_up`, `thumbs_down`, `peace`, `i_love_you`

To use it: select **MediaPipe GestureRecognizer** in the Recognition Backend section, click **Download model**, then save and restart.

---

## Supported Gestures

These are the values that appear in the `gesture` field of the MQTT payload. Which gestures are available depends on the backend selected.

### Landmarks backend

| Value | Description |
|-------|-------------|
| `fist` | All fingers curled, closed fist |
| `thumbs_up` | Thumb extended, all other fingers curled |
| `pointing` | Index finger extended, all others curled |
| `peace` | Index and middle fingers extended (V sign) |
| `open_palm` | All five fingers extended |
| `four_fingers` | Index, middle, ring, and pinky extended, thumb curled |
| `three_fingers` | Index, middle, and ring fingers extended |
| `rock_on` | Index and pinky extended, thumb out (horns sign) |
| `call_me` | Thumb and pinky extended, other fingers curled |
| `pinky` | Pinky finger only extended |
| `unknown` | A hand was detected but did not match any gesture above the score threshold |

### GestureRecognizer backend

| Value | Description |
|-------|-------------|
| `fist` | Closed fist |
| `open_palm` | All fingers extended |
| `pointing` | Index finger pointing up |
| `thumbs_up` | Thumbs up |
| `thumbs_down` | Thumbs down |
| `peace` | Index and middle fingers extended (V sign) |
| `i_love_you` | Thumb, index, and pinky extended (ILY sign) |
| `unknown` | A hand was detected but no gesture was confidently identified |

## Tips for Improving Hand Detection

### Snapshot resolution is tied to Frigate's detect stream

The add-on fetches snapshots via the Frigate API (`/api/events/{id}/snapshot.jpg` or `/api/{camera}/latest.jpg`). These images are sourced from Frigate's **detect stream**, not the camera's full resolution recording stream. If detection feels unreliable — especially when the subject is not directly in front of the camera — low snapshot resolution is usually the cause.

The best approach is to configure Frigate to use your camera's **main (high-resolution) stream** as the detect input and let Frigate downscale it to a resolution your device can handle:

```yaml
cameras:
  your_camera:
    ffmpeg:
      inputs:
        - path: rtsp://user:password@camera-ip:554/main_stream
          roles:
            - detect
            - record
    detect:
      width: 1280
      height: 720
```

This ensures snapshots are taken from the best available source while keeping detection at a resolution appropriate for your hardware. On a Raspberry Pi 4, 1280×720 is a reasonable target. Avoid running detection at 4K — the CPU cost is high and it provides no meaningful benefit over a well-scaled 720p or 1080p stream.

> [!NOTE]
> Frigate snapshots are always sourced from the detect stream regardless of what other streams are configured. There is no separate `snapshots` role in current Frigate versions.

### Snapshot quality and cropping

The **Connections** tab exposes three Frigate API parameters that affect what the add-on receives:

| Setting | Effect |
|---------|--------|
| **Snapshot quality** | JPEG compression (1–100, default 70). Higher values preserve more detail for MediaPipe. |
| **Snapshot height** | Resize the image to this height before recognition. Set to `0` for full detect-stream resolution. |
| **Crop to bounding box** | Asks Frigate to crop the image to the detected object region, making the subject larger in frame. Particularly useful when the person is small or off to the side. Only works during active events. |

### MediaPipe confidence threshold

If hands are missed when the subject is at an angle or partially out of frame, lowering `mediapipe_min_detection_confidence` (default `0.5`) to around `0.35`–`0.4` can help. This makes the model more willing to report a detection at the cost of slightly more false positives.

---

## Home Assistant Automation Example

The following automation turns on a light when an open palm is detected on the front door camera.

```yaml
alias: Open palm detected on front door by Recognized Person
triggers:
  - topic: hand-recognition/front-door
    trigger: mqtt
conditions:
  - condition: template
    value_template: >-
      {{ trigger.payload_json.detections[0].gesture in ['open_palm',
      'four_fingers', 'three_fingers'] }}
action:
  - service: light.turn_on
    target:
      entity_id: light.front_porch
mode: single
```

Notice that in the previous configuration, the camera name in  `hand-recognition/<camera_name>` is obtained from the Frigate MQTT Notification, which is obtained from the camera configuration. This is usefull if there are more than one camera added to the Frigate App and some actions (e.g.: open palm, open front door) are place specific.

To act on any gesture from any camera, use a wildcard topic and reference the camera and gesture from the payload:

```yaml
alias: Log any hand gesture
trigger:
  - platform: mqtt
    topic: hand-recognition/#
action:
  - service: notify.persistent_notification
    data:
      message: >
        {{ trigger.payload_json.detections[0].gesture }}
        detected on {{ trigger.payload_json.camera }}
mode: queued
max: 10
```
