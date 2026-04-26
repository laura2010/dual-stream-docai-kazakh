# Dual-Stream Geometric-Linguistic Fusion Architecture

This repository contains the core algorithmic implementation for the paper:  
**"A dual-stream geometric-linguistic fusion architecture for digitising visually complex Kazakh educational materials."**

## Overview
Current Document AI (DocAI) systems exhibit a "Performance Asymmetry" when processing low-resource, agglutinative languages in complex educational layouts. Models that excel at spatial segmentation often hallucinate Cyrillic characters, while highly accurate linguistic models suffer from structural blindness on non-linear content (e.g., tables, diagrams). 

This repository provides the Python implementation of the **Dual-Stream Fusion** algorithm, which deterministically merges the spatial boundaries from a geometric model (the "skeleton") with the morphological tokens of a linguistic model (the "muscle") using a centroid-based inclusion algorithm.

## Repository Contents
* `dual_stream_fusion.py`: The core script containing the centroid-based mapping, tolerance buffering, and intelligent serialization routing.

## Data Availability & Copyright
The raw image files and Ground Truth annotations of the textbooks evaluated in this study are derived from the official digital repository of the Atamura Publishing House (Almaty, Kazakhstan). 

Due to strict copyright restrictions enforced by the publisher, the original pedagogical images cannot be shared publicly in this repository. The dataset is available from the corresponding author upon reasonable request for verification purposes only.

## Usage
The provided script is designed to process and merge the JSON outputs from AWS Textract (Stream A) and Google Cloud Vision (Stream B).



graph TD
    A[Бастапқы мәтін <br> веб-сайттан алынған] --> B
    
    B[Фонологиялық өңдеу <br> және Prosody_text жасау] --> C
    
    C[Piper моделі <br> акустикалық өңдеу] --> D
    
    D([Дайын аудио <br> көру қабілеті нашар адамдарға ұсынылатын нәтиже])

    style A fill:#f9f9f9,stroke:#333,stroke-width:2px
    style B fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
    style C fill:#e8f5e9,stroke:#388e3c,stroke-width:2px
    style D fill:#fff3e0,stroke:#f57c00,stroke-width:2px,stroke-dasharray: 5 5
