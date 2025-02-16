---

# OneHealth Early Warning

This repository hosts the **OneHealth Early Warning** dashboard and the underlying model that forecasts the potential impact on public health based on food safety recalls (meat products), environmental factors, and regional indicators. The project demonstrates a **One Health** approach by integrating human, animal, and environmental health data to provide early warnings and insights.

---

## Table of Contents

1. [Overview](#overview)  
2. [Key Features](#key-features)  
3. [Data & Modeling](#data--modeling)  
4. [Installation](#installation)  
5. [Usage](#usage)  
6. [Project Structure](#project-structure)  
7. [Contributing](#contributing)  
8. [License](#license)  

---

## Overview

- **Goal**: Provide a unified platform to track and predict the impact of meat product recalls (food safety) in different French regions, alongside environmental indicators such as the Urban Heat Island Index (UHII) and CO₂ emissions.  
- **Why One Health?**: The One Health concept recognizes that the health of humans, animals, and the environment are interconnected. By analyzing food safety events (animal health), environmental factors, and human health outcomes (e.g., medical consultations), we can build more holistic predictive models and early warning systems.

The web-based dashboard shows:
1. A **National Overall Meat Safety Index** (Last Week).  
2. A **Detailed Recall Records** section.  
3. A **Predictive Model** interface (beta) that allows users to select a region and input UHII/CO₂ to forecast future consultations or potential health impacts.

---

## Key Features

1. **Interactive Dashboard**  
   - Displays a gauge chart representing the Overall Food Safety Index (0–100 scale).  
   - Provides a list of detailed recall records for the past weeks.

2. **Predictive Model (Beta)**  
   - Users can select a region and specify environmental indicators (UHII, CO₂).  
   - A pretrained TPOT model runs behind the scenes to predict a health metric (e.g., future consultations or total_CS).

3. **One Health Approach**  
   - Integrates multi-domain data: Meat recalls (animal/food), environment (UHII, CO₂), and human health outcomes.

---

## Data & Modeling

1. **Data Sources**  
   - **Meat Recall Events**: Aggregated from regional recall databases.  
   - **Environmental Factors**: UHII (Urban Heat Island Index) and CO₂ emissions data.  
   - **Human Health Outcomes**: Number of consultations or relevant public health data (labeled as `total_CS`).

2. **Modeling Workflow**  
   - We use a **TPOT (Tree-based Pipeline Optimization Tool)** approach for AutoML, automatically selecting and tuning the best regression pipeline for predicting `total_CS`.  
   - Training includes cross-validation (e.g., RepeatedKFold with 5 splits) for small-sample robustness.  
   - The final pipeline is exported and loaded in the dashboard for on-the-fly predictions.

3. **Key Variables**  
   - **`region`** (categorical)  
   - **`year`** (numerical or categorical)  
   - **`count_risk`** (number of meat recalls in a past period)  
   - **`UHII`** (environmental factor)  
   - **`CO2`** (environmental factor)  
   - **`total_CS`** (target: number of consultations or health metric)

---

## Installation

Below is a generic guide. Adapt for your environment (conda, pipenv, Docker, etc.).

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YourUsername/onehealth-early-warning.git
   cd onehealth-early-warning
   ```
2. **Create and activate a virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate   # macOS/Linux
   # or
   venv\Scripts\activate      # Windows
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   Make sure that `xgboost`, `tpot`, and other required libraries are installed.

4. **Set up environment variables** (if needed):
   - Create a `.env` file or export variables for any API keys or environment configurations.

---

## Usage

1. **Run the Dashboard**  
   ```bash
   python app.py
   ```
   - This should start a local server (e.g., http://127.0.0.1:5000) hosting the dashboard.
2. **Access the Dashboard**  
   - Open your web browser and go to the provided URL to view the OneHealth Early Warning interface.
3. **Interact with the Model**  
   - Under “Prediction with our Model (Version beta)”, select a region and input UHII/CO₂ values.  
   - Click **Predict with TPOT Model** to see the forecasted metric.

---

*Thank you for using the OneHealth Early Warning Dashboard! Together, let’s harness the power of data to improve the health of people, animals, and our environment.*