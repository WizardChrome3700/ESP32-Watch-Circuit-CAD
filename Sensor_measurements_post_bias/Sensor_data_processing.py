import os
import glob
import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import RangeSlider, Button

# --- Configuration ---
V_ADC_RANGE = 5.0   # The ADS1256 full scale range (2 * 2.5V VREF / PGA 1)
MAX_CODE = 8388607
V_DIVIDER = 2.5     # The voltage driving the FSR network
R_BIAS = 100000.0    # Replace with the actual resistor used in your divider (Ohms)
OUTPUT_FILE = "calibration_results.csv"

def extract_numerical_weight(filepath):
    """
    Extracts the numerical weight from the filename for proper mathematical sorting.
    Converts underscores to decimal points and ignores text like 'g' or 'kg'.
    """
    # Get just the filename without the path or the .log extension
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    
    # Replace the underscore with a decimal point
    normalized_name = base_name.replace('_', '.')
    
    # Extract the floating-point number using a regular expression
    match = re.search(r'([\d.]+)', normalized_name)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0
    return 0.0

def process_data(file_path):
    print(f"Loading {file_path}...")
    
    try:
        # Load the CSV data, skipping the header string row
        data = np.genfromtxt(file_path, delimiter=',', skip_header=1)
        
        # Isolate the columns based on your hardware layout
        time = data[:, 0]  # timestamp
        s1 = data[:, 1]    # voltage (ADC 1)
        s2 = data[:, 2]    # Channel 2 (ADC 2)
        s3 = data[:, 3]    # Channel 3 (ADC 3)
        
        return time, s1, s2, s3
    
    except Exception as e:
        print(f"Error loading file: {e}")
        return None, None, None, None

def calculate_conductance(codes):
    # 1. Convert digital code to physical voltage
    voltages = codes * (V_ADC_RANGE / MAX_CODE)
    
    # 2. Prevent division-by-zero or negative roots from noise spikes
    voltages = np.clip(voltages, 0.0001, V_DIVIDER - 0.0001) 
    
    # 3. Corrected Math: Reverse the FSR-on-bottom voltage divider
    resistances = R_BIAS * (voltages / (V_DIVIDER - voltages))
    
    # 4. Convert Resistance to Conductance (Siemens)
    conductances = 1.0 / resistances
    
    return conductances

def main():
    files = glob.glob("*.log")
    
    if not files:
        print("No log files found in the current directory.")
        return

    # Sort the files numerically based on the weight extracted from the filename
    files = sorted(files, key=extract_numerical_weight)

    # Initialize the output file and write headers
    with open(OUTPUT_FILE, 'w') as f:
        f.write("Total_Load,Time_Start,Time_End,Med_S1_Code,Med_S2_Code,Med_S3_Code,Total_Conductance\n")

    # Loop through all sorted log files
    for file_path in files:
        time, s1, s2, s3 = process_data(file_path)
        
        if time is None:
            continue

        # Extract the original label (e.g., "1_5kg") for the plot title and CSV log
        weight_label = os.path.splitext(os.path.basename(file_path))[0]

        # Calculate 10% and 90% span boundaries
        t_min, t_max = time[0], time[-1]
        t_span = t_max - t_min
        init_start = t_min + (0.10 * t_span)
        init_end = t_min + (0.90 * t_span)

        # --- Setup the Matplotlib GUI ---
        fig, ax = plt.subplots(figsize=(10, 6))
        plt.subplots_adjust(bottom=0.25)
        
        line1, = ax.plot(time, s1, label='Sensor 1 (voltage)', alpha=0.7)
        line2, = ax.plot(time, s2, label='Sensor 2 (Ch 2)', alpha=0.7)
        line3, = ax.plot(time, s3, label='Sensor 3 (Ch 3)', alpha=0.7)
        
        ax.set_ylabel("Raw ADC Code")
        ax.set_xlabel("Time")
        ax.set_title(f"Visual Cropping: {weight_label}\nAdjust Window and Press Extract")
        ax.legend()
        ax.grid(True)

        # Create the RangeSlider axis and set initial span
        ax_slider = plt.axes([0.15, 0.1, 0.65, 0.03])
        slider = RangeSlider(ax_slider, "Crop Window", t_min, t_max, valinit=(init_start, init_end))

        # Visual span highlighting the selected area on the main plot
        span = ax.axvspan(init_start, init_end, color='yellow', alpha=0.2)

        def update_span(val):
            span.set_xy([
                [val[0], 0], [val[0], 1], 
                [val[1], 1], [val[1], 0], 
                [val[0], 0]
            ])
            fig.canvas.draw_idle()

        slider.on_changed(update_span)

        # Create the Calculate button axis
        ax_button = plt.axes([0.82, 0.025, 0.15, 0.05])
        btn = Button(ax_button, 'Extract & Next')

        def calculate_window(event):
            t_start, t_end = slider.val
            
            # Find array indices corresponding to the selected time window
            idx_start = np.searchsorted(time, t_start)
            idx_end = np.searchsorted(time, t_end)
            
            # Extract the median code for each sensor in this window
            med_s1 = np.median(s1[idx_start:idx_end])
            med_s2 = np.median(s2[idx_start:idx_end])
            med_s3 = np.median(s3[idx_start:idx_end])
            
            # Convert to Conductance
            g1 = calculate_conductance(med_s1)
            g2 = calculate_conductance(med_s2)
            g3 = calculate_conductance(med_s3)
            g_total = g1 + g2 + g3

            # Save the processed data to the output file
            with open(OUTPUT_FILE, 'a') as f:
                f.write(f"{weight_label},{t_start:.2f},{t_end:.2f},{med_s1:.0f},{med_s2:.0f},{med_s3:.0f},{g_total:.6e}\n")

            print(f"Data saved for '{weight_label}'. Advancing to next log...")
            plt.close(fig) # Closes the current plot to proceed the loop

        btn.on_clicked(calculate_window)
        
        # Halt execution and wait for user to click the extract button
        plt.show() 

    print(f"\nProcessing complete! All extracted data stored in '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    main()