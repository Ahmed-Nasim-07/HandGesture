const video = document.getElementById('webcam');
const canvas = document.getElementById('capture-canvas');
const context = canvas.getContext('2d');
const draftDisplay = document.getElementById('draft-output');
const sentenceDisplay = document.getElementById('sentence-output');
const audioPlayer = document.getElementById('audio-player');

let sentenceWords = [];
let draftedWord = "None";
let lastLoggedGesture = "None";
let isAudioPlaying = false;

navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
    .then(stream => {
        video.srcObject = stream;
        setInterval(sendFrameToBackend, 150);
    })
    .catch(err => console.error("Camera access error:", err));

function sendFrameToBackend() {
    if (isAudioPlaying) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg');

    fetch('/process_frame', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: dataUrl })
    })
    .then(res => res.json())
    .then(data => {
        let recognized = data.gesture;

        if (recognized !== "None") {
            if (recognized === "SPEAK_ALL") {
                if (sentenceWords.length > 0) {
                    triggerTextToSpeech(sentenceWords.join(" "));
                }
                draftedWord = "None";
                draftDisplay.innerText = "None";
            }
            else if (recognized === "CONFIRM_WORD") {
                if (draftedWord !== "None") {
                    sentenceWords.push(draftedWord);
                    sentenceDisplay.innerText = sentenceWords.join(" ");
                    draftedWord = "None";
                    draftDisplay.innerText = "None";
                }
            }
            else if (recognized === "CLEAR_ALL") {
                sentenceWords = [];
                sentenceDisplay.innerText = "...";
                draftedWord = "None";
                draftDisplay.innerText = "None";
            }
            else if (recognized === "DELETE_LAST") {
                sentenceWords.pop();
                sentenceDisplay.innerText = sentenceWords.length > 0 ? sentenceWords.join(" ") : "...";
                draftedWord = "None";
                draftDisplay.innerText = "None";
            }
            else {
                // Added the new backend string keys mapped to lowercase TTS equivalents
                let mapDictionary = {
                    "I": "I", 
                    "HELP": "help", 
                    "EMERGENCY": "emergency", 
                    "NEED": "need",
                    "WATER": "water",
                    "PAIN": "pain",
                    "DOCTOR": "doctor",
                    "TOILET": "toilet",
                    "RECEPTION": "reception"
                };
                if (mapDictionary[recognized]) {
                    draftedWord = mapDictionary[recognized];
                    draftDisplay.innerText = draftedWord;
                }
            }
        }
    });
}

function triggerTextToSpeech(textLine) {
    isAudioPlaying = true;
    draftDisplay.innerText = "SPEAKING SENTENCE...";
    
    audioPlayer.src = `/speak?text=${encodeURIComponent(textLine)}&t=${new Date().getTime()}`;
    audioPlayer.play();
    
    audioPlayer.onended = () => {
        isAudioPlaying = false;
        sentenceWords = [];
        sentenceDisplay.innerText = "...";
        draftDisplay.innerText = "None";
    };
}

function undoLastWord() {
    if (sentenceWords.length > 0) {
        sentenceWords.pop();
        if (sentenceWords.length > 0) {
            sentenceDisplay.innerText = sentenceWords.join(" ");
        } else {
            sentenceDisplay.innerText = "...";
        }
    }
}