import simpy
from workstation import Workstation
from warehouse import Warehouse
from preShopPool import PreShopPool
from orderReleaseControl import ORControlSystem
from loggerConfig import log_manager
from processCSV import ProcessCSV
from kpiTracker import KPITracker
from preShopPool import Order
from preShopPool import Task  # Assuming Task class is in a module named task




def create_test_orders():
    def create_plan1_tasks():
        # task in plan1
        task_t1 = Task(task_name="T1", process_time=3, produced_component=None, revenue=30, station="A", parent_task=None, depth=1)
        task_t2 = Task(task_name="T2", process_time=2, produced_component=None, revenue=10, station="B", parent_task=task_t1, depth=2)
        task_t3 = Task(task_name="T3", process_time=2, produced_component=None, revenue=15, station="C", parent_task=task_t1, depth=2)
        task_t4 = Task(task_name="T4", process_time=3, produced_component=None, revenue=20, station="D", parent_task=task_t2, depth=3)
        task_t5 = Task(task_name="T5", process_time=4, produced_component=None, revenue=25, station="E", parent_task=task_t4, depth=4)

        # dependecies
        task_t1.next_steps = [task_t2, task_t3]
        task_t2.next_steps = [task_t4]
        task_t4.next_steps = [task_t5]
        return [task_t1]

    def create_plan2_tasks():
        # task in plan2
        task_t4 = Task(task_name="T4", process_time=2, produced_component=None, revenue=20, station="D", parent_task=None, depth=1)
        task_t1 = Task(task_name="T1", process_time=2, produced_component=None, revenue=30, station="A", parent_task=task_t4, depth=2)
        task_t2 = Task(task_name="T2", process_time=3, produced_component=None, revenue=10, station="B", parent_task=task_t1, depth=3)
        task_t3 = Task(task_name="T3", process_time=3, produced_component=None, revenue=15, station="C", parent_task=task_t1, depth=3)
        task_t5 = Task(task_name="T5", process_time=4, produced_component=None, revenue=25, station="E", parent_task=task_t2, depth=4)

        # dependencies
        task_t4.next_steps = [task_t1]
        task_t1.next_steps = [task_t2, task_t3]
        task_t2.next_steps = [task_t5]
        return [task_t4]

    # create orders
    orders = []
    orders.append(Order(order_id=f"O-{1}", depth=4, arrival_time=1, due_date=15, priority=2, plan_name="Plan1", process_plan=create_plan1_tasks()))
    orders.append(Order(order_id=f"O-{2}", depth=4, arrival_time=1, due_date=25, priority=2, plan_name="Plan2", process_plan=create_plan2_tasks()))
    orders.append(Order(order_id=f"O-{3}", depth=4, arrival_time=2, due_date=30, priority=2, plan_name="Plan2", process_plan=create_plan2_tasks()))
    orders.append(Order(order_id=f"O-{4}", depth=4, arrival_time=2, due_date=25, priority=2, plan_name="Plan1", process_plan=create_plan1_tasks()))
    orders.append(Order(order_id=f"O-{5}", depth=4, arrival_time=3, due_date=20, priority=2, plan_name="Plan1", process_plan=create_plan1_tasks()))
    orders.append(Order(order_id=f"O-{6}", depth=4, arrival_time=3, due_date=30, priority=2, plan_name="Plan2", process_plan=create_plan2_tasks()))

    return orders



def test_simulation():
    """
    Runs a test simulation with the test setup.
    """
    # Create SimPy environment
    env = simpy.Environment()
    csv_processor = ProcessCSV()   
    kpi_tracker = KPITracker()

    norm_load = 6 
    simulation_time = 20
    simulation_id = "test_simulation"
    pool_rule = "EDD"
    dispatching_rule = "SPT"
    log_manager.set_simulation_info(simulation_id, f"{pool_rule} + {dispatching_rule}")

    # Create stations and warehouses
    station_types = ['A', 'B', 'C', 'D', 'E'] # 5 types of stations. If this variable is modified, make sure to re-match the settings in the JobGenerator class
    station_instances = {'A': 1, 'B': 1, 'C': 1, 'D': 1, 'E': 1} # number of instances per type

    station_list = []
    for type_id in station_types:
            for instance_id in range(1, station_instances[type_id] + 1):
                ws = Workstation(env, type_id, instance_id)
                station_list.append(ws)
                log_manager.main_logger.info(f"Create {ws}")

    warehouse = Warehouse(env, 'output', 'warehouse')
    log_manager.main_logger.info(f"Created warehouse: {warehouse}")

    # Create PreShopPool and ORControlSystem
    preShopPool = PreShopPool(env)
    orders = create_test_orders()
    orControlSystem = ORControlSystem(env, preShopPool, station_list, [warehouse], normload=norm_load, pool_sequencing_rule=pool_rule)

    # Add orders to the ORControlSystem
    env.process(start_order_generate(env, orControlSystem, orders))

    # Start order release
    orControlSystem.order_release_with_lums_cor(round_time=1)

    # Assign dispatching rule and start stations
    for station in station_list:
        station.orControlSystem = orControlSystem
        station.dispatching_rule = "SPT"
        env.process(station.start_processing())

    # Run the simulation
    log_manager.log_event(0.0, "N/A", "N/A", "N/A", "Simulation Start", "N/A")
    env.run(until=20)  # Assuming the simulation time is 50
    log_manager.log_event(simulation_time, "N/A", "N/A", "N/A", "Simulation End", "N/A")

     # Finalize the simulation by logging the work/idle time of each station
    for station in station_list:
        if not station.idle:  
            work_duration = simulation_time - station.last_work_start
            station.total_work_time += work_duration
        else:
            idle_duration = simulation_time - station.last_idle_start
            station.total_idle_time += idle_duration

        log_manager.log_event(simulation_time, station.id, "N/A", "N/A", "Simulation End", f"FWT: {station.total_work_time:.2f}, FIT: {station.total_idle_time:.2f}")


    log_manager.record_current_simulation_data(simulation_id, f"{pool_rule} + {dispatching_rule}", orders, station_list)
    # Store KPI results for this simulation run
    kpi_tracker.store_kpi_results(simulation_id, f"{pool_rule} + {dispatching_rule}", simulation_time, norm_load, orders, station_list)
 

    log_manager.save_to_csv()
    csv_processor.process_and_save_logs()
    log_manager.display_full_event_log_in_frame()

    print("Test simulation completed.")


def start_order_generate(env, orControlSystem, orders):
    """
    This method is used to generate jobs in Simpy envrionment according to the inter-arrival time.
    Note: A job appears at a specific time point and is added to the environment and the job list at that moment. 

    Parameters:    
        env (simpy.Environment): The simulation environment
        job_list (list): The list of jobs that is used by the pre-shop pool
        jobs (list): The list of jobs that will be generated
    """
    for order in orders:
        arrival_time = order.arrival_time
        yield env.timeout(arrival_time - env.now)
        orControlSystem.add_order(order)
        

# Run the test
if __name__ == "__main__":
    test_simulation()
