# ----------------------------------------
# Pothole Detection using YOLOv11 + OpenCV
# ----------------------------------------

from ultralytics import YOLO
import cv2

# Load YOLOv11 model
model = YOLO("yolo11n.pt")

# Input video
video_path = "potholes video.mp4"
cap = cv2.VideoCapture(video_path)

# Check video
if not cap.isOpened():
    print("❌ Video file open nahi ho rahi")
    exit()

# Video properties
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)

# Output video writer
out = cv2.VideoWriter(
    "output_video.mp4",
    cv2.VideoWriter_fourcc(*'mp4v'),
    fps,
    (width, height)
)

# Frame by frame processing
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # YOLOv11 detection
    results = model(frame, conf=0.4)

    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2),
                          (0, 0, 255), 2)

            # Label
            cv2.putText(
                frame,
                f"Pothole {conf:.2f}",
                (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

    out.write(frame)

# Release resources
cap.release()
out.release()

print("✅ Pothole detection completed successfully!")
