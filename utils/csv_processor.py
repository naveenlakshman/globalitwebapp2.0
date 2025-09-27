import pandas as pd
import csv
from io import StringIO
from typing import Dict, List, Tuple, Any, Optional
from werkzeug.datastructures import FileStorage

class CSVProcessor:
    """Handle CSV file processing and parsing"""
    
    @staticmethod
    def read_csv_file(file: FileStorage, encoding: str = 'utf-8') -> Tuple[bool, Any, str]:
        """
        Read and parse CSV file
        Returns: (success, dataframe/error_message, message)
        """
        try:
            # Read file content
            file_content = file.read()
            
            # Try different encodings if utf-8 fails
            encodings_to_try = [encoding, 'utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            
            for enc in encodings_to_try:
                try:
                    decoded_content = file_content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return False, None, "Unable to decode file. Please check file encoding."
            
            # Create StringIO object
            csv_data = StringIO(decoded_content)
            
            # Read CSV with pandas
            df = pd.read_csv(csv_data)
            
            # Basic validation
            if df.empty:
                return False, None, "CSV file is empty"
            
            # Clean column names (remove extra spaces, convert to lowercase)
            df.columns = df.columns.str.strip()
            
            return True, df, f"Successfully read {len(df)} rows"
            
        except pd.errors.EmptyDataError:
            return False, None, "CSV file is empty or contains no data"
        except pd.errors.ParserError as e:
            return False, None, f"CSV parsing error: {str(e)}"
        except Exception as e:
            return False, None, f"Error reading CSV file: {str(e)}"
    
    @staticmethod
    def validate_csv_structure(df: pd.DataFrame, required_columns: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate CSV has required columns
        Returns: (is_valid, missing_columns)
        """
        df_columns = [col.lower().strip() for col in df.columns]
        required_lower = [col.lower().strip() for col in required_columns]
        
        missing_columns = []
        for req_col in required_lower:
            if req_col not in df_columns:
                missing_columns.append(req_col)
        
        return len(missing_columns) == 0, missing_columns
    
    @staticmethod
    def get_sample_data(df: pd.DataFrame, num_rows: int = 5) -> List[Dict]:
        """Get sample rows for preview"""
        sample_df = df.head(num_rows)
        # Convert to list of dictionaries and handle NaN values
        sample_data = []
        for _, row in sample_df.iterrows():
            row_dict = {}
            for col, value in row.items():
                # Handle NaN and None values
                if pd.isna(value):
                    row_dict[col] = ''
                else:
                    row_dict[col] = str(value)
            sample_data.append(row_dict)
        
        return sample_data
    
    @staticmethod
    def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Clean dataframe by handling common issues"""
        # Create a copy to avoid modifying original
        cleaned_df = df.copy()
        
        # Replace NaN with empty strings for string columns
        for col in cleaned_df.columns:
            if cleaned_df[col].dtype == 'object':
                cleaned_df[col] = cleaned_df[col].fillna('')
                # Strip whitespace
                cleaned_df[col] = cleaned_df[col].astype(str).str.strip()
        
        # For numeric columns, replace NaN with 0
        numeric_columns = cleaned_df.select_dtypes(include=['float64', 'int64']).columns
        for col in numeric_columns:
            cleaned_df[col] = cleaned_df[col].fillna(0)
        
        return cleaned_df
    
    @staticmethod
    def map_columns(df: pd.DataFrame, column_mapping: Dict[str, str]) -> pd.DataFrame:
        """
        Map CSV columns to database field names
        column_mapping: {csv_column: db_field}
        """
        mapped_df = df.copy()
        
        # Rename columns based on mapping
        rename_dict = {}
        for csv_col, db_field in column_mapping.items():
            if csv_col in mapped_df.columns:
                rename_dict[csv_col] = db_field
        
        mapped_df = mapped_df.rename(columns=rename_dict)
        
        return mapped_df
    
    @staticmethod
    def get_column_mapping_suggestions(df_columns: List[str], model_fields: List[str]) -> Dict[str, str]:
        """
        Suggest column mappings based on similarity
        Returns: {csv_column: suggested_db_field}
        """
        suggestions = {}
        
        # Common mapping patterns
        common_mappings = {
            'name': 'full_name',
            'student_name': 'full_name',
            'phone': 'mobile',
            'phone_number': 'mobile',
            'contact': 'mobile',
            'email_id': 'email',
            'email_address': 'email',
            'course': 'course_name',
            'batch': 'batch_id',
            'branch': 'branch_id',
            'amount': 'total_amount',
            'fee': 'total_amount',
            'payment_mode': 'mode',
            'payment_method': 'mode',
            'date': 'payment_date',
            'paid_date': 'payment_date'
        }
        
        for csv_col in df_columns:
            csv_col_lower = csv_col.lower().strip()
            
            # Direct match
            if csv_col_lower in [f.lower() for f in model_fields]:
                suggestions[csv_col] = csv_col_lower
                continue
            
            # Check common mappings
            if csv_col_lower in common_mappings:
                suggested_field = common_mappings[csv_col_lower]
                if suggested_field in [f.lower() for f in model_fields]:
                    suggestions[csv_col] = suggested_field
                    continue
            
            # Partial match
            for field in model_fields:
                if csv_col_lower in field.lower() or field.lower() in csv_col_lower:
                    suggestions[csv_col] = field
                    break
        
        return suggestions

class DataMapper:
    """Handle data type conversion and mapping"""
    
    @staticmethod
    def convert_to_database_format(data: Dict, field_types: Dict[str, str]) -> Dict:
        """
        Convert data types to match database requirements
        field_types: {field_name: type} where type is 'string', 'integer', 'float', 'date', 'datetime', 'boolean'
        """
        converted_data = data.copy()
        
        for field, field_type in field_types.items():
            if field not in converted_data:
                continue
                
            value = converted_data[field]
            
            # Skip empty values
            if value is None or value == '':
                continue
                
            try:
                if field_type == 'integer':
                    converted_data[field] = int(float(value))
                elif field_type == 'float':
                    converted_data[field] = float(value)
                elif field_type == 'boolean':
                    if isinstance(value, str):
                        converted_data[field] = value.lower() in ['true', '1', 'yes', 'y']
                    else:
                        converted_data[field] = bool(value)
                elif field_type == 'date':
                    if isinstance(value, str):
                        from datetime import datetime
                        # Convert Indian format to database format
                        converted_date = DataMapper.convert_indian_date_format(value, include_time=False)
                        if converted_date:
                            converted_data[field] = datetime.strptime(converted_date, '%Y-%m-%d').date()
                elif field_type == 'datetime':
                    if isinstance(value, str):
                        from datetime import datetime
                        # Convert Indian format to database format
                        converted_datetime = DataMapper.convert_indian_date_format(value, include_time=True)
                        if converted_datetime:
                            converted_data[field] = datetime.strptime(converted_datetime, '%Y-%m-%d %H:%M:%S')
                        else:
                            # Fallback to existing formats
                            formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']
                            parsed = False
                            for fmt in formats:
                                try:
                                    converted_data[field] = datetime.strptime(value, fmt)
                                    parsed = True
                                    break
                                except ValueError:
                                    continue
                            if not parsed:
                                # If no format matches, use current datetime
                                from datetime import timezone
                                converted_data[field] = datetime.now(timezone.utc)
                # 'string' type requires no conversion
                
            except (ValueError, TypeError) as e:
                # Log the conversion error but don't fail
                print(f"Warning: Could not convert {field} value '{value}' to {field_type}: {e}")
                continue
        
        return converted_data
    
    @staticmethod
    def generate_student_id(prefix: str = "ST", existing_ids: List[str] = None) -> str:
        """Generate unique student ID"""
        if existing_ids is None:
            existing_ids = []
        
        # Find the highest existing number
        max_num = 0
        for existing_id in existing_ids:
            if existing_id.startswith(prefix):
                try:
                    num = int(existing_id[len(prefix):])
                    max_num = max(max_num, num)
                except ValueError:
                    continue
        
        # Generate new ID
        new_num = max_num + 1
        return f"{prefix}{new_num:03d}"  # Format: ST001, ST002, etc.
    
    @staticmethod
    def clean_mobile_number(mobile: str) -> str:
        """Clean and format mobile number"""
        if not mobile:
            return ""
        
        # Remove all non-digit characters
        import re
        cleaned = re.sub(r'[^\d]', '', str(mobile))
        
        # If starts with country code, remove it
        if len(cleaned) > 10 and cleaned.startswith('91'):
            cleaned = cleaned[2:]
        
        return cleaned if len(cleaned) == 10 else mobile
    
    @staticmethod
    def convert_indian_date_format(date_str: str, include_time: bool = False) -> str:
        """Convert DD-MM-YYYY [HH:MM AM/PM] or DD-MM-YYYY HH:MM format to database format"""
        if not date_str:
            return None
            
        try:
            import re
            from datetime import datetime
            
            date_str = str(date_str).strip()
            
            if include_time:
                # Handle DD-MM-YYYY HH:MM AM/PM format (12-hour)
                ampm_patterns = [
                    r'(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)',
                    r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)',
                    r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)'
                ]
                
                # Try 12-hour format first
                for pattern in ampm_patterns:
                    match = re.match(pattern, date_str, re.IGNORECASE)
                    if match:
                        day, month, year, hour, minute, ampm = match.groups()
                        
                        # Convert 12-hour to 24-hour format
                        hour = int(hour)
                        if ampm.upper() == 'PM' and hour != 12:
                            hour += 12
                        elif ampm.upper() == 'AM' and hour == 12:
                            hour = 0
                            
                        # Create datetime object and format for database
                        dt = datetime(int(year), int(month), int(day), hour, int(minute))
                        return dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # Handle DD-MM-YYYY HH:MM format (24-hour, no AM/PM)
                hour24_patterns = [
                    r'(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2})$',
                    r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})$',
                    r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})$'
                ]
                
                for pattern in hour24_patterns:
                    match = re.match(pattern, date_str)
                    if match:
                        day, month, year, hour, minute = match.groups()
                        
                        # Create datetime object and format for database
                        dt = datetime(int(year), int(month), int(day), int(hour), int(minute))
                        return dt.strftime('%Y-%m-%d %H:%M:%S')
            
            else:
                # Handle DD-MM-YYYY format (date only)
                patterns = [
                    r'(\d{1,2})-(\d{1,2})-(\d{4})',
                    r'(\d{1,2})/(\d{1,2})/(\d{4})',
                    r'(\d{1,2})\.(\d{1,2})\.(\d{4})'
                ]
                
                for pattern in patterns:
                    match = re.match(pattern, date_str)
                    if match:
                        day, month, year = match.groups()
                        # Create date object and format for database
                        dt = datetime(int(year), int(month), int(day))
                        return dt.strftime('%Y-%m-%d')
            
            # If no pattern matches, try to parse as existing format
            return date_str
            
        except Exception as e:
            print(f"Warning: Could not convert date '{date_str}': {e}")
            return date_str
    
    @staticmethod
    def convert_time_format(time_str: str) -> str:
        """Convert time from various formats to HH:MM:SS (24-hour) format"""
        if not time_str:
            return None
            
        try:
            import re
            from datetime import datetime, time
            
            time_str = str(time_str).strip()
            
            # Handle 12-hour format with AM/PM
            ampm_patterns = [
                r'(\d{1,2}):(\d{2})\s*(AM|PM)',           # 2:00 PM
                r'(\d{1,2}):(\d{2})(AM|PM)',              # 2:00PM (no space)
                r'(\d{1,2})\.(\d{2})\s*(AM|PM)',          # 2.00 PM  
                r'(\d{1,2})\.(\d{2})(AM|PM)',             # 2.00PM (no space)
                r'(\d{1,2}):(\d{2})\s*([AP]M)',           # 2:00 P
                r'(\d{1,2}):(\d{2})([AP]M)',              # 2:00P (no space)
                r'(\d{1,2})\.(\d{2})\s*([AP]M)',          # 2.00 P
                r'(\d{1,2})\.(\d{2})([AP]M)',             # 2.00P (no space)
                r'(\d{1,2})\s*(AM|PM)',                   # 11 AM, 2 PM
                r'(\d{1,2})(AM|PM)',                      # 11AM, 2PM (no space)
                r'(\d{1,2})\s*([AP]M)',                   # 11 A, 2 P
                r'(\d{1,2})([AP]M)'                       # 11A, 2P (no space)
            ]
            
            for i, pattern in enumerate(ampm_patterns):
                match = re.match(pattern, time_str, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    
                    if i >= 8:  # Patterns without minutes (11 AM, 2 PM, 11AM, 2PM)
                        hour = int(groups[0])
                        minute = 0
                        ampm = groups[1]
                    else:  # Patterns with minutes (2:00 PM, 2:00PM)
                        hour = int(groups[0])
                        minute = int(groups[1])
                        ampm = groups[2] if len(groups) > 2 else groups[1]
                    
                    # Convert 12-hour to 24-hour format
                    if ampm.upper() in ['PM', 'P.M.', 'PM', 'P'] and hour != 12:
                        hour += 12
                    elif ampm.upper() in ['AM', 'A.M.', 'AM', 'A'] and hour == 12:
                        hour = 0
                    
                    # Validate ranges
                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        # Return as time object formatted as string
                        time_obj = time(hour, minute)
                        return time_obj.strftime('%H:%M:%S')
            
            # Handle 24-hour format (HH:MM or HH:MM:SS)
            hour24_patterns = [
                r'^(\d{1,2}):(\d{2}):(\d{2})$',  # HH:MM:SS
                r'^(\d{1,2}):(\d{2})$',          # HH:MM
                r'^(\d{1,2})\.(\d{2})$'          # HH.MM
            ]
            
            for i, pattern in enumerate(hour24_patterns):
                match = re.match(pattern, time_str)
                if match:
                    if i == 0:  # HH:MM:SS format
                        hour, minute, second = match.groups()
                        second = int(second)
                    else:  # HH:MM or HH.MM format
                        hour, minute = match.groups()
                        second = 0
                    
                    # Convert to integers
                    hour = int(hour)
                    minute = int(minute)
                    
                    # Validate ranges
                    if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                        # Return as time object formatted as string
                        time_obj = time(hour, minute, second)
                        return time_obj.strftime('%H:%M:%S')
            
            return None
            
        except Exception as e:
            print(f"Warning: Could not convert time '{time_str}': {e}")
            return None

    @staticmethod
    def generate_student_reg_no(prefix: str = "GIT", existing_reg_nos: List[str] = None) -> str:
        """Generate unique student registration number in format GIT-1, GIT-2, etc."""
        if existing_reg_nos is None:
            existing_reg_nos = []
        
        # Find the highest existing number
        max_num = 0
        for existing_reg_no in existing_reg_nos:
            if existing_reg_no.startswith(f"{prefix}-"):
                try:
                    num = int(existing_reg_no.split('-')[1])
                    max_num = max(max_num, num)
                except (ValueError, IndexError):
                    continue
        
        # Generate new registration number
        new_num = max_num + 1
        return f"{prefix}-{new_num}"  # Format: GIT-1, GIT-2, etc.
