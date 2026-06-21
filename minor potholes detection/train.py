from ultralytics import YOLO

# Load YOLOv11 base model
model = YOLO("yolo11n.pt")

# Train YOLOv11 on pothole dataset
model.train(
    data="pothole.v18i.yolov11/data.yaml",
    epochs=30,
    imgsz=640,
    batch=8,
    device="cpu"
)
