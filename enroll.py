import cv2
import os
import numpy as np

# ── Paths ──────────────────────────────────────────────
FACE_DIR     = "data/faces"
MODEL_PATH   = "data/trainer.yml"
CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

os.makedirs(FACE_DIR, exist_ok=True)

# ── Angle sessions ─────────────────────────────────────
SESSIONS = [
    ("FRONT", "Look straight at the camera"),
    ("LEFT",  "Slowly turn your head LEFT"),
    ("RIGHT", "Slowly turn your head RIGHT"),
    ("UP",    "Tilt your head slightly UP"),
    ("DOWN",  "Tilt your head slightly DOWN"),
]

SAMPLES_PER_ANGLE = 20  # 20 photos x 5 angles = 100 samples


def clear_old_faces():
    """Delete previous face images so we start fresh."""
    for f in os.listdir(FACE_DIR):
        os.remove(os.path.join(FACE_DIR, f))
    print("Old face data cleared.")


def capture_angle(session_name, instruction, face_cascade, cam):
    """Capture SAMPLES_PER_ANGLE images for one angle."""
    count = 0
    ready = False
    print(f"\n>>> {session_name}: {instruction}")
    print("    Press SPACE when ready...")

    while True:
        ret, frame = cam.read()
        if not ret:
            break

        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray, scaleFactor=1.3, minNeighbors=5)

        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h),
                          (0, 255, 255), 2)

        cv2.putText(frame, f"Angle: {session_name}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.putText(frame, instruction, (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        if not ready:
            cv2.putText(frame, "Press SPACE when ready", (10, 95),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(frame, f"Capturing {count}/{SAMPLES_PER_ANGLE}",
                        (10, 95), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 255, 0), 2)

        cv2.imshow("Enrollment - Multi-Angle", frame)
        key = cv2.waitKey(100) & 0xFF

        if key == ord(' '):
            ready = True

        if ready and len(faces) > 0:
            x, y, w, h = faces[0]
            cv2.imwrite(f"{FACE_DIR}/{session_name}_{count}.jpg",
                        gray[y:y + h, x:x + w])
            count += 1

        if key == ord('q'):
            print("Enrollment cancelled.")
            return False

        if count >= SAMPLES_PER_ANGLE:
            print(f"    {session_name} complete!")
            break

    return True


def train_model():
    """Train LBPH on all captured images."""
    print("\nTraining model on all angles...")
    recognizer = cv2.face.LBPHFaceRecognizer_create()

    faces_data, labels = [], []
    for img_file in os.listdir(FACE_DIR):
        img = cv2.imread(os.path.join(FACE_DIR, img_file),
                         cv2.IMREAD_GRAYSCALE)
        if img is not None:
            faces_data.append(img)
            labels.append(1)

    recognizer.train(faces_data, np.array(labels))
    recognizer.save(MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")
    print(f"Total samples used: {len(faces_data)}")


def enroll_user():
    face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
    cam = cv2.VideoCapture(0)

    if not cam.isOpened():
        print("ERROR: Cannot access webcam.")
        return

    print("=" * 50)
    print("  MULTI-ANGLE FACE ENROLLMENT")
    print("=" * 50)

    clear_old_faces()

    for name, instruction in SESSIONS:
        if not capture_angle(name, instruction, face_cascade, cam):
            break

    cam.release()
    cv2.destroyAllWindows()

    if len(os.listdir(FACE_DIR)) == 0:
        print("No faces captured. Enrollment failed.")
        return

    train_model()
    print("\nEnrollment complete! Your model is ready.")


if __name__ == "__main__":
    enroll_user()
