import difflib
from typing import List, Dict, Tuple
from agents.state import ReviewState
from shared.schemas.finding import FindingCreate
from shared.db.models import SeverityLevel

def get_severity_weight(severity: SeverityLevel) -> int:
    weights = {
        SeverityLevel.error: 4,
        SeverityLevel.warning: 3,
        SeverityLevel.info: 2,
        SeverityLevel.suggestion: 1
    }
    return weights.get(severity, 0)

def compute_similarity(msg1: str, msg2: str) -> float:
    """Computes similarity ratio between two finding messages."""
    if not msg1 or not msg2:
        return 0.0
    return difflib.SequenceMatcher(None, msg1.lower(), msg2.lower()).ratio()

def deduplicate_findings(findings: List[FindingCreate]) -> List[FindingCreate]:
    """Deduplicate findings based on file, line, and message similarity."""
    
    deduped = []
    # Group by (file_path, line_number)
    grouped: Dict[Tuple[str, int], List[FindingCreate]] = {}
    
    for f in findings:
        if f.line_number is None:
            deduped.append(f)
            continue
            
        key = (f.file_path, f.line_number)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(f)
    
    for key, group_findings in grouped.items():
        if len(group_findings) <= 1:
            deduped.extend(group_findings)
            continue
            
        # Sort group by severity so we keep the most severe one when deduplicating
        group_findings.sort(key=lambda x: get_severity_weight(x.severity), reverse=True)
        
        unique_for_group = []
        for f in group_findings:
            is_duplicate = False
            for u in unique_for_group:
                if compute_similarity(f.message, u.message) > 0.8:
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_for_group.append(f)
                
        deduped.extend(unique_for_group)
        
    return deduped

def merger_node(state: ReviewState) -> dict:
    """Combines, deduplicates, sorts, and limits findings."""
    
    all_findings = []
    all_findings.extend(state.get("static_findings", []))
    all_findings.extend(state.get("security_findings", []))
    all_findings.extend(state.get("style_findings", []))
    all_findings.extend(state.get("arch_findings", []))
    
    deduped = deduplicate_findings(all_findings)
    
    # Sort by severity (descending)
    deduped.sort(key=lambda x: get_severity_weight(x.severity), reverse=True)
    
    # Limit to top 50
    final_findings = deduped[:50]
    
    return {"merged_findings": final_findings}
