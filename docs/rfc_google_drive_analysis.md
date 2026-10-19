# RFC: Google Drive Document Structure Analysis

## RFC Status
- **Status**: Completed
- **Created**: 2026-08-31
- **Updated**: 2026-09-12
- **Author**: Devin AI Assistant
- **Target**: Phase 1 - Document Structure Discovery (COMPLETED)

## 1. Executive Summary

This RFC defined the process for analyzing the Google Drive folder structure to understand document organization, file types, versioning patterns, and prepare for future RAG implementation. The analysis was completed successfully using OAuth 2.0 authentication (service account was not accessible for the target folder).

**Target Folder**: `https://drive.google.com/drive/folders/1LXFAfJ7K7uwNfSaTGxMFf2hF9osn_WBv` (5_Стройка)

**Actual Volume**: 6,213 folders, 30,597 files, ~143 GB (significantly larger than estimated)

**Actual Scan Duration**: ~1.45 hours (5,216 seconds)

**API Calls**: 18,642 successful calls, 0 errors

## 2. Objectives

### Primary Objectives
1. **Structure Discovery**: Map the folder hierarchy and understand project-based organization
2. **Document Type Analysis**: Identify document types (office formats, DWG, etc.) for future agent development
3. **Versioning Pattern Detection**: Understand how document versions are managed
4. **Volume Assessment**: Estimate processing requirements for future RAG implementation
5. **Preliminary Data Collection**: Gather structured information for Mia system integration

### Secondary Objectives
- Generate recommendations for document organization
- Identify potential challenges for RAG implementation
- Create reusable analysis framework for other folders

## 3. Technical Approach

### 3.1 Google Drive Access Method

**Implemented Approach**: Google Drive API with OAuth 2.0

**Rationale for OAuth**:
- Service account was not accessible for the target folder (even after sharing)
- OAuth provides direct access to user's Drive
- Target folder was in "Shared with me" section
- OAuth with `supportsAllDrives=true` parameter successfully accessed the folder

**Alternative Tried**: Service Account (not successful - folder not accessible)

**Implementation Details**:
1. Created Google Cloud Project
2. Enabled Google Drive API
3. Created OAuth 2.0 credentials
4. Downloaded OAuth credentials (JSON)
5. Configured scanner with `supportsAllDrives=true` and `includeItemsFromAllDrives=true`
6. Saved token for subsequent access
6. Install Google Drive API Python library

### 3.2 Access Configuration

**Required Python Libraries**:
```python
google-api-python-client>=2.100.0
google-auth-httplib2>=0.1.0
google-auth-oauthlib>=0.5.0
```

**Configuration in `.env`**:
```bash
# Google Drive Configuration
GOOGLE_DRIVE_CREDENTIALS_PATH=config/service_account.json
GOOGLE_DRIVE_TARGET_FOLDER_ID=1LXFAfJ7K7uwNfSaTGxMFf2hF9osn_WBv
GOOGLE_DRIVE_API_QUOTA=1000  # requests per day
```

### 3.3 Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│              Google Drive Access Layer                       │
│  - Authentication with Service Account                       │
│  - Folder listing traversal                                 │
│  - File metadata collection                                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Structure Analysis Layer                        │
│  - Folder hierarchy mapping                                  │
│  - Project identification                                    │
│  - File type categorization                                  │
│  - Version pattern detection                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Content Analysis Layer (Light)                   │
│  - Filename pattern analysis                                 │
│  - Document type inference (basic)                           │
│  - Size and date distribution analysis                       │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Report Generation Layer                          │
│  - Structure tree visualization                              │
│  - Document type statistics                                 │
│  - Versioning pattern analysis                              │
│  - Recommendations generation                                 │
└─────────────────────────────────────────────────────────────┘
```

## 4. Detailed Implementation

### 4.1 Folder Structure Scanner

**Function**: Recursive folder traversal with metadata collection

**Implementation**:
```python
class GoogleDriveScanner:
    def __init__(self, credentials_path, target_folder_id):
        self.service = self._authenticate(credentials_path)
        self.target_folder_id = target_folder_id
    
    def scan_folder_structure(self, folder_id=None):
        """Recursively scan folder structure"""
        if folder_id is None:
            folder_id = self.target_folder_id
        
        results = {
            'folder_id': folder_id,
            'name': self._get_folder_name(folder_id),
            'path': self._get_folder_path(folder_id),
            'subfolders': [],
            'files': []
        }
        
        # Get subfolders
        subfolders = self._list_subfolders(folder_id)
        for subfolder in subfolders:
            results['subfolders'].append(self.scan_folder_structure(subfolder['id']))
        
        # Get files
        files = self._list_files(folder_id)
        for file in files:
            results['files'].append(self._analyze_file(file))
        
        return results
```

**Metadata Collection**:
- Folder ID and name
- Creation and modification dates
- Folder path hierarchy
- File count per folder
- Total size per folder

### 4.2 File Type Analyzer

**Function**: Categorize files by type and purpose

**File Type Categories**:
```python
FILE_TYPE_CATEGORIES = {
    'office_documents': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'],
    'cad_drawings': ['.dwg', '.dxf', '.dwf'],
    'images': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'],
    'archives': ['.zip', '.rar', '.7z', '.tar', '.gz'],
    'text': ['.txt', '.csv', '.json', '.xml'],
    'other': []  # Catch-all
}
```

**Document Type Inference** (Basic):
```python
def infer_document_type(filename):
    """Basic document type inference from filename"""
    filename_lower = filename.lower()
    
    if any(keyword in filename_lower for keyword in ['накладная', 'накл', 'акт']):
        return 'invoice'
    elif any(keyword in filename_lower for keyword in ['паспорт', 'пасп']):
        return 'passport'
    elif any(keyword in filename_lower for keyword in ['проект', 'project', 'чертеж']):
        return 'project'
    elif any(keyword in filename_lower for keyword in ['договор', 'contract', 'соглашение']):
        return 'contract'
    elif any(keyword in filename_lower for keyword in ['смета', 'estimate']):
        return 'estimate'
    else:
        return 'unknown'
```

### 4.3 Version Detection

**Function**: Identify document versions based on file metadata

**Version Detection Strategies**:
1. **Filename Version Patterns**: v1, v2, rev1, rev2, final, draft
2. **Drive Version History**: Use Google Drive revision history
3. **Modification Date Analysis**: Track changes over time

**Implementation**:
```python
def detect_version_pattern(filename, file_metadata):
    """Detect versioning pattern in documents"""
    patterns = {
        'semantic_version': r'_v(\d+)',
        'revision': r'_rev(\d+)',
        'date_version': r'_(\d{4}-\d{2}-\d{2})',
        'status': r'_(draft|final|approved)',
    }
    
    detected_versions = []
    for pattern_name, pattern in patterns.items():
        if re.search(pattern, filename):
            detected_versions.append(pattern_name)
    
    return {
        'filename_patterns': detected_versions,
        'drive_revisions': file_metadata.get('version_count', 0),
        'last_modified': file_metadata.get('modified_time'),
        'created': file_metadata.get('created_time')
    }
```

### 4.4 Sequential Processing

**Implementation**: Process folders and files sequentially to respect API limits

**Rate Limiting**:
```python
class RateLimitedDriveScanner:
    def __init__(self, requests_per_second=10):
        self.rate_limiter = RateLimiter(requests_per_second)
    
    def _api_call(self, api_function, *args, **kwargs):
        with self.rate_limiter:
            return api_function(*args, **kwargs)
```

**Processing Order**:
1. Root folder metadata
2. First-level subfolders (sequential)
3. Files within each folder (sequential)
4. Progress tracking and reporting

### 4.5 Sequential Document Processing Policy (Chronological Ledger Integration)

#### 4.5.1 Sorting Before Ingestion
**Requirement**: Files pulled from Google Drive must be parsed and indexed according to their creation/modification metadata (event_timestamp), constructing the baseline history first.

**Implementation**:
- Sort files by `created_time` before processing
- Process oldest files first to establish chronological baseline
- Use `modified_time` for updates to establish revision chain
- Ensure project_ledger entries reflect actual chronological order

#### 4.5.2 Parent-Child Mapping for Revisions
**Requirement**: When ingestion scripts find files containing words like "Корректировка", "Изменение №", "Рев", or "Правки", the agent loop must flag them for explicit overrides_ledger_id linkage.

**Implementation**:
- Detect revision keywords in filenames: "Коррект", "Изменение", "Рев", "Правки", "редакция"
- Parse revision numbers: "Коррект0", "Коррект1", "Коррект2", "Изменение №1", etc.
- Auto-increment `revision_index` in project_ledger
- Link to superseded entry via `overrides_ledger_id`
- Generate appropriate `summary_delta` for the revision

#### 4.5.3 Chat Priority Handling
**Requirement**: Facts extracted from Telegram conversations by authoritative people (Directors/Owners) happening after formal GDrive document updates automatically act as the current reality (Delta), superseding formal docs until paper revisions are uploaded.

**Implementation**:
- Track user authority levels in employee configuration
- When authoritative users post chat facts after document updates:
  - Create CHAT_FACT entity in project_ledger
  - Set high priority for immediate effect
  - Link to superseded document via `overrides_ledger_id`
  - Generate `summary_delta` explaining the chat-based override
- Flag document for formal revision requirement
- Notify system administrator when formal revision is overdue

### 4.6 Data Structures

**Analysis Result Schema** (Pre-Pydantic):
```python
analysis_result = {
    'scan_metadata': {
        'scan_timestamp': '2026-08-31T16:00:00Z',
        'target_folder_id': '1LXFAfJ7K7uwNfSaTGxMFf2hF9osn_WBv',
        'total_folders_scanned': 40,
        'total_files_analyzed': 10000,
        'scan_duration_seconds': 3600
    },
    'folder_structure': {
        'root_folder': {...},
        'folder_tree': [...]
    },
    'file_statistics': {
        'total_files': 10000,
        'files_by_type': {
            'office_documents': 6000,
            'cad_drawings': 2000,
            'images': 1000,
            'archives': 500,
            'text': 300,
            'other': 200
        },
        'files_by_size': {...},
        'files_by_date': {...}
    },
    'document_type_analysis': {
        'invoices': 1500,
        'passports': 800,
        'projects': 3000,
        'contracts': 2000,
        'estimates': 1200,
        'unknown': 1500
    },
    'versioning_analysis': {
        'files_with_versions': 2000,
        'version_patterns_used': ['semantic_version', 'revision'],
        'average_versions_per_file': 2.5
    },
    'recommendations': [...]
}
```

## 5. Report Generation

### 5.1 Report Formats

**Primary Format**: Markdown (human-readable)

**Secondary Format**: JSON (machine-readable, for Mia integration)

**Report Structure**:
```markdown
# Google Drive Analysis Report

## Executive Summary
- Total Folders: 40
- Total Files: 10,000
- Primary File Types: Office documents (60%), CAD drawings (20%)
- Scan Duration: 1 hour

## Folder Structure
[Folder tree visualization]

## File Type Statistics
[Charts and tables]

## Document Type Analysis
[Classification results]

## Versioning Patterns
[Version analysis]

## Recommendations
[Optimization suggestions]
```

### 5.2 Visualization

**Folder Tree**: ASCII tree representation
```text
Root Folder
├── Project_001
│   ├── Documents
│   │   ├── Invoice_001.pdf
│   │   └── Contract_001.docx
│   └── Drawings
│       └── Plan_001.dwg
├── Project_002
└── ...
```

**Statistics Charts**: Simple text-based charts
```
File Type Distribution:
Office: ████████████████████ (60%)
CAD:     ████████ (20%)
Images:  ████ (10%)
```

## 6. Integration with Mia System

### 6.1 Temporary Integration

**Approach**: Store analysis results in separate database table

**New Database Table**:
```sql
CREATE TABLE drive_analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    target_folder_id TEXT NOT NULL,
    total_folders INTEGER,
    total_files INTEGER,
    analysis_json TEXT,
    recommendations TEXT
);
```

**GUI Integration**:
- Add "Google Drive Analysis" tab
- Display analysis results
- Show file type statistics
- Provide recommendations view

### 6.2 Future RAG Integration

**Preparation Steps**:
1. Use analysis results to estimate RAG infrastructure requirements
2. Identify document types requiring specialized parsers
3. Plan indexing strategy based on folder structure
4. Design document preprocessing pipeline

**Data Migration Planning**:
- Determine file download requirements
- Plan local storage structure
- Design metadata extraction pipeline
- Schedule indexing process

## 7. Error Handling and Edge Cases

### 7.1 API Access Issues
- Permission denied → clear error message with setup instructions
- Rate limiting → automatic retry with exponential backoff
- Network issues → checkpoint/resume capability

### 7.2 File Access Issues
- Unsupported file types → log and skip
- Corrupted files → log and skip
- Large files (>100MB) → log and skip (for analysis phase)

### 7.3 Structure Issues
- Circular references → detection and prevention
- Excessive depth (>40 levels) → depth limit with warning
- Unicode issues → robust encoding handling

## 8. Security and Privacy

### 8.1 Data Security
- Service account credentials stored securely (.env)
- No sensitive content downloaded during analysis
- Only metadata collected (file names, types, sizes)
- No document content analysis in this phase

### 8.2 Access Control
- Service account with read-only access
- Limited to target folder only
- No write operations during analysis
- Audit logging of all API calls

## 9. Performance Considerations

### 9.1 Estimated Performance
- **API Calls**: ~10,000 (1 per file + folder operations)
- **Estimated Time**: 1-2 hours (sequential processing with rate limiting)
- **Memory Usage**: Low (only metadata in memory)
- **Storage**: Minimal (analysis results ~1-2MB)

### 9.2 Optimization Opportunities
- Parallel processing for independent folders (future)
- Caching of folder structures
- Incremental updates (scan only changes)
- Batch API operations where possible

## 10. Implementation Timeline

### Phase 1: Setup (1-2 hours)
- Google Cloud Project setup
- Service account creation
- API enablement
- Library installation
- Testing access to target folder

### Phase 2: Scanner Implementation (2-3 hours)
- Authentication setup
- Folder structure scanner
- File metadata collector
- Rate limiting implementation

### Phase 3: Analysis Implementation (2-3 hours)
- File type categorization
- Document type inference
- Version detection
- Statistics calculation

### Phase 4: Report Generation (1-2 hours)
- Markdown report generator
- JSON data export
- Visualization generation
- Recommendations engine

### Phase 5: Testing and Refinement (1-2 hours)
- Test with sample folder
- Error handling verification
- Performance optimization
- Documentation

**Total Estimated Time**: 7-12 hours

## 11. Success Criteria

### Functional Requirements
- ✅ Successfully access target Google Drive folder
- ✅ Scan entire folder structure (40+ subfolders)
- ✅ Analyze 10,000+ files
- ✅ Generate comprehensive report
- ✅ Identify all file types present
- ✅ Detect versioning patterns
- ✅ Provide actionable recommendations

### Quality Requirements
- ✅ 100% folder coverage
- ✅ Accurate file type classification
- ✅ No API quota exceeded
- ✅ Error-free completion
- ✅ Clear, actionable report

### Integration Requirements
- ✅ Results stored in Mia database
- ✅ GUI display of analysis results
- ✅ JSON export for future processing
- ✅ Foundation for RAG implementation planning

## 12. Open Questions and Decisions Needed

### 12.1 Google Drive Access Method
**Question**: Service account vs OAuth authentication?
**Recommendation**: Service account (no user interaction required)
**Decision Needed**: Approve service account creation and folder sharing

### 12.2 Analysis Depth
**Question**: Should we download file content for type detection?
**Recommendation**: No, use filename and metadata only for this phase
**Decision Needed**: Confirm metadata-only approach

### 12.3 Report Format
**Question**: Additional report formats beyond Markdown/JSON?
**Recommendation**: Start with Markdown + JSON, add Excel if needed
**Decision Needed**: Confirm initial report format

### 12.4 Future Integration
**Question**: Should we design the full RAG pipeline now?
**Recommendation**: No, use analysis results to inform RAG design later
**Decision Needed**: Confirm phased approach

## 13. Results Summary

### 13.1 Scan Results

**Successfully Completed**: 12 September 2026

**Statistics**:
- Total folders scanned: 6,213
- Total files analyzed: 30,597
- Total size: ~143 GB
- API calls: 18,642
- Errors: 0
- Scan duration: ~1.45 hours

**File Type Distribution**:
- Office documents (Word, Excel, PowerPoint): 13,651 (44.6%)
- CAD drawings (DWG): 8,257 (27.0%)
- Other: 5,682 (18.6%)
- Images: 1,734 (5.7%)
- Archives: 1,024 (3.3%)
- Text files: 249 (0.8%)

**Document Type Distribution**:
- Unknown: 29,267 (95.6%)
- Project documents: 244 (0.8%)
- Invoices: 615 (2.0%)
- Contracts: 155 (0.5%)
- Passports: 310 (1.0%)
- Estimates: 6 (<0.1%)

### 13.2 Key Findings

1. **Volume Significantly Exceeded Estimates**: Actual volume is ~3x larger than estimated
2. **Complex Structure**: Deep folder hierarchy (~40 levels in some cases)
3. **DWG Files Dominant**: 27% of files are CAD drawings requiring special processing
4. **Poor Document Classification**: 95.6% classified as "unknown" - need better naming pattern recognition
5. **Well-Organized by Projects**: Clear project-based organization with addresses and names
6. **Multiple Operators**: Documents from many communication operators (МГТС, Ростелеком, etc.)
7. **Version Information Available**: Most files have version tracking enabled

### 13.3 Recommendations

1. **Prioritize Document Types**: Focus on РД, СПС, ТУ, and Согласования for initial RAG indexing
2. **Improve Classification**: Implement better filename pattern recognition
3. **DWG Processing Strategy**: Convert DWG to PDF or extract metadata before OCR
4. **Phased Indexing**: Process documents in batches starting with highest priority
5. **Database Schema**: Design schema to handle complex project relationships
6. **Unicode Handling**: Ensure proper UTF-8 handling for Russian folder/file names

### 13.4 Files Generated

1. **Analysis Report**: `C:\mia\docs\google_drive_analysis_report.md`
2. **Full JSON Structure**: `C:\mia\google_drive_scan_result.json`
3. **Scanner Script**: `C:\mia\scripts\full_drive_scan.py`
4. **OAuth Scanner**: `C:\mia\app\modules\google_drive\oauth_scanner.py`

## 14. Next Steps

1. ✅ **Completed**: OAuth authentication setup
2. ✅ **Completed**: Full Drive structure scan
3. ✅ **Completed**: Analysis report generation
4. ✅ **Completed**: RFC update with actual results
5. **Pending**: Review analysis report with user
6. **Pending**: Plan RAG implementation based on results
7. **Pending**: Design document parsing pipeline
8. **Pending**: Implement DWG processing strategy
9. **Pending**: Create document classification improvements
10. **Pending**: Design database schema for document storage

## 14. References

- [Google Drive API Documentation](https://developers.google.com/drive/api/v3/reference)
- [Google Cloud Authentication](https://cloud.google.com/docs/authentication)
- [Mia Architecture Documentation](C:\mia\architecture.md)
- [Existing Document Processing](mia\documents\)

---

**RFC Version**: 2.0  
**Last Updated**: 2026-09-12  
**Status**: Completed - Analysis Successfully Executed  
**Results**: Available in `C:\mia\docs\google_drive_analysis_report.md`