"""
Dual-Stream Geometric-Linguistic Fusion Algorithm
Implementation for: "A dual-stream geometric-linguistic fusion architecture
for digitising visually complex Kazakh educational materials."

This script takes independent JSON outputs from AWS Textract (Layout Geometry) 
and Google Cloud Vision (Semantic Content) and merges them deterministically 
using a centroid-based inclusion matrix with structural preservation.
"""
import os
import json
import numpy as np
from tqdm import tqdm

# --- Configuration ---
IMAGE_FOLDER = 'efficiency_test_set'
AWS_FOLDER = 'api_results/aws'
GOOGLE_FOLDER = 'api_results/google'
OUTPUT_DATASET_FOLDER = 'test_dataset'

os.makedirs(OUTPUT_DATASET_FOLDER, exist_ok=True)

def load_json(path):
    if not os.path.exists(path): return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_google_words_robust(google_data):
    """
    Extracts words + Detected Break information.
    Also fixes the coordinate normalization bug.
    """
    words_raw = []
    max_x = 1.0
    max_y = 1.0

    pages = google_data.get('fullTextAnnotation', {}).get('pages', [])
    if not pages: return [], 1.0, 1.0

    # PASS 1: Find Global Max Dimensions
    for page in pages:
        p_w = page.get('width', 0)
        p_h = page.get('height', 0)
        if p_w > max_x: max_x = float(p_w)
        if p_h > max_y: max_y = float(p_h)

    # PASS 2: Extract
    for page in pages:
        current_w = float(page.get('width', max_x))
        current_h = float(page.get('height', max_y))
        if current_w <= 0: current_w = 1.0
        if current_h <= 0: current_h = 1.0
        
        for block in page.get('blocks', []):
            for paragraph in block.get('paragraphs', []):
                for word in paragraph.get('words', []):
                    # 1. Text
                    text = ''.join([s.get('text', '') for s in word.get('symbols', [])])
                    
                    # 2. Break Detection
                    break_type = None
                    if word.get('symbols'):
                        last_sym = word['symbols'][-1]
                        break_type = last_sym.get('property', {}).get('detectedBreak', {}).get('type')
                    
                    # 3. Geometry
                    box = word.get('boundingBox', {})
                    vertices = box.get('vertices', [])
                    if not vertices: continue
                    
                    xs = [v.get('x', 0) for v in vertices]
                    ys = [v.get('y', 0) for v in vertices]
                    if not xs: continue
                    
                    c_x_px = sum(xs) / len(xs)
                    c_y_px = sum(ys) / len(ys)
                    
                    words_raw.append({
                        'text': text,
                        'break_type': break_type,
                        'center_x': c_x_px / current_w, 
                        'center_y': c_y_px / current_h 
                    })

    return words_raw, max_x, max_y

def join_words_smart(word_list):
    """
    Reconstructs text using Google's detected breaks.
    Correctly handles New Lines and prevents word gluing.
    """
    result = ""
    for i, w in enumerate(word_list):
        result += w['text']
        
        # We process breaks for every word except the absolute last one in the chunk
        if i < len(word_list) - 1:
            bt = w.get('break_type')
            
            # 1. Handle New Lines (This fixes the "glued labels" in Diagrams)
            if bt in ['EOL_SURE_SPACE', 'LINE_BREAK']:
                result += "\n"
            
            # 2. Handle Standard Spaces
            elif bt in ['SPACE', 'SURE_SPACE']:
                result += " "
            
            # 3. Handle Hyphens (Optional, but good for splitting words at line ends)
            elif bt == 'HYPHEN':
                result += " -" 
            
            # 4. Fallback: If Google says nothing, but we are inside a big block, 
            # safe to assume a space unless it's a specific language case. 
            # But usually, trusting Google's 'None' is safer to avoid splitting inside words.
            
    return result

def build_hybrid_entry(filename):
    base_name = os.path.splitext(filename)[0]
    aws_path = os.path.join(AWS_FOLDER, f"{base_name}_aws.json")
    google_path = os.path.join(GOOGLE_FOLDER, f"{base_name}_google.json")
    
    aws_data = load_json(aws_path)
    google_data = load_json(google_path)
    
    if not aws_data or not google_data: return None

    google_words, width, height = get_google_words_robust(google_data)
    if not google_words: return None
    
    # AWS Blocks
    aws_blocks = [b for b in aws_data.get('Blocks', []) if b.get('BlockType', '').startswith('LAYOUT_')]
    block_info = []
    for b in aws_blocks:
        box = b['Geometry']['BoundingBox']
        coords = [box['Left'], box['Top'], box['Left'] + box['Width'], box['Top'] + box['Height']]
        block_info.append({
            'label': b['BlockType'].replace('LAYOUT_', ''),
            'coords': coords,
            'area': box['Width'] * box['Height'],
            'matched_indices': [] 
        })

    block_info.sort(key=lambda x: x['area'])
    used_word_indices = set()
    TOLERANCE = 0.02 

    # Assign Words
    for i, word in enumerate(google_words):
        w_x, w_y = word['center_x'], word['center_y']
        best_block = None
        for block in block_info:
            c = block['coords']
            if (c[0]-TOLERANCE <= w_x <= c[2]+TOLERANCE) and \
               (c[1]-TOLERANCE <= w_y <= c[3]+TOLERANCE):
                best_block = block
                break 
        if best_block:
            best_block['matched_indices'].append(i)
            used_word_indices.add(i)

    # Reconstruct
    final_regions = []
    for block in block_info:
        indices = sorted(block['matched_indices'])
        
        # --- FIX: PRESERVE EMPTY BLOCKS ---
        if not indices: 
            final_regions.append({
                'label': block['label'],
                'box_2d': block['coords'],
                'text': "", # No text
                'sort_key': 999999 # Push to end
            })
            continue

        chunks = []
        current_chunk = [indices[0]]
        for x in indices[1:]:
            if x > current_chunk[-1] + 1:
                chunks.append(current_chunk)
                current_chunk = []
            current_chunk.append(x)
        chunks.append(current_chunk)
        
        for chunk in chunks:
            chunk_words = [google_words[idx] for idx in chunk]
            text_content = join_words_smart(chunk_words)
            final_regions.append({
                'label': block['label'],
                'box_2d': block['coords'],
                'text': text_content,
                'sort_key': chunk[0]
            })

    # Orphans
    orphaned_indices = [i for i in range(len(google_words)) if i not in used_word_indices]
    if orphaned_indices:
        orphan_chunks = []
        current_chunk = [orphaned_indices[0]]
        for x in orphaned_indices[1:]:
            if x > current_chunk[-1] + 1:
                orphan_chunks.append(current_chunk)
                current_chunk = []
            current_chunk.append(x)
        orphan_chunks.append(current_chunk)
        
        for chunk in orphan_chunks:
            chunk_words = [google_words[idx] for idx in chunk]
            text_content = join_words_smart(chunk_words)
            avg_x = sum(w['center_x'] for w in chunk_words)/len(chunk_words)
            avg_y = sum(w['center_y'] for w in chunk_words)/len(chunk_words)
            final_regions.append({
                'label': 'Paragraph', 
                'box_2d': [avg_x, avg_y, avg_x, avg_y],
                'text': text_content,
                'sort_key': chunk[0]
            })

    final_regions.sort(key=lambda x: x['sort_key'])
    output_regions = [{k:v for k,v in r.items() if k != 'sort_key'} for r in final_regions]

    return {
        'image_filename': filename,
        'width': width, 'height': height,
        'annotations': output_regions,
        'words_found': len(google_words)
    }

print(f"Building Hybrid Dataset into: {OUTPUT_DATASET_FOLDER}")
files = [f for f in os.listdir(IMAGE_FOLDER) if f.endswith(('.jpg', '.png'))]
for filename in tqdm(files):
    entry = build_hybrid_entry(filename)
    if entry:
        out_path = os.path.join(OUTPUT_DATASET_FOLDER, filename.replace(os.path.splitext(filename)[1], '.json'))
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
