import cv2
import numpy as np

def process_omr_sheet(image_path, num_questions):
    """
    Processes an OMR sheet image and returns detected answers.
    
    Args:
        image_path: Path to the uploaded image.
        num_questions: Number of questions in the exam.
        
    Returns:
        dict: {question_index: detected_alternative}
    """
    # Load image
    img = cv2.imread(image_path)
    if img is None:
        return None
    
    # 1. Preprocessing
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                 cv2.THRESH_BINARY_INV, 11, 2)
    
    # 2. Find markers (4 large black squares)
    cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    markers = []
    
    for c in cnts:
        (x, y, w, h) = cv2.boundingRect(c)
        ar = w / float(h)
        # Markers are squares, should be larger than bubbles
        if w > 20 and h > 20 and 0.8 <= ar <= 1.2:
            markers.append(c)
            
    if len(markers) < 4:
        # Fallback: maybe the image is low contrast
        return {"error": "Não foi possível encontrar os 4 marcadores de canto. Certifique-se de que o cartão está bem iluminado e visível."}
    
    # Sort markers to identify TL, TR, BL, BR
    markers = sorted(markers, key=lambda c: cv2.boundingRect(c)[1]) # Sort by Y
    top = sorted(markers[:2], key=lambda c: cv2.boundingRect(c)[0]) # Top 2 by X
    bottom = sorted(markers[-2:], key=lambda c: cv2.boundingRect(c)[0]) # Bottom 2 by X
    
    tl = cv2.boundingRect(top[0])
    tr = cv2.boundingRect(top[1])
    bl = cv2.boundingRect(bottom[0])
    br = cv2.boundingRect(bottom[1])
    
    # Get center points of markers
    pts1 = np.float32([
        [tl[0] + tl[2]/2, tl[1] + tl[3]/2],
        [tr[0] + tr[2]/2, tr[1] + tr[3]/2],
        [bl[0] + bl[2]/2, bl[1] + bl[3]/2],
        [br[0] + br[2]/2, br[1] + br[3]/2]
    ])
    
    # Perspective transform to a standard 800x1000 size
    width, height = 800, 1000
    pts2 = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
    matrix = cv2.getPerspectiveTransform(pts1, pts2)
    warped = cv2.warpPerspective(gray, matrix, (width, height))
    
    # 3. Process warped image
    # Re-apply threshold on warped image
    warped_thresh = cv2.threshold(warped, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    
    # Define grid parameters based on refined print_student.html layout
    # 3 columns, 20 questions each
    results = {}
    cols = 3
    rows_per_col = 20
    
    # Define margins (Standardized for 800x1000 warped image)
    # These are calibrated to match the proportions in the new template
    margin_top = 210  # Increased due to larger info box and instructions
    margin_bottom = 80 # Increased for larger bottom markers
    margin_left = 45
    margin_right = 45
    
    col_width = (width - margin_left - margin_right) // cols
    row_height = (height - margin_top - margin_bottom) // rows_per_col
    
    alternatives = ['A', 'B', 'C', 'D', 'E']
    # The first part of col_width is the "Q." label, then 5 bubbles
    q_label_width = col_width // 6
    bubble_width = (col_width - q_label_width) // 5 
    
    for q_idx in range(num_questions):
        col = q_idx // rows_per_col
        row = q_idx % rows_per_col
        
        # Calculate bounding box for this question's row
        x_base = margin_left + (col * col_width)
        y_base = margin_top + (row * row_height)
        
        # We search within the row for the most filled bubble
        # Each bubble is centered within its part of the row
        
        bubbled_alt = None
        max_fill_ratio = 0
        
        for a_idx, alt_label in enumerate(alternatives):
            # Target center of bubble
            bx = x_base + q_label_width + (a_idx * bubble_width)
            by = y_base
            bw = bubble_width
            bh = row_height
            
            # Crop bubble area with a slight inner margin to avoid border noise
            inner_padding = int(min(bw, bh) * 0.2)
            bubble_roi = warped_thresh[by+inner_padding:by+bh-inner_padding, 
                                       bx+inner_padding:bx+bw-inner_padding]
            
            if bubble_roi.size == 0: continue
            
            # Count non-zero pixels (filled areas)
            total = cv2.countNonZero(bubble_roi)
            fill_ratio = total / float(bubble_roi.size)
            
            # Heuristic: Find bubble with highest fill ratio
            if fill_ratio > max_fill_ratio:
                max_fill_ratio = fill_ratio
                bubbled_alt = alt_label
                
        # Only accept if fill ratio is significantly higher than a "clear" bubble
        # A clear bubble with just a label might have 5-8% noise. 
        # A filled one should have > 40%.
        if max_fill_ratio > 0.25: # 25% fill minimum
            results[q_idx + 1] = bubbled_alt
    
    return results
