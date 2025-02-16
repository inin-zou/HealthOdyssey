import os
from dotenv import load_dotenv
import streamlit as st
import requests
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from mistralai import Mistral

import joblib  # For loading the model and LabelEncoder

# -------------------------------
# Configuration
# -------------------------------

load_dotenv()

# Example: Mistral Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
client = Mistral(api_key=MISTRAL_API_KEY)
model_mistral = "mistral-large-latest"

# RAPPEL Website Configuration
RAPPEL_URL = "https://rappel.conso.gouv.fr/categorie/94/1"

# Define time range: Last 7 days
TODAY = datetime.today()
START_DATE = TODAY - timedelta(days=7)

# -------------------------------
# Functions
# -------------------------------

def fetch_recalls():
    """
    Fetch recall records from rappel.conso.gouv.fr (e.g., Viandes category page)
    and filter records published in the last 7 days.
    """
    recalls = []
    response = requests.get(RAPPEL_URL)
    if response.status_code != 200:
        st.error(f"Unable to fetch recall data, status code: {response.status_code}")
        return recalls

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.find_all("li", class_="product-item")
    if not items:
        st.warning("No recall records found, please check the page structure or URL.")
        return recalls

    for li in items:
        # Title and link
        title_tag = li.find("a", class_="product-link")
        title = title_tag.get_text(strip=True) if title_tag else "No Title"
        link = title_tag["href"] if (title_tag and title_tag.has_attr("href")) else ""
        full_link = link if link.startswith("http") else "https://rappel.conso.gouv.fr" + link

        # Manufacturer
        maker_tag = li.find("p", class_="product-maker")
        maker = maker_tag.get_text(strip=True) if maker_tag else ""

        # "Risques" & "Motif"
        desc_div = li.find("div", class_="product-desc")
        risks, motif = "", ""
        if desc_div:
            desc_items = desc_div.find_all("div", class_="product-desc-item")
            if len(desc_items) >= 1:
                risks = desc_items[0].get_text(strip=True).replace("Risques : ", "")
            if len(desc_items) >= 2:
                motif = desc_items[1].get_text(strip=True).replace("Motif : ", "")

        # Date
        date_tag = li.find("p", class_="text-muted product-date")
        date_text = ""
        if date_tag:
            time_tag = date_tag.find("time")
            if time_tag and time_tag.has_attr("datetime"):
                date_text = time_tag["datetime"]  # e.g. "14/02/2025 15:43:31"

        # Parse date
        record_date = None
        if date_text:
            try:
                record_date = datetime.strptime(date_text, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                pass

        # If date is missing or not within the last 7 days, skip it
        if not record_date or not (START_DATE <= record_date <= TODAY):
            continue

        recalls.append({
            "date": date_text,
            "title": title,
            "maker": maker,
            "risks": risks,
            "motif": motif,
            "link": full_link
        })
    return recalls

def analyze_with_mistral(article_text):
    """
    Call the Mistral model to analyze the recall text risk score (0-100).
    """
    prompt_system = (
        "You are a food safety expert. You will receive a recall announcement in French. "
        "Determine how risky it is in terms of food safety, from 0 to 100. "
        "0 means extremely dangerous; 100 means perfectly safe or irrelevant. "
        "Output ONLY the integer (no additional text)."
    )
    
    prompt_user = f"{article_text}\n\nOutput the risk score (0-100) only."
    
    try:
        response = client.chat.complete(
            model=model_mistral,
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": prompt_user}
            ],
            tool_choice="any"
        )
        score_str = response.choices[0].message.content.strip()
        score = int(score_str)
        return score
    except Exception as e:
        print(f"[Error] Mistral API Error or parse error: {str(e)}")
        return 100

def get_recall_ratings(progress_bar=None):
    """
    Fetch recall records and score them with Mistral,
    returning a DataFrame.
    """
    recalls = fetch_recalls()
    data = []
    
    if progress_bar:
        progress_bar.progress(10)
    
    total = len(recalls)
    step = 90 / total if total else 90
    
    for i, recall in enumerate(recalls):
        full_text = f"{recall['title']}. Risks: {recall['risks']}. Motif: {recall['motif']}"
        score = analyze_with_mistral(full_text)
        data.append({
            "date": recall["date"],
            "title": recall["title"],
            "link": recall["link"],
            "score": score
        })
        if progress_bar:
            current_progress = 10 + int(step * (i + 1))
            progress_bar.progress(min(current_progress, 100))
    
    return pd.DataFrame(data)

# -------------------------------
# TPOT Model Loading
# -------------------------------

def load_tpot_model():
    """
    Load the pre-trained TPOT model and associated LabelEncoder (if available).
    """
    model = None
    label_encoder = None
    
    try:
        model = joblib.load("tpot_model.pkl")
        label_encoder = joblib.load("region_label_encoder.pkl")
    except Exception as e:
        st.error(f"Unable to load TPOT model or LabelEncoder: {e}")
    
    return model, label_encoder

# -------------------------------
# Streamlit App
# -------------------------------

def main():
    st.title("🇫🇷 OneHealth Early Warning")
    
    # Progress bar message
    progress_text = st.empty()
    progress_text.write("Fetching recalls from rappel.conso.gouv.fr and analyzing food safety risks with Mistral AI...")
    progress_bar = st.progress(0)
    
    # Fetch recall records and score them with Mistral
    df = get_recall_ratings(progress_bar=progress_bar)
    
    # Clear progress bar
    progress_text.empty()
    progress_bar.empty()
    
    # Calculate overall safety index
    if df.empty:
        avg_index = 100
    else:
        df_valid = df[df["score"] != "Error"]
        avg_index = df_valid["score"].mean() if not df_valid.empty else 100
    
    st.subheader(f"📊 National Overall Meat Safety Index (Last Week): {avg_index:.2f} / 100")
    
    # Gauge chart
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=avg_index,
        title={'text': "Overall Food Safety Index"},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "green"},
            'steps': [
                {'range': [0, 50], 'color': "red"},
                {'range': [50, 80], 'color': "yellow"},
                {'range': [80, 100], 'color': "green"}
            ]
        }
    ))
    st.plotly_chart(fig)
    
    # Display all recall records in one expander
    if not df.empty:
        st.subheader("📢 Detailed Recall Records (Last Week)")
        with st.expander("View All Recall Details"):
            for _, row in df.iterrows():
                st.write(f"**Title:** {row['title']}")
                st.write(f"**Risk Score:** {row['score']} / 100")
                st.write(f"**Published on:** {row['date']}")
                st.markdown(f"**[Read More]({row['link']})**")
                st.markdown("---")
    else:
        st.info("No recall records found in the last week.")

    # ---------------------------------------
    # Manual Prediction with TPOT Model
    # ---------------------------------------
    st.subheader("🔍 Manual Prediction with our Model")
    st.markdown("Enter features below to predict using the pre-trained model.")

    # Load model and encoder
    tpot_model, region_label_encoder = load_tpot_model()
    
    if tpot_model is not None and region_label_encoder is not None:
        # Retrieve the list of all region labels seen during training
        valid_regions = region_label_encoder.classes_
        
        # Allow the user to select a region from the dropdown instead of entering it manually
        region_input = st.selectbox("Region", options=valid_regions, index=0)
        
        year_input = st.number_input("Year", min_value=1900, max_value=2100, value=2023, step=1)
        count_risk_input = st.number_input("count_risk", min_value=0, max_value=1000000, value=100, step=1)
        uhii_input = st.number_input("UHII", min_value=0.0, max_value=100.0, value=2.5)
        co2_input = st.number_input("CO2", min_value=0.0, max_value=1e6, value=500.0)
        
        if st.button("Predict with TPOT Model"):
            # Encode region
            region_encoded = region_label_encoder.transform([region_input])[0]
            
            # Features order must be consistent with training
            features = [[
                region_encoded,
                year_input,
                count_risk_input,
                uhii_input,
                co2_input
            ]]
            
            # Call the model
            prediction = tpot_model.predict(features)
            
            # Convert prediction to integer (rounded)
            prediction_rounded = int(round(prediction[0]/52.14))
            
            # Display the integer output
            st.success(f"Prediction for Nomber of Consultation in {region_input} next week on Doctolib is {prediction_rounded}")
    
    else:
        st.warning("TPOT model or region_label_encoder was not loaded successfully, unable to make predictions.")


if __name__ == "__main__":
    main()
