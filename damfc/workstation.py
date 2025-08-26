import simpy
from loggerConfig import log_manager
from appConfig import app_config

class Workstation(object):
    """
    A class to represent a workstation.
    """
    def __init__(self, env, type_id, instance_id, cost_per_time_unit=10, orControlSystem=None, dispatching_rule=app_config.DISPATCHING_RULE):
        """
        Initialize the workstation.

        Parameters:
        - env: The simulation environment.
        - type_id: The type of the workstation.
        - instance_id: The instance ID of the workstation.
        - cost_per_time_unit: The cost per time unit for the workstation.
        - orControlSystem: The order release control system.
        """
        self.env = env
        self.type_id = type_id
        self.instance_id = instance_id
        self.id = f"{type_id}-{instance_id}"
        self.output_warehouse = "output-warehouse"
        self.orControlSystem = orControlSystem  # Reference to OrderReleaseControl system (initially set to None)
        self.dispatching_rule = dispatching_rule

        self.resource = simpy.Resource(env, capacity=1)
        self.ws_tasks_queue = []
        self.indirect_load = 0 # Initialize indirect load

        self.idle = True
        self.idle_event = env.event()  # Initialize idle_event
        self.total_idle_time = 0 
        self.total_work_time = 0
        self.cost_per_time_unit = cost_per_time_unit

        self.last_idle_start = 0  # To track when the last idle state starts
        self.last_work_start = 0 # To track when the last work state starts

    @property
    def direct_load(self):
        """
        Calculates the direct load of the workstation based on the number of tasks in the queue.
        """
        return sum(task.process_time for order, task in self.ws_tasks_queue)      
     
        
    @property
    def current_load(self):
        """
        Calculates the current load of the workstation based on the tasks in the queue.
        """
        return self.direct_load + self.indirect_load

    @property
    def total_cost(self):
        """
        Calculates the total cost of the workstation based on the total work time and the cost per unit of time.
        """
        time = self.total_work_time
        return time * self.cost_per_time_unit

    def add_task(self, order, task):
        """
        Add a job to the station's tasks queue.
        Calculate planned start time before adding.
        """
        if self.orControlSystem:
            self.orControlSystem.calculate_planned_start_time(order, task)  # Calculate PST before adding to queue
           
        # Decrease indirect load when task arrives
        load = task.process_time/ task.depth
        self.indirect_load -= load
        if self.indirect_load < 0 and abs(self.indirect_load) < 1e-10:
            self.indirect_load = 0
        if self.indirect_load < 0:
            raise ValueError("Station indirect load <0")  # Ensure indirect load doesn't go negative

        order.ready_tasks.remove(task)

        # Add the task to the queue
        self.ws_tasks_queue.append((order, task))
        log_manager.log_event(self.env.now, self.id, order.order_id, task.task_name, "Task Added")
        # Trigger the station if it was idle
        if self.idle:
            self.idle_event.succeed()  # Wake up the station by triggering the event
            self.idle_event = self.env.event()  # Reset the event for future use


    def mark_task_as_completed(self, order, task):
        """
        Mark a task of an order as completed and add its child tasks to ready_tasks.
        """
        order.completed_tasks.add(task)

        # Add the child tasks of the completed task to the ready_tasks list
        for child_task in task.next_steps:
            order.ready_tasks.append(child_task)
        
        # Check if the order is finished and record finish_time
        if order.is_finished():
            order.finish_time = self.env.now  # Assuming self.env.now gives the current simulation time
            log_manager.log_event(self.env.now, "N/A", order.order_id, "N/A", "Order Finished")
 
       
    def remove_task(self, order, task):
        """
        Remove a job from the station's task queue and increment number of finished tasks of the jo
        """
        if (order, task) in self.ws_tasks_queue:
            self.mark_task_as_completed(order, task)
            self.ws_tasks_queue.remove((order, task))

            # Notify ORControlSystem to remove load contributions
            self.orControlSystem.update_stations_loads(order, task)
        else:
            log_manager.main_logger.error(f"Task {task.task_name} of Order {order.order_id} is not in the task queue of workstation {self.id}!")
        
    def sort_tasks(self): 
        """
        Sort the tasks queue of a workstation according to the dispatching rule
            FCFS: First come first serve
            SPT: Shortest processing time
            PST: Planned start time
        """
        dispatching_rule = self.dispatching_rule
       
        # Sort the tasks queue based on the priority and dispatching rule
        # NOTE: task[0] refers to the order object and task[1] refers to the task object
        if dispatching_rule == 'FCFS':
            self.ws_tasks_queue.sort(key=lambda task: task[0].priority) 
        elif dispatching_rule == 'SPT':
            self.ws_tasks_queue.sort(key=lambda task: (task[0].priority, task[1].process_time))
        elif dispatching_rule == 'PST':
            self.ws_tasks_queue.sort(key=lambda task: (task[0].priority, task[1].planned_start_time))
        else:
            log_manager.main_logger.error(f"Invalid dispatching rule, please choose from FCFS, SPT, PST")
            print("Invalid dispatching rule, please choose from FCFS, SPT, PST")
        
    def start_processing(self):
        """
        Main processing loop for the workstation.
        This function runs continuously, checking the task queue and processing tasks.
        When the task queue is empty, it logs the station's idle state and notifies the control system.
        When a task arrives, it logs the end of the idle state, updates the idle time, and starts processing the task.
        """
        while True:
            if len(self.ws_tasks_queue) == 0: # If a station's task queue is empty, trigger the idle_event          
                self.last_idle_start = self.env.now  
                log_manager.log_event(self.last_idle_start, self.id, "N/A", "N/A", "Idle Start")
                self.idle = True

                # Inform ORControlSystem that the station is idle and wait for the next task
                self.orControlSystem.continuous_release(self)
                yield self.idle_event

                # Once a task arrives, log the end of idle time          
                idle_duration = self.env.now - self.last_idle_start
                self.total_idle_time += idle_duration
                self.idle_event = self.env.event() # Reset the event for future use

                event_detail = f"Idle duration: {idle_duration:.2f}"
                log_manager.log_event(self.env.now, self.id, "N/A", "N/A", "Idle End", event_detail)
                
                
            else: # The task queue is not empty               
                self.idle = False
                self.sort_tasks() # Sort the task queue according to the dispatching rule
                order, task = self.ws_tasks_queue[0] # get the first job in the queue
                yield self.env.process(self.process_task(order, task))
            
    def process_task(self, order, task):
        """
        Process a specific task for an order.

        This function simulates the processing of a task at a workstation, including checking if the task is correctly assigned to the workstation,
        logging the start and completion of the task, handling the production and transfer of components, and dispatching subsequent tasks.

        """
        required_ws_id = task.assigned_station.id
        if required_ws_id != self.id:
            log_manager.main_logger.error(f"Task {task.task_name} of Order {order.order_id} not assigned to the correct workstation.")
        else:
            with self.resource.request() as request:
                yield request
                process_time = task.process_time
                self.last_work_start = self.env.now
                process_time_detail = f"Process time: {process_time:.2f}"
                log_manager.log_event(self.env.now, self.id, order.order_id, task.task_name, "Task Start", process_time_detail)
                yield self.env.timeout(process_time)
                self.total_work_time += process_time
                work_time_detail = f"TWT: {self.total_work_time:.2f}, TIT: {self.total_idle_time:.2f}"
                log_manager.log_event(self.env.now, self.id, order.order_id, task.task_name, "Task Complete", work_time_detail)
                    
                # Check if the task has a produced component to send to the output warehouse
                if task.produced_component:
                    warehouse_list = self.orControlSystem.warehouse_list
                    target_warehouse = next((wh for wh in warehouse_list if wh.id == self.output_warehouse), None)
                    target_warehouse.add_item(task.produced_component)
                    log_manager.main_logger.info(f"{self.env.now:.2f}: Produced component {task.produced_component} from Order {order.order_id} added to the output warehouse.")

                self.remove_task(order, task)
                log_manager.main_logger.info(f"{self.env.now:.2f}: Task {task.task_name} of Order {order.order_id} is completed.")

                    
                # After completing the task, check whether there remains further tasks to be completed.
                next_tasks = list(self.orControlSystem.get_next_ready_tasks(order)) 
                if next_tasks:
                    station_list = self.orControlSystem.station_list
                    for next_task in next_tasks:
                        # Find the corresponding workstation for the next task
                        child_station = next_task.assigned_station
                        if child_station:
                            child_station.add_task(order, next_task)
                            log_manager.main_logger.info(f"{self.env.now:.2f}: Task {next_task.task_name} of Order {order.order_id} is dispatched to Station {child_station.id}.")
                        else:
                            log_manager.main_logger.error(f"No workstation found for station {child_station.id} for Task {next_task.task_name}")

                
                
         

            
        



   