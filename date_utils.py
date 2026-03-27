"""
Date parsing utilities for relative date handling
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

class DateExtractor:
    """Extract and parse relative dates from text"""
    
    def __init__(self):
        # Define relative date patterns
        self.date_patterns = {
            # English patterns
            'today': 0,
            'yesterday': -1,
            'day before yesterday': -2,
            'tomorrow': 1,
            'day after tomorrow': 2,
            'this morning': 0,
            'this afternoon': 0,
            'this evening': 0,
            'tonight': 0,
            'last night': -1,
            'this week': 0,
            'last week': -7,
            'next week': 7,
            'this month': 0,
            'last month': -30,
            'next month': 30,
            
            # Common variations
            'today morning': 0,
            'today afternoon': 0,
            'today evening': 0,
            'yesterday morning': -1,
            'yesterday afternoon': -1,
            'yesterday evening': -1,
            'tomorrow morning': 1,
            'tomorrow afternoon': 1,
            'tomorrow evening': 1,
        }
        
        # Compile regex patterns for case-insensitive matching
        self.compiled_patterns = {}
        for pattern, offset in self.date_patterns.items():
            # Create regex that matches the pattern as whole words
            regex_pattern = r'\b' + re.escape(pattern) + r'\b'
            self.compiled_patterns[pattern] = re.compile(regex_pattern, re.IGNORECASE)
    
    def extract_relative_dates(self, text: str, reference_date: Optional[datetime] = None) -> Dict[str, any]:
        """
        Extract relative dates from text and convert to actual dates
        
        Args:
            text: Input text to search for relative dates
            reference_date: Reference date (defaults to current date)
            
        Returns:
            Dict containing:
            - 'found_dates': List of found relative date phrases
            - 'converted_dates': List of actual dates
            - 'text_with_dates': Text with relative dates replaced with actual dates
            - 'has_relative_dates': Boolean indicating if relative dates were found
        """
        if reference_date is None:
            reference_date = datetime.now()
        
        found_dates = []
        converted_dates = []
        text_with_dates = text
        
        # Search for each pattern
        for pattern, offset in self.date_patterns.items():
            if pattern in self.compiled_patterns:
                matches = self.compiled_patterns[pattern].finditer(text)
                
                for match in matches:
                    found_dates.append(match.group())
                    
                    # Calculate actual date
                    actual_date = reference_date + timedelta(days=offset)
                    date_str = actual_date.strftime("%Y-%m-%d")
                    converted_dates.append(date_str)
                    
                    # Replace in text
                    text_with_dates = text_with_dates.replace(match.group(), date_str)
        
        return {
            'found_dates': found_dates,
            'converted_dates': converted_dates,
            'text_with_dates': text_with_dates,
            'has_relative_dates': len(found_dates) > 0
        }
    
    def parse_query_dates(self, query: str, reference_date: Optional[datetime] = None) -> Tuple[str, Optional[str]]:
        """
        Parse query for relative dates and return modified query with date filter
        
        Args:
            query: Search query text
            reference_date: Reference date (defaults to current date)
            
        Returns:
            Tuple of (modified_query, date_filter)
        """
        if reference_date is None:
            reference_date = datetime.now()
        
        # Extract relative dates
        result = self.extract_relative_dates(query, reference_date)
        
        if result['has_relative_dates']:
            # Use the first found date as filter
            date_filter = result['converted_dates'][0]
            modified_query = result['text_with_dates']
            
            logger.info(f"Query date parsing: '{query}' -> date_filter: {date_filter}")
            return modified_query, date_filter
        
        return query, None
    
    def add_date_to_memory_text(self, text: str, reference_date: Optional[datetime] = None) -> str:
        """
        Add date information to memory text when relative dates are found
        
        Args:
            text: Memory text
            reference_date: Reference date (defaults to current date)
            
        Returns:
            Enhanced text with date information
        """
        if reference_date is None:
            reference_date = datetime.now()
        
        result = self.extract_relative_dates(text, reference_date)
        
        if result['has_relative_dates']:
            # Add date information to the text
            date_info = f" [Dates mentioned: {', '.join(result['found_dates'])} -> {', '.join(result['converted_dates'])}]"
            return text + date_info
        
        return text

# Global instance
date_extractor = DateExtractor()
