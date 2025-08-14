import logging
import os
from typing import Dict, List, Any
from granite_utils import query_granite

logger = logging.getLogger(__name__)

class IBMGraniteAlerts:
    """
    IBM Granite AI-powered contextual alerts system
    """
    
    def __init__(self):
        """Initialize the IBM Granite alerts system"""
        self.model_mode = os.environ.get('MODEL_LOADING_MODE', 'api')
        
        self.alert_templates = {
            'major': {
                'template': "🚨 MAJOR INTERACTION: {drug1} and {drug2} combination poses significant risk. {description} Immediate medical consultation recommended.",
                'priority': 'high'
            },
            'moderate': {
                'template': "⚠️ MODERATE INTERACTION: {drug1} and {drug2} may interact. {description} Monitor patient closely.",
                'priority': 'medium'
            },
            'minor': {
                'template': "ℹ️ MINOR INTERACTION: {drug1} and {drug2} have potential interaction. {description} Consider alternative if possible.",
                'priority': 'low'
            }
        }
        
        self.contextual_rules = {
            'bleeding_risk': {
                'drugs': ['aspirin', 'warfarin', 'ibuprofen', 'heparin', 'clopidogrel'],
                'alert': "Increased bleeding risk - monitor for signs of bleeding",
                'recommendations': [
                    "Monitor INR if on warfarin",
                    "Check for unusual bruising or bleeding",
                    "Consider PPI for GI protection"
                ]
            },
            'kidney_function': {
                'drugs': ['ibuprofen', 'naproxen', 'lisinopril', 'furosemide'],
                'alert': "May affect kidney function - monitor renal status",
                'recommendations': [
                    "Check creatinine levels",
                    "Ensure adequate hydration",
                    "Monitor urine output"
                ]
            },
            'blood_sugar': {
                'drugs': ['metformin', 'insulin', 'gliclazide', 'prednisone'],
                'alert': "May affect blood glucose levels - monitor closely",
                'recommendations': [
                    "Monitor blood glucose regularly",
                    "Adjust insulin dose if needed",
                    "Watch for hypo/hyperglycemia symptoms"
                ]
            }
        }
    
    async def generate_contextual_alert(self, drug1: str, drug2: str, 
                                      interaction_description: str, 
                                      severity: str = 'moderate') -> str:
        """
        Generate contextual alert for drug interaction
        
        Args:
            drug1: First drug name
            drug2: Second drug name
            interaction_description: Description of the interaction
            severity: Severity level (major, moderate, minor)
            
        Returns:
            Contextual alert string
        """
        try:
            if self.model_mode == 'api':
                prompt = f"""Generate a contextual alert for the interaction between {drug1} and {drug2}.
Description: {interaction_description}
Severity: {severity}
Include priority (high/medium/low) and recommendations. Return as a single string."""
                return await query_granite(prompt)
            
            template_info = self.alert_templates.get(severity, self.alert_templates['moderate'])
            alert = template_info['template'].format(
                drug1=drug1.title(),
                drug2=drug2.title(),
                description=interaction_description
            )
            contextual_info = self._get_contextual_recommendations(drug1, drug2)
            if contextual_info:
                alert += f" {contextual_info}"
            
            logger.info(f"Generated contextual alert for {drug1} and {drug2}")
            return alert
            
        except Exception as e:
            logger.error(f"Error generating contextual alert: {str(e)}")
            return f"⚠️ Interaction detected between {drug1} and {drug2}. Please consult healthcare provider."
    
    async def generate_age_based_alert(self, drug: str, age: int, 
                                     dosage: str = None) -> List[str]:
        """
        Generate age-based medication alerts
        
        Args:
            drug: Drug name
            age: Patient age
            dosage: Optional dosage information
            
        Returns:
            List of age-based alerts
        """
        alerts = []
        
        try:
            if self.model_mode == 'api':
                prompt = f"""Generate age-based alerts for {drug} in a {age}-year-old patient.
Dosage: {dosage or 'Not specified'}
Return a JSON array of alert strings (e.g., ["ALERT: ...", "WARNING: ..."])."""
                response = await query_granite(prompt)
                import json
                alerts = json.loads(response)
                if isinstance(alerts, list):
                    return alerts
            
            drug_lower = drug.lower()
            if age < 18:
                pediatric_contraindications = {
                    'aspirin': "Aspirin contraindicated in children under 12 due to Reye's syndrome risk",
                    'ibuprofen': "Use caution with ibuprofen in children - weight-based dosing required",
                    'codeine': "Codeine contraindicated in children under 12"
                }
                if drug_lower in pediatric_contraindications:
                    alerts.append(f"🚨 PEDIATRIC ALERT: {pediatric_contraindications[drug_lower]}")
            
            elif age >= 65:
                geriatric_considerations = {
                    'ibuprofen': "Reduce dose in elderly - increased risk of kidney and GI complications",
                    'aspirin': "Monitor for bleeding risk - elderly more susceptible",
                    'prednisone': "Increased risk of osteoporosis and diabetes in elderly"
                }
                if drug_lower in geriatric_considerations:
                    alerts.append(f"👴 GERIATRIC ALERT: {geriatric_considerations[drug_lower]}")
            
            if dosage and self._is_high_dose(drug_lower, dosage):
                alerts.append(f"⚠️ HIGH DOSE ALERT: {drug} {dosage} exceeds typical therapeutic range")
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error generating age-based alert: {str(e)}")
            return [f"⚠️ Consider age-appropriate dosing for {drug} in {age}-year-old patient"]
    
    async def generate_condition_based_alerts(self, drugs: List[str], 
                                            conditions: List[str] = None) -> List[str]:
        """
        Generate alerts based on medical conditions
        
        Args:
            drugs: List of drug names
            conditions: List of medical conditions (optional)
            
        Returns:
            List of condition-based alerts
        """
        alerts = []
        
        try:
            if self.model_mode == 'api':
                prompt = f"""Generate condition-based alerts for drugs: {', '.join(drugs)}.
Conditions: {conditions or ['unknown']}
Return a JSON array of alert strings."""
                response = await query_granite(prompt)
                import json
                alerts = json.loads(response)
                if isinstance(alerts, list):
                    return alerts
            
            condition_alerts = {
                'diabetes': {
                    'prednisone': "Corticosteroids may increase blood glucose levels",
                    'thiazide': "Thiazide diuretics may worsen glucose control"
                },
                'kidney_disease': {
                    'ibuprofen': "NSAIDs may worsen kidney function",
                    'metformin': "Contraindicated in severe kidney disease"
                },
                'heart_disease': {
                    'ibuprofen': "NSAIDs may increase cardiovascular risk",
                    'rosiglitazone': "May increase risk of heart failure"
                }
            }
            
            if not conditions:
                for drug in drugs:
                    drug_lower = drug.lower()
                    if drug_lower in ['prednisone', 'prednisolone']:
                        alerts.append("💊 Monitor blood glucose if diabetic - steroids may raise sugar levels")
                    elif drug_lower in ['ibuprofen', 'naproxen', 'diclofenac']:
                        alerts.append("💊 Caution with kidney or heart disease - NSAIDs may worsen these conditions")
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error generating condition-based alerts: {str(e)}")
            return []
    
    def _get_contextual_recommendations(self, drug1: str, drug2: str) -> str:
        """
        Get contextual recommendations based on drug categories
        
        Args:
            drug1: First drug name
            drug2: Second drug name
            
        Returns:
            Contextual recommendations string
        """
        recommendations = []
        
        for rule_name, rule_info in self.contextual_rules.items():
            drugs_in_rule = [drug.lower() for drug in rule_info['drugs']]
            if drug1.lower() in drugs_in_rule or drug2.lower() in drugs_in_rule:
                recommendations.extend(rule_info['recommendations'][:2])
        
        if recommendations:
            return f"Recommendations: {'; '.join(recommendations[:3])}"
        
        return ""
    
    def _is_high_dose(self, drug: str, dosage: str) -> bool:
        """
        Check if dosage is considered high for the given drug
        
        Args:
            drug: Drug name
            dosage: Dosage string
            
        Returns:
            True if dosage is considered high
        """
        import re
        
        match = re.search(r'(\d+(?:\.\d+)?)', dosage)
        if not match:
            return False
        
        dose_value = float(match.group(1))
        
        high_dose_thresholds = {
            'aspirin': 1000,
            'ibuprofen': 800,
            'acetaminophen': 1000,
            'prednisone': 60,
            'metformin': 2000,
            'furosemide': 80
        }
        
        threshold = high_dose_thresholds.get(drug.lower())
        return threshold and dose_value > threshold
    
    async def generate_comprehensive_alert(self, prescription_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive alert summary
        
        Args:
            prescription_data: Dictionary containing prescription information
            
        Returns:
            Comprehensive alert summary
        """
        try:
            drugs = prescription_data.get('drugs', [])
            age = prescription_data.get('age', 0)
            conditions = prescription_data.get('conditions', [])
            
            alert_summary = {
                'high_priority_alerts': [],
                'medium_priority_alerts': [],
                'low_priority_alerts': [],
                'recommendations': []
            }
            
            if self.model_mode == 'api':
                prompt = f"""Generate comprehensive alerts for drugs: {', '.join(drugs)} in a {age}-year-old with conditions: {', '.join(conditions or ['none'])}.
Return JSON: {{"high_priority_alerts": [], "medium_priority_alerts": [], "low_priority_alerts": [], "recommendations": []}}"""
                try:
                    response = await query_granite(prompt)
                    import json
                    return json.loads(response)
                except Exception as e:
                    logger.warning(f"Granite comprehensive alert failed: {str(e)}. Falling back.")
            
            for drug in drugs:
                age_alerts = await self.generate_age_based_alert(drug, age)
                for alert in age_alerts:
                    if '🚨' in alert:
                        alert_summary['high_priority_alerts'].append(alert)
                    elif '⚠️' in alert:
                        alert_summary['medium_priority_alerts'].append(alert)
                    else:
                        alert_summary['low_priority_alerts'].append(alert)
            
            condition_alerts = await self.generate_condition_based_alerts(drugs, conditions)
            alert_summary['medium_priority_alerts'].extend(condition_alerts)
            
            alert_summary['recommendations'] = [
                "Regular monitoring recommended",
                "Consult healthcare provider for any concerns",
                "Follow prescribed dosing schedule"
            ]
            
            return alert_summary
            
        except Exception as e:
            logger.error(f"Error generating comprehensive alert: {str(e)}")
            return {
                'high_priority_alerts': [],
                'medium_priority_alerts': ["Error generating alerts - please consult healthcare provider"],
                'low_priority_alerts': [],
                'recommendations': []
            }