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
![Main menu](media/main_menu.png)

### Team jersey color selection
The user manually defines team and goalkeeper jersey colors to improve classification accuracy.
![Team colors](media/team_color_selection.png)

### Analysis in progress
During this stage, the system performs detection, tracking, and pitch mapping.
![Loading](media/analysis_loading.png)

### Analysis and replay view
The replay view allows interactive exploration of the analyzed match fragment, including visual overlays and spatial analytics.
![Analysis preview](media/analysis_preview.gif)


