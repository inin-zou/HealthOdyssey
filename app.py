import os
import time
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

year_input = datetime.today().year

# -------------------------------
# Functions
# -------------------------------

def get_zone_geographique(url):
    """
    Request the recall detail page and extract the region information corresponding to "Zone géographique de vente".
    """
    try:
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"Error fetching details for URL: {url} (status code: {resp.status_code})")
            return ""
        detail_soup = BeautifulSoup(resp.text, "html.parser")
        for li in detail_soup.find_all("li", class_="product-desc-item"):
            carac = li.find("span", class_="carac")
            if carac and "Zone géographique de vente" in carac.get_text(strip=True):
                val = li.find("span", class_="val")
                if val:
                    return val.get_text(strip=True)
        return ""
    except Exception as e:
        print(f"Error scraping zone for {url}: {e}")
        return ""

def fetch_recalls():
    """
    Scrape recall records from rappel.conso.gouv.fr (e.g., the Viandes category page), 
    and filter records from the last 7 days.
    Also, for each record, scrape the detail page to obtain the region information (zone).
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

        # "Risks" & "Reason"
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

        # Skip if the date is missing or not within the last 7 days
        if not record_date or not (START_DATE <= record_date <= TODAY):
            continue

        # Get the "Zone géographique de vente" from the detail page
        zone = get_zone_geographique(full_link)
        # Pause briefly to avoid making requests too rapidly
        time.sleep(0.5)

        recalls.append({
            "date": date_text,
            "title": title,
            "maker": maker,
            "risks": risks,
            "motif": motif,
            "link": full_link,
            "zone": zone
        })
    return recalls

def count_region_occurrences_last_week(records, region_input):
    """
    Count the number of times the specified region_input appears in the records from the last week.
    Parameters:
      records: List of dictionaries containing recall records, each record should have "date" and "zone" fields.
      region_input: The region string to count occurrences of.
    Returns:
      The number of occurrences of the specified region in the last week.
    """
    count = 0
    now = datetime.now()
    one_week_ago = now - timedelta(days=7)
    
    for record in records:
        date_str = record.get("date", "")
        try:
            record_date = datetime.strptime(date_str, "%d/%m/%Y %H:%M:%S")
        except Exception as e:
            print(f"Failed to parse date format: {date_str}, error: {e}")
            continue
        
        if one_week_ago <= record_date <= now:
            # Use substring matching to determine if the region matches
            if region_input in record.get("zone", ""):
                count += 1
    return count

def analyze_with_mistral(article_text):
    """
    Use the Mistral model to analyze the recall text and assign a food safety risk score (0-100).
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

def get_recall_ratings(progress_bar=None, recalls=None):
    """
    Use Mistral to score recall records and return a DataFrame.
    If recalls are provided, use that list; otherwise, call fetch_recalls().
    """
    if recalls is None:
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

def load_tpot_model():
    """
    Load the pre-trained TPOT model and the associated LabelEncoder (if available).
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
    
    # Progress bar
    progress_text = st.empty()
    progress_text.write("Fetching recalls from rappel.conso.gouv.fr and analyzing food safety risks with Mistral AI...")
    progress_bar = st.progress(0)
    
    # First, fetch raw recall records (including zone information)
    recalls = fetch_recalls()
    # Then, use these records to score with Mistral, generating a DataFrame
    df = get_recall_ratings(progress_bar=progress_bar, recalls=recalls)
    
    progress_text.empty()
    progress_bar.empty()
    
    # Calculate overall safety index
    if df.empty:
        avg_index = 100
    else:
        df_valid = df[df["score"] != "Error"]
        avg_index = df_valid["score"].mean() if not df_valid.empty else 100
    
    st.subheader(f"📊 National Overall Meat Safety Index (Last Week): {avg_index:.2f} / 100")
    
    # Gauge indicator chart
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
    
    # Display all recall records
    if not df.empty:
        st.subheader("📢 Detailed Recall Records")
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
    st.subheader("🔍 Prediction with our Model (Version beta)")
    st.markdown("Enter features below to predict using the pre-trained model.")

    # Load model and encoder
    tpot_model, region_label_encoder = load_tpot_model()
    
    if tpot_model is not None and region_label_encoder is not None:
        # Get the list of all region labels used during training
        valid_regions = region_label_encoder.classes_
        
        # User selects region (dropdown menu)
        region_input = st.selectbox("Region", options=valid_regions, index=0)
        uhii_input = st.number_input("UHII", min_value=0.0, max_value=100.0, value=2.5)
        co2_input = st.number_input("CO2", min_value=0.0, max_value=1e6, value=500.0)
        
        # Using previously scraped recall records, count occurrences of the selected region
        occurrence_count = count_region_occurrences_last_week(recalls, region_input)
        count_risk_input = occurrence_count*52.14

        if st.button("Predict with TPOT Model"):
            # Encode region
            region_encoded = region_label_encoder.transform([region_input])[0]
            
            # Feature order must match the training order
            features = [[
                region_encoded,
                year_input,
                count_risk_input,
                uhii_input,
                co2_input
            ]]
            
            # Call the model
            prediction = tpot_model.predict(features)
            # Compute the predicted value (e.g., divide the prediction by 52.14 and round)
            prediction_rounded = int(round(prediction[0] / 52.14))
            
            st.info(f"In the last week, region **{region_input}** appeared in **{occurrence_count}** recall records.")
            st.success(f"Prediction for Number of Consultation in {region_input} next week on Doctolib is {prediction_rounded}")
    
    else:
        st.warning("TPOT model or region_label_encoder was not loaded successfully, unable to make predictions.")

if __name__ == "__main__":
    main()
