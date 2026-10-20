#!/usr/bin/env python3
"""
Script to draw a grid on the streamline.png image with numbered cells.
"""

from PIL import Image, ImageDraw, ImageFont
import os
import re

def parse_indicated_values(input_string):
    """
    Parse a string containing indicated values and ranges.
    
    Args:
        input_string (str): String like ''
    
    Returns:
        set: Set of all indicated numbers
    """
    indicated_values = set()
    
    # Clean the input string and split by commas
    cleaned_string = re.sub(r'\s+', '', input_string)  # Remove whitespace
    parts = cleaned_string.split(',')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        # Check if it's a range (contains '-')
        if '-' in part:
            try:
                start, end = part.split('-')
                start_num = int(start)
                end_num = int(end)
                # Add all numbers in the range (inclusive)
                for num in range(start_num, end_num + 1):
                    indicated_values.add(num)
            except ValueError:
                print(f"Warning: Invalid range format '{part}', skipping")
        else:
            # Single number
            try:
                num = int(part)
                indicated_values.add(num)
            except ValueError:
                print(f"Warning: Invalid number format '{part}', skipping")
    
    return indicated_values

def print_indicated_values(input_string):
    """
    Parse and print the indicated values from a string for debugging.
    
    Args:
        input_string (str): String containing indicated values and ranges
    """
    indicated_values = parse_indicated_values(input_string)
    print(f"Parsed {len(indicated_values)} indicated values:")
    print(f"Values: {sorted(indicated_values)}")
    
    # Show some statistics
    if indicated_values:
        print(f"Range: {min(indicated_values)} to {max(indicated_values)}")
        print(f"Missing values in range (example):")
        missing_count = 0
        for i in range(min(indicated_values), max(indicated_values) + 1):
            if i not in indicated_values:
                print(f"  {i}", end=" ")
                missing_count += 1
                if missing_count >= 10:  # Show first 10 missing values
                    print("...")
                    break
        if missing_count == 0:
            print("  None (all values in range are indicated)")
    return indicated_values

def draw_grid_with_grayed_values(image_path, indicated_values_string, output_path=None, grid_width=32, grid_height=32, grid_color=(255, 0, 0), grid_thickness=1, offset_x=0, offset_y=0, num_columns=16, start_number=48, gray_opacity=128):
    """
    Draw a grid on an image with numbered cells, graying out values that are NOT indicated.
    
    Args:
        image_path (str): Path to the input image
        indicated_values_string (str): String containing indicated values and ranges
        output_path (str): Path for the output image (if None, overwrites input)
        grid_width (int): Width of grid cells in pixels (if 0, will be calculated based on remaining width and num_columns)
        grid_height (int): Height of grid cells in pixels
        grid_color (tuple): RGB color for the grid lines
        grid_thickness (int): Thickness of grid lines
        offset_x (int): X offset from top-left corner
        offset_y (int): Y offset from top-left corner
        num_columns (int): Number of columns to create (used when grid_width is 0)
        start_number (int): Starting number for cell indexing
        gray_opacity (int): Opacity for grayed out values (0-255, where 0 is transparent, 255 is opaque)
    """
    try:
        # Parse the indicated values
        indicated_values = parse_indicated_values(indicated_values_string)
        print(f"Indicated values: {sorted(indicated_values)}")
        
        # Open the image
        with Image.open(image_path) as img:
            # Convert to RGBA to support transparency
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Create a drawing object
            draw = ImageDraw.Draw(img)
            
            width, height = img.size
            
            # Calculate grid width if needed (divide remaining width by number of columns)
            if grid_width == 0:
                remaining_width = width - offset_x
                grid_width = remaining_width // num_columns
                print(f"Calculated grid width: {grid_width}px (remaining width: {remaining_width}px / {num_columns} columns)")
            
            # Draw vertical lines
            # Start from offset_x and draw lines at each grid division
            for i in range(num_columns + 1):  # +1 to include the boundary line
                x = offset_x + (i * grid_width)
                draw.line([(x, 0), (x, height)], fill=grid_color, width=grid_thickness)
            
            # Draw horizontal lines
            # Calculate number of rows based on remaining height
            remaining_height = height - offset_y
            num_rows = remaining_height // grid_height
            
            # Start from offset_y and draw lines at each grid division
            for i in range(num_rows + 1):  # +1 to include the boundary line
                y = offset_y + (i * grid_height)
                draw.line([(0, y), (width, y)], fill=grid_color, width=grid_thickness)
            
            # Add numbered labels to each cell
            cell_number = start_number
            for row in range(num_rows):
                for col in range(num_columns):
                    # Calculate cell position
                    cell_x = offset_x + (col * grid_width)
                    cell_y = offset_y + (row * grid_height)
                    
                    # Determine if this cell should be grayed out
                    if cell_number not in indicated_values:
                        # Create a gray overlay for the cell
                        gray_overlay = Image.new('RGBA', (grid_width, grid_height), (128, 128, 128, gray_opacity))
                        img.paste(gray_overlay, (cell_x, cell_y), gray_overlay)
                    
                    # # Calculate text position (center of cell)
                    # text_x = cell_x + (grid_width // 2)
                    # text_y = cell_y + (grid_height // 2)
                    
                    # # Draw the number
                    # text = str(cell_number)
                    # # Use default bitmap font to avoid anti-aliasing
                    # font = ImageFont.load_default()
                    
                    # # Get text size for centering
                    # bbox = draw.textbbox((0, 0), text, font=font)
                    # text_width = bbox[2] - bbox[0]
                    # text_height = bbox[3] - bbox[1]
                    
                    # # Adjust position to center the text
                    # text_x -= text_width // 2
                    # text_y -= text_height // 2
                    
                    # # Always draw text in red (the gray background will make non-indicated cells appear grayed out)
                    # text_color = (255, 0, 0, 255)  # Red, fully opaque
                    
                    # # Draw the number
                    # draw.text((text_x, text_y), text, fill=text_color, font=font)
                    
                    cell_number += 1
            
            # Save the image
            if output_path is None:
                output_path = image_path
            
            img.save(output_path)
            print(f"Grid with numbered cells and grayed values drawn successfully! Saved to: {output_path}")
            print(f"Image size: {width}x{height} pixels")
            print(f"Grid size: {grid_width}x{grid_height} pixels")
            print(f"Numbered cells from {start_number} to {cell_number - 1}")
            print(f"Indicated values: {len(indicated_values)} out of {cell_number - start_number} total cells")
            
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
    except Exception as e:
        print(f"Error processing image: {e}")

def draw_grid_on_image(image_path, output_path=None, grid_width=32, grid_height=32, grid_color=(255, 0, 0), grid_thickness=1, offset_x=0, offset_y=0, num_columns=16, start_number=48):
    """
    Draw a grid on an image with numbered cells.
    
    Args:
        image_path (str): Path to the input image
        output_path (str): Path for the output image (if None, overwrites input)
        grid_width (int): Width of grid cells in pixels (if 0, will be calculated based on remaining width and num_columns)
        grid_height (int): Height of grid cells in pixels
        grid_color (tuple): RGB color for the grid lines
        grid_thickness (int): Thickness of grid lines
        offset_x (int): X offset from top-left corner
        offset_y (int): Y offset from top-left corner
        num_columns (int): Number of columns to create (used when grid_width is 0)
        start_number (int): Starting number for cell indexing
    """
    try:
        # Open the image
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (in case it's RGBA or other format)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create a drawing object
            draw = ImageDraw.Draw(img)
            
            width, height = img.size
            
            # Calculate grid width if needed (divide remaining width by number of columns)
            if grid_width == 0:
                remaining_width = width - offset_x
                grid_width = remaining_width // num_columns
                print(f"Calculated grid width: {grid_width}px (remaining width: {remaining_width}px / {num_columns} columns)")
            
            # Draw vertical lines
            # Start from offset_x and draw lines at each grid division
            for i in range(num_columns + 1):  # +1 to include the boundary line
                x = offset_x + (i * grid_width)
                draw.line([(x, 0), (x, height)], fill=grid_color, width=grid_thickness)
            
            # Draw horizontal lines
            # Calculate number of rows based on remaining height
            remaining_height = height - offset_y
            num_rows = remaining_height // grid_height
            
            # Start from offset_y and draw lines at each grid division
            for i in range(num_rows + 1):  # +1 to include the boundary line
                y = offset_y + (i * grid_height)
                draw.line([(0, y), (width, y)], fill=grid_color, width=grid_thickness)
            
            # Add numbered labels to each cell
            cell_number = start_number
            for row in range(num_rows):
                for col in range(num_columns):
                    # Calculate cell position
                    cell_x = offset_x + (col * grid_width)
                    cell_y = offset_y + (row * grid_height)
                    
                    # Calculate text position (center of cell)
                    text_x = cell_x + (grid_width // 2)
                    text_y = cell_y + (grid_height // 2)
                    
                    # Draw the number
                    text = str(cell_number)
                    # Use default bitmap font to avoid anti-aliasing
                    font = ImageFont.load_default()
                    
                    # Get text size for centering
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    # Adjust position to center the text
                    text_x -= text_width // 2
                    text_y -= text_height // 2
                    
                    # Draw the number in red with no anti-aliasing
                    draw.text((text_x, text_y), text, fill=(255, 0, 0), font=font)
                    
                    cell_number += 1
            
            # Save the image
            if output_path is None:
                output_path = image_path
            
            img.save(output_path)
            print(f"Grid with numbered cells drawn successfully! Saved to: {output_path}")
            print(f"Image size: {width}x{height} pixels")
            print(f"Grid size: {grid_width}x{grid_height} pixels")
            print(f"Numbered cells from {start_number} to {cell_number - 1}")
            
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
    except Exception as e:
        print(f"Error processing image: {e}")

def read_csv_values(csv_path):
    """
    Read indicated values from a CSV file.
    
    Args:
        csv_path (str): Path to the CSV file
        
    Returns:
        str: String containing all values from the CSV file
    """
    try:
        with open(csv_path, 'r') as file:
            content = file.read().strip()
            return content
    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_path}")
        return ""
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return ""

def main():
    """Main function to run the grid drawing script."""
    # Get the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the streamline.png image
    image_path = os.path.join(script_dir, "fonts", "streamline.png")
    
    # Path to the CSV file
    csv_path = os.path.join(script_dir, "fonts", "steamlineInclude.csv")
    
    # Check if the image exists
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return
    
    # Check if the CSV file exists
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
    
    # Read indicated values from CSV file
    indicated_values_string = read_csv_values(csv_path)
    
    if not indicated_values_string:
        print("Error: No values found in CSV file")
        return
    
    # First, let's parse and display the indicated values
    print("=== Parsing Indicated Values from CSV ===")
    print_indicated_values(indicated_values_string)
    print()
    
    # Create output path (save as new file to preserve original)
    output_path = os.path.join(script_dir, "fonts", "streamline_with_grayed_grid.png")
    
    # Draw grid on the image with numbered cells and grayed out non-indicated values
    # You can customize these parameters:
    # - grid_width: Width of each grid cell (22 pixels)
    # - grid_height: Height of each grid cell (21 pixels)
    # - grid_color: Color of grid lines (default: red)
    # - grid_thickness: Thickness of grid lines (default: 1 pixel)
    # - offset_x: X offset from top-left corner (77px)
    # - offset_y: Y offset from top-left corner (35px)
    # - num_columns: Number of columns to create (16)
    # - start_number: Starting number for cell indexing (48)
    # - gray_opacity: Opacity for grayed out values (128 = 50% opacity)
    draw_grid_with_grayed_values(
        image_path=image_path,
        indicated_values_string=indicated_values_string,
        output_path=output_path,
        grid_width=22,  # Fixed width of 22 pixels
        grid_height=21,
        grid_color=(255, 0, 0),  # Red
        grid_thickness=1,
        offset_x=77,
        offset_y=35,
        num_columns=16,
        start_number=48,  # Start numbering from 48
        gray_opacity=128  # 50% opacity for grayed values (128/255 = 50%)
    )

if __name__ == "__main__":
    main()
