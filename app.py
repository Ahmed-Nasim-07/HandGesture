from flask import Flask, render_template, request, jsonify, send_file
import cv2
import mediapipe as mp
import numpy as np
import base64
import os
import time  # <--- 1. IMPORT TIME MODULE
from gtts import gTTS

app = Flask(__name__)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

gesture_counters = {
    "CONFIRM_WORD": 0,
    "CLEAR_ALL": 0,
    "SPEAK_ALL": 0
}
FRAME_THRESHOLD = 6  
cooldown_frames = 0  
last_delete_time = 0  # <--- 2. INITIALIZE GLOBAL TRACKING VARIABLE

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_frame', methods=['POST'])
def process_frame():
    global cooldown_frames, gesture_counters, last_delete_time  # <--- 3. ADD TO GLOBAL DECLARATIONS
    
    data = request.json
    if not data or 'image' not in data:
        return jsonify({'gesture': 'None'})

    header, encoded = data['image'].split(",", 1)
    image_bytes = base64.b64decode(encoded)
    np_array = np.frombuffer(image_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb_frame)

    detected_raw = "None"

    if cooldown_frames > 0:
        cooldown_frames -= 1
        return jsonify({'gesture': 'None'})

    if results.multi_hand_landmarks:
        num_hands = len(results.multi_hand_landmarks)
        
        # -------------------------------------------------------------
        # TWO-HANDED GLOBAL CONTROLS
        # -------------------------------------------------------------
        if num_hands == 2:
            hand1 = results.multi_hand_landmarks[0]
            hand2 = results.multi_hand_landmarks[1]
            
            palm_distance = abs(hand1.landmark[9].x - hand2.landmark[9].x)
            
            if palm_distance > 0.15: 
                h1_i = hand1.landmark[8].y < hand1.landmark[6].y
                h1_m = hand1.landmark[12].y < hand1.landmark[10].y
                h1_r = hand1.landmark[16].y < hand1.landmark[14].y
                h1_p = hand1.landmark[20].y < hand1.landmark[18].y

                h2_i = hand2.landmark[8].y < hand2.landmark[6].y
                h2_m = hand2.landmark[12].y < hand2.landmark[10].y
                h2_r = hand2.landmark[16].y < hand2.landmark[14].y
                h2_p = hand2.landmark[20].y < hand2.landmark[18].y

                if h1_i and h1_m and h1_r and h1_p and h2_i and h2_m and h2_r and h2_p:
                    detected_raw = "SPEAK_ALL"
                elif (h1_i and h1_m and not h1_r and not h1_p and 
                      h2_i and h2_m and not h2_r and not h2_p):
                    detected_raw = "CLEAR_ALL"
                elif (h1_i and not h1_m and not h1_r and not h1_p and 
                      h2_i and not h2_m and not h2_r and not h2_p):
                    detected_raw = "CONFIRM_WORD"

        # -------------------------------------------------------------
        # SINGLE-HANDED VOCABULARY DRAFTING
        # -------------------------------------------------------------
        elif num_hands == 1:
            hand_landmarks = results.multi_hand_landmarks[0]
            
            def get_pt(lm):
                return np.array([lm.x, lm.y, lm.z])

            p_wrist = get_pt(hand_landmarks.landmark[0])
            p_index_tip = get_pt(hand_landmarks.landmark[8])
            p_middle_tip = get_pt(hand_landmarks.landmark[12])
            p_ring_tip = get_pt(hand_landmarks.landmark[16])
            
            thumb_tip = hand_landmarks.landmark[4]
            thumb_ip = hand_landmarks.landmark[3]
            thumb_mcp = hand_landmarks.landmark[2]
            
            index_tip = hand_landmarks.landmark[8]
            index_knuckle = hand_landmarks.landmark[6]
            middle_tip = hand_landmarks.landmark[12]
            middle_knuckle = hand_landmarks.landmark[10]
            ring_tip = hand_landmarks.landmark[16]
            ring_knuckle = hand_landmarks.landmark[14]
            pinky_tip = hand_landmarks.landmark[20]
            pinky_knuckle = hand_landmarks.landmark[18]

            index_up = index_tip.y < index_knuckle.y
            middle_up = middle_tip.y < middle_knuckle.y
            ring_up = ring_tip.y < ring_knuckle.y
            pinky_up = pinky_tip.y < pinky_knuckle.y

            d_index = np.linalg.norm(p_index_tip - p_wrist)
            d_middle = np.linalg.norm(p_middle_tip - p_wrist)
            d_ring = np.linalg.norm(p_ring_tip - p_wrist)
            
            if (0.28 < d_index < 0.42) and (0.28 < d_middle < 0.42) and (0.28 < d_ring < 0.42):
                detected_raw = "NEED"
            elif index_up and middle_up and ring_up and pinky_up:
                detected_raw = "EMERGENCY"
            elif index_up and middle_up and ring_up and not pinky_up:
                detected_raw = "WATER"
            elif index_up and pinky_up and not middle_up and not ring_up:
                detected_raw = "PAIN"
            elif pinky_up and not index_up and not middle_up and not ring_up:
                detected_raw = "TOILET"
            elif ring_up and not index_up and not middle_up and not pinky_up:
                detected_raw = "RECEPTION"
            elif index_up and not middle_up and not ring_up and not pinky_up:
                if abs(thumb_tip.x - index_knuckle.x) < 0.08:
                    detected_raw = "HELP"
                else:
                    detected_raw = "I"
            elif not index_up and not middle_up and not ring_up and not pinky_up:
                if thumb_tip.y < index_knuckle.y:
                    detected_raw = "DOCTOR"
                # --- TIME DELAY LOGIC FOR DELETION ---
                elif thumb_tip.y > thumb_ip.y and thumb_ip.y > thumb_mcp.y:
                    current_time = time.time()
                    # Only allow deletion if 3 seconds have passed since the last one
                    if current_time - last_delete_time >= 3.0:
                        detected_raw = "DELETE_LAST"
                        last_delete_time = current_time  # Reset timestamp anchor
                    else:
                        detected_raw = "None"

    # --- DEBOUNCE EVALUATION SMOOTHER ---
    final_output_gesture = "None"
    
    for ctrl in gesture_counters:
        if detected_raw == ctrl:
            gesture_counters[ctrl] += 1
            if gesture_counters[ctrl] >= FRAME_THRESHOLD:
                final_output_gesture = ctrl
                cooldown_frames = 12  
                gesture_counters = {k: 0 for k in gesture_counters}
                break
        else:
            gesture_counters[ctrl] = max(0, gesture_counters[ctrl] - 1)

    if final_output_gesture == "None" and detected_raw not in ["CONFIRM_WORD", "CLEAR_ALL", "SPEAK_ALL"]:
        final_output_gesture = detected_raw

    return jsonify({'gesture': final_output_gesture})

@app.route('/speak')
def speak():
    text_to_say = request.args.get('text', '')
    tts = gTTS(text=text_to_say, lang='en')
    filename = "speech_output.mp3"
    if os.path.exists(filename):
        os.remove(filename)
    tts.save(filename)
    return send_file(filename, mimetype="audio/mp3")

if __name__ == '__main__':
    app.run(debug=True, port=5000)