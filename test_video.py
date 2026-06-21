from ultralytics import YOLO
import cv2

# Load trained YOLOv11 model
model = YOLO("runs/detect/train4/weights/best.pt")

# Input and output video paths
input_video = "potholes video.mp4"
output_video = "output_test_video.mp4"

# Open input video
cap = cv2.VideoCapture(input_video)

if not cap.isOpened():
    print("Error: Unable to open video file")
    exit()

# Get video properties
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)

# Create output video writer
out = cv2.VideoWriter(
    output_video,
    cv2.VideoWriter_fourcc(*'mp4v'),
    fps,
    (width, height)
)

print("Video testing started...")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Run YOLOv11 detection
    results = model(frame, conf=0.4)

    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            confidence = float(box.conf[0])

            # Draw bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

            # Display label
            cv2.putText(
                frame,
                f"Pothole {confidence:.2f}",
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

    out.write(frame)

cap.release()
out.release()

print("Video testing completed successfully")
print("Output saved as output_test_video.mp4")
