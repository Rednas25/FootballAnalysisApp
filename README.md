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

## How to Run
I created exe file to make it easy to test program so you just need to download it and start by clicking icon.


Link: https://drive.google.com/file/d/1Fiizyoj52dJz0ADsAYmtcRvO-ofgqtGr/view?usp=sharing


The `_internal` folder contains all required resources needed to run the application, including external libraries, YOLO models, and the configuration file, which can be modified to adjust project settings.

## Limitations
- The system is designed for the analysis of short match fragments rather than full 90-minute games
- Best results are achieved under limited occlusions and moderate player density
- Team jersey color classification requires manual initialization
- The analysis process is computationally intensive due to the chosen system architecture; the use of a CUDA-enabled GPU is therefore recommended
For a more detailed discussion of these limitations and their underlying reasons, please refer to the engineering thesis.

## Future Work / Project State

At this stage, no further development of the project is planned.

Shortly after the completion of this work, a new generation of segmentation models, such as **SAM-3 (Segment Anything Model)**, was introduced.  
These models significantly change the landscape of visual understanding by enabling prompt-based, training-free object segmentation, which will probably open new possibilities for sports video analysis. 
I can't wait to see the results of other projects that will apply this new technology in a sports environment.

I plan to explore and test SAM-3-based approaches in a separate future projects, rather than extending this one. 

If you would like to learn more about this project, including its internal design and detailed results - I strongly recommend to check my engineering thesis.  
The document will be linked here in the future once it has been formally approved.
23.01.2026 – I successfully defended my engineering thesis. You can find it at the link below, but for now it is available only in Polish.


[Kacper_Sieczko_praca_inżynierska.pdf](https://github.com/user-attachments/files/24913203/Kacper_Sieczko_praca_inzynierska.pdf)



