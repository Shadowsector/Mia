"""Project Ledger Manager - manages construction object diaries with Google Drive integration.

Each ledger represents a construction object with chronological document tracking.
Files are downloaded temporarily, processed, added to RAG, then deleted.
Only metadata and links are preserved.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ObjectMetadata:
    """Metadata for a construction object."""
    ledger_name: str  # e.g., "Судакова 5 - МГТС"
    address: str  # e.g., "г. Москва, улица Судакова, владение 5"
    customer: str  # e.g., "МГТС"
    city: str = "Москва"  # default city
    google_drive_folder_id: Optional[str] = None
    telegram_chat_id: Optional[int] = None
    created_at: str = None
    last_synced: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class ProjectLedgerManager:
    """Manages project ledgers for construction objects."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.ledgers_dir = data_dir / "project_ledgers"
        self.ledgers_dir.mkdir(parents=True, exist_ok=True)
        self.ledgers_index_file = self.ledgers_dir / "index.json"
        self._load_index()
    
    def _load_index(self):
        """Load the ledgers index from file."""
        if self.ledgers_index_file.exists():
            with open(self.ledgers_index_file, 'r', encoding='utf-8') as f:
                self.ledgers_index = json.load(f)
        else:
            self.ledgers_index = {}
    
    def _save_index(self):
        """Save the ledgers index to file."""
        with open(self.ledgers_index_file, 'w', encoding='utf-8') as f:
            json.dump(self.ledgers_index, f, ensure_ascii=False, indent=2)
    
    def create_ledger_name(self, folder_name: str, customer: Optional[str] = None) -> str:
        """Generate a standardized ledger name from folder name and customer.
        
        Examples:
            "Судакова 5" + "МГТС" → "Судакова 5 - МГТС"
            "Профсоюзная 60" + "Моссвет" → "Профсоюзная 60 - Моссвет"
        
        Note: This name is used for display only. Directory names are sanitized.
        """
        # Clean up folder name
        clean_name = folder_name.strip()
        
        # Add customer if provided
        if customer:
            return f"{clean_name} - {customer}"
        return clean_name
    
    def _sanitize_dir_name(self, ledger_name: str) -> str:
        """Sanitize ledger name for use as directory name.
        
        Replaces invalid characters with underscores.
        """
        import re
        # Replace invalid characters for Windows filenames
        # Invalid: < > : " / \ | ? *
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', ledger_name)
        # Also replace multiple underscores with single
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized
    
    def infer_customer_from_path(self, folder_path: str) -> Optional[str]:
        """Infer customer from folder path or parent folders.
        
        Known customers: МГТС, Ростелеком, Вымпелком, Моссвет, Комкор, 
                       МПТЦ, 2КОМ, Мослифт, ОЭК, МОЭК, Мосгаз, ЦОДД, Россети
        """
        known_customers = [
            "МГТС", "Ростелеком", "Вымпелком", "Моссвет", "Комкор",
            "МПТЦ", "2КОМ", "Мослифт", "ОЭК", "МОЭК", "Мосгаз", "ЦОДД", "Россети"
        ]
        
        # Check if any known customer is in the path
        for customer in known_customers:
            if customer in folder_path:
                return customer
        
        return None
    
    def detect_object_folders(self, drive_scan_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Detect construction object folders from Google Drive scan result.
        
        Returns list of detected objects with metadata.
        Only considers folders at appropriate depth (not deep subfolders).
        """
        detected_objects = []
        
        # Handle both old format (folders dict) and new format (folder_structure tree)
        folders_to_scan = []
        
        if 'folders' in drive_scan_result:
            # Old format: direct folders dict
            for folder_id, folder_data in drive_scan_result['folders'].items():
                folders_to_scan.append({
                    'id': folder_id,
                    'name': folder_data.get('name', ''),
                    'path': folder_data.get('path', '')
                })
        elif 'folder_structure' in drive_scan_result:
            # New format: hierarchical folder_structure
            def extract_folders(node, path_prefix=""):
                """Recursively extract folders from folder_structure."""
                current_name = node.get('name', '')
                current_path = f"{path_prefix}/{current_name}" if path_prefix else current_name
                
                # Add current folder
                folders_to_scan.append({
                    'id': node.get('folder_id', ''),
                    'name': current_name,
                    'path': current_path
                })
                
                # Recursively process subfolders
                for subfolder in node.get('subfolders', []):
                    extract_folders(subfolder, current_path)
            
            extract_folders(drive_scan_result['folder_structure'])
        
        # Look for top-level folders that look like construction objects
        seen_names = set()
        for folder in folders_to_scan:
            folder_name = folder['name']
            folder_path = folder['path']
            
            # Skip if it's clearly a system folder or technical category
            if folder_name.lower() in ['docs', 'documents', 'архив', 'backup', 'temp', 'сканы', 'scans']:
                continue
            
            # Skip the scan folder
            if '!_Сканы' in folder_path:
                continue
            
            # Skip the root folder
            if folder_name == '5_Стройка':
                continue
            
            # Filter by path depth - only consider folders at depth 2-3
            # Example: "5_Стройка/Москва. Стройка/Маршала Жукова 25/1" (depth 3)
            path_parts = folder_path.split('/')
            path_depth = len(path_parts)
            
            # Temporarily remove strict depth filter to see all candidates
            # Skip deep subfolders (depth > 4)
            if path_depth > 4:
                continue
            
            # Skip very shallow folders (depth 1 = direct under root)
            if path_depth <= 1:
                continue
            
            # Skip the scan folder
            if '!_Сканы' in folder_path:
                continue
            
            # Skip if already seen this name (remove duplicates)
            # But allow duplicates across different depth levels
            if folder_name in seen_names and path_depth == 3:
                continue
            
            # Heuristic: construction object folders often have:
            # - Address-like names (e.g., "Судакова 5", "Профсоюзная 60")
            # - Street names (e.g., "Маршала Жукова", "Вернадского")
            # - Numbers combined with words
            
            if self._is_construction_object(folder_name):
                customer = self.infer_customer_from_path(folder_path)
                ledger_name = self.create_ledger_name(folder_name, customer)
                
                detected_objects.append({
                    'folder_id': folder['id'],
                    'folder_name': folder_name,
                    'folder_path': folder_path,
                    'ledger_name': ledger_name,
                    'customer': customer,
                    'detected_at': datetime.now().isoformat()
                })
                
                seen_names.add(folder_name)
        
        return detected_objects
    
    def _is_construction_object(self, folder_name: str) -> bool:
        """Heuristic to determine if a folder is a construction object.
        
        RADICAL SIMPLIFICATION: if it starts with a city name and has depth 2-3, it's likely an object.
        """
        import re
        
        # RADICAL: If it starts with "Москва," it's likely an object (highest priority)
        if folder_name.startswith('Москва,'):
            return True
        
        # Also for other cities
        if re.match(r'^(Москва|Сергиев|Щербинка|Котельники|Мытищи|Балашиха|Одинцово|Звенигород|Сколково|Алабушево),\s+', folder_name):
            return True
        
        # Exclude very short names
        if len(folder_name) < 3:
            return False
        
        # Exclude numbers-only
        if re.match(r'^\d+$', folder_name):
            return False
        
        # Exclude clearly technical/organizational folders
        exclude_keywords = [
            'нсс', 'участок', 'замечания', 'коррект', 'редакция', 'правки',
            'согласование', 'ппр', 'пд', 'ид', 'ос', 'опс', 'ту', 'рту',
            'план', 'схема', 'паспорт', 'ак', 'кк', 'ккс', 'скан', 'red',
            'подпись', 'эцп', 'исполнительная', 'технический', 'проект',
            'счета', 'аренда', 'архив', 'исходные данные', 'сети связи',
            'гп', 'рт', 'авр', 'списки', 'этап', 'бюро'
        ]
        
        folder_lower = folder_name.lower()
        for keyword in exclude_keywords:
            if keyword in folder_lower:
                return False
        
        # Exclude "РД" patterns (e.g., "РД 2024", "РД 2024 г")
        if re.match(r'^РД\s*\d', folder_name, re.IGNORECASE):
            return False
        
        # Exclude "ВОЛС" patterns
        if re.search(r'ВОЛС', folder_name, re.IGNORECASE):
            return False
        
        # Exclude date patterns (e.g., "РД на 15.01.26", "Архив 16.03.2023")
        if re.search(r'\d{2}\.\d{2}\.\d{2,4}', folder_name):
            return False
        
        # Exclude date-only patterns (e.g., "20230602")
        if re.match(r'^\d{8}$', folder_name):
            return False
        
        # Exclude stage patterns (e.g., "Этап 1", "Этап 2", "Этап 3.2, 3.3")
        if re.match(r'^Этап\s+\d', folder_name):
            return False
        
        # Exclude patterns like "1 Замечания", "2 План"
        if re.match(r'^\d+\s+\w+', folder_name):
            return False
        
        # POSITIVE INDICATORS - be very permissive
        
        # Address pattern: word + number (e.g., "Судакова 5", "Профсоюзная 60")
        if re.search(r'[А-Яа-яA-Za-z]+\s+\d+', folder_name):
            return True
        
        # Street name pattern (e.g., "Маршала Жукова", "Вернадского")
        street_keywords = ['улица', 'ул', 'бульвар', 'проспект', 'проезд', 'переулок', 'шоссе', 'пр-т']
        if any(keyword in folder_lower for keyword in street_keywords):
            return True
        
        # Known street names
        known_streets = [
            'Маршала Жукова', 'Люблинская', 'Новохорошевский', 'Сиреневый',
            'Звенигородская', 'Вернадского', 'Профсоюзная', 'Судакова',
            'Ярославское', 'Локомотивный', 'Производственная', 'Коммунарка',
            'Бескудниковский', 'Лухмановская', 'Верхоянская', 'Олимпийский',
            'Очаковская', 'Химушкина', 'Полярная', 'Филевская', 'Переведеновский',
            'Рижский', 'Марьиной', 'Парковая', 'Щелковский', 'Симоновская',
            'Ереванские', 'Новощукинская', 'Окружная', 'Переведеновский'
        ]
        if any(street in folder_name for street in known_streets):
            return True
        
        # City + address pattern (e.g., "Москва, Маршала Жукова")
        if re.search(r'[А-Яа-я]+\s*,\s*[А-Яа-я]+', folder_name):
            return True
        
        # Address with suffix in parentheses (e.g., "Маршала Жукова 25/1 (ГК ПИК)")
        if re.search(r'[А-Яа-я]+\s+\d+[\/\\]?\d*\s*\([^)]+\)', folder_name):
            return True
        
        # Address with "к" suffix (e.g., "Профсоюзная 60к1 60к2")
        if re.search(r'[А-Яа-я]+\s+\d+[кК]\d+', folder_name):
            return True
        
        # Named locations (e.g., "Сергиев Посад", "Щербинка", "Котельники")
        location_keywords = ['Посад', 'поселок', 'село', 'деревня', 'город', 'д.']
        if any(keyword in folder_name for keyword in location_keywords):
            return True
        
        # Known cities/locations
        known_locations = [
            'Сергиев Посад', 'Щербинка', 'Котельники', 'Мытищи', 'Балашиха',
            'Одинцово', 'Звенигород', 'Сколково', 'Алабушево'
        ]
        if any(location in folder_name for location in known_locations):
            return True
        
        # "влд" pattern (e.g., "Новощукинская влд 3")
        if 'влд' in folder_name.lower():
            return True
        
        # "бл" pattern (e.g., "Сиреневый бл 4")
        if re.search(r'бл\s*\d', folder_name):
            return True
        
        # "вл" pattern (e.g., "Люблинская 125")
        if re.search(r'[А-Яа-я]+\s+\d+[вВ]', folder_name):
            return True
        
        # "двор" pattern (e.g., "Рижский двор")
        if 'двор' in folder_name.lower():
            return True
        
        # "развязка" pattern (e.g., "Каширское шоссе Развязка")
        if 'развязка' in folder_name.lower():
            return True
        
        # Assume it's an object if it has a city name at the start
        if re.match(r'^[А-Яа-я]+,\s+', folder_name):
            return True
        
        return False
    
    def create_object_ledger(self, metadata: ObjectMetadata) -> str:
        """Create a new ledger for a construction object.
        
        Returns the ledger path.
        """
        # Use sanitized name for directory, keep original for display
        dir_name = self._sanitize_dir_name(metadata.ledger_name)
        ledger_dir = self.ledgers_dir / dir_name
        ledger_dir.mkdir(parents=True, exist_ok=True)
        
        # Save metadata with original ledger name
        metadata_file = ledger_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(metadata), f, ensure_ascii=False, indent=2)
        
        # Add to index (use original ledger name as key)
        self.ledgers_index[metadata.ledger_name] = {
            'dir_name': dir_name,
            'path': str(ledger_dir),
            'metadata': asdict(metadata),
            'created_at': metadata.created_at
        }
        self._save_index()
        
        logger.info(f"Created ledger: {metadata.ledger_name} (dir: {dir_name})")
        return str(ledger_dir)
    
    def get_ledger_by_name(self, ledger_name: str) -> Optional[Dict[str, Any]]:
        """Get ledger information by name."""
        return self.ledgers_index.get(ledger_name)
    
    def get_all_ledgers(self) -> Dict[str, Any]:
        """Get all ledgers."""
        return self.ledgers_index
    
    def update_last_synced(self, ledger_name: str):
        """Update the last synced timestamp for a ledger."""
        if ledger_name in self.ledgers_index:
            self.ledgers_index[ledger_name]['last_synced'] = datetime.now().isoformat()
            self._save_index()
    
    def add_document_reference(self, ledger_name: str, document_ref: Dict[str, Any]):
        """Add a document reference to a ledger (not the file itself).
        
        document_ref format:
        {
            'source': 'google_drive' | 'telegram',
            'source_id': 'file_id' or 'message_id',
            'source_url': 'https://drive.google.com/...' or 'Telegram message reference',
            'file_name': 'document.pdf',
            'added_at': '2026-09-13T14:30:00Z',
            'metadata': {...}
        }
        """
        ledger_info = self.get_ledger_by_name(ledger_name)
        if not ledger_info:
            logger.error(f"Ledger not found: {ledger_name}")
            return
        
        ledger_dir = Path(ledger_info['path'])
        documents_dir = ledger_dir / "documents"
        documents_dir.mkdir(exist_ok=True)
        
        # Save document reference (not the file)
        doc_ref_file = documents_dir / f"{document_ref['source_id']}.json"
        with open(doc_ref_file, 'w', encoding='utf-8') as f:
            json.dump(document_ref, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Added document reference to {ledger_name}: {document_ref['file_name']}")
