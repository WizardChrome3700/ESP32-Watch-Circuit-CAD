import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import re

# --- Configuration ---
CSV_FILE = "calibration_results.csv"
V_DIVIDER = 2.5  # Voltage driving the divider

def parse_weight_to_grams(weight_str):
    """
    Converts strings like '13_6g' or '1_5kg' into pure float values in grams.
    """
    normalized_str = str(weight_str).replace('_', '.')
    match = re.search(r'([\d.]+)', normalized_str)
    if not match:
        return 0.0
    
    val = float(match.group(1))
    if 'kg' in normalized_str.lower():
        val *= 1000.0
        
    return val

def main():
    print(f"Loading data from {CSV_FILE}...")
    
    try:
        df = pd.read_csv(CSV_FILE)
    except FileNotFoundError:
        print(f"Error: Could not find '{CSV_FILE}'.")
        return

    # Extract numerical weights and sort
    df['Total_Weight_g'] = df['Total_Load'].apply(parse_weight_to_grams)
    df = df.sort_values(by='Total_Weight_g')

    # --- Single Sensor Conversion ---
    # Divide total weight and total conductance by 3 to isolate a single sensor
    x_single = df['Total_Weight_g'].values / 3.0
    y_single = df['Total_Conductance'].values / 3.0

    # =========================================================
    # PLOT 1: Single Sensor Calibration Curve
    # =========================================================
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    
    ax1.scatter(x_single, y_single, color='blue', label='Extracted Medians (Per Sensor)', zorder=5)

    slope, intercept = 0, 0
    if len(x_single) > 1:
        slope, intercept = np.polyfit(x_single, y_single, 1)
        trendline = (slope * x_single) + intercept
        
        ax1.plot(x_single, trendline, color='red', linestyle='--', alpha=0.7, 
                 label=f'Linear Fit: $G = {slope:.2e} \cdot W + {intercept:.2e}$')

    ax1.set_title("Single FSR Calibration: Conductance vs. Applied Weight\n(Close this window to continue to R_bias tuning)")
    ax1.set_xlabel("Applied Weight per Sensor (grams)")
    ax1.set_ylabel("Sensor Conductance (Siemens)")
    ax1.grid(True, linestyle=':', alpha=0.7)
    ax1.legend()
    plt.tight_layout()
    
    # Blocks execution until the user manually closes the window
    plt.show()

    # --- Print the final equation to the console for C++ ---
    print("\n" + "="*55)
    print("SINGLE SENSOR CALIBRATION EQUATION (C++ Ready):")
    print(f"float conductance = ({slope:.6e} * weight_g) + {intercept:.6e};")
    print(f"float weight_g = (conductance - {intercept:.6e}) / {slope:.6e};")
    print("="*55 + "\n")

# =========================================================
    # PLOT 2: Interactive R_bias Linearity Simulator
    # =========================================================
    
    # Instead of raw data, generate a smooth, idealized array from 50g to 400g
    x_sim = np.linspace(50, 400, 500)
    
    # Calculate extrapolated conductance using the linear fit equation from Plot 1
    g_sim = (slope * x_sim) + intercept
    
    # Convert idealized conductance back to single sensor resistance
    r_single = 1.0 / g_sim

    fig2, ax2 = plt.subplots(figsize=(10, 6))
    plt.subplots_adjust(bottom=0.25) # Make room for the slider

    init_rbias = 10000.0

    # Voltage divider equations based on hardware topology
    def calc_v_top(rb):
        return V_DIVIDER * (rb / (r_single + rb))
        
    def calc_v_bottom(rb):
        return V_DIVIDER * (r_single / (r_single + rb))

    # Plot both idealized hardware configurations
    line_top, = ax2.plot(x_sim, calc_v_top(init_rbias), lw=2, color='green', 
                         label='FSR on Top (Voltage rises with force)')
    line_bot, = ax2.plot(x_sim, calc_v_bottom(init_rbias), lw=2, color='purple', 
                         label='FSR on Bottom (Voltage drops with force)')

    ax2.set_title("Single Sensor Linearity Simulator (Idealized)\nAdjust R_bias to optimize voltage curve")
    ax2.set_xlabel("Applied Weight per Sensor (grams)")
    ax2.set_ylabel("Simulated ADC Voltage (V)")
    
    # Lock the axes to your specified bounds
    ax2.set_xlim(50, 400)
    ax2.set_ylim(0, V_DIVIDER + 0.2)
    ax2.grid(True, linestyle=':', alpha=0.7)
    ax2.legend()

    # Generate the interactive Slider axis
    ax_slider = plt.axes([0.15, 0.1, 0.65, 0.03])
    r_slider = Slider(
        ax=ax_slider,
        label='R_bias ($\Omega$)',
        valmin=100.0,
        valmax=100000.0,
        valinit=init_rbias,
        valstep=100.0
    )

    # Dynamic update function
    def update(val):
        rb = r_slider.val
        line_top.set_ydata(calc_v_top(rb))
        line_bot.set_ydata(calc_v_bottom(rb))
        fig2.canvas.draw_idle()

    r_slider.on_changed(update)
    
    print("Opening interactive R_bias simulator...")
    plt.show()

if __name__ == "__main__":
    main()