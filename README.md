Biometric Protection System

A Windows desktop application that protects shared workstations by continuously verifying the authorized user's face through the webcam. If the authorized face is absent or does not match for 5 seconds, the workstation is locked automatically.

Final-year project, BSc Information and Communication Technology, KCA University.

Features
Continuous face verification (Haar Cascade detection + LBPH recognition)
Automatic workstation lock via the Windows API
Live camera feed with confidence score
Multi-angle self-enrollment (front, left, right, up, down)
Username recorded in an activity log, with CSV download
Password-protected disarm and settings (adjustable threshold and timeout)
Modern dark Tkinter interface
Tech stack

Python 3.10, OpenCV (opencv-contrib-python), NumPy, Pillow, Tkinter, PyInstaller.

Setup
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
mkdir data logs
python app.py
Click Enroll User, enter your name and capture the five angles (press SPACE at each).
Click ARM SYSTEM.
Build a standalone .exe
python -m PyInstaller --onefile --windowed --name "BiometricProtectionSystem" --add-data "data;data" app.py
Privacy

Face images and the trained model (data/) stay on your machine and are excluded from this repository by .gitignore. Each user must enroll on their own machine.

Limitations
Windows only
One enrolled user per machine (re-enrolling replaces the model)
Sensitive to lighting conditions
The default admin password (admin123) is hardcoded; change it in Settings or in app.py before real deployment
Not a replacement for strong authentication; LBPH can be fooled by photos (no liveness detection)