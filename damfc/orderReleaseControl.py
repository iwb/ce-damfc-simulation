from loggerConfig import log_manager
from appConfig import app_config


class ORControlSystem(object):
    """
    Simulation control system for order release and dispatching
    The ORControlSystem class is responsible for managing the overall control flow of the simulation. It manages the
    pre-shop pool, the order list, and the stations involved in the simulation. It also manages the dispatching of
    orders to stations based on the specified dispatching rule.
    """

    def __init__(
        self,
        env,
        preShopPool,
        station_list,
        warehouse_list,
        normload=app_config.WORKLOAD_NORM,
        pool_sequencing_rule=app_config.POOL_SEQUENCING_RULE,
    ):
        """
        Initialize the OrderReleaseControlSystem.

        Parameters:
        - env (simpy.Environment): The simulation environment.
        - pre_shop_pool (PreShopPool): The pre-shop pool object.
        - station_list (list): A list of Station objects representing the stations in the simulation.
        - warehouse_list (list): A list of Warehouse objects representing the warehouses in the simulation.
        - workload_norm (float): The workload normalization factor.
        - pool_sequencing_rule (str): The pool sequencing rule to use for order release.

        """
        self.env = env
        self.preShopPool = preShopPool  # The Preshop Pool will store arriving orders
        # self.order_list_general = order_list_general
        self.station_list = station_list
        self.warehouse_list = warehouse_list
        self.workload_norm = normload
        self.pool_sequencing_rule = pool_sequencing_rule

    def add_order(self, order):
        """
        Add a new order to the preShopPool and notify idle stations.

        Parameters
        - order (Order): Order object to be added
        """
        log_manager.main_logger.info(
            f"{self.env.now:.2f}: Order {order.order_id} arrives"
        )
        self.preShopPool.add_order(order)
        # Immediately try to release the order if there are idle stations
        self.check_and_release_idle_stations()

    def check_and_release_idle_stations(self):
        """
        Check for any idle stations and assign an order if possible.
        """
        for station in self.station_list:
            if (
                station.idle and not station.idle_event.triggered
            ):  # Only proceed if the station is idle
                self.continuous_release(
                    station
                )  # Attempt to assign an order to this idle station

    def select_station(self, workstations):
        """
        Select the workstation with the least current load
        """
        return min(workstations, key=lambda ws: ws.current_load)

    def sort_orders(self):
        """
        Sort orders in the preShopPool based on the specified pool sequencing rule.
            FCFS: First Come First Served
            EDD: Earliest Due Date
            CR: Critical Ratio = (Due Date - Current Time) / Total Processing Time
        """
        order_list = self.preShopPool.order_list
        rule = self.pool_sequencing_rule
        if len(order_list) > 0:
            if rule == "FCFS":
                order_list.sort(key=lambda order: (order.priority, order.arrival_time))
            elif rule == "EDD":
                order_list.sort(key=lambda order: (order.priority, order.due_date))
            elif rule == "CR":
                order_list.sort(
                    key=lambda order: (
                        order.priority,
                        (order.due_date - self.env.now) / order.total_process_time,
                    )
                )
            else:
                log_manager.main_logger.error(
                    "Invalid pool sequencing rule, please choose from FCFS, EDD, CR"
                )
                print("Invalid pool sequencing rule, please choose from FCFS, EDD, CR")

    def order_release_with_lums_cor(self, round_time=4):
        """
        This method is used to release jobs based on the LUMS COR rule.
        Start the periodic release process and continuously release orders when any workstation becomes idle.
        """
        log_manager.main_logger.info(
            f"{self.env.now:.2f}: Start LUMS COR order release control"
        )
        # Start periodic release process
        self.env.process(self.periodic_release(round_time))

        # Start releasing orders when any workstation becomes idle
        # Do nothing, triggered by the station's event

    def periodic_release(self, roud_time):
        """
        Periodically release orders from the PreShopPool.
        """
        order_list = self.preShopPool.order_list
        while True:
            yield self.env.timeout(roud_time)  # Periodic release accoring to round time
            log_manager.main_logger.info(
                f"{self.env.now:.2f}: New round of Periodic Order Release: there remains {len(order_list)} orders."
            )

            if len(order_list) > 0:
                self.sort_orders()  # Sort order list
                # Go through the order list, decide for each order whether it can be released or not
                for order in order_list[:]:
                    self.set_detailed_routing(order)

                    can_release, overloaded_stations = self.can_release_order(
                        order
                    )  # Check if the order can be released
                    if can_release:
                        # Log order release approval
                        log_manager.log_event(
                            self.env.now,
                            "N/A",
                            order.order_id,
                            "N/A",
                            "Order Released",
                            "Periodic Release",
                        )
                        log_manager.main_logger.info(
                            f"{self.env.now:.2f}: Periodic release approved, Order {order.order_id} can be released."
                        )
                        # Release the order
                        self.release_order(order)
                        self.preShopPool.remove_order(order)
                    else:
                        # Log order release rejection with details of overloaded stations
                        overload_details = ", ".join(
                            [
                                f"Station {station_id}: {load:.2f}"
                                for station_id, load in overloaded_stations
                            ]
                        )
                        log_manager.log_event(
                            self.env.now,
                            "N/A",
                            order.order_id,
                            "N/A",
                            "Order Release Rejected",
                            f"Periodic Release - Overloaded Stations: {overload_details}",
                        )

    def continuous_release(self, station):
        """
        Continuously release orders to idle stations.
        Called when a station becomes idle. Attempt to assign an order to the station.
        """
        log_manager.main_logger.debug(
            f"{self.env.now:.2f}: Station {station.id} reported as idle, checking for orders."
        )
        order_list = self.preShopPool.order_list

        if len(order_list) > 0:
            # Sort orders according to the defined pool sequencing rule
            self.sort_orders()
            # Find an order that can be assigned to this station
            for order in order_list:
                # Get all tasks that are ready to be processed in this order
                ready_tasks = self.get_next_ready_tasks(order)
                for next_task in ready_tasks:
                    if (
                        next_task.station == station.type_id
                    ):  # and station.id.startswith(f"{next_task.station}"):
                        log_manager.main_logger.info(
                            f"{self.env.now:.2f}: Continuous Release, assigning Order {order.order_id} to Station {station.id}."
                        )
                        log_manager.log_event(
                            self.env.now,
                            station.id,
                            order.order_id,
                            next_task.task_name,
                            "Order Released",
                            "Continuous Release",
                        )
                        self.set_detailed_routing(
                            order, triggered_station=station
                        )  # using triggered station for detailed routing
                        self.release_order(order)
                        self.preShopPool.remove_order(order)

                        # Wake up the station
                        station.idle_event.succeed()
                        return  # Only release one order per station at a time

        # If no suitable order is found, the station remains idle
        log_manager.main_logger.debug(
            f"{self.env.now:.2f}: No suitable order found for Station {station.id}, remaining idle."
        )

    def set_detailed_routing(self, order, triggered_station=None):
        """
        Assign workstations for all ready tasks in the order before releasing it.

        Parameters:
        order (Order): The order to be processed.
        triggered_station (Workstation): The station that triggered the order release (continous release trigger).
        """
        # Use the flattened process plan to ensure all tasks are included
        for task in order.flat_plan:  # Assign a workstation to each task
            st_type_id = task.station
            if triggered_station and task.station == triggered_station.type_id:
                task.assigned_station = triggered_station
            else:
                suitable_stations = [
                    st for st in self.station_list if st.id.startswith(st_type_id)
                ]
                ws = self.select_station(
                    suitable_stations
                )  # Always select the least-loaded station
                task.assigned_station = ws

            log_manager.main_logger.debug(
                f"Task {task.task_name} of Order {order.order_id} assigned to Station {task.assigned_station.id}."
            )
        order.compute_load_contributions()

    def get_next_ready_tasks(self, order):
        """
        Retrieve all tasks in the order that are ready to be processed.
        """
        if order.ready_tasks:
            return order.ready_tasks  # Return the entire list of ready tasks
        return []

    def can_release_order(self, order):
        """
        Check if the order can be released based on the Corrected Workload it would impose on the stations.
        Corrected Workload = process time / operation depth.
        """
        norm_load = self.workload_norm
        overloaded_stations = []

        # Create a copy of station loads to simulate after releasing the order
        station_loads = {
            ws.id: ws.current_load for ws in self.station_list
        }  # Get current loads of all stations
        log_manager.main_logger.info(
            f"{self.env.now:.2f}: Check station loads before releasing Order {order.order_id}: {station_loads}"
        )
        estimated_loads = order.estimate_load_contribution(
            station_loads
        )  # Estimate load contribution of the order and add it to the station_loads
        # Check for overloaded stations
        for ws in self.station_list:
            if estimated_loads[ws.id] > norm_load:
                overloaded_stations.append((ws.id, station_loads[ws.id]))

        if overloaded_stations:
            # Log the overloaded stations
            overload_details = ", ".join(
                [f"Station {station_id}" for station_id, load in overloaded_stations]
            )
            log_manager.main_logger.info(
                f"{self.env.now:.2f}: Periodic release rejected, Order {order.order_id} cannot be released due to overloaded stations: {overload_details}."
            )
            return False, overloaded_stations

        return True, []  # If all stations are within norm load

    def release_order(self, order):
        """
        Release the order by dispatching all its ready tasks to the corresponding workstations.
        """
        # Add load contributions to stations' indirect loads
        order.add_load_contribution(self.station_list)

        ready_tasks = list(self.get_next_ready_tasks(order))
        for task in ready_tasks:
            assigned_station = task.assigned_station
            # assigned_station = next((station for station in self.station_list if station.id == assigned_station_id), None)
            if assigned_station:
                assigned_station.add_task(order, task)
                log_manager.main_logger.debug(
                    f"{self.env.now:.2f}: Task {task.task_name} of Order {order.order_id} is released to Station {assigned_station.id}."
                )
            else:
                log_manager.main_logger.error(
                    f"Error: No workstation found for {assigned_station.id}."
                )

    def update_stations_loads(self, order, completed_task):
        """
        Remove load contributions of a completed task and update order's load contribution.
        """
        # Update load contributions
        order.update_load_contribution(self.station_list, completed_task)

    def calculate_planned_start_time(self, order, task):
        """
        Calculate and assign the planned start time (PST) for a given task, considering the most time-consuming branch.
        Planned Start Time (PST) = Order Due Date - Total Process Time of Most Time-Consuming Branch - k * Number of Remaining Tasks
        """
        # Calculate the maximal process time and number of tasks in the most time-consuming branch
        max_process_time, num_remaining_tasks = (
            self.calculate_most_time_consuming_branch(task)
        )
        k = (
            app_config.PLANNED_START_TIME_ALLOWANCE
        )  # k is the allowance for the waiting time per operation from the config
        pst = order.due_date - max_process_time - k * num_remaining_tasks
        task.planned_start_time = pst

    def calculate_most_time_consuming_branch(self, task):
        """
        Recursively calculate the most time-consuming branch starting from the given task.
        This method returns the total process time of the longest path and the number of tasks along that path.
        """
        if not task.next_steps:  # Base case: If the task has no child tasks
            return task.process_time, 1

        # Recursive case: Find the most time-consuming branch in the child tasks
        child_results = [
            self.calculate_most_time_consuming_branch(child_task)
            for child_task in task.next_steps
        ]
        max_child_time, max_child_count = max(
            child_results, key=lambda x: x[0]
        )  # Find the child task with the longest path
        total_time = (
            task.process_time + max_child_time
        )  # Add the current task's process time

        # Total tasks include the current task and those in the longest branch
        total_tasks = 1 + max_child_count

        return total_time, total_tasks
