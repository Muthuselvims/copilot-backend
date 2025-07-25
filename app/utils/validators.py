from difflib import get_close_matches

def validate_against_sample_data(sample_data: set, text: str) -> bool:
    """
    Returns True if the text (as a phrase or words) has close match in sample data values.
    """
    # Lowercase version of sample data
    lower_sample = {s.lower() for s in sample_data}
    
    # Check full phrase match
    if text.lower() in lower_sample:
        return True

    # Split into words and check for fuzzy matches
    words = text.lower().split()
    match_count = 0

    for word in words:
        if get_close_matches(word, lower_sample, cutoff=0.9):  # strict match
            match_count += 1

    # Require at least 2 strong matches for relevance
    return match_count >= 2
