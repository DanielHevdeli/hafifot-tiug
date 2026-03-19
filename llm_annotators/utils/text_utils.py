from ..config import LABELS
def normalize_label(raw_output: str) -> str:
    s = raw_output.strip().lower()
    labels = LABELS.keys()
    for label in labels:
        if label in s:
            return label
    return "unknown"

def truncate_text(text: str, max_length: int = 3000) -> str:
    return text[:max_length]