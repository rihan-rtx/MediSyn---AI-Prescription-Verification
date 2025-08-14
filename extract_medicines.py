import re
import logging
import os
from typing import List, Dict, Any
from granite_utils import query_granite

logger = logging.getLogger(__name__)

class MedicineExtractor:
    """
    Medicine extractor using regex patterns and Granite model
    """
    
    def __init__(self):
        """Initialize the medicine extractor"""
        self.model_mode = os.environ.get('MODEL_LOADING_MODE', 'api')
        self.common_medicines = {
            'aspirin', 'ibuprofen', 'acetaminophen', 'paracetamol', 'warfarin',
            'metformin', 'insulin', 'amoxicillin', 'lisinopril', 'atorvastatin',
            'amlodipine', 'metoprolol', 'omeprazole', 'losartan', 'furosemide',
            'prednisone', 'tramadol', 'gabapentin', 'sertraline', 'fluoxetine'
        }
        
        self.patterns = [
            r'\b([a-zA-Z]+)\s*(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|units?)\b',
            r'(?:take|prescribed)\s+([a-zA-Z]+)',
            r'\b(' + '|'.join(self.common_medicines) + r')\b'
        ]
    
    async def extract_medicines(self, prescription_text: str) -> List[str]:
        """
        Extract medicine names from prescription text
        
        Args:
            prescription_text: The prescription text to analyze
            
        Returns:
            List of extracted medicine names
        """
        medicines = set()
        text_lower = prescription_text.lower()
        
        try:
            if self.model_mode == 'api':
                prompt = f"""Extract all unique medicine names from the following prescription text. 
Return only a JSON array of strings (e.g., ["medicine1", "medicine2"]), no other text or explanations.

Prescription text: {prescription_text}"""
                
                response = await query_granite(prompt)
                import json
                try:
                    extracted = json.loads(response)
                    if isinstance(extracted, list):
                        medicines = {med.lower().strip() for med in extracted if med.strip()}
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse Granite response as JSON: {response}. Falling back to regex.")
            
            if not medicines:
                for pattern in self.patterns:
                    matches = re.findall(pattern, text_lower, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            medicine_name = match[0] if match[0] else match[-1]
                        else:
                            medicine_name = match
                        medicine_name = medicine_name.strip()
                        if len(medicine_name) > 2 and medicine_name.isalpha():
                            medicines.add(medicine_name)
                
                stop_words = {
                    'take', 'with', 'food', 'daily', 'twice', 'once', 'three', 'times',
                    'tablet', 'capsule', 'pill', 'dose', 'after', 'before', 'morning',
                    'evening', 'night', 'day', 'week', 'month', 'per', 'as', 'needed'
                }
                medicines = {med for med in medicines if med not in stop_words}
            
            logger.info(f"Extracted medicines: {list(medicines)}")
            return list(medicines)
            
        except Exception as e:
            logger.error(f"Error extracting medicines: {str(e)}")
            return []
    
    async def extract_medicines_with_dosages(self, prescription_text: str) -> List[Dict[str, Any]]:
        """
        Extract medicines along with their dosages
        
        Args:
            prescription_text: The prescription text to analyze
            
        Returns:
            List of dictionaries containing medicine and dosage information
        """
        medicines_with_dosages = []
        text_lower = prescription_text.lower()
        
        try:
            if self.model_mode == 'api':
                prompt = f"""Extract medicines with their dosages from the prescription text. 
Return only a JSON array of objects, each with keys: "medicine" (string), "dosage" (string, e.g., "325mg").
Example: [{{"medicine": "aspirin", "dosage": "325mg"}}]

Prescription text: {prescription_text}"""
                
                response = await query_granite(prompt)
                import json
                try:
                    extracted = json.loads(response)
                    if isinstance(extracted, list):
                        for item in extracted:
                            med = item.get('medicine', '').strip().lower()
                            dos = item.get('dosage', 'Not specified').strip()
                            if med:
                                try:
                                    amount_match = re.search(r'(\d+(?:\.\d+)?)', dos)
                                    amount = float(amount_match.group(1)) if amount_match else None
                                    unit_match = re.search(r'(mg|g|ml|mcg|units?)', dos, re.I)
                                    unit = unit_match.group(1) if unit_match else None
                                except:
                                    amount, unit = None, None
                                medicines_with_dosages.append({
                                    'medicine': med,
                                    'dosage': dos,
                                    'amount': amount,
                                    'unit': unit
                                })
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse Granite response: {response}. Falling back to regex.")
            
            if not medicines_with_dosages:
                dosage_pattern = r'\b([a-zA-Z]+)\s*(\d+(?:\.\d+)?)\s*(mg|g|ml|mcg|units?)\b'
                matches = re.findall(dosage_pattern, text_lower, re.IGNORECASE)
                
                for medicine, amount, unit in matches:
                    if len(medicine) > 2 and medicine.isalpha():
                        medicines_with_dosages.append({
                            'medicine': medicine,
                            'dosage': f"{amount}{unit}",
                            'amount': float(amount),
                            'unit': unit
                        })
                
                if not medicines_with_dosages:
                    medicine_names = await self.extract_medicines(prescription_text)
                    for med in medicine_names:
                        medicines_with_dosages.append({
                            'medicine': med,
                            'dosage': 'Not specified',
                            'amount': None,
                            'unit': None
                        })
            
            logger.info(f"Extracted medicines with dosages: {medicines_with_dosages}")
            return medicines_with_dosages
            
        except Exception as e:
            logger.error(f"Error extracting medicines with dosages: {str(e)}")
            return []
    
    def extract_frequency(self, prescription_text: str) -> Dict[str, str]:
        """
        Extract frequency information from prescription text
        
        Args:
            prescription_text: The prescription text to analyze
            
        Returns:
            Dictionary with frequency information
        """
        frequency_patterns = {
            'once_daily': r'\b(?:once|one time)\s*(?:daily|per day|a day)\b',
            'twice_daily': r'\b(?:twice|two times)\s*(?:daily|per day|a day)\b',
            'three_times_daily': r'\b(?:three times|thrice)\s*(?:daily|per day|a day)\b',
            'four_times_daily': r'\b(?:four times)\s*(?:daily|per day|a day)\b',
            'as_needed': r'\b(?:as needed|prn|when needed)\b',
            'every_x_hours': r'\bevery\s*(\d+)\s*hours?\b'
        }
        
        frequencies = {}
        text_lower = prescription_text.lower()
        
        for freq_type, pattern in frequency_patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                if freq_type == 'every_x_hours':
                    frequencies[freq_type] = f"every {match.group(1)} hours"
                else:
                    frequencies[freq_type] = freq_type.replace('_', ' ')
        
        return frequencies