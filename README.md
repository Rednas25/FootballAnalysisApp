## Project Overview

This project presents an attempt to create an automated application for analyzing video recordings from football matches, based on modern **image processing** and **machine learning** techniques.

The application allows the analysis of shorter match segments that are free from significant occlusions and dense player clusters.  
The user receives an analyzed match fragment with **descriptive, interactive labels** assigned to individual players, along with the ability to generate:
- Average position maps  
- Activity (heat) maps  


## Project Background & Motivation

This project was developed as an **engineering thesis** at **Wrocław University of Science and Technology**, during the **7th semester** of the **Telecommunications and Informatics** program.

The main motivation behind the project was a strong interest in:
- **Machine learning**, **Computer vision**
- **Sports analytics**, particularly football

This project was strongly inspired by the videos and open-source repositories created by Piotr Skalski, which demonstrated the feasibility of building practical applications in the field of football video analysis and motivated me to select this topic for my thesis.

So check this out:
- https://github.com/roboflow/sports
- https://www.youtube.com/watch?v=aBVGKoNZQUw

These are not the only works from which I drew knowledge and inspiration. All materials reviewed during the development of this project are included in the bibliography of the engineering thesis, which is linked at the bottom of this README.
## 🔑 Features

- Automatic detection of players, goalkeepers, and referees
- Team classification based on jersey color analysis
- Pitch keypoint detection and homography estimation for 2D mapping
- Player tracking across video frames
- Interactive replay system with timeline control
- Average position maps for tactical analysis (for teams)
- Activity (heat) maps based on player movement  (for whole teams and individual players)
- Desktop GUI built with PySide6 and QML

## Application Preview 
The following screenshots and recordings present the complete workflow of the application — from loading a match recording to generating advanced visual analytics.

### Main application screen
![gui_2_but](https://github.com/user-attachments/assets/30843fdd-77ca-4a15-97d8-f27a8ebb49e9)

### Team jersey color selection
The user manually defines team and goalkeeper jersey colors by drawing bounding boxes over representative shirt regions, which serve as input for the jersey color classification process.


![wybór koloru drużyn 1](https://github.com/user-attachments/assets/0271b6e4-d995-452b-9740-9b1393149324)
![wyboru koloru drużyny 2](https://github.com/user-attachments/assets/407381dd-aa99-43a3-a250-f32c96e3dcad)

### Analysis in progress
During this stage, the system performs detection, tracking, and pitch mapping.  The user can enable either **2D** or **3D** previews of detections and team classifications.


![loading_screen](https://github.com/user-attachments/assets/43eca2b0-4c1c-4431-852a-488902228663)

### Analysis and replay view
The replay view allows interactive exploration of the analyzed match fragment, including visual overlays and generating analytics like heatmaps.


https://github.com/user-attachments/assets/1bcf3234-f937-426b-817d-81bd73be44e2


https://github.com/user-attachments/assets/d24c3d01-dcc5-4956-8c42-3e64314ab618


