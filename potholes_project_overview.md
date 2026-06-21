# Smart Pothole Detection & Route Planning Platform

## 📌 Project Overview
The **Smart Pothole Detection & Route Planning Platform** is an enterprise-grade AI solution designed for infrastructure monitoring and intelligent navigation. By leveraging state-of-the-art computer vision models and geographic information systems (GIS), the platform detects road hazards, logs their exact geographic coordinates, and provides drivers with the safest possible routes.

The application features a strictly professional **Sky Blue & White** UI/UX design, making it suitable for government command centers, municipal corporations, or commercial fleet management operations.

---

## 🚀 Key Features

### 1. AI Detection Pipelines
The platform utilizes **YOLOv11** (You Only Look Once) for highly accurate and fast pothole detection across three distinct mediums:
*   **Image Detection:** Upload road images for instant inference. Features **Smart Location Resolution** that automatically extracts embedded EXIF GPS data from photos or allows manual map pinning.
*   **Video Detection:** Upload dashcam footage (MP4/AVI/MOV) for frame-by-frame analysis. Supports **GPX track integration** to sync video frames with real-world geographic coordinates automatically.
*   **Live Camera Detection:** Uses WebRTC to process live webcam feeds in real-time, instantly logging detected potholes into the active database without storing the video stream.

### 2. GIS & Telemetry (Mapping)
*   **Live Pothole Map:** An interactive, light-themed map (CartoDB Positron) displaying all active potholes. Features clustering, severity-based color coding (High, Medium, Low), and a dynamic heatmap layer to identify critical road segments.
*   **Smart Route Planner:** A revolutionary navigation tool powered by OSRM. Users enter a start and destination, and the system fetches possible driving routes. It then **scores each route** against the active pothole database, highlighting the safest recommended route and providing a segment-by-segment breakdown of road conditions.

### 3. Analytics & Dashboard
*   **Home Dashboard:** Provides at-a-glance KPIs including Total Scans, Active vs. Resolved hazards, Resolution Rates, and System Health.
*   **Interactive Charts:** Clean, white-themed Plotly charts displaying detection trends over time and media type breakdowns.
*   **Detection History:** A comprehensive, tabular log of all historical detections that can be filtered by date, type, or severity, and exported to **CSV or JSON**.

### 4. Hazard Management
*   **Pothole Management System:** An administrative tool to oversee the database. Users can update the status of repaired potholes from "Active" to "Resolved" (removing them from the live map and route planner) or delete false positives.
*   **System Health Check:** A dedicated diagnostics page that verifies YOLO model weights, SQLite database integrity, and critical system dependencies.

---

## 🛠️ Technology Stack
*   **Frontend / Web Framework:** [Streamlit](https://streamlit.io/) (Python)
*   **Computer Vision:** [Ultralytics YOLOv11](https://docs.ultralytics.com/)
*   **Database:** SQLite (Local persistent storage)
*   **Mapping & GIS:** [Folium](https://python-visualization.github.io/folium/) (Leaflet.js) & OSRM (Open Source Routing Machine)
*   **Data Visualization:** [Plotly](https://plotly.com/python/) & Pandas
*   **Real-time Video:** `streamlit-webrtc`
*   **UI/UX:** Custom CSS (Inter & Poppins typography, Light Mode Design System)

---

## 🎨 Design Philosophy
The application deliberately avoids "hackathon" aesthetics. It features a corporate **Sky Blue (`#0EA5E9`) and White** design system with:
*   No emojis or cluttered icons.
*   Clean, minimalist metric cards with soft shadows.
*   A fully responsive layout that works across desktop and tablet displays.
*   Strict light-mode enforcement for maximum readability in professional environments.
