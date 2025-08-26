import json
import numpy as np
import os
from preShopPool import Order, Task


class AppConfig:
    # ====================
    # CONTROL RULES
    # ====================
    # Default rules - these can be overridden when running specific scenarios
    POOL_SEQUENCING_RULE = "FCFS"  # Options: "FCFS", "CR", "EDD"
    DISPATCHING_RULE = "FCFS"  # Options: "FCFS", "SPT", "PST"

    # ====================
    # SYSTEM PARAMETERS
    # ====================
    WORKLOAD_NORM = 10  # Workload norm for Order Release Control
    PLANNED_START_TIME_ALLOWANCE = 0.2  # Allowance for waiting time per operation (while using PST dispatching rule)
    SIMULATION_TIME = 100  # Total simulation duration in time units

    # ====================
    # WORKSTATION CONFIGURATION
    # ====================
    # 5 types of workstations as defined in the research article. If this variable is modified, make sure to re-match the settings in the JobGenerator class
    STATION_TYPES = ["A", "B", "C", "D", "E"]
    # Number of instances per type (A:2, B:2, C:2, D:3, E:1) as defined in the research article
    STATION_INSTANCES = {"A": 2, "B": 2, "C": 2, "D": 3, "E": 1}

    # ====================
    # DISASSEMBLY PROCESS PLANS
    # ====================
    # Read disassembly process plans from JSON files
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dpp1_path = os.path.join(base_dir, "input", "dpp1.json")
    dpp2_path = os.path.join(base_dir, "input", "dpp2.json")

    with open(dpp1_path) as file:
        DPP_PLAN1 = json.load(file)
    with open(dpp2_path) as file:
        DPP_PLAN2 = json.load(file)

    # ====================
    # TASK-TO-STATION MAPPING
    # ====================
    # Assignment of tasks to stations
    Task_to_Station = {"T1": "A", "T2": "B", "T3": "C", "T4": "D", "T5": "E"}

    # ====================
    # ORDER GENERATION PARAMETERS
    # ====================
    TOTAL_ORDERS = 70  # Total number of orders to generate
    INTER_ARRIVAL_TIME_MEAN = (
        0.648  # Mean inter-arrival time (exponential distribution)
    )
    DUE_DATE_RANGE = (40, 50)  # Range for random due date generation

    # ====================
    # SIMULATION SCENARIOS
    # ====================
    # Default simulation scenarios as described in the research article
    SCENARIOS = [
        {"id": "Simulation1", "pool": "FCFS", "dispatch": "FCFS"},
        {"id": "Simulation2", "pool": "FCFS", "dispatch": "SPT"},
        {"id": "Simulation3", "pool": "FCFS", "dispatch": "PST"},
        {"id": "Simulation4", "pool": "CR", "dispatch": "FCFS"},
        {"id": "Simulation5", "pool": "CR", "dispatch": "SPT"},
        {"id": "Simulation6", "pool": "CR", "dispatch": "PST"},
        {"id": "Simulation7", "pool": "EDD", "dispatch": "FCFS"},
        {"id": "Simulation8", "pool": "EDD", "dispatch": "SPT"},
        {"id": "Simulation9", "pool": "EDD", "dispatch": "PST"},
    ]


app_config = AppConfig()


class OrderGenerator:
    """
    Generates orders based on disassembly process plans and simulation configurations.
    """

    def __init__(self):
        self.dpp_plan1 = app_config.DPP_PLAN1
        self.dpp_plan2 = app_config.DPP_PLAN2
        self.total_orders = app_config.TOTAL_ORDERS
        self.inter_arrival_time_mean = app_config.INTER_ARRIVAL_TIME_MEAN
        self.order_max_depth = 4
        self.due_date_range = app_config.DUE_DATE_RANGE
        self.task_to_station = app_config.Task_to_Station

    def generate_orders(self):
        """
        Generate a list of orders with tasks based on disassembly process plans.

        Returns:
        - list: A list of `Order` objects.
        """
        orders = []
        arrival_time = 0
        for i in range(self.total_orders):
            # Randomly select dpp_plan1 or dpp_plan2
            dpp_plan = (
                self.dpp_plan1 if np.random.choice([True, False]) else self.dpp_plan2
            )
            order = self.generate_dpp_order(i, dpp_plan, arrival_time)
            orders.append(order)
            arrival_time += np.random.exponential(
                self.inter_arrival_time_mean
            )  # Update arrival time
        return orders

    def generate_dpp_order(self, order_index, dpp, arrival_time):
        """
        Generate an `Order` object from a disassembly process plan.

        Parameters:
        - order_index (int): Index of the order.
        - dpp (dict): Disassembly process plan.
        - arrival_time (float): Arrival time for the order.

        Returns:
        - Order: The generated order object.
        """
        order_depth = np.random.randint(
            1, self.order_max_depth + 1
        )  # Randomly choose order depth between 1,2,3,4
        due_date = arrival_time + np.random.uniform(*self.due_date_range)
        priority = np.random.choice([0, 1, 2], p=[0.1, 0.2, 0.7])
        order_id = f"O-{order_index + 1}"
        plan_name = dpp["process_plan"]
        process_plan = []
        for root_task_data in dpp["disassembly_flow"]:
            root_task = self.traverse_and_generate(
                root_task_data, current_depth=1, max_depth=order_depth
            )
            process_plan.append(root_task)
        # process_plan = self.traverse_and_generate(dpp["disassembly_flow"][0], current_depth=1, max_depth=order_depth)
        return Order(
            order_id,
            order_depth,
            arrival_time,
            due_date,
            priority,
            plan_name,
            process_plan,
        )

    def traverse_and_generate(
        self, task_data, current_depth, max_depth, parent_task=None
    ):
        """
        Recursively traverse the disassembly process and generate Task objects.

        Parameters:
        - task_data (dict): The current task's data.
        - current_depth (int): The current depth of the task.
        - max_depth (int): The maximum depth allowed for the process plan.
        - parent_task (str): Name of the parent task, if any.

        Returns:
        - Task: The generated task object.
        """
        if current_depth > max_depth:
            return None  # Stop if beyond max depth

        process_time = self.generate_erlang_process_time(
            task_data["time_min"], task_data["time_max"]
        )
        task = Task(
            task_name=task_data["task"],
            process_time=round(process_time, 2),
            produced_component=task_data["produced_component"],
            revenue=task_data["revenue"],
            station=self.task_to_station.get(task_data["task"], "Unknown"),
            parent_task=parent_task,
            depth=current_depth,
        )

        # Generate child tasks
        for next_task_data in task_data.get("next_steps", []):
            child_task = self.traverse_and_generate(
                next_task_data, current_depth + 1, max_depth, task.task_name
            )
            if child_task:
                task.next_steps.append(child_task)

        return task

    def generate_erlang_process_time(self, min_time, max_time, shape=2, scale=1.0):
        """
        Generate a processing time using an Erlang distribution.

        Parameters:
        - min_time (float): Minimum processing time.
        - max_time (float): Maximum processing time.
        - shape (int): Shape parameter for the distribution.
        - scale (float): Scale parameter for the distribution.

        Returns:
        - float: Generated processing time.
        """
        erlang_random = np.random.gamma(shape, scale)
        scaled_time = min_time + (max_time - min_time) * (
            erlang_random / (shape * scale)
        )
        return scaled_time


order_generator = OrderGenerator()
