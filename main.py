
"""
FastAPI backend for AI-powered medical prescription verification
Main application entry point with API endpoints
"""

import os
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import logging
from dotenv import load_dotenv
import jsonschema

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Verify environment variables
if not os.environ.get('HUGGINGFACE_API_TOKEN'):
    logger.warning("HUGGINGFACE_API_TOKEN not found in environment. Granite model will not be available.")
    os.environ['MODEL_LOADING_MODE'] = 'rule_based'
else:
    logger.info("Granite model integration enabled")

# Load environment variables
load_dotenv()

# Import custom modules
from extract_medicines import MedicineExtractor
from dosage_checker import DosageChecker
from ibm_alerts import IBMGraniteAlerts
from granite_utils import query_granite

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI application instance
app = FastAPI(
    title="Medical Prescription Verification API",
    description="AI-powered system for checking drug interactions and dosage verification",
    version="1.0.0"
)

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request validation
class PrescriptionRequest(BaseModel):
    prescription_text: str
    age: int
    weight: float

class DosageRequest(BaseModel):
    prescription_text: str
    age: int
    weight: float

class AlternativesRequest(BaseModel):
    prescription_text: str
    age: int
    weight: float

# Response models
class InteractionResponse(BaseModel):
    status: str
    interactions: List[Dict[str, Any]]

class DosageResponse(BaseModel):
    status: str
    dosage_analysis: List[Dict[str, Any]]
    recommendations: List[str]

class AlternativesResponse(BaseModel):
    status: str
    alternatives: List[Dict[str, Any]]
    recommendations: List[str]

# Global instances - initialized on startup
medicine_extractor = None
dosage_checker = None
ibm_alerts = None

@app.on_event("startup")
async def startup_event():
    """Initialize services and load datasets on application startup"""
    global medicine_extractor, dosage_checker, ibm_alerts
    
    try:
        logger.info("Initializing services...")
        
        # Initialize medicine extractor
        medicine_extractor = MedicineExtractor()
        
        # Initialize dosage checker
        dosage_checker = DosageChecker()
        
        # Initialize IBM Granite alerts system
        ibm_alerts = IBMGraniteAlerts()
        
        logger.info("All services initialized successfully!")
        
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/check_interactions", response_model=InteractionResponse)
async def check_interactions(request: PrescriptionRequest):
    """
    Check for drug-drug interactions in the prescription text
    """
    try:
        logger.info(f"Processing interaction check for prescription: {request.prescription_text[:50]}...")
        
        # Extract medicines from prescription text
        medicines = await medicine_extractor.extract_medicines(request.prescription_text)
        logger.info(f"Extracted medicines: {medicines}")
        
        interactions = []
        
        if not medicines:
            interactions.append({
                "severity": "warning",
                "description": "No medicines detected in the prescription text. Please check the input.",
                "recommendations": ["Verify prescription text for accuracy"]
            })
            return {"status": "ok", "interactions": interactions}
        
        # Enhanced rule-based interaction database
        dangerous_combinations = [
            {
                "drugs": ("aspirin", "warfarin"),
                "severity": "major",
                "description": "Increased bleeding risk due to combined anticoagulant effects",
                "recommendations": ["Monitor INR closely", "Consider alternative analgesic", "Consult hematologist"]
            },
            {
                "drugs": ("aspirin", "ibuprofen"),
                "severity": "moderate",
                "description": "Increased bleeding risk and potential for GI irritation",
                "recommendations": ["Space doses by at least 2 hours", "Consider PPI for GI protection"]
            },
            {
                "drugs": ("ibuprofen", "warfarin"),
                "severity": "major",
                "description": "Significantly increased bleeding risk",
                "recommendations": ["Monitor INR frequently", "Consider acetaminophen as alternative"]
            },
            {
                "drugs": ("metformin", "insulin"),
                "severity": "moderate",
                "description": "Risk of hypoglycemia with combined glucose-lowering effects",
                "recommendations": ["Monitor blood glucose levels", "Adjust doses under medical supervision"]
            },
            {
                "drugs": ("lisinopril", "potassium"),
                "severity": "moderate",
                "description": "Risk of hyperkalemia due to potassium retention",
                "recommendations": ["Monitor potassium levels", "Limit potassium-rich foods"]
            },
            {
                "drugs": ("digoxin", "furosemide"),
                "severity": "moderate",
                "description": "Furosemide may increase digoxin toxicity via electrolyte imbalances",
                "recommendations": ["Monitor electrolytes", "Check digoxin levels regularly"]
            },
            {
                "drugs": ("prednisone", "warfarin"),
                "severity": "moderate",
                "description": "Prednisone may enhance warfarin’s anticoagulant effect",
                "recommendations": ["Monitor INR closely", "Adjust warfarin dose as needed"]
            },
            {
                "drugs": ("amoxicillin", "warfarin"),
                "severity": "moderate",
                "description": "Amoxicillin may enhance warfarin’s anticoagulant effect",
                "recommendations": ["Monitor INR during antibiotic course", "Consult prescriber"]
            },
            {
                "drugs": ("fluoxetine", "warfarin"),
                "severity": "moderate",
                "description": "Fluoxetine may increase warfarin levels via CYP2C9 inhibition",
                "recommendations": ["Monitor INR frequently", "Consider dose adjustment"]
            },
            {
                "drugs": ("atorvastatin", "clarithromycin"),
                "severity": "major",
                "description": "Clarithromycin inhibits atorvastatin metabolism, increasing myopathy risk",
                "recommendations": ["Consider alternative antibiotic", "Monitor for muscle pain"]
            }
        ]
        
        # Use Granite model for interaction check if multiple medicines
        if len(medicines) > 1 and os.environ.get('MODEL_LOADING_MODE') == 'api':
            prompt = f"""Analyze potential drug interactions for a {request.age}-year-old patient weighing {request.weight}kg taking: {', '.join(medicines)}.
Return a JSON array of objects, each with keys: severity (major/moderate/minor), description (string), recommendations (array of strings).
Example: [{{"severity": "major", "description": "Drug1-Drug2 interaction increases bleeding risk", "recommendations": ["Monitor INR", "Consult doctor"]}}]
Only include interactions with clinical significance. If none, return an empty array."""
            try:
                response = await query_granite(prompt, cache_key=f"interactions_{','.join(sorted(medicines))}_{request.age}")
                import json
                # Validate JSON response
                schema = {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "severity": {"type": "string", "enum": ["major", "moderate", "minor"]},
                            "description": {"type": "string"},
                            "recommendations": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["severity", "description", "recommendations"]
                    }
                }
                granite_interactions = json.loads(response)
                jsonschema.validate(granite_interactions, schema)
                if isinstance(granite_interactions, list):
                    interactions.extend(granite_interactions)
            except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                logger.warning(f"Granite interaction check failed: {str(e)}. Falling back to rule-based.")
            except Exception as e:
                logger.warning(f"Granite API error: {str(e)}. Falling back to rule-based.")
        
        # Rule-based checks
        interaction_found = False
        if len(medicines) == 1:
            medicine = medicines[0]
            age_alerts = await ibm_alerts.generate_age_based_alert(medicine, request.age)
            for alert in age_alerts:
                interactions.append({
                    "severity": "moderate" if "🚨" in alert else "minor",
                    "description": alert,
                    "recommendations": ["Consult prescriber for age-appropriate guidance"]
                })
            if not age_alerts:
                interactions.append({
                    "severity": "info",
                    "description": f"{medicine.title()} appears safe for a {request.age}-year-old patient.",
                    "recommendations": ["Monitor for adverse effects"]
                })
        else:
            for i, med1 in enumerate(medicines):
                for med2 in medicines[i+1:]:
                    for combo in dangerous_combinations:
                        drug1, drug2 = combo["drugs"]
                        if (med1.lower() in drug1 and med2.lower() in drug2) or \
                           (med1.lower() in drug2 and med2.lower() in drug1):
                            interactions.append({
                                "severity": combo["severity"],
                                "description": combo["description"],
                                "recommendations": combo["recommendations"]
                            })
                            interaction_found = True
                
                # Age-based alerts for each medicine
                age_alerts = await ibm_alerts.generate_age_based_alert(med1, request.age)
                for alert in age_alerts:
                    interactions.append({
                        "severity": "moderate" if "🚨" in alert else "minor",
                        "description": alert,
                        "recommendations": ["Consult prescriber for age-appropriate guidance"]
                    })
            
            if not interaction_found and len(medicines) > 1:
                interactions.append({
                    "severity": "info",
                    "description": f"No major interactions found between {', '.join(medicines)}.",
                    "recommendations": ["Continue monitoring for new symptoms"]
                })
        
        # Enhanced patient context: Age and weight-based considerations
        if request.age < 18:
            interactions.append({
                "severity": "moderate",
                "description": "Pediatric patient: Weight-based dosing and interaction risks require careful monitoring.",
                "recommendations": [
                    f"Verify dosing for {request.weight}kg child",
                    "Consult pediatric specialist",
                    "Use pediatric formulations if available"
                ]
            })
        elif request.age >= 65:
            interactions.append({
                "severity": "moderate",
                "description": "Geriatric patient: Increased risk of adverse effects due to age-related changes.",
                "recommendations": [
                    "Consider 25-50% dose reduction",
                    "Monitor renal and hepatic function",
                    "Review polypharmacy risks"
                ]
            })
        
        # Weight-based considerations for specific drugs
        if request.weight < 40 and any(med.lower() in ['ibuprofen', 'acetaminophen'] for med in medicines):
            interactions.append({
                "severity": "moderate",
                "description": f"Low weight ({request.weight}kg) may require adjusted dosing for NSAIDs or acetaminophen.",
                "recommendations": [
                    "Use weight-based dosing (e.g., 10mg/kg for ibuprofen, 15mg/kg for acetaminophen)",
                    "Consult prescriber"
                ]
            })
        
        # Deduplicate interactions by description
        seen_descriptions = set()
        unique_interactions = []
        for interaction in interactions:
            if interaction["description"] not in seen_descriptions:
                seen_descriptions.add(interaction["description"])
                unique_interactions.append(interaction)
        
        return {"status": "ok", "interactions": unique_interactions}
        
    except Exception as e:
        logger.error(f"Error in check_interactions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing prescription: {str(e)}")

@app.post("/check_dosage", response_model=DosageResponse)
async def check_dosage(request: DosageRequest):
    """
    Check dosage appropriateness based on patient age, weight, and frequency
    """
    try:
        logger.info(f"Processing dosage check for prescription: {request.prescription_text[:50]}...")
        
        # Extract medicines with dosages and frequency
        medicines = await medicine_extractor.extract_medicines_with_dosages(request.prescription_text)
        frequencies = medicine_extractor.extract_frequency(request.prescription_text)
        logger.info(f"Extracted medicines: {medicines}, Frequencies: {frequencies}")
        
        dosage_analysis = []
        recommendations = []
        
        if not medicines:
            recommendations.append("No medications detected in the prescription text. Please verify input.")
            return {
                "status": "ok",
                "dosage_analysis": [],
                "recommendations": recommendations
            }
        
        # Check dosage for each medicine
        for med_info in medicines:
            medicine = med_info['medicine']
            dosage = med_info['dosage']
            amount = med_info['amount']
            unit = med_info['unit']
            
            # Verify dosage using Granite or rule-based logic
            result = await dosage_checker.verify_dosage(
                medicine=medicine,
                dosage=dosage,
                age=request.age,
                weight=request.weight,
                frequency=frequencies.get('detected_frequency', 'Not specified')
            )
            
            analysis = {
                "medicine": medicine.title(),
                "prescribed_dosage": dosage,
                "frequency": frequencies.get('detected_frequency', 'Not specified'),
                "age_group": result['age_group'],
                "status": "appropriate" if not result['has_issues'] else "needs_attention",
                "severity": result['severity'],
                "therapeutic_range": result.get('therapeutic_range', 'Not available'),
                "clinical_notes": result.get('clinical_notes', []),
                "issues": result.get('issues', []),
                "recommended_dosage": result.get('recommended_dosage', 'Consult prescriber'),
                "weight_based_analysis": result.get('weight_based_analysis', {})
            }
            
            dosage_analysis.append(analysis)
        
        # General patient-specific recommendations
        if request.age < 18:
            recommendations.append(
                f"Pediatric patient ({request.age} years, {request.weight}kg): "
                "Use weight-based dosing and pediatric formulations."
            )
            if request.weight < 40:
                recommendations.append(
                    "Low body weight detected. Ensure doses are calculated at "
                    f"appropriate mg/kg ratios (e.g., ibuprofen: 5-10mg/kg, acetaminophen: 10-15mg/kg)."
                )
        elif request.age >= 65:
            recommendations.append(
                "Geriatric patient: Consider 25-50% dose reduction due to "
                "potential renal/hepatic impairment and increased sensitivity."
            )
        
        # Frequency-based recommendations
        if 'as_needed' in frequencies:
            recommendations.append(
                "PRN (as needed) dosing detected. Ensure maximum daily dose is not exceeded "
                "and monitor for overuse."
            )
        elif 'every_x_hours' in frequencies:
            recommendations.append(
                f"Frequent dosing ({frequencies['every_x_hours']}) detected. "
                "Verify cumulative daily dose and monitor for toxicity."
            )
        
        # General clinical recommendations
        recommendations.extend([
            "Verify all dosages against current clinical guidelines (e.g., Lexicomp, Micromedex).",
            "Monitor patient for therapeutic response and adverse effects.",
            "Consult a clinical pharmacist or prescriber for complex regimens."
        ])
        
        # Deduplicate recommendations
        recommendations = list(dict.fromkeys(recommendations))
        
        return {
            "status": "ok",
            "dosage_analysis": dosage_analysis,
            "recommendations": recommendations
        }
        
    except Exception as e:
        logger.error(f"Error in check_dosage: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing dosage: {str(e)}")

@app.post("/get_alternatives", response_model=AlternativesResponse)
async def get_alternatives(request: AlternativesRequest):
    """
    Get alternative medications and suggestions
    """
    try:
        logger.info(f"Finding alternatives for prescription")
        
        # Extract medicines
        medicines = await medicine_extractor.extract_medicines(request.prescription_text)
        
        if not medicines:
            return {
                "status": "error",
                "alternatives": [],
                "recommendations": ["No medications detected in prescription text."]
            }
        
        alternatives = []
        recommendations = []
        
        # Define alternative medications
        alternative_db = {
            'aspirin': [
                {"name": "Acetaminophen", "reason": "Less GI irritation", "dosage": "500-1000mg"},
                {"name": "Celecoxib", "reason": "Lower bleeding risk", "dosage": "100-200mg"},
                {"name": "Topical NSAIDs", "reason": "Reduced systemic effects", "dosage": "Apply locally"}
            ],
            'ibuprofen': [
                {"name": "Naproxen", "reason": "Longer duration of action", "dosage": "220-440mg"},
                {"name": "Diclofenac", "reason": "Similar efficacy", "dosage": "50-100mg"},
                {"name": "Acetaminophen", "reason": "Different mechanism", "dosage": "500-1000mg"}
            ],
            'acetaminophen': [
                {"name": "Ibuprofen", "reason": "Anti-inflammatory properties", "dosage": "200-400mg"},
                {"name": "Aspirin", "reason": "Additional cardioprotective effects", "dosage": "325-650mg"},
                {"name": "Naproxen", "reason": "Longer-lasting relief", "dosage": "220mg"}
            ],
            'metformin': [
                {"name": "Gliclazide", "reason": "Different mechanism", "dosage": "40-80mg"},
                {"name": "Sitagliptin", "reason": "Lower hypoglycemia risk", "dosage": "25-100mg"},
                {"name": "Empagliflozin", "reason": "Cardiovascular benefits", "dosage": "10-25mg"}
            ],
            'lisinopril': [
                {"name": "Losartan", "reason": "ARB alternative, less cough", "dosage": "25-100mg"},
                {"name": "Amlodipine", "reason": "Different class, CCB", "dosage": "2.5-10mg"},
                {"name": "Hydrochlorothiazide", "reason": "Diuretic alternative", "dosage": "12.5-25mg"}
            ],
            'warfarin': [
                {"name": "Rivaroxaban", "reason": "No INR monitoring needed", "dosage": "10-20mg"},
                {"name": "Apixaban", "reason": "Lower bleeding risk", "dosage": "2.5-5mg"},
                {"name": "Dabigatran", "reason": "Reversible anticoagulant", "dosage": "75-150mg"}
            ]
        }
        
        for medicine in medicines:
            med_lower = medicine.lower()
            if med_lower in alternative_db:
                med_alternatives = alternative_db[med_lower]
                
                for alt in med_alternatives:
                    age_note = ""
                    if request.age < 18:
                        age_note = " (Pediatric dosing required)"
                    elif request.age >= 65:
                        age_note = " (Consider reduced dose for elderly)"
                    
                    alternatives.append({
                        "original_medicine": medicine,
                        "alternative_name": alt["name"],
                        "reason": alt["reason"],
                        "suggested_dosage": alt["dosage"] + age_note,
                        "safety_profile": "Generally well tolerated"
                    })
        
        if not alternatives:
            for medicine in medicines:
                alts = await dosage_checker.find_alternatives(medicine)
                for alt in alts:
                    alternatives.append({
                        "original_medicine": medicine,
                        "alternative_name": alt.get("name", "Alternative medication"),
                        "reason": alt.get("reason", "Same active ingredient"),
                        "suggested_dosage": "Consult prescribing information",
                        "safety_profile": "Similar to original"
                    })
        
        recommendations.extend([
            "Always consult healthcare provider before switching medications.",
            "Consider patient allergies and contraindications.",
            "Monitor patient response when starting new medication.",
            "Gradual transition may be needed for some medications."
        ])
        
        if request.age < 18:
            recommendations.append("Ensure pediatric formulations are available.")
        elif request.age >= 65:
            recommendations.append("Consider drug interactions in elderly patients.")
        
        return {
            "status": "ok",
            "alternatives": alternatives,
            "recommendations": recommendations
        }
        
    except Exception as e:
        logger.error(f"Error in get_alternatives: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error finding alternatives: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000,
        reload=True,
        log_level="info"
    )
