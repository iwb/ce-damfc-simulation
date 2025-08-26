import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import tkinter as tk
from tkinter import ttk
import pandas as pd
import sys
import os

# Access output directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_dir = os.path.join(base_dir, 'output')

class KPITracker:
    def __init__(self, summary_file_path=os.path.join(output_dir, 'summary_simulation.csv')):
        """
        This class is used to track the KPIs of the simulation.
        
        Parameters
        summary_file_path(str): Path for saving the summary file.
        """
        self.summary_file_path = summary_file_path


        # Ensure the CSVs is reset (emptied) when the program starts
        open(self.summary_file_path, 'w').close()

        # Initialize the simulation results structure (empty dictionary)
        self.simulation_results = {
            'Simulation ID': [],
            'Rules': [],
            'Simulation Time': [],
            'Total Orders': [],
            'Workload Norm': [],
            'Overdue Orders': [],
            'Unfinished Orders': [],
            'Throughput Time Mean': [],
            'Idle Time': [],
            'Work Time': [],
            'Revenue': [],
            'Process Cost': [],
            'Net Profit': []
        }
        # Store idle times and utilization by simulation_id (update: not by rule)
        # self.station_idle_times = {}  # To store idle times of each workstation
        # self.station_utilization = {}
        self.station_idle_times = {}  # {simulation_id: {station_id: idle_time}}
        self.station_utilization = {}  # {simulation_id: {station_id: utilization}}
        self.simulation_rules = {}  # {simulation_id: rule_string} to keep track of which rules each simulation used

    def store_kpi_results(self, simulation_id, rule ,total_simulation_time, workload_norm, orders, workstations):
        """
        Store KPI results after a simulation run.
        """
        # Collect idle time and utilization for each workstation
        idle_times = {ws.id: ws.total_idle_time for ws in workstations}
        work_times = {ws.id: ws.total_work_time for ws in workstations}
        utilization = {ws.id: (ws.total_work_time / total_simulation_time) * 100 for ws in workstations}
        
        # self.station_idle_times[rule] = idle_times
        # self.station_utilization[rule] = utilization
        self.station_idle_times[simulation_id] = idle_times
        self.station_utilization[simulation_id] = utilization
        self.simulation_rules[simulation_id] = rule

        # Other KPIs
        total_orders = len(orders)
        finished_orders = [order for order in orders if order.is_finished()]
        overdue_orders = sum(order.is_overdue() for order in finished_orders)  # Only consider finished orders
        # Unfinished orders count
        unfinished_orders = len(orders) - len(finished_orders)

        total_revenue = sum(order.total_revenue for order in orders)
        process_costs = sum((ws.cost_per_time_unit * ws.total_work_time) for ws in workstations)
        net_profit = total_revenue - process_costs
        lead_time = sum(order.finish_time - order.arrival_time for order in finished_orders) / len(finished_orders)

        # Store the KPIs in the simulation results dictionary
        self.simulation_results['Simulation ID'].append(simulation_id)
        self.simulation_results['Rules'].append(rule)
        self.simulation_results['Simulation Time'].append(total_simulation_time)
        self.simulation_results['Total Orders'].append(total_orders)
        self.simulation_results['Workload Norm'].append(workload_norm)
        self.simulation_results['Throughput Time Mean'].append(lead_time)
        self.simulation_results['Idle Time'].append(sum(idle_times.values()))
        self.simulation_results['Work Time'].append(sum(work_times.values()))
        self.simulation_results['Overdue Orders'].append(overdue_orders)
        self.simulation_results['Unfinished Orders'].append(unfinished_orders) 
        self.simulation_results['Revenue'].append(total_revenue)
        self.simulation_results['Process Cost'].append(process_costs)
        self.simulation_results['Net Profit'].append(net_profit)
    

        # Save the results to CSV
        df = pd.DataFrame(self.simulation_results)
        df.to_csv(self.summary_file_path, index=False)
        print(f"Results saved to {self.summary_file_path}")


    def print_results(self):
        df = pd.DataFrame(self.simulation_results)
        print(df)

        # Display idle time for each simulation
        for sim_id in self.station_idle_times.keys():
            rule = self.simulation_rules.get(sim_id, "Unknown")
            idle_times = self.station_idle_times[sim_id]
            print(f"\nIdle Times for {sim_id} ({rule}):")
            for station, idle_time in idle_times.items():
                print(f"Station {station}: {idle_time:.2f} hours")

        # Display utilization for each simulation
        for sim_id in self.station_utilization.keys():
            rule = self.simulation_rules.get(sim_id, "Unknown")
            utilization = self.station_utilization[sim_id]
            print(f"\nUtilization for {sim_id} ({rule}):")
            for station, util in utilization.items():
                print(f"Station {station}: {util:.2f}%")

    
    def display_combined_results(self):
        """
        Display idle time, utilization, and KPI table in a combined window for easy comparison.
        """

        # Create the Tkinter window
        window = tk.Tk()
        window.title("Combined Simulation Results")

        # Create a notebook to organize tabs for different results
        notebook = ttk.Notebook(window)
        notebook.pack(fill='both', expand=True)

        # Create a frame for KPI Table
        kpi_frame = ttk.Frame(notebook)
        notebook.add(kpi_frame, text='KPI Table')
        self.display_kpi_table_in_frame(kpi_frame)

        # Create a frame for Idle Time plot
        idle_frame = ttk.Frame(notebook)
        notebook.add(idle_frame, text='Idle Time Plot')
        self.plot_idle_time_in_frame(idle_frame)

        # Create a frame for Utilization plot
        utilization_frame = ttk.Frame(notebook)
        notebook.add(utilization_frame, text='Utilization Plot')
        self.plot_utilization_in_frame(utilization_frame)

        # Set a callback to destroy the window properly when it's closed
        def on_closing():
            window.destroy()
            sys.exit()  # Exit the program completely

        window.protocol("WM_DELETE_WINDOW", on_closing)

        # Run the GUI main loop
        window.mainloop()

    def plot_idle_time_in_frame(self, frame):
        """
        Plot idle time per station for each simulation based on its applied rule in the given frame.
        """
        # Get all simulations and stations
        sim_ids = list(self.station_idle_times.keys())
        if not sim_ids:
            return
        
        # stations = list(self.station_idle_times[rules[0]].keys())
        stations = list(self.station_idle_times[sim_ids[0]].keys())

        # Prepare the figure with a dynamic width based on the number of simulations
        fig_width = max(10, len(sim_ids) * 1.5)
        fig, ax = plt.subplots(figsize=(fig_width, 6))

        # Bar width and positioning
        bar_width = 0.8 / len(sim_ids)
        index = np.arange(len(stations))

        # Define a color map for each simulation
        colors = [
            '#a1dab4',  
            '#41b6c4',  
            '#2c7fb8',  
            '#636363',  
            '#969696',  
            '#cccccc', 
            '#fee08b', 
            '#e6f598', 
            '#8c96c6'
        ]

        # Plot each simulation's idle times
        for i, sim_id in enumerate(sim_ids):
            idle_times = [self.station_idle_times[sim_id][station] for station in stations]
            rule = self.simulation_rules.get(sim_id, "Unknown")
            label = f"{sim_id} ({rule})"
            ax.bar(index + i * bar_width, idle_times, bar_width, label=label, color=colors[i % len(colors)])

        # Set chart labels and title
        ax.set_xlabel('Workstations')
        ax.set_ylabel('Idle Time (time unit)')
        ax.set_title('Idle Time per Station for Each Pool Sequencing Rule')
        ax.set_xticks(index + bar_width * len(sim_ids) / 2)
        ax.set_xticklabels(stations, rotation=45)

        # Add a legend to differentiate between the simulations
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

        # Adjust layout to prevent legend cutoff
        plt.tight_layout()

        # Embed the plot in the Tkinter frame
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    def plot_utilization_in_frame(self, frame):
        """
        Plot utilization per station for simulation based on its applied rule in the given frame.
        """
        # Get all simulations and stations
        sim_ids = list(self.station_utilization.keys())
        if not sim_ids:
            return
        
        stations = list(self.station_utilization[sim_ids[0]].keys())

        # Prepare the figure with a dynamic width based on the number of simulations
        fig_width = max(10, len(sim_ids) * 1.5)
        fig, ax = plt.subplots(figsize=(fig_width, 6))

        # Bar width and positioning
        bar_width = 0.8 / len(sim_ids)
        index = np.arange(len(stations))

        # Use a color palette (e.g., pastel colors)
        colors = [
            '#a1dab4',  
            '#41b6c4',  
            '#2c7fb8',  
            '#636363',  
            '#969696',  
            '#cccccc', 
            '#fee08b', 
            '#e6f598', 
            '#8c96c6'
        ]

        # Plot each simulation's utilization
        for i, sim_id in enumerate(sim_ids):
            utilization = [self.station_utilization[sim_id][station] for station in stations]
            rule = self.simulation_rules.get(sim_id, "Unknown")
            label = f"{sim_id} ({rule})"
            ax.bar(index + i * bar_width, utilization, bar_width, label=label, color=colors[i % len(colors)])

        # Set chart labels and title
        ax.set_xlabel('Workstations')
        ax.set_ylabel('Utilization (%)')
        ax.set_title('Utilization per Station for Each Pool Sequencing Rule')
        ax.set_xticks(index + bar_width * len(sim_ids) / 2)
        ax.set_xticklabels(stations, rotation=45)

        # Add a legend to differentiate between the simulations
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

        # Adjust layout to prevent legend cutoff
        plt.tight_layout()

        # Embed the plot in the Tkinter frame
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    def display_kpi_table_in_frame(self, frame):
        """
        Display the KPIs in a table format for easy comparison in the given frame.
        """
        # Convert the simulation results dictionary to a DataFrame for easier manipulation and display
        df = pd.DataFrame(self.simulation_results)
        df = df.round(2)

        column_headers = {
            'Pool Rule': 'Rules',
            'Simulation Time': 'Simulation Time',
            'Workload Norm': 'Workload Norm',
            'Overdue Orders': 'Overdue Orders',
            'Unfinished Orders': 'Unfinished Orders',
            'Idle Time': 'Idle Time',
            'Work Time': 'Work Time',
            'Revenue': 'Revenue',
            'Process Cost': 'Process Cost',
            'Net Profit': 'Net Profit',
            'Throughput Time Mean': 'Throughput Time Mean'
        }

        df.columns = [column_headers.get(col, col) for col in df.columns]

        # Create the treeview to display the DataFrame
        tree = ttk.Treeview(frame, style="Custom.Treeview")
        tree.pack(side='left', fill='both', expand=True)

        # Define columns
        tree["column"] = list(df.columns)
        tree["show"] = "headings"

        # Set up styles for Treeview to control font size and header appearance
        style = ttk.Style()
        style.configure("Custom.Treeview.Heading", font=("Helvetica", 10, "bold"), padding=[10, 10])  
        style.configure("Custom.Treeview", font=("Helvetica", 10), rowheight=25)  

        # Set the columns and headings with modified column headers
        for column in df.columns:
            tree.heading(column, text=column, anchor='center')  
            tree.column(column, anchor='center', width=120)  

        # Insert rows
        for _, row in df.iterrows():
            tree.insert("", "end", values=list(row))

        # Add a scrollbar
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)

        # Frame for slider to control font size
        slider_frame = ttk.Frame(frame)
        slider_frame.pack(fill='x')

        def adjust_font_size(event):
            size = font_size.get()
            style.configure("Custom.Treeview.Heading", font=("Helvetica", size, "bold"), padding=[10, 10])  
            style.configure("Custom.Treeview", font=("Helvetica", size))

        # Create a slider for adjusting font size
        font_size = tk.IntVar(value=10)
        slider = ttk.Scale(slider_frame, from_=8, to=20, orient='horizontal', variable=font_size, command=adjust_font_size)
        slider.pack(fill='x')