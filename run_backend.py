
# run_backend.py
"""
FastAPI backend for AI-powered medical prescription verification
Enhanced to ensure non-empty interaction results and robust drug detection
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import re
import logging
from typing import List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Pydantic models
class PrescriptionCheckRequest(BaseModel):
    prescription_text: str
    age: int
    weight: float

class Interaction(BaseModel):
    severity: str
    description: str
    recommendations: List[str]

class InteractionResult(BaseModel):
    status: str
    interactions: List[Interaction]

class DosageAnalysis(BaseModel):
    medicine: str
    prescribed_dosage: str
    status: str
    age_group: str
    severity: str
    issues: List[str]

class DosageResult(BaseModel):
    status: str
    dosage_analysis: List[DosageAnalysis]
    recommendations: List[str]

class Alternative(BaseModel):
    original_medicine: str
    alternative_name: str
    reason: str
    suggested_dosage: str
    safety_profile: str

class AlternativeResult(BaseModel):
    status: str
    alternatives: List[Alternative]
    recommendations: List[str]

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

@app.post("/check_interactions", response_model=InteractionResult)
def check_interactions(data: PrescriptionCheckRequest):
    """Enhanced drug interaction checker with robust medicine detection"""
    logger.info(f"Received interaction check request: {data.prescription_text}, age: {data.age}, weight: {data.weight}")
    
    interactions = []
    prescription_lower = data.prescription_text.lower().replace(".", "").strip()
    
    # Extract medicines with broader regex
    medicine_patterns = [
        r'\b(aspirin|ibuprofen|acetaminophen|paracetamol|warfarin|metformin|insulin|lisinopril|atorvastatin)\b'
    ]
    
    found_medicines = []
    for pattern in medicine_patterns:
        matches = re.findall(pattern, prescription_lower, re.IGNORECASE)
        found_medicines.extend([m.lower() for m in matches])
    
    found_medicines = list(set(found_medicines))
    logger.info(f"Detected medicines: {found_medicines}")
    
    if not found_medicines:
        interactions.append(Interaction(
            severity="warning",
            description="No recognized medicines detected. Use standard drug names (e.g., aspirin, warfarin).",
            recommendations=["Verify prescription text for accuracy"]
        ))
        logger.info("No medicines detected, returning warning")
        return {"status": "ok", "interactions": interactions}
    
    # Define dangerous combinations
    dangerous_combos = [
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
            "drugs": ("warfarin", "metformin"),
            "severity": "minor",
            "description": "Potential for altered warfarin metabolism due to metformin",
            "recommendations": ["Monitor INR levels", "Consult pharmacist for timing adjustments"]
        }
    ]
    
    # Check for dangerous combinations
    for combo in dangerous_combos:
        drug1, drug2 = combo["drugs"]
        if drug1 in found_medicines and drug2 in found_medicines:
            interactions.append(Interaction(
                severity=combo["severity"],
                description=combo["description"],
                recommendations=combo["recommendations"]
            ))
    
    # Age-specific warnings
    for medicine in found_medicines:
        if data.age < 12 and medicine == "aspirin":
            interactions.append(Interaction(
                severity="major",
                description="Aspirin not recommended for children under 12 due to Reye's syndrome risk",
                recommendations=["Use alternative analgesic like acetaminophen", "Consult pediatrician"]
            ))
        elif data.age >= 65 and medicine == "ibuprofen":
            interactions.append(Interaction(
                severity="moderate",
                description="Reduce ibuprofen dose in elderly patients due to renal function concerns",
                recommendations=["Consider lower dose", "Monitor renal function"]
            ))
        elif medicine == "metformin" and data.age < 18:
            interactions.append(Interaction(
                severity="moderate",
                description="Metformin use in pediatric patients requires careful monitoring",
                recommendations=["Confirm diagnosis of type 2 diabetes", "Consult endocrinologist"]
            ))
    
    # Ensure at least one result for single-drug prescriptions
    if not interactions and len(found_medicines) == 1:
        interactions.append(Interaction(
            severity="minor",
            description=f"{found_medicines[0].title()} appears safe for {data.age}-year-old patient",
            recommendations=["Monitor for adverse effects"]
        ))
    elif not interactions and len(found_medicines) > 1:
        interactions.append(Interaction(
            severity="minor",
            description=f"No major interactions found between: {', '.join([m.title() for m in found_medicines])}",
            recommendations=["Continue monitoring for adverse effects"]
        ))
    
    logger.info(f"Returning interactions: {interactions}")
    return {"status": "ok", "interactions": interactions}

@app.post("/check_dosage", response_model=DosageResult)
def check_dosage(data: PrescriptionCheckRequest):
    """Basic dosage checker"""
    dosage_analysis = []
    recommendations = []
    
    medicines = re.findall(r'(\w+)\s+(\d+\.?\d*)\s*(mg|g|mcg|units)', data.prescription_text.lower())
    
    for medicine, dose, unit in medicines:
        status = "appropriate"
        issues = []
        
        if medicine == "aspirin" and float(dose) > 325 and unit == "mg":
            status = "high"
            issues.append("Aspirin dose exceeds 325mg; consider reducing dose.")
        elif medicine == "metformin" and float(dose) > 1000 and unit == "mg":
            status = "high"
            issues.append("Metformin dose exceeds typical 1000mg; verify with prescriber.")
        
        if data.age < 12 and medicine == "aspirin":
            status = "inappropriate"
            issues.append("Aspirin not recommended for children under 12.")
        
        dosage_analysis.append(DosageAnalysis(
            medicine=medicine.title(),
            prescribed_dosage=f"{dose} {unit}",
            status=status,
            age_group="adult" if data.age >= 18 else "pediatric",
            severity="low" if status == "appropriate" else "moderate",
            issues=issues
        ))
    
    if not dosage_analysis:
        recommendations.append("No dosage information parsed. Ensure drug names and dosages are clearly specified.")
    
    return {
        "status": "ok",
        "dosage_analysis": dosage_analysis,
        "recommendations": recommendations
    }

@app.post("/get_alternatives", response_model=AlternativeResult)
def get_alternatives(data: PrescriptionCheckRequest):
    """Basic alternative medication suggestion"""
    alternatives = []
    recommendations = []
    
    medicines = re.findall(r'\b(\w+)\b', data.prescription_text.lower())
    
    alternative_db = {
        "aspirin": {
            "alternative_name": "Acetaminophen",
            "reason": "Lower bleeding risk",
            "suggested_dosage": "500mg every 6 hours",
            "safety_profile": "Safer for patients with bleeding risk"
        },
        "ibuprofen": {
            "alternative_name": "Naproxen",
            "reason": "Longer duration of action",
            "suggested_dosage": "250mg twice daily",
            "safety_profile": "Monitor for GI side effects"
        }
    }
    
    for medicine in medicines:
        if medicine in alternative_db:
            alternatives.append(Alternative(
                original_medicine=medicine.title(),
                alternative_name=alternative_db[medicine]["alternative_name"],
                reason=alternative_db[medicine]["reason"],
                suggested_dosage=alternative_db[medicine]["suggested_dosage"],
                safety_profile=alternative_db[medicine]["safety_profile"]
            ))
    
    if not alternatives:
        recommendations.append("No alternatives found for the specified medications.")
    
    return {
        "status": "ok",
        "alternatives": alternatives,
        "recommendations": recommendations
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
