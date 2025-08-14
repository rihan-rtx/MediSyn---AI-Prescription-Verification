
# app.py
"""
Streamlit frontend for AI-powered medical prescription verification
Restored to original structure without graph, compatible with provided analysis_history
"""

import streamlit as st
import requests
import logging
from typing import List
import json
import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend API configuration
API_BASE_URL = "http://localhost:8000"

# ---------------------------
# Helper functions
# ---------------------------

def check_api_status() -> bool:
    """Check if backend API is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.RequestException as e:
        logger.error(f"API health check failed: {str(e)}")
        return False

def call_interaction_check_api(prescription_text: str, age: int, weight: float):
    """Call the backend API for interaction checking"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/check_interactions",
            json={
                "prescription_text": prescription_text,
                "age": age,
                "weight": weight
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Interaction check response: {result}")
            return result
        else:
            logger.error(f"API Error: {response.status_code} - {response.text}")
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        st.error("⏰ Request timed out. Please try again.")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to backend API")
        st.error("🔌 Cannot connect to backend API. Please ensure it's running.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        st.error(f"❌ Unexpected error: {str(e)}")
        return None

def call_dosage_check_api(prescription_text: str, age: int, weight: float):
    """Call the backend API for dosage checking"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/check_dosage",
            json={
                "prescription_text": prescription_text,
                "age": age,
                "weight": weight
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"API Error: {response.status_code} - {response.text}")
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        st.error("⏰ Request timed out. Please try again.")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to backend API")
        st.error("🔌 Cannot connect to backend API. Please ensure it's running.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        st.error(f"❌ Unexpected error: {str(e)}")
        return None

def call_alternatives_api(prescription_text: str, age: int, weight: float):
    """Call the backend API for alternative suggestions"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/get_alternatives",
            json={
                "prescription_text": prescription_text,
                "age": age,
                "weight": weight
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"API Error: {response.status_code} - {response.text}")
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error("Request timed out")
        st.error("⏰ Request timed out. Please try again.")
        return None
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to backend API")
        st.error("🔌 Cannot connect to backend API. Please ensure it's running.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        st.error(f"❌ Unexpected error: {str(e)}")
        return None

def display_results_history_tab():
    """Display results history tab without graph"""
    st.header("📊 Results History")
    
    # Initialize session state for history
    if 'analysis_history' not in st.session_state:
        st.session_state.analysis_history = []
    
    if st.session_state.analysis_history:
        st.subheader("Previous Analyses")
        
        for i, record in enumerate(reversed(st.session_state.analysis_history)):
            with st.expander(f"Analysis {len(st.session_state.analysis_history) - i} - {record['timestamp']}"):
                st.write(f"**Prescription:** {record['prescription'][:100]}...")
                st.write(f"**Patient Age:** {record['age']}")
                st.write(f"**Analysis Type:** {record['type']}")
                st.write(f"**Results:**")
                if record['results']:
                    for result in record['results']:
                        st.write(f"- {result}")
                else:
                    st.warning("No interaction results recorded for this analysis.")
    else:
        st.info("No analysis history yet. Run some prescription checks to see results here.")

def display_settings_tab():
    """Display settings tab"""
    st.header("⚙️ Settings")
    
    st.subheader("API Configuration")
    current_api = st.text_input("Backend API URL", value=API_BASE_URL, key="api_url_setting")
    
    st.subheader("Analysis Preferences")
    default_severity = st.selectbox(
        "Default Severity Filter:",
        ["All", "Low", "Moderate", "High", "Critical"],
        index=0,
        key="default_severity"
    )
    
    show_alternatives = st.checkbox(
        "Always show alternative medications",
        value=True,
        key="show_alternatives"
    )
    
    st.subheader("Display Options")
    compact_view = st.checkbox("Compact view", value=False, key="compact_view")
    show_technical_details = st.checkbox("Show technical details", value=False, key="show_tech")
    
    if st.button("Save Settings"):
        st.success("Settings saved successfully!")

# ---------------------------
# Main functions
# ---------------------------

def display_prescription_analysis_tab(api_status: bool):
    """Display the main prescription analysis interface"""
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("🔍 Prescription Information")
        
        prescription_text = st.text_area(
            "Enter Prescription Text:",
            height=150,
            placeholder="Example: Take aspirin 325mg twice daily with food. Also prescribed ibuprofen 200mg as needed for pain.",
            help="Enter the complete prescription text including drug names, dosages, and instructions.",
            key="prescription_input"
        )
        
        col_age, col_weight = st.columns(2)
        with col_age:
            patient_age = st.number_input(
                "Patient Age (years):",
                min_value=0,
                max_value=120,
                value=45,
                help="Patient's age for dosage verification",
                key="age_input"
            )
        
        with col_weight:
            patient_weight = st.number_input(
                "Patient Weight (kg):",
                min_value=1.0,
                max_value=300.0,
                value=70.0,
                help="Patient's weight for dosage verification",
                key="weight_input"
            )
    
    with col2:
        st.header("🛠️ Analysis Tools")
        
        check_interactions_btn = st.button(
            "Check Interactions",
            help="Analyze for drug-drug interactions",
            key="check_inter_btn"
        )
        
        verify_dosage_btn = st.button(
            "Verify Dosage",
            help="Check dosage appropriateness",
            key="verify_dosage_btn"
        )
        
        get_alternatives_btn = st.button(
            "Get Alternatives",
            help="Suggest alternative medications",
            key="get_alt_btn"
        )
    
    # Interaction check
    if check_interactions_btn and prescription_text.strip():
        with st.spinner("🔄 Checking for drug interactions..."):
            result = call_interaction_check_api(prescription_text, patient_age, patient_weight)
            
            if result:
                st.success("✅ Interaction check completed!")
                
                st.subheader("⚠️ Drug Interactions")
                
                if result["status"] == "ok":
                    interactions = result.get("interactions", [])
                    
                    if interactions:
                        # Group interactions by severity for better organization
                        severity_groups = {
                            "MAJOR": [],
                            "MODERATE": [],
                            "MINOR": [],
                            "WARNING": []
                        }
                        
                        for interaction in interactions:
                            severity = interaction.get('severity', 'warning').upper()
                            if severity in severity_groups:
                                severity_groups[severity].append(interaction)
                            else:
                                severity_groups["WARNING"].append(interaction)
                        
                        # Display interactions by severity
                        for severity, interactions in severity_groups.items():
                            if interactions:
                                st.markdown(f"**{severity} Interactions**")
                                for interaction in interactions:
                                    description = interaction.get('description', 'No description available')
                                    recommendations = interaction.get('recommendations', [])
                                    
                                    # Color-coded severity with icons
                                    if severity == 'MAJOR':
                                        color = 'red'
                                        icon = '🚨'
                                    elif severity == 'MODERATE':
                                        color = 'orange'
                                        icon = '⚠️'
                                    elif severity == 'MINOR':
                                        color = 'blue'
                                        icon = 'ℹ️'
                                    else:
                                        color = 'gray'
                                        icon = '❓'
                                    
                                    with st.expander(f":{color}[{icon} {severity} Interaction: {description[:60]}...]"):
                                        st.markdown(f"**Description:** {description}")
                                        if recommendations:
                                            st.markdown("**Recommendations:**")
                                            for rec in recommendations:
                                                st.markdown(f"- {rec}")
                                        else:
                                            st.info("No specific recommendations available.")
                                        # Add visual separator for clarity
                                        st.markdown("---")
                    
                        # Summary metrics
                        st.markdown("**Interaction Summary**")
                        total_interactions = len(interactions)
                        severity_counts = {k: len(v) for k, v in severity_groups.items() if v}
                        for sev, count in severity_counts.items():
                            st.write(f"- {sev}: {count} interaction(s)")
                    
                    else:
                        st.info("✅ No significant interactions found.")
                    
                    # Save to history
                    if 'analysis_history' not in st.session_state:
                        st.session_state.analysis_history = []
                    
                    history_results = []
                    for intx in interactions:
                        rec_str = "; ".join(intx.get('recommendations', []))
                        history_results.append(f"{intx.get('severity', 'unknown').upper()}: {intx.get('description', '')} (Rec: {rec_str})")
                    
                    st.session_state.analysis_history.append({
                        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'prescription': prescription_text,
                        'age': patient_age,
                        'type': 'Interaction Check',
                        'results': history_results
                    })
                else:
                    st.error(f"❌ Interaction check failed: {result.get('message', 'Unknown error')}")
    
    elif check_interactions_btn and not prescription_text.strip():
        st.warning("⚠️ Please enter prescription text before checking interactions.")
    
    # Dosage verification
    if verify_dosage_btn and prescription_text.strip():
        with st.spinner("🔄 Verifying dosages..."):
            result = call_dosage_check_api(prescription_text, patient_age, patient_weight)
            
            if result:
                st.success("✅ Dosage verification completed!")
                
                st.subheader("📏 Dosage Analysis")
                
                if result["status"] == "ok":
                    dosage_analysis = result.get("dosage_analysis", [])
                    recommendations = result.get("recommendations", [])
                    
                    if dosage_analysis:
                        for analysis in dosage_analysis:
                            medicine = analysis.get('medicine', 'Unknown').title()
                            status = analysis.get('status', 'unknown')
                            dosage = analysis.get('prescribed_dosage', 'Not specified')
                            issues = analysis.get('issues', [])
                            
                            with st.expander(f"{medicine}: {status.upper()} ({dosage})"):
                                st.write(f"**Age Group:** {analysis.get('age_group', 'Unknown')}")
                                st.write(f"**Severity:** {analysis.get('severity', 'low').upper()}")
                                if issues:
                                    st.subheader("Issues:")
                                    for issue in issues:
                                        st.write(f"- {issue}")
                                else:
                                    st.info("No issues detected.")
                        st.markdown("---")
                        
                        st.subheader("📋 Recommendations")
                        for rec in recommendations:
                            st.info(rec)
                    else:
                        st.info("No dosage information found in prescription.")
                    
                    # Save to history
                    if 'analysis_history' not in st.session_state:
                        st.session_state.analysis_history = []
                    
                    st.session_state.analysis_history.append({
                        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'prescription': prescription_text,
                        'age': patient_age,
                        'type': 'Dosage Verification',
                        'results': [f"{a.get('medicine', 'Unknown')}: {a.get('status', 'unknown')}" for a in dosage_analysis]
                    })
                else:
                    st.error(f"❌ Dosage verification failed: {result.get('message', 'Unknown error')}")
    
    elif verify_dosage_btn and not prescription_text.strip():
        st.warning("⚠️ Please enter prescription text before verifying dosage.")
    
    # Alternatives
    if get_alternatives_btn and prescription_text.strip():
        with st.spinner("🔄 Finding alternative medications..."):
            result = call_alternatives_api(prescription_text, patient_age, patient_weight)
            
            if result:
                st.success("✅ Alternative analysis completed!")
                
                st.subheader("🔄 Alternative Medication Suggestions")
                
                if result["status"] == "ok":
                    alternatives = result.get("alternatives", [])
                    recommendations = result.get("recommendations", [])
                    
                    if alternatives:
                        for alt in alternatives:
                            original = alt.get("original_medicine", "Unknown")
                            alternative_name = alt.get("alternative_name", "Alternative")
                            reason = alt.get("reason", "No reason specified")
                            dosage = alt.get("suggested_dosage", "Consult prescribing info")
                            
                            with st.expander(f"Alternative to {original.title()}: {alternative_name}"):
                                st.write(f"**Reason:** {reason}")
                                st.write(f"**Suggested Dosage:** {dosage}")
                                st.write(f"**Safety Profile:** {alt.get('safety_profile', 'Consult healthcare provider')}")
                    else:
                        st.info("No specific alternatives found in database. Please consult healthcare provider for alternative options.")
                    
                    if recommendations:
                        st.subheader("📋 General Recommendations")
                        for rec in recommendations:
                            st.info(rec)
                    
                    # Save to history
                    if 'analysis_history' not in st.session_state:
                        st.session_state.analysis_history = []
                    
                    st.session_state.analysis_history.append({
                        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'prescription': prescription_text,
                        'age': patient_age,
                        'type': 'Alternative Suggestions',
                        'results': [f"{a.get('original_medicine', 'Unknown')} -> {a.get('alternative_name', 'Alternative')}" for a in alternatives]
                    })
                else:
                    st.error(f"❌ Alternative search failed: {result.get('message', 'Unknown error')}")
    
    elif get_alternatives_btn and not prescription_text.strip():
        st.warning("⚠️ Please enter prescription text before getting alternatives.")
    
    # API status warning
    if not api_status:
        st.error("⚠️ Backend API is not available. Please start the FastAPI backend server.")
        st.code("python run_backend.py", language="bash")

# ---------------------------
# Main Streamlit App
# ---------------------------

def main():
    """Main Streamlit application"""
    
    st.set_page_config(
        page_title="Medical Prescription Verification",
        page_icon="💊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🏥 AI-Powered Medical Prescription Verification")
    st.markdown("---")
    st.markdown("""
    **Professional medical prescription verification system** powered by AI for checking drug interactions 
    and dosage appropriateness. This tool assists healthcare providers in ensuring patient safety.
    """)
    
    # Sidebar
    with st.sidebar:
        st.header("📋 System Status")
        
        # Check API status
        with st.spinner("Checking backend connection..."):
            api_status = check_api_status()
        
        if api_status:
            st.success("✅ Backend API Connected")
        else:
            st.error("❌ Backend API Disconnected")
            st.warning("Please ensure the FastAPI backend is running on http://localhost:8000")
            
            with st.expander("🔧 Troubleshooting"):
                st.markdown("""
                **To start the backend:**
                1. Open terminal/command prompt
                2. Navigate to your project directory
                3. Run: `python run_backend.py`
                4. Wait for "Application startup complete"
                5. Refresh this page
                """)
        
        st.markdown("---")
        st.header("ℹ️ How to Use")
        st.markdown("""
        1. **Enter Prescription Text**: Input the prescription details
        2. **Specify Patient Age**: For dosage verification
        3. **Check Interactions**: Analyze drug-drug interactions
        4. **Verify Dosage**: Check age-appropriate dosing
        5. **Get Alternatives**: Find alternative medications
        6. **Review Results**: View alerts and recommendations
        """)
        
        st.markdown("---")
        st.header("📊 Quick Stats")
        if 'analysis_history' in st.session_state:
            st.metric("Analyses Performed", len(st.session_state.analysis_history))
        else:
            st.metric("Analyses Performed", 0)
        
        st.markdown("---")
        st.header("⚠️ Disclaimer")
        st.warning("""
        This tool is for educational and assistive purposes only. 
        Always consult with qualified healthcare professionals for medical decisions.
        """)
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["🔍 Prescription Analysis", "📊 Results History", "⚙️ Settings"])
    
    with tab1:
        display_prescription_analysis_tab(api_status)
    
    with tab2:
        display_results_history_tab()
    
    with tab3:
        display_settings_tab()
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray;'>
        Medical Prescription Verification System v1.0.0<br>
        For educational and research purposes only
        </div>
        """, 
        unsafe_allow_html=True
    )

# ---------------------------
# Entry point
# ---------------------------
if __name__ == "__main__":
    main()
