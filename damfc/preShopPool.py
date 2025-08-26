from loggerConfig import log_manager


class PreShopPool(object):
    def __init__(self, env) :
        """
        Initialize a PreShopPool object.
        """
        self.order_list = []
        self.env = env

    def add_order(self, order):
        """
        Add an order to the pre-shop pool.

        Parameters:
        - order (Order): The order to be added.
        """
        self.order_list.append(order)
        task_summary = f"{len(order.flat_plan)} tasks included"
        log_manager.log_event(self.env.now, "N/A", order.order_id, "N/A", "Order Arrival", task_summary)
 
    
    def remove_order(self, order):
        """
        Remove an order from the pre-shop pool.

        Parameters:
        - order (Order): The order to be removed.
        """
        self.order_list.remove(order)

class Task:
    def __init__(self, task_name, process_time, produced_component, revenue, station, next_steps=None, parent_task=None, depth=1):
        """
        Initialize a Task object.

        Parameters:
        - task_name (str): The name of the task.
        - process_time (float): The time required to process the task.
        - produced_component (str): The component produced by this task.
        - revenue (float): The revenue generated upon completion of the task.
        - station (str): The workstation assigned to this task.
        - next_steps (list): A list of subsequent tasks (dependencies), default is None.
        - parent_task (str): The name of the parent task, default is None.
        - depth (int): The depth of the task in the process plan, default is 1.
        - planned_start_time (float): The planned start time for the task, default is None.
        """
        self.task_name = task_name
        self.process_time = process_time
        self.produced_component = produced_component
        self.revenue = revenue
        self.station = station
        self.assigned_station = None
        self.next_steps = next_steps if next_steps else []
        self.parent_task = parent_task
        self.depth = depth
        self.planned_start_time = None

    def calculate_load(self):
        """
        Calculate the load of the task based on its depth.

        Returns:
        - float: The load value.
        """
        return self.process_time / self.depth

    def __str__(self):
        """
        String representation of the Task object for debugging or logging.

        Returns:
        - str: A readable representation of the task.
        """
        return (f"Task({self.task_name}, Process Time: {self.process_time:.2f}, "
                f"Revenue: {self.revenue}, Station: {self.station}, Depth: {self.depth})")

class Order:
    def __init__(self, order_id, depth, arrival_time, due_date, priority, plan_name, process_plan):
        """
        Initialize an Order object.

        Parameters:
        - order_id (str): Unique identifier for the order.
        - depth (int): Depth of the disassembly process.
        - arrival_time (float): The time at which the order arrives.
        - due_date (float): The due date for the order.
        - priority (int): The priority level of the order (0, 1, or 2).
        - plan_name (str): Name of the disassembly process plan.
        - process_plan (list): A list of Task objects representing the order's process plan.
        """
        self.order_id = order_id
        self.depth = depth
        self.arrival_time = arrival_time
        self.due_date = due_date
        self.priority = priority
        self.plan_name = plan_name
        self.process_plan = process_plan # List of Task with dependencies
        self.flat_plan = self.create_flat_plan()

        self.finish_time = 0.0
        self.completed_tasks = set()  # Keep track of completed tasks
        self.ready_tasks = self.initialize_tasks()  # Intialize tasks ready to be processed
        self.load_contributions = {} # # Track load contribution by workstation (key: work station, value: load contribution)

    
    def initialize_tasks(self):
        """
        Identify root tasks (tasks with no parent) and add them to ready_tasks.

        Returns:
        - list: A list of root Task objects.
        """
        ready_tasks = []
        for task in self.flat_plan:
             if task.parent_task is None:
                ready_tasks.append(task)
        return ready_tasks
    
    def create_flat_plan(self):
        """
        Flatten the hierarchical task structure into a list of all tasks.

        Returns:
        - list: A flat list of all tasks in the process plan.
        """
        def flatten(tasks):
            flat_list = []
            for task in tasks:
                flat_list.append(task)
                flat_list.extend(flatten(task.next_steps))
            return flat_list

        return flatten(self.process_plan)
    
    
    def compute_load_contributions(self):
        """
        Precompute load contributions for all tasks at each depth level.
        """
        for task in self.flat_plan:
            if task.depth > 0:
                load = task.calculate_load()
                # Initialize the load contribution for the station
                if task.assigned_station.id not in self.load_contributions:
                    self.load_contributions[task.assigned_station.id] = {}
                self.load_contributions[task.assigned_station.id][task.task_name] = {'load': load, 'depth': task.depth}
               

    def estimate_load_contribution(self, station_current_loads):
        """
        Add the load contributions of all tasks to the stations' current loads.

        Parameters:
        - station_loads (dict): Dictionary tracking current loads for each station.

        Returns:
        - dict: A dictionary with updated loads for each station.
        """
        estimated_loads = station_current_loads.copy()
        for station_id, tasks in self.load_contributions.items():
            for task_name, data in tasks.items():
                load = data['load']
                estimated_loads[station_id] += load
        return estimated_loads
    
    def add_load_contribution(self, station_list):
        """
        Add load contributions to stations' loads

        Parameters
        - station_list (list):List of stations
        """
        for station_id, tasks in self.load_contributions.items():
            station = next((ws for ws in station_list if ws.id == station_id), None)
            if station:
                for task_name, data in tasks.items():
                    station.indirect_load += data['load']
    

    def update_load_contribution(self, station_list, completed_task):
        """
        Set the load contributions and depth of the completed task to 0 and update contributions of child tasks.

        Parameters:
        - station_indirect_loads (dict): Dictionary tracking indirect loads for each station.
        - completed_task_name (str): The name of the completed task.
        """
        task = next((t for t in self.flat_plan if t.task_name == completed_task.task_name), None)
        if not task:
            raise ValueError(f"Task {completed_task} not found in order {self.order_id}")

        assigned_station = task.assigned_station
        if not assigned_station:
            raise ValueError(f"Task {task.task_name} has no assigned station")
        
        # Set the completed task's depth to -1; its load contributions to 0
        task.depth = -1
        if assigned_station.id in self.load_contributions and completed_task.task_name in self.load_contributions[assigned_station.id]:
            self.load_contributions[assigned_station.id][completed_task.task_name] = {'load': 0, 'depth': task.depth}
        
        def update_childs_indrect_load(task):
                for child_task in task.next_steps:
                    assigned_station = child_task.assigned_station
                    old_indirect_load = child_task.calculate_load()
                    assigned_station.indirect_load -= old_indirect_load

                    if assigned_station.indirect_load < 0 and abs(assigned_station.indirect_load) < 1e-10:
                        assigned_station.indirect_load = 0
                    if (assigned_station.indirect_load < 0):
                        print(f"Negative load contribution for task {child_task.task_name}: {assigned_station.indirect_load}")
                        raise ValueError(f"Negative load contribution for task {child_task.task_name} in station {assigned_station.id}")
                    
                    child_task.depth -= 1 
                    new_indirect_load = child_task.calculate_load()
                    assigned_station.indirect_load += new_indirect_load
                    if (child_task.next_steps):
                        update_childs_indrect_load(child_task)

                    # for station_id, tasks in self.load_contributions.items():
                    #     if (tasks[child_task.task_name] == child_task.task_name):
                    #         station = next((ws for ws in station_list if ws.id == station_id), None)
                    #         print(tasks[child_task.task_name]['load'])
                    #         station.indirect_load -= tasks[child_task.task_name]['load']
                    #         if (station.indirect_load < 0):
                    #             raise ValueError(f"Negative load contribution for task {child_task.task_name} in station {station.id}")
                    # if (child_task.next_steps):
                    #     update_childs_indrect_load(child_task)

        # Update following tasks' load contribution
        update_childs_indrect_load(task)
        self.compute_load_contributions()
        
       
    @property
    def total_process_time(self):
        """
        Calculate the total process time for the order.

        Returns:
        - float: The total process time for the order.
        """
        return sum(task.process_time for task in self.flat_plan)
    
     

    
    @ property
    def total_revenue(self):
        """
        Calculate the total revenue of completed tasks in the order.
        If the order is not finished, only the revenue of completed tasks is considered.

        Returns:
        - float: The total revenue of completed tasks.
        """
        completed_task_revenue = sum(task.revenue for task in self.flat_plan if task in self.completed_tasks)
        return completed_task_revenue
    
    @property
    def order_lead_time(self, order):
        """
        Calculate the lead time of the order.

        Returns:
        - float: The lead time of the order.
        """
        if order.finish_time == 0.0:
            return 0.0
        else:
            return order.finish_time - order.arrival_time
        
    
    def is_overdue(self):
        """
        Check if the order is overdue.

        Returns:
        - bool: True if the order is overdue, False otherwise. None if the order is not finished.
        """
        if self.is_finished():
            return self.finish_time > self.due_date
        else:
            return None
     
    def is_finished(self):
        """
        Check if all tasks have been completed by comparing the number of completed tasks with the process plan.
        
        Returns:
        - bool: True if all tasks are completed, False otherwise.
        """
        all_task_names = {task.task_name for task in self.flat_plan}
        completed_task_names = {task.task_name for task in self.completed_tasks}
        return completed_task_names == all_task_names


        
    def __str__(self):
        """
        String representation of the Order object, including task relationships.

        Returns:
        - str: A detailed string representation of the order.
        """
        def format_task(task, indent=0):
            task_info = (
                f"{' ' * indent}- Task Name: {task.task_name}, Process Time: {task.process_time:.2f}, "
                f"Revenue: {task.revenue}, Station: {task.station}"
            )
            children_info = "\n".join(format_task(child, indent + 4) for child in task.next_steps)
            return f"{task_info}\n{children_info}" if children_info else task_info

        task_details = "\n".join(format_task(task) for task in self.process_plan if not task.parent_task)

        return (f"Order ID: {self.order_id}\n"
                f"Plan Name: {self.plan_name}\n"
                f"Depth: {self.depth}\n"
                f"Arrival Time: {self.arrival_time:.2f}\n"
                f"Due Date: {self.due_date:.2f}\n"
                f"Priority: {self.priority}\n"
                f"Tasks:\n{task_details}")


