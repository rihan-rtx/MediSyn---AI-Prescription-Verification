# medical_chatbot.py
"""
AI-Powered Medical Prescription Verification Chatbot
Interactive Streamlit interface with conversational AI capabilities
"""

import streamlit as st
import requests
import json
import logging
from typing import Dict, List, Any, Optional
import datetime
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Backend API configuration
API_BASE_URL = "http://localhost:8000"

class MedicalChatbot:
    """Medical prescription verification chatbot"""
    
    def __init__(self):
        self.session_state_keys = [
            'chat_history', 'current_prescription', 'patient_age', 
            'patient_weight', 'chat_mode', 'pending_analysis'
        ]
        self.init_session_state()
        
    def init_session_state(self):
        """Initialize session state variables"""
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
            st.session_state.current_prescription = ""
            st.session_state.patient_age = 45
            st.session_state.patient_weight = 70.0
            st.session_state.chat_mode = "greeting"
            st.session_state.pending_analysis = None
            
            # Add welcome message
            self.add_message("assistant", 
                "👋 Hello! I'm your AI medical prescription assistant. I can help you:\n\n"
                "• Check for drug interactions\n"
                "• Verify dosage appropriateness\n"
                "• Find alternative medications\n"
                "• Provide safety recommendations\n\n"
                "To get started, please tell me about the prescription you'd like me to analyze."
            )
    
    def add_message(self, role: str, content: str, metadata: Dict = None):
        """Add a message to chat history"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now(),
            "metadata": metadata or {}
        }
        st.session_state.chat_history.append(message)
    
    def check_api_status(self) -> bool:
        """Check if backend API is running"""
        try:
            response = requests.get(f"{API_BASE_URL}/health", timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def extract_prescription_info(self, user_input: str) -> Dict[str, Any]:
        """Extract prescription information from user input"""
        info = {
            'has_prescription': False,
            'medicines': [],
            'age_mentioned': None,
            'weight_mentioned': None,
            'dosages': []
        }
        
        # Look for medicine names and dosages
        medicine_pattern = r'\b([a-zA-Z]+)\s*(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|units?)\b'
        matches = re.findall(medicine_pattern, user_input, re.IGNORECASE)
        
        if matches:
            info['has_prescription'] = True
            for medicine, dose, unit in matches:
                info['medicines'].append(medicine.lower())
                info['dosages'].append(f"{dose}{unit}")
        
        # Look for common medicine names without dosages
        common_medicines = ['aspirin', 'ibuprofen', 'acetaminophen', 'warfarin', 'metformin', 'insulin', 'lisinopril']
        for med in common_medicines:
            if med in user_input.lower() and med not in info['medicines']:
                info['medicines'].append(med)
                info['has_prescription'] = True
        
        # Look for age mentions
        age_pattern = r'\b(?:age|years?|yo)\s*:?\s*(\d+)|(\d+)\s*(?:years?\s*old|yo)\b'
        age_match = re.search(age_pattern, user_input, re.IGNORECASE)
        if age_match:
            info['age_mentioned'] = int(age_match.group(1) or age_match.group(2))
        
        # Look for weight mentions
        weight_pattern = r'\b(?:weight|weighs?)\s*:?\s*(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)\b|(\d+(?:\.\d+)?)\s*kg\b'
        weight_match = re.search(weight_pattern, user_input, re.IGNORECASE)
        if weight_match:
            info['weight_mentioned'] = float(weight_match.group(1) or weight_match.group(2))
        
        return info
    
    def determine_intent(self, user_input: str) -> str:
        """Determine user intent from input"""
        input_lower = user_input.lower()
        
        # Check for specific analysis requests
        if any(word in input_lower for word in ['interact', 'interaction', 'combine', 'together']):
            return 'check_interactions'
        elif any(word in input_lower for word in ['dosage', 'dose', 'amount', 'how much']):
            return 'check_dosage'
        elif any(word in input_lower for word in ['alternative', 'substitute', 'replace', 'different']):
            return 'get_alternatives'
        elif any(word in input_lower for word in ['help', 'what can you do', 'guide']):
            return 'help'
        elif any(word in input_lower for word in ['prescription', 'medicine', 'medication', 'drug', 'pill']):
            return 'prescription_input'
        else:
            return 'general'
    
    def format_interaction_results(self, results: Dict) -> str:
        """Format interaction check results for chat display"""
        if not results or results.get('status') != 'ok':
            return "❌ Sorry, I couldn't analyze the interactions. Please try again."
        
        interactions = results.get('interactions', [])
        if not interactions:
            return "✅ No significant interactions found in your prescription."
        
        response = f"🔍 **Interaction Analysis Results:**\n\n"
        
        # Group by severity
        severity_groups = {'major': [], 'moderate': [], 'minor': [], 'info': [], 'warning': []}
        for interaction in interactions:
            severity = interaction.get('severity', 'minor').lower()
            if severity in severity_groups:
                severity_groups[severity].append(interaction)
        
        # Display by severity
        severity_emojis = {
            'major': '🚨', 'moderate': '⚠️', 'minor': 'ℹ️', 
            'info': '💡', 'warning': '⚠️'
        }
        
        for severity, items in severity_groups.items():
            if items:
                response += f"\n**{severity_emojis.get(severity, '•')} {severity.upper()} ALERTS:**\n"
                for i, interaction in enumerate(items, 1):
                    description = interaction.get('description', 'No description available')
                    recommendations = interaction.get('recommendations', [])
                    
                    response += f"{i}. {description}\n"
                    if recommendations:
                        response += f"   **Recommendations:** {'; '.join(recommendations[:2])}\n"
                    response += "\n"
        
        response += "\n💡 **Remember:** Always consult your healthcare provider before making any changes to your medication regimen."
        return response
    
    def format_dosage_results(self, results: Dict) -> str:
        """Format dosage check results for chat display"""
        if not results or results.get('status') != 'ok':
            return "❌ Sorry, I couldn't analyze the dosages. Please try again."
        
        dosage_analysis = results.get('dosage_analysis', [])
        recommendations = results.get('recommendations', [])
        
        if not dosage_analysis:
            return "ℹ️ No dosage information found in your prescription."
        
        response = "💊 **Dosage Analysis Results:**\n\n"
        
        for analysis in dosage_analysis:
            medicine = analysis.get('medicine', 'Unknown')
            status = analysis.get('status', 'unknown')
            prescribed_dosage = analysis.get('prescribed_dosage', 'Not specified')
            issues = analysis.get('issues', [])
            
            # Status emoji
            status_emoji = "✅" if status == "appropriate" else "⚠️"
            
            response += f"{status_emoji} **{medicine}**: {prescribed_dosage}\n"
            response += f"   Status: {status.replace('_', ' ').title()}\n"
            
            if issues:
                response += f"   Issues: {'; '.join(issues[:2])}\n"
            
            response += "\n"
        
        if recommendations:
            response += "**📋 General Recommendations:**\n"
            for rec in recommendations[:3]:
                response += f"• {rec}\n"
        
        return response
    
    def format_alternatives_results(self, results: Dict) -> str:
        """Format alternative medication results for chat display"""
        if not results or results.get('status') != 'ok':
            return "❌ Sorry, I couldn't find alternatives. Please try again."
        
        alternatives = results.get('alternatives', [])
        recommendations = results.get('recommendations', [])
        
        if not alternatives:
            return "ℹ️ No specific alternatives found in my database for your medications."
        
        response = "🔄 **Alternative Medication Suggestions:**\n\n"
        
        for alt in alternatives:
            original = alt.get('original_medicine', 'Unknown')
            alternative = alt.get('alternative_name', 'Alternative')
            reason = alt.get('reason', 'Similar therapeutic effect')
            dosage = alt.get('suggested_dosage', 'Consult prescriber')
            
            response += f"**{original}** → **{alternative}**\n"
            response += f"   Reason: {reason}\n"
            response += f"   Suggested Dosage: {dosage}\n\n"
        
        if recommendations:
            response += "**📋 Important Notes:**\n"
            for rec in recommendations[:3]:
                response += f"• {rec}\n"
        
        return response
    
    async def call_api_endpoint(self, endpoint: str, data: Dict) -> Optional[Dict]:
        """Call backend API endpoint"""
        try:
            response = requests.post(
                f"{API_BASE_URL}/{endpoint}",
                json=data,
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API Error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"API call failed: {str(e)}")
            return None
    
    def process_user_input(self, user_input: str) -> str:
        """Process user input and generate response"""
        # Extract prescription information
        info = self.extract_prescription_info(user_input)
        
        # Update session state with extracted information
        if info['has_prescription']:
            st.session_state.current_prescription = user_input
        if info['age_mentioned']:
            st.session_state.patient_age = info['age_mentioned']
        if info['weight_mentioned']:
            st.session_state.patient_weight = info['weight_mentioned']
        
        # Determine intent
        intent = self.determine_intent(user_input)
        
        # Handle different intents
        if intent == 'help':
            return self.get_help_response()
        elif intent == 'prescription_input' and info['has_prescription']:
            return self.handle_prescription_input(info)
        elif intent in ['check_interactions', 'check_dosage', 'get_alternatives']:
            return self.handle_analysis_request(intent, user_input)
        else:
            return self.get_general_response(user_input, info)
    
    def get_help_response(self) -> str:
        """Generate help response"""
        return """
🤖 **I can help you with:**

**1. Drug Interaction Checks**
   Say: "Check interactions for aspirin and warfarin"
   
**2. Dosage Verification**
   Say: "Is 325mg aspirin twice daily appropriate for a 65-year-old?"
   
**3. Alternative Medications**
   Say: "What are alternatives to ibuprofen?"
   
**4. General Prescription Analysis**
   Just paste your prescription text and I'll analyze it!

**📝 Example:**
"I have a prescription for aspirin 325mg twice daily and warfarin 5mg once daily for a 70-year-old patient weighing 65kg. Can you check for interactions?"

What would you like me to help you with?
        """
    
    def handle_prescription_input(self, info: Dict) -> str:
        """Handle prescription input"""
        medicines = ", ".join([med.title() for med in info['medicines']])
        response = f"📝 I found these medications: **{medicines}**\n\n"
        
        # Check if we have patient info
        missing_info = []
        if not st.session_state.patient_age or st.session_state.patient_age == 45:
            if not info['age_mentioned']:
                missing_info.append("patient age")
        if not st.session_state.patient_weight or st.session_state.patient_weight == 70.0:
            if not info['weight_mentioned']:
                missing_info.append("patient weight")
        
        if missing_info:
            response += f"To provide the most accurate analysis, I'd also need: {', '.join(missing_info)}.\n\n"
        
        response += "What would you like me to analyze?\n"
        response += "• Type 'check interactions' for drug interaction analysis\n"
        response += "• Type 'check dosage' for dosage verification\n"
        response += "• Type 'find alternatives' for alternative medications\n"
        response += "• Type 'analyze all' for comprehensive analysis"
        
        return response
    
    def handle_analysis_request(self, analysis_type: str, user_input: str) -> str:
        """Handle analysis requests"""
        # Check if we have prescription data
        if not st.session_state.current_prescription:
            return "📝 I need prescription information first. Please provide the medications you'd like me to analyze."
        
        # Check API status
        if not self.check_api_status():
            return "❌ Sorry, the analysis service is currently unavailable. Please ensure the backend server is running."
        
        # Prepare API call data
        api_data = {
            "prescription_text": st.session_state.current_prescription,
            "age": st.session_state.patient_age,
            "weight": st.session_state.patient_weight
        }
        
        # Store for async processing
        st.session_state.pending_analysis = {
            'type': analysis_type,
            'data': api_data
        }
        
        return f"🔄 Analyzing {analysis_type.replace('_', ' ')}... Please wait."
    
    def get_general_response(self, user_input: str, info: Dict) -> str:
        """Generate general response"""
        input_lower = user_input.lower()
        
        if any(greeting in input_lower for greeting in ['hi', 'hello', 'hey']):
            return "👋 Hello! I'm here to help you with prescription verification. You can share a prescription with me or ask about drug interactions, dosages, or alternatives."
        
        elif any(thanks in input_lower for thanks in ['thank', 'thanks']):
            return "😊 You're welcome! Is there anything else I can help you with regarding your prescription?"
        
        elif 'bye' in input_lower or 'goodbye' in input_lower:
            return "👋 Goodbye! Remember to always consult your healthcare provider for medical decisions. Stay safe!"
        
        else:
            return ("🤔 I'm not sure I understand. I can help you with:\n"
                   "• Prescription analysis\n"
                   "• Drug interactions\n"
                   "• Dosage verification\n"
                   "• Alternative medications\n\n"
                   "Try sharing your prescription or asking a specific question!")

def main():
    """Main Streamlit application"""
    st.set_page_config(
        page_title="Medical Prescription AI Chatbot",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize chatbot
    chatbot = MedicalChatbot()
    
    # Header
    st.title("🤖 Medical Prescription AI Assistant")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("💊 Current Session Info")
        
        # API Status
        api_status = chatbot.check_api_status()
        status_color = "🟢" if api_status else "🔴"
        st.write(f"{status_color} Backend API: {'Connected' if api_status else 'Disconnected'}")
        
        # Current prescription info
        st.subheader("📝 Current Prescription")
        if st.session_state.current_prescription:
            st.text_area("Prescription Text", st.session_state.current_prescription, height=100, disabled=True)
        else:
            st.info("No prescription entered yet")
        
        st.subheader("👤 Patient Information")
        st.write(f"**Age:** {st.session_state.patient_age} years")
        st.write(f"**Weight:** {st.session_state.patient_weight} kg")
        
        # Quick actions
        st.subheader("⚡ Quick Actions")
        if st.button("🔄 Clear Chat"):
            st.session_state.chat_history = []
            st.session_state.current_prescription = ""
            st.rerun()
        
        if st.button("📊 New Analysis"):
            st.session_state.current_prescription = ""
            st.session_state.pending_analysis = None
        
        # Help section
        with st.expander("ℹ️ How to Use"):
            st.markdown("""
            **Example Queries:**
            - "Check interactions for aspirin and warfarin"
            - "Is 325mg aspirin safe for a 70-year-old?"
            - "Find alternatives to ibuprofen"
            - Paste your full prescription text
            
            **Supported Medications:**
            Aspirin, Ibuprofen, Acetaminophen, Warfarin, Metformin, Lisinopril, and many more.
            """)
    
    # Main chat interface
    st.subheader("💬 Chat with AI Assistant")
    
    # Chat history container
    chat_container = st.container()
    
    with chat_container:
        # Display chat history
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Add metadata if present
                if message.get("metadata"):
                    with st.expander("📊 Analysis Details"):
                        st.json(message["metadata"])
    
    # Handle pending analysis
    if st.session_state.pending_analysis:
        analysis_info = st.session_state.pending_analysis
        analysis_type = analysis_info['type']
        api_data = analysis_info['data']
        
        with st.spinner(f"Analyzing {analysis_type.replace('_', ' ')}..."):
            # Map analysis type to API endpoint
            endpoint_map = {
                'check_interactions': 'check_interactions',
                'check_dosage': 'check_dosage',
                'get_alternatives': 'get_alternatives'
            }
            
            endpoint = endpoint_map.get(analysis_type)
            if endpoint:
                result = chatbot.call_api_endpoint(endpoint, api_data)
                
                if result:
                    # Format response based on analysis type
                    if analysis_type == 'check_interactions':
                        response = chatbot.format_interaction_results(result)
                    elif analysis_type == 'check_dosage':
                        response = chatbot.format_dosage_results(result)
                    elif analysis_type == 'get_alternatives':
                        response = chatbot.format_alternatives_results(result)
                    
                    # Add to chat history
                    chatbot.add_message("assistant", response, metadata=result)
                else:
                    chatbot.add_message("assistant", 
                        "❌ Sorry, I encountered an error during analysis. Please try again or check if the backend service is running.")
                
                # Clear pending analysis
                st.session_state.pending_analysis = None
                st.rerun()
    
    # Chat input
    if prompt := st.chat_input("Type your message here... (e.g., 'Check interactions for aspirin and warfarin')"):
        # Add user message to chat
        chatbot.add_message("user", prompt)
        
        # Process input and generate response
        response = chatbot.process_user_input(prompt)
        
        # Add assistant response
        chatbot.add_message("assistant", response)
        
        # Refresh the page to show new messages
        st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray; font-size: 0.8em;'>
        🏥 Medical Prescription AI Chatbot v1.0<br>
        ⚠️ For educational purposes only. Always consult healthcare professionals for medical decisions.
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()