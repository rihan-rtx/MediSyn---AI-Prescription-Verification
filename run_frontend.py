# frontend.py
import streamlit as st
import requests

API_BASE_URL = "http://localhost:8000"  # Backend URL

st.set_page_config(page_title="Medicine Interaction Checker")
st.title("💊 Medicine Interaction Checker")

# Input fields
prescription_text = st.text_area("Enter Prescription Text", height=150)
patient_age = st.number_input("Patient Age", min_value=0, max_value=120, step=1)
patient_weight = st.number_input("Patient Weight (kg)", min_value=0.0, step=0.1)

if st.button("Check Interactions"):
    if not prescription_text.strip():
        st.warning("Please enter a prescription first.")
    else:
        with st.spinner("Checking interactions..."):
            try:
                resp = requests.post(
                    f"{API_BASE_URL}/check_interactions",
                    json={
                        "prescription_text": prescription_text,
                        "age": patient_age,
                        "weight": patient_weight
                    }
                )
                if resp.status_code == 200:
                    result = resp.json()
                    st.success("Interaction check complete ✅")
                    for interaction in result["interactions"]:
                        st.write(f"- {interaction}")
                else:
                    st.error(f"Backend error: {resp.text}")
            except Exception as e:
                st.error(f"Request failed: {e}")