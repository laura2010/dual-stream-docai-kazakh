import math

def deterministic_hybrid_fusion(aws_layout_blocks, google_ocr_tokens, page_width, page_height):
    """
    Implements the Deterministic Hybrid Layout-OCR Fusion algorithm.
    
    Args:
        aws_layout_blocks (list): List of dicts with keys ['Id', 'BlockType', 'Geometry'] from AWS.
        google_ocr_tokens (list): List of dicts with keys ['description', 'boundingPoly', 'property'] from GCV.
        page_width (int): Pixel width of the page.
        page_height (int): Pixel height of the page.
        
    Returns:
        list: Structured document object D (list of regions).
    """
    
    TOLERANCE = 0.02  # 2% spatial tolerance
    
    # --- Helper: Calculate Centroid ---
    def get_centroid(token, w, h):
        vertices = token['boundingPoly']['vertices']
        # Handle cases where vertices might be missing coordinates
        x_vals = [v.get('x', 0) for v in vertices]
        y_vals = [v.get('y', 0) for v in vertices]
        cx = sum(x_vals) / len(x_vals) / w # Normalize to 0-1
        cy = sum(y_vals) / len(y_vals) / h # Normalize to 0-1
        return cx, cy

    # --- Step 1: Prepare Layout Blocks (B) ---
    blocks = []
    for b in aws_layout_blocks:
        box = b['Geometry']['BoundingBox']
        blocks.append({
            'id': b['Id'],
            'label': b['BlockType'],
            'left': box['Left'],
            'top': box['Top'],
            'right': box['Left'] + box['Width'],
            'bottom': box['Top'] + box['Height'],
            'area': box['Width'] * box['Height'],
            'matched_indices': []
        })

    # Sort B in ascending order of area (to capture nested elements first)
    blocks.sort(key=lambda x: x['area'])

    # --- Step 2: Assign Tokens to Blocks ---
    used_indices = set()
    
    for i, token in enumerate(google_ocr_tokens):
        cx, cy = get_centroid(token, page_width, page_height)
        
        for b in blocks:
            # Check if centroid is within block bounds + tolerance
            if (b['left'] - TOLERANCE <= cx <= b['right'] + TOLERANCE) and \
               (b['top'] - TOLERANCE <= cy <= b['bottom'] + TOLERANCE):
                
                b['matched_indices'].append(i)
                used_indices.add(i)
                break # Matched to the smallest enclosing block, stop searching

    # --- Step 3: Reconstruct Regions (R) ---
    reconstructed_regions = []

    for b in blocks:
        # Sort matched indices to preserve reading order
        b['matched_indices'].sort()
        
        # Case A: Empty Blocks (Preserve visual anchors like Diagrams/Tables without text)
        if not b['matched_indices']:
            reconstructed_regions.append({
                'label': b['label'],
                'text': "",
                'sort_key': float('inf'), # Append to end
                'coords': [b['left'], b['top'], b['right'], b['bottom']]
            })
            continue

        # Case B: Blocks with Text (Split into contiguous runs if necessary)
        # Note: A simple implementation groups all tokens in the block. 
        # For strict LaTeX adherence "SplitIntoContiguousRuns", we group sequential indices.
        
        current_run = []
        if b['matched_indices']:
            # Simplified text joining for the run
            full_text = ""
            start_index = b['matched_indices'][0]
            
            for idx in b['matched_indices']:
                token = google_ocr_tokens[idx]
                text = token['description']
                
                # Check for break types (Space vs Newline)
                detected_break = token.get('property', {}).get('detectedBreak', {}).get('type', 'UNKNOWN')
                
                full_text += text
                
                if detected_break in ['SPACE', 'SURE_SPACE']:
                    full_text += " "
                elif detected_break in ['EOL_SURE_SPACE', 'LINE_BREAK']:
                    full_text += "\n"
            
            reconstructed_regions.append({
                'label': b['label'],
                'text': full_text.strip(),
                'sort_key': start_index, # Use first token index as sort key
                'coords': [b['left'], b['top'], b['right'], b['bottom']]
            })

    # --- Step 4: Handle Orphans (O) ---
    all_indices = set(range(len(google_ocr_tokens)))
    orphan_indices = sorted(list(all_indices - used_indices))

    if orphan_indices:
        # Group orphans into a generic Paragraph
        full_text = ""
        start_index = orphan_indices[0]
        
        for idx in orphan_indices:
            token = google_ocr_tokens[idx]
            text = token['description']
            detected_break = token.get('property', {}).get('detectedBreak', {}).get('type', 'UNKNOWN')
            
            full_text += text
            if detected_break in ['SPACE', 'SURE_SPACE']:
                full_text += " "
            elif detected_break in ['EOL_SURE_SPACE', 'LINE_BREAK']:
                full_text += "\n"
        
        # Calculate bounding box for orphans (simplified)
        reconstructed_regions.append({
            'label': 'Paragraph', # Default fallback
            'text': full_text.strip(),
            'sort_key': start_index,
            'coords': [0, 0, 0, 0] # Placeholder coords
        })

    # --- Step 5: Final Sort ---
    final_document = sorted(reconstructed_regions, key=lambda x: x['sort_key'])
    
    return final_document
