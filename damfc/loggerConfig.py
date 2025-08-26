import logging
import pandas as pd
import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import os


class LogManager:
    def __init__(self, env=None,orders=None):
        # Create output directory structure
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = os.path.join(base_dir, 'output')
        
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Define file paths in output directory
        self.event_log = os.path.join(self.output_dir, 'log_events.csv')
        self.summary_orders = os.path.join(self.output_dir, 'summary_orders.csv')
        self.summary_stations = os.path.join(self.output_dir, 'summary_stations.csv')

        self.main_logger = None
        self.order_logger = None

        # Ensure the CSVs is reset (emptied) when the program starts
        open(self.event_log, 'w').close()
        open(self.summary_orders, 'w').close()
        open(self.summary_stations, 'w').close()


        self.env = env
        self.simulation_id = None
        self.simulation_rules = None
        self.events = []

        self.orders = orders if orders is not None else []   # Initialize orders as None or an empty list if not provided
        self.orders_dict = {} # Create an empty dictionary to store orders by their IDs
    
    def set_orders(self, orders):
        # Set the orders attribute and update the orders dictionary
        self.orders = orders
        self.orders_dict = {order.order_id: order for order in orders}
        

    def setup_logger(self, level=logging.DEBUG):
        """Setup main logger"""
        formatter = logging.Formatter('%(asctime)s - %(levelname)s  - %(message)s')
        self.main_logger = logging.getLogger('main_logger')
        self.main_logger.setLevel(level)
        
        all_handler = logging.FileHandler(os.path.join(self.output_dir, 'app_all_logs.log'), mode='w')
        no_debug_handler = logging.FileHandler(os.path.join(self.output_dir, 'app_no_debug_logs.log'), mode='w')

        all_handler.setLevel(logging.DEBUG)
        no_debug_handler.setLevel(logging.INFO)
        
        all_handler.setFormatter(formatter)
        no_debug_handler.setFormatter(formatter)
        
        if self.main_logger.hasHandlers():
            self.main_logger.handlers.clear()

        self.main_logger.addHandler(all_handler)
        self.main_logger.addHandler(no_debug_handler)

    
        
    def set_simulation_info(self, simulation_id, simulation_rules):
        """
        Set the simulation details (ID and rules) for logging.
        """
        self.simulation_id = simulation_id
        self.simulation_rules = simulation_rules

    def log_event(self, timestamp, station_id, order_id, task_name, event_type, additional_details=None):
        """
        Log an event to the event log.
        """
        event = {
            'Simulation ID': self.simulation_id,
            'Rules':self.simulation_rules,
            'Timestamp': timestamp,
            'Station ID': station_id,
            'Order ID': order_id,
            'Task Name': task_name,
            'Event Type': event_type,
            'Details': additional_details
        }
        self.events.append(event)

    def record_current_simulation_data(self, simulation_id, rules, orders, stations):
        # Prepare data lists for orders and stations
        order_data = []
        station_data = []

        # Gather order data for current simulation
        for order in orders:
            # Initialize order data dictionary
            order_entry = {
                "Simulation ID": simulation_id,
                "Rules": rules,
                "Order ID": order.order_id,
                "Priority": order.priority,
                "Plan Name": order.plan_name,
                "Depth": order.depth,
                "Arrival Time": round(order.arrival_time, 2),
                "Due Date": round(order.due_date, 2),
                "Finish Time": round(order.finish_time, 2) if order.finish_time else "Not Finished",
                "Throughput Time": round(order.finish_time - order.arrival_time, 2) if order.finish_time else "Not Finished",
                "Total Process Time": round(order.total_process_time,2),
            }

            # Append to order data list
            order_data.append(order_entry)

        # Gather station data for current simulation
        for station in stations:
            station_entry = {
                "Simulation ID": simulation_id,
                "Rules": rules,
                "Station ID": station.id,
                "Total Work Time": round(station.total_work_time, 2),
                "Total Idle Time": round(station.total_idle_time, 2),
                #"Cost per Time Unit": station.cost_per_time_unit,
                "Utilization": round((station.total_work_time / (station.total_work_time + station.total_idle_time)) * 100, 2)
            }

            # Append to station data list
            station_data.append(station_entry)

        # Convert order and station data to DataFrames
        df_orders = pd.DataFrame(order_data)
        df_stations = pd.DataFrame(station_data)

        # Append data to the respective CSV files
        df_orders.to_csv(self.summary_orders, mode='a', index=False)
        df_stations.to_csv(self.summary_stations, mode='a', index=False)
  

    
    def get_event_log_df(self):
        """
        Return the event log as a pandas DataFrame
        """
        df = pd.DataFrame(self.events)
        df['Timestamp'] = df['Timestamp'].apply(lambda x: format(float(x), '.2f'))
        return df
    
    
    def save_to_csv(self):
        """
        Save the event log to a CSV file.
        """
        df = self.get_event_log_df()
        df.to_csv(self.event_log, mode='a', index=False)  
        print(f"Event log saved to {self.event_log}")

    
    def show_table_in_window(self, df, title="Event Log"):
        """
        Display the event log in a new Tkinter window with a Treeview widget.
        """
        def on_double_click(event):
            item = tree.selection()[0]  
            values = tree.item(item, "values")
            order_id = values[4] 
            order_details = self.get_order_details(order_id) 
            self.show_order_details_window(order_details)  

        # Create the Tkinter window
        window = tk.Tk()
        window.title(title)

        # Create a frame for the table
        frame = ttk.Frame(window)
        frame.pack(fill="both", expand=True)

        # Create the treeview to display the DataFrame
        tree = ttk.Treeview(frame)
        tree.pack(side="left", fill="both", expand=True)

        # Define columns
        tree["column"] = list(df.columns)
        tree["show"] = "headings"

        # Set the columns and headings
        for column in df.columns:
            tree.heading(column, text=column)
            tree.column(column, anchor="center", width=100)

        # Insert rows
        for index, row in df.iterrows():
            tree.insert("", "end", values=list(row))

        # Add a scrollbar
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)

        # Create a search entry and button for filtering
        search_frame = ttk.Frame(window)
        search_frame.pack(fill='x')

        search_label = ttk.Label(search_frame, text="Search:")
        search_label.pack(side='left', padx=5)

        search_entry = ttk.Entry(search_frame)
        search_entry.pack(side='left', fill='x', expand=True, padx=5)

        def filter_results():
            query = search_entry.get().strip().lower()
            if query:
                # Check if search is for a specific Order ID or Station ID
                filtered_df = df[
                    df['Station ID'].str.lower().eq(query) |  # Exact match for Station ID
                    df['Order ID'].str.lower().eq(query) |  # Exact match for Order ID
                    df['Event Type'].str.lower().str.contains(query)  # Partial match for Event Type
                ]
                self.show_table_in_window(filtered_df, title=f"Filtered Results for '{query}'")

        search_button = ttk.Button(search_frame, text="Search", command=filter_results)
        search_button.pack(side='left', padx=5)

        # Bind double click event to treeview
        tree.bind("<Double-1>", on_double_click)

        # Run the GUI main loop
        window.mainloop()

    def show_order_details_window(self, order_details):
        detail_window = tk.Toplevel()
        detail_window.title("Order Details")
        text = tk.Text(detail_window)
        text.insert("1.0", order_details)
        text.pack(fill="both", expand=True)
    
    def get_order_details(self, order_id):
        # get the order details from the dictionary
        order = self.orders_dict.get(order_id)  
        return order if order else "Order not found."
    
    def display_full_event_log_in_frame(self):
        """
        Display the full event log in the given frame.
        """
        df = self.get_event_log_df()
        self.show_table_in_window(df, title="Full Event Log")



log_manager = LogManager()  # assuming `env` is defined globally
log_manager.setup_logger()

