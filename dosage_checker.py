
"""
Dosage verification module using RxNorm RESTful APIs and Granite model
Handles dosage checking and alternative drug suggestions
"""

import logging
import aiohttp
from typing import Dict, List, Any, Optional
import re
import os
from granite_utils import query_granite
import jsonschema

logger = logging.getLogger(__name__)

class DosageChecker:
    """
    Dosage checker using RxNorm RESTful APIs and Granite model for drug information
    """
    
    def __init__(self):
        """Initialize the dosage checker with RxNorm API endpoints"""
        self.base_url = "https://rxnav.nlm.nih.gov/REST"
        self.session = None
        self.model_mode = os.environ.get('MODEL_LOADING_MODE', 'api')
        
        self.age_groups = {
            'pediatric': (0, 17),
            'adult': (18, 64),
            'geriatric': (65, 120)
        }
        
        self.dosage_adjustments = {
            'pediatric': {
                'factor': 0.5,
                'special_considerations': [
                    "Use weight-based dosing where applicable",
                    "Prefer pediatric formulations (e.g., suspensions)",
                    "Monitor for developmental toxicities"
                ]
            },
            'geriatric': {
                'factor': 0.75,
                'special_considerations': [
                    "Adjust for reduced renal/hepatic function",
                    "Monitor for drug accumulation",
                    "Review polypharmacy interactions"
                ]
            },
            'adult': {
                'factor': 1.0,
                'special_considerations': [
                    "Verify adherence to standard therapeutic ranges",
                    "Monitor for patient-specific factors (e.g., renal function)"
                ]
            }
        }
        
        # Expanded rule-based dosage database
        self.dosage_guidelines = {
            'aspirin': {
                'adult': {'range': (81, 325), 'unit': 'mg', 'max_daily': 4000, 'frequency': 'once or twice daily'},
                'pediatric': {'range': (10, 15), 'unit': 'mg/kg', 'max_daily': 80, 'frequency': 'every 4-6 hours'},
                'geriatric': {'range': (81, 162), 'unit': 'mg', 'max_daily': 2000, 'frequency': 'once daily'},
                'notes': ["Low-dose for cardioprotection", "Higher doses for analgesia"]
            },
            'ibuprofen': {
                'adult': {'range': (200, 800), 'unit': 'mg', 'max_daily': 3200, 'frequency': 'every 6-8 hours'},
                'pediatric': {'range': (5, 10), 'unit': 'mg/kg', 'max_daily': 40, 'frequency': 'every 6-8 hours'},
                'geriatric': {'range': (200, 400), 'unit': 'mg', 'max_daily': 2400, 'frequency': 'every 8 hours'},
                'notes': ["Take with food to reduce GI irritation", "Monitor renal function"]
            },
            'acetaminophen': {
                'adult': {'range': (500, 1000), 'unit': 'mg', 'max_daily': 4000, 'frequency': 'every 4-6 hours'},
                'pediatric': {'range': (10, 15), 'unit': 'mg/kg', 'max_daily': 75, 'frequency': 'every 4-6 hours'},
                'geriatric': {'range': (500, 650), 'unit': 'mg', 'max_daily': 3000, 'frequency': 'every 6 hours'},
                'notes': ["Monitor for hepatotoxicity", "Avoid alcohol"]
            },
            'metformin': {
                'adult': {'range': (500, 1000), 'unit': 'mg', 'max_daily': 2550, 'frequency': 'twice daily'},
                'pediatric': {'range': (500, 1000), 'unit': 'mg', 'max_daily': 2000, 'frequency': 'twice daily'},
                'geriatric': {'range': (500, 850), 'unit': 'mg', 'max_daily': 1500, 'frequency': 'once or twice daily'},
                'notes': ["Monitor renal function", "Risk of lactic acidosis"]
            },
            'lisinopril': {
                'adult': {'range': (10, 40), 'unit': 'mg', 'max_daily': 80, 'frequency': 'once daily'},
                'pediatric': {'range': (0.07, 0.3), 'unit': 'mg/kg', 'max_daily': 40, 'frequency': 'once daily'},
                'geriatric': {'range': (2.5, 20), 'unit': 'mg', 'max_daily': 40, 'frequency': 'once daily'},
                'notes': ["Monitor blood pressure and potassium", "Risk of angioedema"]
            },
            'warfarin': {
                'adult': {'range': (2, 10), 'unit': 'mg', 'max_daily': 15, 'frequency': 'once daily'},
                'pediatric': {'range': (0.1, 0.2), 'unit': 'mg/kg', 'max_daily': 10, 'frequency': 'once daily'},
                'geriatric': {'range': (1, 5), 'unit': 'mg', 'max_daily': 10, 'frequency': 'once daily'},
                'notes': ["Monitor INR regularly", "Avoid with certain foods/drugs"]
            }
        }

    async def verify_dosage(self, medicine: str, dosage: str, age: int, 
                           weight: float, frequency: str = 'Not specified') -> Dict[str, Any]:
        """
        Verify if the prescribed dosage is appropriate for the patient's age, weight, and frequency
        
        Args:
            medicine: Name of the medicine
            dosage: Prescribed dosage string
            age: Patient's age
            weight: Patient's weight in kg
            frequency: Dosing frequency (e.g., 'twice daily')
            
        Returns:
            Dictionary with dosage verification results
        """
        result = {
            'has_issues': False,
            'severity': 'low',
            'issues': [],
            'recommended_dosage': 'Not available',
            'therapeutic_range': 'Not available',
            'clinical_notes': [],
            'age_group': self._get_age_group(age),
            'weight_based_analysis': {}
        }
        
        try:
            med_lower = medicine.lower()
            cache_key = f"dosage_{med_lower}_{dosage}_{age}_{weight}_{frequency}"
            
            if self.model_mode == 'api':
                prompt = f"""Verify the appropriateness of {dosage} {frequency} for {medicine} in a {age}-year-old patient weighing {weight}kg.
Return JSON: {{
    "has_issues": bool,
    "severity": "low|medium|high",
    "issues": ["string"],
    "recommended_dosage": "string",
    "therapeutic_range": "string",
    "clinical_notes": ["string"],
    "age_group": "pediatric|adult|geriatric",
    "weight_based_analysis": {{"prescribed_mg_per_kg": "string", "recommended_mg_per_kg": "string"}}
}}
Example: {{
    "has_issues": true,
    "severity": "medium",
    "issues": ["Dose exceeds therapeutic range"],
    "recommended_dosage": "200-400mg every 6 hours",
    "therapeutic_range": "200-800mg/dose, max 3200mg/day",
    "clinical_notes": ["Monitor renal function"],
    "age_group": "adult",
    "weight_based_analysis": {{"prescribed_mg_per_kg": "12mg/kg", "recommended_mg_per_kg": "5-10mg/kg"}}
}}"""
                try:
                    response = await query_granite(prompt, cache_key=cache_key)
                    import json
                    # Validate JSON response
                    schema = {
                        "type": "object",
                        "properties": {
                            "has_issues": {"type": "boolean"},
                            "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "recommended_dosage": {"type": "string"},
                            "therapeutic_range": {"type": "string"},
                            "clinical_notes": {"type": "array", "items": {"type": "string"}},
                            "age_group": {"type": "string", "enum": ["pediatric", "adult", "geriatric"]},
                            "weight_based_analysis": {
                                "type": "object",
                                "properties": {
                                    "prescribed_mg_per_kg": {"type": "string"},
                                    "recommended_mg_per_kg": {"type": "string"}
                                }
                            }
                        },
                        "required": ["has_issues", "severity", "issues", "recommended_dosage", 
                                    "therapeutic_range", "clinical_notes", "age_group"]
                    }
                    granite_result = json.loads(response)
                    jsonschema.validate(granite_result, schema)
                    if isinstance(granite_result, dict):
                        return granite_result
                    logger.warning("Invalid Granite response format. Falling back to rule-based.")
                except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                    logger.warning(f"Granite verification failed: {str(e)}. Falling back to rule-based.")
            
            # Rule-based verification
            prescribed_amount = self._parse_dosage_amount(dosage)
            age_group = self._get_age_group(age)
            adjustment_info = self.dosage_adjustments.get(age_group, self.dosage_adjustments['adult'])
            
            # Get dosage guidelines
            dosage_info = self.dosage_guidelines.get(med_lower, self._get_mock_dosage_guidelines(med_lower))
            dosage_info = dosage_info.get(age_group, dosage_info.get('adult', {}))
            
            # Analyze dosage
            if prescribed_amount and dosage_info.get('range'):
                analysis = self._analyze_dosage(
                    prescribed_amount=prescribed_amount,
                    dosage_info=dosage_info,
                    adjustment_info=adjustment_info,
                    age_group=age_group,
                    weight=weight,
                    frequency=frequency
                )
                result.update(analysis)
            else:
                result.update(self._get_general_age_recommendations(med_lower, age_group, dosage))
            
            # Weight-based analysis for pediatric/low-weight patients
            if weight > 0 and med_lower in ['ibuprofen', 'acetaminophen', 'lisinopril', 'warfarin']:
                weight_analysis = self._analyze_weight_based_dosage(
                    medicine=med_lower,
                    prescribed_amount=prescribed_amount,
                    weight=weight,
                    dosage_info=dosage_info
                )
                result['weight_based_analysis'] = weight_analysis
                if weight_analysis.get('issues'):
                    result['has_issues'] = True
                    result['issues'].extend(weight_analysis['issues'])
                    result['severity'] = max(result['severity'], weight_analysis['severity'], key=lambda x: ['low', 'medium', 'high'].index(x))
            
            # Frequency validation
            if frequency != 'Not specified':
                freq_analysis = self._analyze_frequency(
                    frequency=frequency,
                    dosage_info=dosage_info,
                    prescribed_amount=prescribed_amount
                )
                if freq_analysis.get('issues'):
                    result['has_issues'] = True
                    result['issues'].extend(freq_analysis['issues'])
                    result['severity'] = max(result['severity'], freq_analysis['severity'], key=lambda x: ['low', 'medium', 'high'].index(x))
            
            # Add clinical notes from guidelines
            if med_lower in self.dosage_guidelines:
                result['clinical_notes'].extend(self.dosage_guidelines[med_lower].get('notes', []))
            
            logger.info(f"Dosage verification completed for {medicine}: {result}")
            
        except Exception as e:
            logger.error(f"Error verifying dosage for {medicine}: {str(e)}")
            result['issues'].append(f"Unable to verify dosage for {medicine}. Consult healthcare provider.")
            result['severity'] = 'medium'
        
        return result

    async def find_alternatives(self, medicine: str) -> List[Dict[str, Any]]:
        """
        Find alternative medications with the same active ingredient
        
        Args:
            medicine: Name of the medicine to find alternatives for
            
        Returns:
            List of alternative medications
        """
        alternatives = []
        
        try:
            if self.model_mode == 'api':
                prompt = f"""Suggest 5 alternative medications to {medicine} with the same active ingredient or similar effects.
Return JSON array: [{{"name": "string", "rxcui": "string", "strength": "string", "dosage_form": "string", "reason": "string"}}]"""
                try:
                    response = await query_granite(prompt)
                    import json
                    # Validate JSON response
                    schema = {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "rxcui": {"type": "string"},
                                "strength": {"type": "string"},
                                "dosage_form": {"type": "string"},
                                "reason": {"type": "string"}
                            },
                            "required": ["name", "reason"]
                        }
                    }
                    alternatives = json.loads(response)
                    jsonschema.validate(alternatives, schema)
                    if alternatives:
                        return alternatives[:5]
                    logger.warning("Granite returned empty alternatives. Falling back.")
                except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                    logger.warning(f"Granite alternatives failed: {str(e)}. Falling back.")
            
            rxcui = await self._get_rxcui(medicine)
            if not rxcui:
                return alternatives
            
            related_drugs = await self._get_related_drugs(rxcui)
            
            for drug in related_drugs:
                if drug.get('name', '').lower() != medicine.lower():
                    alternatives.append({
                        'name': drug.get('name'),
                        'rxcui': drug.get('rxcui'),
                        'strength': drug.get('strength', 'Unknown'),
                        'dosage_form': drug.get('doseFormName', 'Unknown'),
                        'reason': 'Same active ingredient with potentially safer profile'
                    })
            
            alternatives = alternatives[:5]
            
        except Exception as e:
            logger.error(f"Error finding alternatives for {medicine}: {str(e)}")
        
        return alternatives

    async def _get_rxcui(self, medicine: str) -> Optional[str]:
        """
        Get RxCUI (unique identifier) for a medicine from RxNorm API
        
        Args:
            medicine: Medicine name
            
        Returns:
            RxCUI string or None if not found
        """
        try:
            url = f"{self.base_url}/rxcui.json"
            params = {
                'name': medicine,
                'search': '2'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        id_group = data.get('idGroup', {})
                        rxnorm_ids = id_group.get('rxnormId', [])
                        if rxnorm_ids:
                            return rxnorm_ids[0]
            
        except Exception as e:
            logger.error(f"Error getting RxCUI for {medicine}: {str(e)}")
        
        return None

    def _parse_dosage_amount(self, dosage_str: str) -> Optional[float]:
        """
        Parse numerical dosage amount from string
        
        Args:
            dosage_str: Dosage string (e.g., "325mg")
            
        Returns:
            Dosage amount as float or None if invalid
        """
        try:
            match = re.search(r'(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg)', dosage_str, re.IGNORECASE)
            if match:
                amount = float(match.group(1))
                unit = match.group(2).lower()
                
                if unit == 'g':
                    return amount * 1000
                elif unit == 'mcg':
                    return amount / 1000
                elif unit == 'ml':
                    return amount
                return amount
        except Exception as e:
            logger.error(f"Error parsing dosage amount from '{dosage_str}': {str(e)}")
        
        return None

    def _analyze_dosage(self, prescribed_amount: float, dosage_info: Dict[str, Any], 
                       adjustment_info: Dict[str, Any], age_group: str, 
                       weight: float, frequency: str) -> Dict[str, Any]:
        """
        Analyze dosage appropriateness based on standard dosage and age adjustments
        
        Args:
            prescribed_amount: Prescribed dosage amount
            dosage_info: Standard dosage information
            adjustment_info: Age-based adjustment information
            age_group: Patient's age group
            weight: Patient's weight in kg
            frequency: Dosing frequency
            
        Returns:
            Analysis results dictionary
        """
        analysis = {
            'has_issues': False,
            'severity': 'low',
            'issues': [],
            'recommended_dosage': 'Not available',
            'therapeutic_range': 'Not available',
            'clinical_notes': adjustment_info.get('special_considerations', [])
        }
        
        try:
            min_dose, max_dose = dosage_info.get('range', (0, 0))
            max_daily = dosage_info.get('max_daily', float('inf'))
            standard_frequency = dosage_info.get('frequency', 'Not specified')
            
            # Set therapeutic range
            if dosage_info.get('unit') == 'mg/kg':
                analysis['therapeutic_range'] = (
                    f"{min_dose}-{max_dose} {dosage_info['unit']}/dose, "
                    f"max {max_daily} {dosage_info['unit']}/day"
                )
            else:
                analysis['therapeutic_range'] = (
                    f"{min_dose}-{max_dose} {dosage_info['unit']}/dose, "
                    f"max {max_daily} {dosage_info['unit']}/day"
                )
            
            # Adjust dose for age group
            adjusted_min = min_dose * adjustment_info['factor']
            adjusted_max = max_dose * adjustment_info['factor']
            
            # Check if prescribed dose is within range
            if prescribed_amount:
                if dosage_info.get('unit') == 'mg/kg':
                    prescribed_mg_per_kg = prescribed_amount
                    prescribed_amount = prescribed_amount * weight
                
                if prescribed_amount < adjusted_min:
                    analysis['has_issues'] = True
                    analysis['severity'] = 'medium'
                    analysis['issues'].append(
                        f"Prescribed dose ({prescribed_amount} {dosage_info['unit']}) is below "
                        f"therapeutic range ({adjusted_min}-{adjusted_max} {dosage_info['unit']})."
                    )
                    analysis['recommended_dosage'] = (
                        f"{adjusted_min}-{adjusted_max} {dosage_info['unit']} {standard_frequency}"
                    )
                elif prescribed_amount > adjusted_max:
                    analysis['has_issues'] = True
                    analysis['severity'] = 'high'
                    analysis['issues'].append(
                        f"Prescribed dose ({prescribed_amount} {dosage_info['unit']}) exceeds "
                        f"therapeutic range ({adjusted_min}-{adjusted_max} {dosage_info['unit']})."
                    )
                    analysis['recommended_dosage'] = (
                        f"{adjusted_min}-{adjusted_max} {dosage_info['unit']} {standard_frequency}"
                    )
                else:
                    analysis['recommended_dosage'] = (
                        f"{adjusted_min}-{adjusted_max} {dosage_info['unit']} {standard_frequency}"
                    )
            
            # Check daily dose limit
            if max_daily != float('inf') and prescribed_amount:
                daily_dose = self._estimate_daily_dose(prescribed_amount, frequency)
                if daily_dose and daily_dose > max_daily:
                    analysis['has_issues'] = True
                    analysis['severity'] = max(analysis['severity'], 'high', key=lambda x: ['low', 'medium', 'high'].index(x))
                    analysis['issues'].append(
                        f"Estimated daily dose ({daily_dose} {dosage_info['unit']}/day) exceeds "
                        f"maximum daily limit ({max_daily} {dosage_info['unit']}/day)."
                    )
                    analysis['recommended_dosage'] = (
                        f"{adjusted_min}-{adjusted_max} {dosage_info['unit']} {standard_frequency}, "
                        f"max {max_daily} {dosage_info['unit']}/day"
                    )
            
        except Exception as e:
            logger.error(f"Error analyzing dosage: {str(e)}")
            analysis['issues'].append("Unable to analyze dosage. Consult clinical guidelines.")
            analysis['severity'] = 'medium'
        
        return analysis

    def _analyze_weight_based_dosage(self, medicine: str, prescribed_amount: float, 
                                   weight: float, dosage_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze weight-based dosing for pediatric or low-weight patients
        
        Args:
            medicine: Medicine name
            prescribed_amount: Prescribed dosage amount
            weight: Patient's weight in kg
            dosage_info: Dosage information
            
        Returns:
            Weight-based analysis dictionary
        """
        analysis = {
            'prescribed_mg_per_kg': 'Not applicable',
            'recommended_mg_per_kg': 'Not applicable',
            'issues': [],
            'severity': 'low'
        }
        
        if not weight or not prescribed_amount or dosage_info.get('unit') != 'mg/kg':
            return analysis
        
        try:
            prescribed_mg_per_kg = prescribed_amount / weight
            min_mg_per_kg, max_mg_per_kg = dosage_info.get('range', (0, 0))
            analysis['prescribed_mg_per_kg'] = f"{prescribed_mg_per_kg:.1f} mg/kg"
            analysis['recommended_mg_per_kg'] = f"{min_mg_per_kg}-{max_mg_per_kg} mg/kg"
            
            if prescribed_mg_per_kg < min_mg_per_kg:
                analysis['issues'].append(
                    f"Prescribed dose ({prescribed_mg_per_kg:.1f} mg/kg) is below "
                    f"recommended range ({min_mg_per_kg}-{max_mg_per_kg} mg/kg)."
                )
                analysis['severity'] = 'medium'
            elif prescribed_mg_per_kg > max_mg_per_kg:
                analysis['issues'].append(
                    f"Prescribed dose ({prescribed_mg_per_kg:.1f} mg/kg) exceeds "
                    f"recommended range ({min_mg_per_kg}-{max_mg_per_kg} mg/kg)."
                )
                analysis['severity'] = 'high'
        
        except Exception as e:
            logger.error(f"Error in weight-based analysis for {medicine}: {str(e)}")
            analysis['issues'].append("Unable to perform weight-based analysis.")
        
        return analysis

    def _analyze_frequency(self, frequency: str, dosage_info: Dict[str, Any], 
                          prescribed_amount: float) -> Dict[str, Any]:
        """
        Analyze dosing frequency for appropriateness
        
        Args:
            frequency: Prescribed frequency
            dosage_info: Dosage information
            prescribed_amount: Prescribed dosage amount
            
        Returns:
            Frequency analysis dictionary
        """
        analysis = {
            'issues': [],
            'severity': 'low'
        }
        
        standard_frequency = dosage_info.get('frequency', 'Not specified')
        if frequency.lower() == 'not specified' or standard_frequency == 'not specified':
            analysis['issues'].append("Frequency not specified. Verify dosing schedule.")
            analysis['severity'] = 'medium'
            return analysis
        
        # Check for frequency mismatch
        freq_map = {
            'once daily': 1,
            'twice daily': 2,
            'three times daily': 3,
            'four times daily': 4,
            'every 4-6 hours': 4,
            'every 6-8 hours': 3,
            'every 8 hours': 3,
            'as needed': 1  # Conservative estimate for PRN
        }
        
        prescribed_freq = freq_map.get(frequency.lower(), 1)
        standard_freq = freq_map.get(standard_frequency.lower(), 1)
        
        if prescribed_freq > standard_freq:
            analysis['issues'].append(
                f"Prescribed frequency ({frequency}) is more frequent than recommended ({standard_frequency})."
            )
            analysis['severity'] = 'medium'
        
        return analysis

    def _estimate_daily_dose(self, prescribed_amount: float, frequency: str) -> Optional[float]:
        """
        Estimate daily dose based on frequency
        
        Args:
            prescribed_amount: Single dose amount
            frequency: Dosing frequency
            
        Returns:
            Estimated daily dose or None
        """
        try:
            freq_map = {
                'once daily': 1,
                'twice daily': 2,
                'three times daily': 3,
                'four times daily': 4,
                'every 4-6 hours': 4,
                'every 6-8 hours': 3,
                'every 8 hours': 3,
                'as needed': 1  # Conservative estimate
            }
            
            match = re.search(r'every (\d+) hours', frequency, re.IGNORECASE)
            if match:
                hours = int(match.group(1))
                doses_per_day = 24 / hours
                return prescribed_amount * doses_per_day
            
            return prescribed_amount * freq_map.get(frequency.lower(), 1)
        
        except Exception as e:
            logger.error(f"Error estimating daily dose: {str(e)}")
            return None

    def _get_general_age_recommendations(self, medicine: str, age_group: str, 
                                       dosage: str) -> Dict[str, Any]:
        """
        Provide general age-based recommendations when specific dosage info is not available
        
        Args:
            medicine: Medicine name
            age_group: Patient's age group
            dosage: Prescribed dosage string
            
        Returns:
            General recommendations dictionary
        """
        adjustment_info = self.dosage_adjustments.get(age_group, self.dosage_adjustments['adult'])
        
        recommendations = {
            'has_issues': True,
            'severity': 'medium',
            'issues': [f"Insufficient dosage data for {medicine}. Verify with clinical guidelines."],
            'recommended_dosage': 'Consult clinical guidelines',
            'therapeutic_range': 'Not available',
            'clinical_notes': adjustment_info.get('special_considerations', [])
        }
        
        return recommendations

    def _get_mock_dosage_guidelines(self, rxcui: str) -> Dict[str, Any]:
        """
        Mock dosage guidelines for demonstration purposes
        
        Args:
            rxcui: RxNorm unique identifier
            
        Returns:
            Mock dosage guidelines
        """
        return {
            'adult': {'range': (500, 1000), 'unit': 'mg', 'max_daily': 2000, 'frequency': 'twice daily'},
            'pediatric': {'range': (10, 20), 'unit': 'mg/kg', 'max_daily': 40, 'frequency': 'every 6 hours'},
            'geriatric': {'range': (250, 750), 'unit': 'mg', 'max_daily': 1500, 'frequency': 'twice daily'},
            'notes': ["Monitor for adverse effects", "Consult prescribing information"]
        }

    async def _get_related_drugs(self, rxcui: str) -> List[Dict[str, Any]]:
        """
        Get related drugs by RxCUI from RxNorm API
        
        Args:
            rxcui: RxNorm unique identifier
            
        Returns:
            List of related drugs
        """
        try:
            url = f"{self.base_url}/rxcui/{rxcui}/related.json"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        related_groups = data.get('relatedGroup', {}).get('conceptGroup', [])
                        drugs = []
                        for group in related_groups:
                            if 'conceptProperties' in group:
                                for prop in group['conceptProperties']:
                                    drugs.append({
                                        'name': prop.get('name'),
                                        'rxcui': prop.get('rxcui'),
                                        'strength': prop.get('strength', 'Unknown'),
                                        'dosage_form': prop.get('doseFormName', 'Unknown')
                                    })
                        return drugs
        except Exception as e:
            logger.error(f"Error getting related drugs for RxCUI {rxcui}: {str(e)}")
        return []

    async def close(self):
        """Close any open sessions"""
        if self.session:
            await self.session.close()
